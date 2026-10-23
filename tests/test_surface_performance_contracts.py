"""Behavioral regressions for chunk-selective eviction and batched IDs."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from common.constants import Material
from game.entities.registry import EntityRegistry
from game.world.game_map import TILE_ID_FLOOR, GameMap
from game.world.lod_hydration import ChunkHydrationManager, EvictionLocks
from game.world.registry_actor_store import EntityRegistryActorStore
from game.world.save_diff_journal import SaveDiffJournal
from game.world.surface_context import SurfaceContext
from game.world.surface_identity import SurfaceIdentityLedger
from game.world.surface_materializer import (
    InMemoryPromiseSource,
    RegionalPromise,
    SurfaceFeatureKind,
    SurfaceMaterializer,
    apply_materialized_chunk,
)
from game.world.surface_population import SurfacePopulationPlanner
from worldgen.overland.schema import TraversalClass


def _actor(actor_id: int, x: int, y: int) -> dict[str, Any]:
    return {
        "actor_id": actor_id,
        "x": x,
        "y": y,
        "glyph": 64,
        "color_fg_r": 1,
        "color_fg_g": 2,
        "color_fg_b": 3,
        "name": "otter",
        "hp": 4,
        "max_hp": 5,
        "blocks_movement": True,
        "template_id": "otter",
        "behavior": "seek_water",
    }


def test_chunk_eviction_serializes_only_local_unlocked_actors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Number of snapshots scales with local actors, not world population."""
    registry = EntityRegistry()
    store = EntityRegistryActorStore(registry)
    # Remote residents occupy a large non-overlapping range of coordinates.
    for i in range(500):
        store.spawn_actor(_actor(0x80010000 + i, 32 + i, 8))
    local = (0x80030000, 0x80030001, 0x80030002)
    for index, actor_id in enumerate(local):
        store.spawn_actor(_actor(actor_id, index + 2, 4))
    calls: list[int] = []
    original_snapshot = store.snapshot_actor

    def spy(actor_id: int) -> dict[str, Any]:
        calls.append(actor_id)
        return original_snapshot(actor_id)

    monkeypatch.setattr(store, "snapshot_actor", spy)
    locks = EvictionLocks()
    locks.lock(local[1])
    manager = ChunkHydrationManager(
        store, chunk_size=16, can_occupy=lambda x, y: True, locks=locks
    )
    journal = SaveDiffJournal(0, 0)
    assert manager.dehydrate_chunk_entities(journal, 0, 0) == [local[0], local[2]]
    assert calls == [local[0], local[2]]
    assert len(store.active_actor_ids()) == 501


def test_vectorized_bounds_support_negative_global_viewports() -> None:
    registry = EntityRegistry()
    store = EntityRegistryActorStore(
        registry, viewport_origin_x=-32, viewport_origin_y=64
    )
    local_id = 0x80020001
    store.spawn_actor(_actor(local_id, -30, 66))
    store.spawn_actor(_actor(0x80020002, -10, 66))
    assert store.active_actor_ids_in_rect(-32, 64, -16, 80) == [local_id]
    manager = ChunkHydrationManager(store, chunk_size=16, can_occupy=lambda x, y: True)
    assert manager.dehydrate_chunk_entities(SaveDiffJournal(-2, 4), -2, 4) == [local_id]


def test_population_ledger_flushes_once_before_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = InMemoryPromiseSource(
        [RegionalPromise(SurfaceFeatureKind.SPRING, 8, 8)],
        chunk_size=16,
    )
    chunk = SurfaceMaterializer(
        source, world_seed=91, chunk_size=16, debris_fraction=0.0
    ).materialize_chunk(0, 0)
    game_map = GameMap(width=16, height=16)
    apply_materialized_chunk(game_map, chunk)
    registry = EntityRegistry()
    registry.ensure_occupancy_shape(16, 16)
    store = EntityRegistryActorStore(registry)

    with tempfile.TemporaryDirectory() as directory:
        ledger = SurfaceIdentityLedger.load_or_create(directory)
        flushes: list[Path] = []
        write_original = ledger.write_atomic

        def record_flush(target: str | Path) -> Path:
            result = write_original(target)
            flushes.append(result)
            return result

        monkeypatch.setattr(ledger, "write_atomic", record_flush)
        spawn_original = store.spawn_actor

        def guarded_spawn(snapshot: dict[str, Any]) -> None:
            durable = SurfaceIdentityLedger.load_or_create(directory)
            assert durable.id_for(str(snapshot["birth_key"])) == snapshot["actor_id"]
            spawn_original(snapshot)

        monkeypatch.setattr(store, "spawn_actor", guarded_spawn)
        planner = SurfacePopulationPlanner(
            store,
            SurfaceContext(game_map),
            world_seed=91,
            identity_ledger=ledger,
            min_per_anchor=2,
            max_per_anchor=2,
        )
        journal = SaveDiffJournal(0, 0)
        assert len(planner.populate_chunk(chunk, journal)) == 2
        assert len(flushes) == 1
        assert planner.populate_chunk(chunk, journal) == []
        assert len(flushes) == 1


def test_batch_collision_probe_and_failed_flush_roll_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CollidingLedger(SurfaceIdentityLedger):
        @staticmethod
        def _candidate(birth_key: str, salt: int) -> int:
            return 0x80000000 if salt == 0 else 0x80000100 + salt

    with tempfile.TemporaryDirectory() as directory:
        ledger = CollidingLedger(directory=directory)
        writes: list[Path] = []
        write_original = ledger.write_atomic

        def record_flush(target: str | Path) -> Path:
            result = write_original(target)
            writes.append(result)
            return result

        monkeypatch.setattr(ledger, "write_atomic", record_flush)
        assigned = ledger.reserve_many(("alpha", "bravo", "charlie"))
        assert len(set(assigned.values())) == 3
        assert len(writes) == 1
        reloaded = SurfaceIdentityLedger.load_or_create(directory)
        assert all(reloaded.id_for(key) == value for key, value in assigned.items())

    def fail_flush(target: str | Path) -> Path:
        raise OSError("disk full")

    with tempfile.TemporaryDirectory() as directory:
        ledger = CollidingLedger(directory=directory)
        monkeypatch.setattr(ledger, "write_atomic", fail_flush)
        with pytest.raises(OSError, match="disk full"):
            ledger.reserve_many(("alpha", "bravo"))
        assert ledger.id_for("alpha") is None
        assert ledger.id_for("bravo") is None


def test_rerecorded_geometry_retains_semantics_until_explicit_clear() -> None:
    journal = SaveDiffJournal(0, 0)
    journal.record_tile_mutation(
        2,
        2,
        TILE_ID_FLOOR,
        material=int(Material.DOOR_OPEN),
        traversal=int(TraversalClass.NORMAL),
        movement_cost=1.0,
    )
    journal.record_tile_mutation(2, 2, TILE_ID_FLOOR)
    assert journal.tile_metadata[(2, 2)] == {
        "material": int(Material.DOOR_OPEN),
        "traversal": int(TraversalClass.NORMAL),
        "movement_cost": 1.0,
    }
    restored = SaveDiffJournal.from_json(journal.to_json())
    assert restored.tile_metadata == journal.tile_metadata
    restored.record_tile_mutation(2, 2, TILE_ID_FLOOR, movement_cost=1.25)
    assert restored.tile_metadata[(2, 2)]["material"] == int(Material.DOOR_OPEN)
    assert restored.tile_metadata[(2, 2)]["movement_cost"] == 1.25
    restored.record_tile_mutation(2, 2, TILE_ID_FLOOR, clear_semantics=True)
    assert restored.tile_metadata == {}
