"""Tests for LOD hydration and dehydration (Surface Map Plan Phase 5).

Covers docs/Surface Map Plan.md Phase 5: stable actor identity across
hydration cycles, dehydration into Save-Diff Journal records, the
no-double-simulation rule, eviction locks for visible/audible/engaged
actors, and conflict relocation when a hydrated actor's tile became
occupied while it was away.
"""

from __future__ import annotations

import tempfile

import pytest

from game.world.lod_hydration import (
    EVICT_LOCK_AUDIBLE,
    EVICT_LOCK_ENGAGED,
    EVICT_LOCK_VISIBLE,
    ActorStore,
    ChunkHydrationManager,
    EvictionLocks,
    InMemoryActorStore,
)
from game.world.save_diff_journal import SaveDiffJournal

_CHUNK = 16
_CX, _CY, _CZ = 1, -1, 0


def _wolf(actor_id: int, x: int, y: int, **extra):
    snapshot = {
        "actor_id": actor_id,
        "name": "wolf",
        "species": "gray_wolf",
        "x": x,
        "y": y,
        "hp": 12,
        "max_hp": 20,
        "faction": "wild",
        "inventory": ["rabbit_pelt"],
        "status_effects": [{"id": "bleeding", "duration": 3, "intensity": 1.0}],
    }
    snapshot.update(extra)
    return snapshot


def _store_with_wolves():
    store = InMemoryActorStore()
    store.add_actor(_wolf(100, 20, -8))
    store.add_actor(_wolf(101, 25, -3))
    return store


def _manager(store, **kwargs) -> ChunkHydrationManager:
    return ChunkHydrationManager(store, chunk_size=_CHUNK, **kwargs)


def _journal() -> SaveDiffJournal:
    return SaveDiffJournal(_CX, _CY, _CZ)


def test_hydrate_dehydrate_actor_identity() -> None:
    """Stable ID, HP, inventory, and status survive a full cycle."""
    store = _store_with_wolves()
    manager = _manager(store)
    with tempfile.TemporaryDirectory() as saves:
        journal = _journal()
        dehydrated = manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)
        assert dehydrated == [100, 101]
        journal.write_atomic(saves)  # chunk unloads; records hit the disk

        # Unload confirmed: the bubble no longer tracks the actors.
        assert store.active_actor_ids() == []

        # Reload from disk into a brand-new store and bubble.
        loaded = SaveDiffJournal.load_or_create(saves, _CX, _CY, _CZ)
        fresh_store = InMemoryActorStore()
        hydrated = _manager(fresh_store).hydrate_chunk_entities(
            loaded, _CX, _CY, _CZ
        )
        assert hydrated == [100, 101]
        for actor_id in (100, 101):
            actor = fresh_store.actor(actor_id)
            assert actor is not None
            assert actor["actor_id"] == actor_id
            assert actor["hp"] == 12
            assert actor["max_hp"] == 20
            assert actor["inventory"] == ["rabbit_pelt"]
            assert actor["status_effects"] == [
                {"id": "bleeding", "duration": 3, "intensity": 1.0}
            ]
        # Records are consumed: no double tracking.
        assert loaded.entity_snapshots == {}


def test_dehydrated_actors_exist_only_as_records() -> None:
    """After dehydration an actor is a journal record, never both forms."""
    store = _store_with_wolves()
    manager = _manager(store)
    journal = _journal()
    dehydrated = manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)

    assert dehydrated == [100, 101]
    assert store.active_actor_ids() == []
    for actor_id in (100, 101):
        record = journal.entity_snapshots[str(actor_id)]
        assert record["actor_id"] == actor_id
        assert store.actor(actor_id) is None
    # A second dehydration pass finds nothing left to take.
    assert manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ) == []


def test_eviction_locks_prevent_dehydration() -> None:
    """Visible, audible, and engaged actors never leave the bubble."""
    store = _store_with_wolves()
    locks = EvictionLocks()
    manager = _manager(store, locks=locks)

    locks.lock(100, EVICT_LOCK_VISIBLE)
    locks.lock(101, EVICT_LOCK_AUDIBLE)
    locks.lock(101, EVICT_LOCK_ENGAGED)

    journal = _journal()
    dehydrated = manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert dehydrated == []
    assert store.active_actor_ids() == [100, 101]
    assert journal.entity_snapshots == {}

    # Releasing every lock lets the chunk dehydrate normally.
    locks.unlock(100)
    locks.unlock(101, EVICT_LOCK_AUDIBLE)
    assert locks.reasons_for(101) == frozenset({EVICT_LOCK_ENGAGED})
    locks.unlock(101)
    assert not locks.is_locked(101)

    dehydrated = manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert dehydrated == [100, 101]
    assert store.active_actor_ids() == []


