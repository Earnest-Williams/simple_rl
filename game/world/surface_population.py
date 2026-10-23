"""Deterministic surface population and context-aware actor behaviors.

Implements Phase 6 of ``docs/Surface Map Plan.md``: populating the
playable surface layer with deterministic NPCs, wildlife, and monsters
placed through the :class:`SurfaceContext` semantic API, plus the basic
context-aware behaviors they run every turn.

Design invariants (carried over from Phases 1-5):

* **Determinism.** Every placement and behavior choice derives from
  SHA-256 counter digests (:class:`SeedStream`) or ordered ring
  searches; the module never touches ``random``, ``secrets``,
  ``uuid4``, or ``os.urandom`` and passes
  ``scripts/check_deterministic_random.py``.
* **SurfaceContext as the seam.** Placement validates tiles with
  ``is_valid_spawn_anchor`` and movement validates with ``can_walk``,
  so behaviors never read overland grids or the raw tile map directly.
* **Stable identity.** Actors are spawned into an :class:`ActorStore`
  with sequential stable IDs assigned by the planner; snapshots carry
  the same ``actor_id`` key used by the Phase 5 hydration machinery,
  so populated actors dehydrate and re-hydrate like any other actor.
* **No double simulation.** :func:`run_surface_turn` only steps actors
  that are active in the store; dehydrated journal records stay frozen
  until their chunk is hydrated again.
* **Surface bounds.** Behavior steps are bounded before any
  ``SurfaceContext`` verb is called, so actors can never walk off the
  map even when seeded to try.

Behavior vocabulary (snapshot ``behavior`` key):

* ``wander`` -- deterministic seeded drift among enterable neighbors.
* ``seek_water`` -- animals (heron, otter) move toward the nearest
  water/wet tile and stop once they reach it.
* ``forage`` -- animals (deer, boar) move toward the nearest forage
  tile and stop once they reach it.
* ``anchor_leash`` -- monsters (cave creepers, ruin stalkers) wander
  near their spawn anchor and are pulled back once they exceed their
  leash radius.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Final

from game.world.lod_hydration import ACTOR_ID_KEY, ActorStore
from game.world.save_diff_journal import SaveDiffJournal
from game.world.surface_chunks import chunk_id, derive_chunk_seed
from game.world.surface_context import (
    WATER_SPAWN_MATERIALS,
    SurfaceContext,
    SurfaceSpawnProfile,
)
from game.world.surface_identity import SurfaceIdentityLedger
from game.world.surface_materializer import (
    MaterializedChunk,
    SurfaceSpawnAnchor,
)
from worldgen.overland.actor_traversal import ActorTraversalProfile

BEHAVIOR_WANDER: Final[str] = "wander"
BEHAVIOR_SEEK_WATER: Final[str] = "seek_water"
BEHAVIOR_FORAGE: Final[str] = "forage"
BEHAVIOR_ANCHOR_LEASH: Final[str] = "anchor_leash"

KNOWN_BEHAVIORS: Final[frozenset[str]] = frozenset(
    {
        BEHAVIOR_WANDER,
        BEHAVIOR_SEEK_WATER,
        BEHAVIOR_FORAGE,
        BEHAVIOR_ANCHOR_LEASH,
    }
)

DEFAULT_PLACEMENT_RADIUS: Final[int] = 8
"""Maximum ring search radius around a spawn anchor for actor tiles."""

DEFAULT_MIN_PER_ANCHOR: Final[int] = 1
DEFAULT_MAX_PER_ANCHOR: Final[int] = 3
"""Population bounds per spawn anchor; roster counts draw between them."""


@dataclass(frozen=True, slots=True)
class ActorTemplate:
    """A deterministic actor template for surface population.

    Field values flow into placement snapshots and drive behavior:
    ``behavior`` selects the per-turn routine, ``move_every`` gates how
    often the actor acts, and ``leash_radius`` bounds anchor-leash
    monsters to their spawn anchor.
    """

    template_id: str
    name: str
    glyph: int
    color_fg: tuple[int, int, int]
    species: str
    faction: str
    spawn_profile: SurfaceSpawnProfile
    traversal: ActorTraversalProfile
    behavior: str
    hp: int
    max_hp: int
    intelligence: int
    blocks_movement: bool = True
    leash_radius: int = 6
    move_every: int = 1
    seek_radius: int = 16

    def __post_init__(self) -> None:
        if self.behavior not in KNOWN_BEHAVIORS:
            raise ValueError(f"Unknown behavior: {self.behavior!r}")
        if self.hp < 0 or self.max_hp < 1 or self.hp > self.max_hp:
            raise ValueError(f"Invalid hp/max_hp for template {self.template_id!r}")
        if self.move_every < 1:
            raise ValueError(
                f"move_every must be >= 1 for template {self.template_id!r}"
            )
        if self.leash_radius < 1:
            raise ValueError(
                f"leash_radius must be >= 1 for template {self.template_id!r}"
            )


TEMPLATE_LIBRARY: Final[dict[str, ActorTemplate]] = {
    "villager": ActorTemplate(
        template_id="villager",
        name="villager",
        glyph=0x68,
        color_fg=(220, 210, 190),
        species="human",
        faction="settler",
        spawn_profile=SurfaceSpawnProfile.HUMAN_SETTLEMENT,
        traversal=ActorTraversalProfile.HUMAN_ON_FOOT,
        behavior=BEHAVIOR_WANDER,
        hp=10,
        max_hp=10,
        intelligence=3,
    ),
    "dock_worker": ActorTemplate(
        template_id="dock_worker",
        name="dock worker",
        glyph=0x64,
        color_fg=(200, 180, 140),
        species="human",
        faction="settler",
        spawn_profile=SurfaceSpawnProfile.HUMAN_SETTLEMENT,
        traversal=ActorTraversalProfile.HUMAN_ON_FOOT,
        behavior=BEHAVIOR_WANDER,
        hp=12,
        max_hp=12,
        intelligence=3,
    ),
    "deer": ActorTemplate(
        template_id="deer",
        name="deer",
        glyph=0x76,
        color_fg=(180, 130, 80),
        species="deer",
        faction="wildlife",
        spawn_profile=SurfaceSpawnProfile.FORAGE_WILDLIFE,
        traversal=ActorTraversalProfile.PACK_ANIMAL,
        behavior=BEHAVIOR_FORAGE,
        hp=8,
        max_hp=8,
        intelligence=1,
        move_every=1,
        seek_radius=12,
    ),
    "boar": ActorTemplate(
        template_id="boar",
        name="boar",
        glyph=0x62,
        color_fg=(120, 90, 70),
        species="boar",
        faction="wildlife",
        spawn_profile=SurfaceSpawnProfile.FORAGE_WILDLIFE,
        traversal=ActorTraversalProfile.PACK_ANIMAL,
        behavior=BEHAVIOR_FORAGE,
        hp=12,
        max_hp=12,
        intelligence=1,
        move_every=2,
        seek_radius=12,
    ),
    "heron": ActorTemplate(
        template_id="heron",
        name="heron",
        glyph=0x48,
        color_fg=(150, 160, 180),
        species="heron",
        faction="wildlife",
        spawn_profile=SurfaceSpawnProfile.WATER_WILDLIFE,
        traversal=ActorTraversalProfile.SMALL_AMPHIBIOUS,
        behavior=BEHAVIOR_SEEK_WATER,
        hp=4,
        max_hp=4,
        intelligence=1,
        seek_radius=16,
    ),
    "otter": ActorTemplate(
        template_id="otter",
        name="otter",
        glyph=0x6F,
        color_fg=(130, 100, 80),
        species="otter",
        faction="wildlife",
        spawn_profile=SurfaceSpawnProfile.WATER_WILDLIFE,
        traversal=ActorTraversalProfile.SMALL_AMPHIBIOUS,
        behavior=BEHAVIOR_SEEK_WATER,
        hp=6,
        max_hp=6,
        intelligence=2,
        move_every=1,
        seek_radius=16,
    ),
    "cave_creeper": ActorTemplate(
        template_id="cave_creeper",
        name="cave creeper",
        glyph=0x63,
        color_fg=(90, 110, 90),
        species="cave creeper",
        faction="monster",
        spawn_profile=SurfaceSpawnProfile.CAVE_MONSTER,
        traversal=ActorTraversalProfile.SMALL_AMPHIBIOUS,
        behavior=BEHAVIOR_ANCHOR_LEASH,
        hp=14,
        max_hp=14,
        intelligence=1,
        leash_radius=5,
    ),
    "ruin_stalker": ActorTemplate(
        template_id="ruin_stalker",
        name="ruin stalker",
        glyph=0x72,
        color_fg=(140, 120, 130),
        species="ruin stalker",
        faction="monster",
        spawn_profile=SurfaceSpawnProfile.CAVE_MONSTER,
        traversal=ActorTraversalProfile.SMALL_AMPHIBIOUS,
        behavior=BEHAVIOR_ANCHOR_LEASH,
        hp=16,
        max_hp=16,
        intelligence=2,
        leash_radius=7,
        move_every=2,
    ),
}
"""Built-in actor templates for humans, wildlife, and monsters."""

DEFAULT_TEMPLATES_BY_PROFILE: Final[dict[SurfaceSpawnProfile, tuple[str, ...]]] = {
    SurfaceSpawnProfile.HUMAN_SETTLEMENT: ("villager", "dock_worker"),
    SurfaceSpawnProfile.WATER_WILDLIFE: ("heron", "otter"),
    SurfaceSpawnProfile.FORAGE_WILDLIFE: ("deer", "boar"),
    SurfaceSpawnProfile.CAVE_MONSTER: ("cave_creeper", "ruin_stalker"),
}
"""Which templates each spawn profile may draw from, by default."""


class SeedStream:
    """Deterministic integer stream from SHA-256 counter digests.

    Replaces the ``random`` module for population and behavior
    choices, per the repo-wide determinism policy: identical stream
    labels and draw orders yield identical results in every process.
    """

    __slots__ = ("_label", "_counter")

    def __init__(self, label: int | str) -> None:
        self._label = f"surface-population:{label}"
        self._counter = 0

    def next_int(self, modulo: int) -> int:
        """Draw the next deterministic integer in ``range(modulo)``."""
        if modulo < 1:
            raise ValueError(f"modulo must be >= 1, got {modulo}")
        digest = hashlib.sha256(f"{self._label}:{self._counter}".encode()).digest()
        self._counter += 1
        return int.from_bytes(digest[:8], "big") % modulo


@dataclass(frozen=True, slots=True)
class PopulationRosterEntry:
    """One spawn anchor's share of a chunk's population."""

    anchor: SurfaceSpawnAnchor
    template_id: str
    count: int


def derive_population_roster(
    chunk: MaterializedChunk,
    *,
    population_seed: int,
    templates_by_profile: Mapping[
        SurfaceSpawnProfile, tuple[str, ...]
    ] = DEFAULT_TEMPLATES_BY_PROFILE,
    min_per_anchor: int = DEFAULT_MIN_PER_ANCHOR,
    max_per_anchor: int = DEFAULT_MAX_PER_ANCHOR,
) -> list[PopulationRosterEntry]:
    """Derive a chunk's population roster from its seed deterministically.

    Anchors are processed in sorted ``(y, x, profile)`` order; each
    draws one template from its profile's template list and a count
    between ``min_per_anchor`` and ``max_per_anchor`` (inclusive) from
    the seeded stream, so the same chunk and seed always produce the
    same roster.
    """
    if min_per_anchor < 0:
        raise ValueError(f"min_per_anchor must be >= 0, got {min_per_anchor}")
    if max_per_anchor < min_per_anchor:
        raise ValueError(
            "max_per_anchor must be >= min_per_anchor "
            f"({max_per_anchor} < {min_per_anchor})"
        )
    stream = SeedStream(population_seed)
    roster: list[PopulationRosterEntry] = []
    anchors = sorted(
        chunk.spawn_anchors,
        key=lambda a: (a.y, a.x, int(a.profile), a.note),
    )
    for anchor in anchors:
        choices = templates_by_profile.get(anchor.profile)
        if not choices:
            continue
        template_id = choices[stream.next_int(len(choices))]
        span = max_per_anchor - min_per_anchor
        count = min_per_anchor + (stream.next_int(span + 1) if span else 0)
        roster.append(
            PopulationRosterEntry(anchor=anchor, template_id=template_id, count=count)
        )
    return roster


class SurfacePopulationPlanner:
    """Places deterministic actors at a chunk's spawn anchors.

    Each placement validates candidate tiles with
    ``SurfaceContext.is_valid_spawn_anchor`` and the store's occupancy
    check, spiraling outward from the anchor when the anchor tile
    itself is unavailable. Actors enter the active store as snapshots
    carrying stable sequential IDs compatible with the Phase 5
    hydration machinery.
    """

    def __init__(
        self,
        store: ActorStore,
        context: SurfaceContext,
        *,
        world_seed: int | str,
        content_version: int = 1,
        generation_version: int = 1,
        first_actor_id: int = 1,
        identity_ledger: SurfaceIdentityLedger | None = None,
        placement_radius: int = DEFAULT_PLACEMENT_RADIUS,
        templates_by_profile: Mapping[
            SurfaceSpawnProfile, tuple[str, ...]
        ] = DEFAULT_TEMPLATES_BY_PROFILE,
        min_per_anchor: int = DEFAULT_MIN_PER_ANCHOR,
        max_per_anchor: int = DEFAULT_MAX_PER_ANCHOR,
    ) -> None:
        if first_actor_id < 0:
            raise ValueError(f"first_actor_id must be >= 0, got {first_actor_id}")
        if placement_radius < 0:
            raise ValueError(f"placement_radius must be >= 0, got {placement_radius}")
        self._store = store
        self._context = context
        self._world_seed = world_seed
        self._content_version = int(content_version)
        self._generation_version = int(generation_version)
        self._first_actor_id = int(first_actor_id)
        self._next_actor_id = int(first_actor_id)
        self._ledger = identity_ledger or SurfaceIdentityLedger()
        self._has_world_ledger = identity_ledger is not None
        self._populated_chunks: set[str] = set()
        self._placement_radius = int(placement_radius)
        self._templates_by_profile = dict(templates_by_profile)
        self._min_per_anchor = int(min_per_anchor)
        self._max_per_anchor = int(max_per_anchor)

    @property
    def next_actor_id(self) -> int:
        """Deprecated initial namespace hint; IDs now come from the ledger."""
        return self._next_actor_id

    def populate_chunk(
        self, chunk: MaterializedChunk, journal: SaveDiffJournal | None = None
    ) -> list[int]:
        """Populate ``chunk`` per its derived roster; return actor IDs.

        The roster derives from the chunk's SHA-256 seed (Phase 1
        formula), so identical chunks and world seeds always populate
        identically. Actors whose anchor has no valid, unoccupied tile
        within the placement radius are simply not placed.
        """
        chunk_key = chunk_id(chunk.cx, chunk.cy, chunk.cz)
        from game.world.registry_actor_store import EntityRegistryActorStore

        if journal is None and isinstance(self._store, EntityRegistryActorStore):
            raise ValueError("Production surface population requires its chunk journal")
        if journal is not None:
            if journal.chunk_id != chunk_key:
                raise ValueError("Population journal belongs to a different chunk")
            if not self._has_world_ledger:
                raise ValueError(
                    "Persistent population requires an explicit world identity ledger"
                )
            if journal.population_initialized:
                return []
        elif chunk_key in self._populated_chunks:
            return []

        if self._min_per_anchor < 0 or self._max_per_anchor < self._min_per_anchor:
            raise ValueError(
                "Invalid anchor population bounds "
                f"({self._min_per_anchor}, {self._max_per_anchor})"
            )
        population_seed = derive_chunk_seed(
            self._world_seed,
            chunk.cx,
            chunk.cy,
            chunk.cz,
            content_version=self._content_version,
            generation_version=self._generation_version,
        )
        roster = derive_population_roster(
            chunk,
            population_seed=population_seed,
            templates_by_profile=self._templates_by_profile,
            min_per_anchor=self._min_per_anchor,
            max_per_anchor=self._max_per_anchor,
        )
        placed: list[int] = []
        active_ids = set(self._store.active_actor_ids())
        reserved = set(active_ids)
        if journal is not None:
            reserved.update(journal.population_births.values())
            reserved.update(
                int(actor_id)
                for actor_id in journal.entity_snapshots
                if actor_id.isdecimal()
            )
        for entry_index, entry in enumerate(roster):
            template = TEMPLATE_LIBRARY[entry.template_id]
            for ordinal in range(entry.count):
                birth_key = self._birth_key(chunk_key, entry_index, ordinal)
                tile = self._find_spawn_tile(entry.anchor, template)
                if tile is None:
                    continue
                actor_id = self._ledger.reserve(birth_key, occupied_ids=reserved)
                if actor_id in active_ids:
                    active = self._store.snapshot_actor(actor_id)
                    if active.get("birth_key") != birth_key:
                        raise ValueError(f"Conflicting generated actor ID {actor_id}")
                    continue
                snapshot = _build_snapshot(
                    template,
                    actor_id,
                    tile[0],
                    tile[1],
                    chunk_key,
                    entry.anchor,
                    birth_key,
                )
                self._store.spawn_actor(snapshot)
                active_ids.add(actor_id)
                reserved.add(actor_id)
                if journal is not None:
                    journal.record_population_birth(birth_key, actor_id)
                placed.append(actor_id)
        if journal is not None:
            journal.mark_population_initialized()
        self._populated_chunks.add(chunk_key)
        return placed

    def _birth_key(self, chunk_key: str, entry: int, ordinal: int) -> str:
        """Canonical identity that survives surrogate-ID hash collisions."""
        return (
            f"{self._world_seed}:{self._content_version}:"
            f"{self._generation_version}:{self._first_actor_id}:"
            f"{chunk_key}:{entry}:{ordinal}"
        )

    def _find_spawn_tile(
        self, anchor: SurfaceSpawnAnchor, template: ActorTemplate
    ) -> tuple[int, int] | None:
        """Nearest valid, unoccupied tile for ``template`` at ``anchor``.

        Rings around the anchor are searched in deterministic order
        (radius, then dy, then dx); the first tile satisfying the
        template's spawn profile and free of other actors wins.
        """
        for radius in range(0, self._placement_radius + 1):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    tx, ty = anchor.x + dx, anchor.y + dy
                    if not self._context.in_bounds(tx, ty):
                        continue
                    if not self._context.is_valid_spawn_anchor(
                        template.spawn_profile, tx, ty
                    ):
                        continue
                    if self._store.is_tile_blocked(tx, ty):
                        continue
                    return (tx, ty)
        return None


def _build_snapshot(
    template: ActorTemplate,
    actor_id: int,
    x: int,
    y: int,
    chunk_key: str,
    anchor: SurfaceSpawnAnchor,
    birth_key: str,
) -> dict[str, Any]:
    """Build the JSON-serializable snapshot for a placed actor."""
    return {
        ACTOR_ID_KEY: int(actor_id),
        "birth_key": birth_key,
        "template_id": template.template_id,
        "name": template.name,
        "glyph": int(template.glyph),
        "color_fg_r": int(template.color_fg[0]),
        "color_fg_g": int(template.color_fg[1]),
        "color_fg_b": int(template.color_fg[2]),
        "species": template.species,
        "faction": template.faction,
        "behavior": template.behavior,
        "hp": int(template.hp),
        "max_hp": int(template.max_hp),
        "intelligence": int(template.intelligence),
        "blocks_movement": bool(template.blocks_movement),
        "leash_radius": int(template.leash_radius),
        "move_every": int(template.move_every),
        "seek_radius": int(template.seek_radius),
        "traversal": int(template.traversal),
        "spawn_profile": int(template.spawn_profile),
        "home_x": int(anchor.x),
        "home_y": int(anchor.y),
        "x": int(x),
        "y": int(y),
        "chunk_id": chunk_key,
    }


def run_surface_turn(
    store: ActorStore,
    context: SurfaceContext,
    turn: int,
) -> dict[str, int]:
    """Step every active actor once; return per-outcome counts.

    This is the Phase 6 seam for the engine's normal turn loop: call
    it once per turn with the current turn number. Only actors active
    in the store are stepped; dehydrated journal records are never
    touched here (no double simulation). Outcomes: ``moved`` (actor
    changed tile), ``waited`` (speed gating or no reason to move), and
    ``blocked`` (no enterable step existed).
    """
    stats = {"moved": 0, "waited": 0, "blocked": 0}
    for actor_id in sorted(store.active_actor_ids()):
        snapshot = store.snapshot_actor(actor_id)
        if snapshot.get("behavior") not in KNOWN_BEHAVIORS:
            continue
        stats[step_actor(store, context, snapshot, turn)] += 1
    return stats


def step_actor(
    store: ActorStore,
    context: SurfaceContext,
    snapshot: dict[str, Any],
    turn: int,
) -> str:
    """Run one actor's behavior for ``turn``; return the outcome."""
    move_every = int(snapshot.get("move_every", 1))
    if move_every > 1 and turn % move_every != 0:
        return "waited"
    x, y = int(snapshot["x"]), int(snapshot["y"])
    target = _choose_step(store, context, snapshot, x, y, turn)
    if target is None:
        return "blocked"
    if target == (x, y):
        return "waited"
    if store.move_actor(int(snapshot[ACTOR_ID_KEY]), target[0], target[1]):
        return "moved"
    return "blocked"


