"""Three-tier LOD hydration and dehydration for surface actors.

Implements Phase 5 of ``docs/Surface Map Plan.md``: the movement of
actors between the active Immediate Bubble (Tier 1, the ECS registry)
and their dehydrated record form in Save-Diff Journals (Tier 3 storage).

Design invariants (from the plan's "Hydration & Dehydration Contracts"):

* **Stable identity.** Every actor keeps the integer ID it received at
  birth through every dehydration/hydration cycle. Snapshots carry the
  ``actor_id`` key and stores must honor it on spawn (see
  :class:`EntityRegistryActorStore` and the ``entity_id`` parameter of
  ``EntityRegistry.create_entity``).
* **No double simulation.** A dehydrated actor exists *only* as its
  journal record; a hydrated actor exists *only* in the active store.
  Hydration consumes (pops) the journal snapshot, dehydration writes it
  and removes the actor from the store. Abstract population counters
  (Tier 2) never re-simulate a hydrated actor.
* **Eviction locks.** Actors that are visible to the player, audible,
  or engaged in gameplay interactions (combat, conversation) are never
  dehydrated; :class:`EvictionLocks` tracks the reasons.
* **Conflict resolution.** If a hydrated actor's tile became occupied
  while it was away (by a regional simulation moving another actor
  there), the hydration manager shifts it to the nearest unblocked tile
  instead of overlapping.
* **Determinism.** Tile search is an ordered spiral, and no module-level
  randomness exists; all state flows through explicit inputs. Compatible
  with ``scripts/check_deterministic_random.py``.

The :class:`ActorStore` protocol is the seam: the in-memory reference
implementation backs the tests, and
:class:`game.world.registry_actor_store.EntityRegistryActorStore`
bridges the production ``EntityRegistry``.
"""

from __future__ import annotations

from typing import Any, Final, Protocol, runtime_checkable

from game.world.save_diff_journal import SaveDiffJournal
from game.world.surface_chunks import DEFAULT_CHUNK_SIZE

ACTOR_ID_KEY: Final[str] = "actor_id"
"""Snapshot key holding the actor's stable identity."""

POSITION_KEYS: Final[tuple[str, str]] = ("x", "y")
"""Snapshot keys holding the actor's global tile position."""

DEFAULT_RELOCATION_RADIUS: Final[int] = 8
"""Maximum spiral-search radius for conflict-relocation on hydration."""

EVICT_LOCK_VISIBLE: Final[str] = "visible"
EVICT_LOCK_AUDIBLE: Final[str] = "audible"
EVICT_LOCK_ENGAGED: Final[str] = "engaged"
"""Canonical eviction-lock reasons named by the plan."""


class EvictionLocks:
    """Tracks actors that must never be dehydrated out of the bubble.

    An actor is eviction-locked while visible to the player, within
    hearing, or engaged in active gameplay (combat, conversation). Each
    lock records its reasons so systems can stack and release them
    independently.
    """

    def __init__(self) -> None:
        self._locks: dict[int, set[str]] = {}

    def lock(self, actor_id: int, reason: str = EVICT_LOCK_ENGAGED) -> None:
        """Add an eviction lock reason for ``actor_id``."""
        self._locks.setdefault(actor_id, set()).add(reason)

    def unlock(self, actor_id: int, reason: str | None = None) -> None:
        """Remove one lock reason, or all of them when ``reason`` is None."""
        if actor_id not in self._locks:
            return
        if reason is None:
            del self._locks[actor_id]
            return
        self._locks[actor_id].discard(reason)
        if not self._locks[actor_id]:
            del self._locks[actor_id]

    def is_locked(self, actor_id: int) -> bool:
        """Whether the actor is currently protected from dehydration."""
        return actor_id in self._locks

    def reasons_for(self, actor_id: int) -> frozenset[str]:
        """Return the active lock reasons for ``actor_id``."""
        return frozenset(self._locks.get(actor_id, ()))

    def clear(self) -> None:
        """Release every lock (e.g. on session teardown)."""
        self._locks.clear()