def test_dehydrate_respects_chunk_bounds() -> None:
    """Actors outside the chunk rect stay active and untouched."""
    store = InMemoryActorStore()
    store.add_actor(_wolf(100, 20, -8))    # inside chunk (1, -1)
    store.add_actor(_wolf(200, 5, 5))      # chunk (0, 0) — outside
    store.add_actor(_wolf(201, 40, -5))   # chunk (2, -1) — outside
    manager = _manager(store)
    journal = _journal()

    dehydrated = manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert dehydrated == [100]
    assert store.active_actor_ids() == [200, 201]
    assert journal.has_entity_snapshot("100")
    assert not journal.has_entity_snapshot("200")


def test_hydrate_conflict_relocation() -> None:
    """An occupied home tile relocates the actor to the nearest free tile."""
    store = InMemoryActorStore()
    store.add_actor(_wolf(100, 20, -8))
    manager = _manager(store)
    journal = _journal()
    manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)

    # While actor 100 was away, a regional simulation moved a settler
    # onto its tile (20, -8) and static debris blocked (21, -8).
    store.add_actor(_wolf(300, 20, -8, name="settler", faction="village"))
    store._blocked_tiles.add((21, -8))

    hydrated = manager.hydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert hydrated == [100]
    actor = store.actor(100)
    assert actor is not None
    # Original tile and its right neighbor are blocked; the spiral's
    # first candidate is the deterministic (19, -9).
    assert (actor["x"], actor["y"]) == (19, -9)
    # The relocated position is inside the chunk rect.
    assert store.actor(300) is not None  # the settler is untouched


def test_hydrate_no_free_tile_stays_dehydrated() -> None:
    """With no room in the bubble the record waits, un-spawned."""
    store = InMemoryActorStore()
    store.add_actor(_wolf(100, 20, -8))
    manager = _manager(store, relocation_radius=2)
    journal = _journal()
    manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)

    # Block every tile within the relocation radius of the home tile.
    for dy in range(-3, 4):
        for dx in range(-3, 4):
            store._blocked_tiles.add((20 + dx, -8 + dy))

    hydrated = manager.hydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert hydrated == []
    assert store.active_actor_ids() == []
    # The record survives for a later hydration attempt.
    assert journal.has_entity_snapshot("100")


def test_hydrate_only_chunk_residents() -> None:
    """Hydrating one chunk leaves other chunks' records alone."""
    store = InMemoryActorStore()
    store.add_actor(_wolf(100, 20, -8))   # chunk (1, -1)
    store.add_actor(_wolf(200, 5, 5))     # chunk (0, 0)
    journal = _journal()
    manager = _manager(store)
    manager.dehydrate_chunk_entities(journal, _CX, _CY, _CZ)
    # Sneak a foreign record into this journal from a different chunk.
    journal.record_entity_snapshot("200", _wolf(200, 5, 5))

    hydrated = manager.hydrate_chunk_entities(journal, _CX, _CY, _CZ)
    assert hydrated == [100]
    # Actor 200 never left the store (different chunk) and its injected
    # record is not this chunk's business.
    assert store.active_actor_ids() == [100, 200]
    assert journal.has_entity_snapshot("200")  # not this chunk's actor


def test_in_memory_store_matches_protocol() -> None:
    """The reference store satisfies the ActorStore protocol at runtime."""
    store = InMemoryActorStore()
    assert isinstance(store, ActorStore)  # structural protocol check

    with pytest.raises(KeyError):
        store.snapshot_actor(999)  # inactive actors cannot be snapshotted
    assert store.is_tile_blocked(0, 0) is False
    store._blocked_tiles.add((0, 0))
    assert store.is_tile_blocked(0, 0) is True


def test_hydration_manager_validation() -> None:
    """Constructor rejects nonsensical chunk sizes and radii."""
    store = InMemoryActorStore()
    with pytest.raises(ValueError):
        ChunkHydrationManager(store, chunk_size=0)
    with pytest.raises(ValueError):
        ChunkHydrationManager(store, chunk_size=_CHUNK, relocation_radius=0)