def _choose_step(
    store: ActorStore,
    context: SurfaceContext,
    snapshot: dict[str, Any],
    x: int,
    y: int,
    turn: int,
) -> tuple[int, int] | None:
    """Decide an actor's next tile, or ``None`` if none is enterable.

    Behavior dispatch by the snapshot's ``behavior`` key; every
    candidate tile is bounded, checked through ``SurfaceContext``
    semantics, and checked for occupancy before being returned.
    """
    profile = ActorTraversalProfile(
        int(snapshot.get("traversal", int(ActorTraversalProfile.HUMAN_ON_FOOT)))
    )
    behavior = str(snapshot.get("behavior", BEHAVIOR_WANDER))

    def in_bounds(tx: int, ty: int) -> bool:
        return context.in_bounds(tx, ty)

    def enterable(tx: int, ty: int) -> bool:
        return (
            in_bounds(tx, ty)
            and context.can_walk(profile, tx, ty)
            and not store.is_tile_blocked(tx, ty)
        )

    if behavior == BEHAVIOR_SEEK_WATER:
        if in_bounds(x, y) and _is_water_tile(context, x, y):
            return (x, y)
        goal = _scan_for_tile(
            context,
            x,
            y,
            int(snapshot.get("seek_radius", 16)),
            lambda tx, ty: _is_water_tile(context, tx, ty),
        )
        if goal is None:
            return _wander_step(store, snapshot, x, y, turn, enterable)
        return _greedy_step_toward(goal, x, y, enterable)

    if behavior == BEHAVIOR_FORAGE:
        if in_bounds(x, y) and context.can_forage(x, y):
            return (x, y)
        goal = _scan_for_tile(
            context,
            x,
            y,
            int(snapshot.get("seek_radius", 16)),
            lambda tx, ty: in_bounds(tx, ty) and context.can_forage(tx, ty),
        )
        if goal is None:
            return _wander_step(store, snapshot, x, y, turn, enterable)
        return _greedy_step_toward(goal, x, y, enterable)

    if behavior == BEHAVIOR_ANCHOR_LEASH:
        home_x = int(snapshot.get("home_x", x))
        home_y = int(snapshot.get("home_y", y))
        leash = int(snapshot.get("leash_radius", 6))
        distance = max(abs(x - home_x), abs(y - home_y))

        def leashed(tx: int, ty: int) -> bool:
            return max(abs(tx - home_x), abs(ty - home_y)) <= leash

        if distance > leash:
            return _greedy_step_toward(
                (home_x, home_y),
                x,
                y,
                lambda tx, ty: enterable(tx, ty) and leashed(tx, ty),
            )
        wander = _wander_step(store, snapshot, x, y, turn, enterable)
        if wander is None:
            return None
        if wander != (x, y) and not leashed(wander[0], wander[1]):
            return (x, y)  # Would break the leash; hold position instead.
        return wander

    # BEHAVIOR_WANDER and any unknown key fall back to seeded drift.
    return _wander_step(store, snapshot, x, y, turn, enterable)