@runtime_checkable
class ActorStore(Protocol):
    """The active-actor seam hydration flows through.

    Implementations own the Immediate Bubble's actor state: the
    production ``EntityRegistry`` (via
    ``EntityRegistryActorStore``) or the in-memory reference store used
    by tests.
    """

    def active_actor_ids(self) -> list[int]:
        """Return every currently active (hydrated) actor ID."""
        ...

    def snapshot_actor(self, actor_id: int) -> dict[str, Any]:
        """Return a JSON-serializable snapshot dict for an active actor.

        Must include ``actor_id`` and the global position keys
        ``"x"``/``"y"``.
        """
        ...

    def despawn_actor(self, actor_id: int) -> None:
        """Remove an actor from the active store (Tier 1 teardown)."""
        ...

    def spawn_actor(self, snapshot: dict[str, Any]) -> None:
        """Re-create an actor from a snapshot, keeping its stable ID.

        Implementations must honor ``snapshot["actor_id"]`` as the
        actor's identity rather than allocating a new one.
        """
        ...

    def move_actor(self, actor_id: int, x: int, y: int) -> bool:
        """Move an active actor to tile ``(x, y)``.

        Surface behaviors (Phase 6) call this after validating
        walkability, bounds, and occupancy themselves. Returns
        ``False`` when the actor is not active.
        """
        ...

    def is_tile_blocked(self, x: int, y: int) -> bool:
        """Whether ``(x, y)`` cannot host an actor (occupied/unwalkable)."""
        ...