def _wander_step(
    store: ActorStore,
    snapshot: dict[str, Any],
    x: int,
    y: int,
    turn: int,
    enterable: Callable[[int, int], bool],
) -> tuple[int, int] | None:
    """Seeded deterministic drift among enterable neighbor tiles.

    The direction order rotates by a per-actor, per-turn SHA-256 draw
    so identical actors in identical situations follow identical
    trajectories while different actors spread out.
    """
    stream = SeedStream(f"{int(snapshot[ACTOR_ID_KEY])}:{turn}")
    ring = [
        (0, -1),
        (1, -1),
        (1, 0),
        (1, 1),
        (0, 1),
        (-1, 1),
        (-1, 0),
        (-1, -1),
    ]
    rotation = stream.next_int(len(ring))
    ordered = ring[rotation:] + ring[:rotation]
    for dx, dy in ordered:
        if enterable(x + dx, y + dy):
            return (x + dx, y + dy)
    return None


def _greedy_step_toward(
    goal: tuple[int, int],
    x: int,
    y: int,
    enterable: Callable[[int, int], bool],
) -> tuple[int, int] | None:
    """Deterministic single-tile step reducing distance to ``goal``."""
    gx, gy = goal
    step_x = (gx > x) - (gx < x)
    step_y = (gy > y) - (gy < y)
    candidates = [(step_x, step_y), (step_x, 0), (0, step_y)]
    seen: set[tuple[int, int]] = set()
    for dx, dy in candidates:
        if (dx, dy) in seen or (dx, dy) == (0, 0):
            continue
        seen.add((dx, dy))
        if enterable(x + dx, y + dy):
            return (x + dx, y + dy)
    return None


def _scan_for_tile(
    context: SurfaceContext,
    x: int,
    y: int,
    radius: int,
    predicate: Callable[[int, int], bool],
) -> tuple[int, int] | None:
    """Deterministic ring scan for the nearest tile passing ``predicate``."""
    for r in range(1, radius + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if max(abs(dx), abs(dy)) != r:
                    continue
                tx, ty = x + dx, y + dy
                if not context.in_bounds(tx, ty):
                    continue
                if predicate(tx, ty):
                    return (tx, ty)
    return None


def _is_water_tile(context: SurfaceContext, x: int, y: int) -> bool:
    """Whether the tile's material is water or water-adjacent wet mud."""
    material = context.material_at(x, y)
    return material is not None and material in WATER_SPAWN_MATERIALS


__all__ = [
    "BEHAVIOR_ANCHOR_LEASH",
    "BEHAVIOR_FORAGE",
    "BEHAVIOR_SEEK_WATER",
    "BEHAVIOR_WANDER",
    "DEFAULT_MAX_PER_ANCHOR",
    "DEFAULT_MIN_PER_ANCHOR",
    "DEFAULT_PLACEMENT_RADIUS",
    "DEFAULT_TEMPLATES_BY_PROFILE",
    "KNOWN_BEHAVIORS",
    "ActorTemplate",
    "PopulationRosterEntry",
    "SeedStream",
    "SurfacePopulationPlanner",
    "TEMPLATE_LIBRARY",
    "derive_population_roster",
    "run_surface_turn",
    "step_actor",
]