class ChunkHydrationManager:
    """Moves actors between the active registry and journal records.

    Works in global tile coordinates and chunk-space boundaries, mirroring
    the Phase 1 transforms and the Phase 3/4 chunk machinery.
    """

    def __init__(
        self,
        store: ActorStore,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        locks: EvictionLocks | None = None,
        relocation_radius: int = DEFAULT_RELOCATION_RADIUS,
        can_occupy: Callable[[int, int], bool] | None = None,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError(
                f"chunk_size must be a positive integer, got {chunk_size}"
            )
        if relocation_radius < 1:
            raise ValueError(
                f"relocation_radius must be >= 1, got {relocation_radius}"
            )
        self._store = store
        self._chunk_size = chunk_size
        self._locks = locks if locks is not None else EvictionLocks()
        self._relocation_radius = relocation_radius
        self._can_occupy = can_occupy

    @property
    def chunk_size(self) -> int:
        """Configured chunk dimension in tiles."""
        return self._chunk_size

    @property
    def locks(self) -> EvictionLocks:
        """The eviction-lock registry used on dehydration."""
        return self._locks

    def _chunk_rect(
        self, cx: int, cy: int
    ) -> tuple[int, int, int, int]:
        """Return the chunk's global tile rectangle ``(x0, y0, x1, y1)``."""
        size = self._chunk_size
        return (cx * size, cy * size, (cx + 1) * size, (cy + 1) * size)

    def dehydrate_chunk_entities(
        self,
        journal: SaveDiffJournal,
        cx: int,
        cy: int,
        cz: int = 0,
    ) -> list[int]:
        """Dehydrate every unlocked actor inside chunk ``(cx, cy, cz)``.

        Each actor's snapshot is written into the chunk's journal
        (``entity_snapshots`` table) and the actor is removed from the
        active store, so it exists only as its record until hydration.
        Actors eviction-locked as visible, audible, or engaged are
        skipped and stay active. Returns the dehydrated actor IDs.
        """
        x0, y0, x1, y1 = self._chunk_rect(cx, cy)
        dehydrated: list[int] = []
        for actor_id in self._store.active_actor_ids():
            snapshot = self._store.snapshot_actor(actor_id)
            gx, gy = int(snapshot["x"]), int(snapshot["y"])
            if not (x0 <= gx < x1 and y0 <= gy < y1):
                continue
            if self._locks.is_locked(actor_id):
                continue
            snapshot[ACTOR_ID_KEY] = actor_id
            journal.record_entity_snapshot(str(actor_id), snapshot)
            self._store.despawn_actor(actor_id)
            dehydrated.append(actor_id)
        return dehydrated

    def hydrate_chunk_entities(
        self,
        journal: SaveDiffJournal,
        cx: int,
        cy: int,
        cz: int = 0,
    ) -> list[int]:
        """Hydrate every journal-recorded actor residing in the chunk.

        Snapshots positioned inside the chunk rect are re-created in the
        active store with their stable IDs; the journal record is
        consumed (popped) so the actor is never double-tracked. If the
        recorded tile is now blocked, the actor relocates to the nearest
        unblocked tile within ``relocation_radius``; if none exists the
        record stays dehydrated for a later attempt. Returns the
        hydrated actor IDs.
        """
        x0, y0, x1, y1 = self._chunk_rect(cx, cy)
        hydrated: list[int] = []
        for record_id in sorted(journal.entity_snapshots.keys()):
            snapshot = journal.entity_snapshots[record_id]
            gx, gy = int(snapshot["x"]), int(snapshot["y"])
            if not (x0 <= gx < x1 and y0 <= gy < y1):
                continue
            if not self._tile_available(gx, gy, (x0, y0, x1, y1)):
                relocated = self._nearest_free_tile(gx, gy, (x0, y0, x1, y1))
                if relocated is None:
                    continue  # No room in the bubble; stay a record.
                rx, ry = relocated
                snapshot = dict(snapshot)
                snapshot["x"], snapshot["y"] = rx, ry
            actor_id = int(snapshot.get(ACTOR_ID_KEY, record_id))
            self._store.spawn_actor(snapshot)
            journal.pop_entity_snapshot(record_id)
            hydrated.append(actor_id)
        return hydrated

    def _tile_available(
        self, x: int, y: int, bounds: tuple[int, int, int, int]
    ) -> bool:
        x0, y0, x1, y1 = bounds
        return (
            x0 <= x < x1 and y0 <= y < y1
            and not self._store.is_tile_blocked(x, y)
            and (self._can_occupy is None or self._can_occupy(x, y))
        )

    def _nearest_free_tile(
        self, x: int, y: int, bounds: tuple[int, int, int, int]
    ) -> tuple[int, int] | None:
        """Deterministic spiral search for the nearest unblocked tile."""
        for radius in range(1, self._relocation_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue  # Only this ring, inner rings done earlier.
                    candidate_x, candidate_y = x + dx, y + dy
                    if self._tile_available(candidate_x, candidate_y, bounds):
                        return (candidate_x, candidate_y)
        return None


class InMemoryActorStore:
    """Reference ActorStore holding actor snapshots in a dictionary.

    Test double and template for production adapters. Actors are
    JSON-serializable snapshot dicts; blocked tiles are either occupied
    by an actor or listed as static blockers (unwalkable terrain).
    """

    def __init__(
        self,
        *,
        blocked_tiles: set[tuple[int, int]] | None = None,
    ) -> None:
        self._actors: dict[int, dict[str, Any]] = {}
        self._blocked_tiles: set[tuple[int, int]] = set(blocked_tiles or ())

    def add_actor(self, snapshot: dict[str, Any]) -> int:
        """Insert an actor (test helper); returns its stable ID."""
        actor_id = int(snapshot[ACTOR_ID_KEY])
        self._actors[actor_id] = dict(snapshot)
        return actor_id

    def actor(self, actor_id: int) -> dict[str, Any] | None:
        """Return a copy of an active actor's snapshot, if present."""
        snapshot = self._actors.get(actor_id)
        return dict(snapshot) if snapshot is not None else None

    # -- ActorStore protocol ------------------------------------------

    def active_actor_ids(self) -> list[int]:
        """Return every currently active actor ID."""
        return sorted(self._actors.keys())

    def snapshot_actor(self, actor_id: int) -> dict[str, Any]:
        """Return the actor's snapshot dict (must be active)."""
        snapshot = self._actors.get(actor_id)
        if snapshot is None:
            raise KeyError(f"Actor {actor_id} is not active")
        return dict(snapshot)

    def despawn_actor(self, actor_id: int) -> None:
        """Remove the actor from the active store."""
        self._actors.pop(actor_id, None)

    def spawn_actor(self, snapshot: dict[str, Any]) -> None:
        """Re-create an actor from a snapshot, keeping its stable ID."""
        actor_id = int(snapshot[ACTOR_ID_KEY])
        self._actors[actor_id] = dict(snapshot)

    def move_actor(self, actor_id: int, x: int, y: int) -> bool:
        """Move an active actor to ``(x, y)`` (caller-validated)."""
        snapshot = self._actors.get(actor_id)
        if snapshot is None:
            return False
        snapshot["x"], snapshot["y"] = int(x), int(y)
        return True

    def is_tile_blocked(self, x: int, y: int) -> bool:
        """A tile is blocked if unwalkable or occupied by an actor."""
        if (x, y) in self._blocked_tiles:
            return True
        return any(
            int(snapshot["x"]) == x and int(snapshot["y"]) == y
            for snapshot in self._actors.values()
        )


__all__ = [
    "ACTOR_ID_KEY",
    "ActorStore",
    "ChunkHydrationManager",
    "DEFAULT_RELOCATION_RADIUS",
    "EVICT_LOCK_AUDIBLE",
    "EVICT_LOCK_ENGAGED",
    "EVICT_LOCK_VISIBLE",
    "EvictionLocks",
    "InMemoryActorStore",
]
