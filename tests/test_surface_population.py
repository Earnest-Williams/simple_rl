"""Tests for deterministic surface population and behaviors (Phase 6).

Covers docs/Surface Map Plan.md Phase 6: actor templates for humans,
wildlife, and monsters; deterministic roster derivation and placement
through the SurfaceContext spawn-anchor API; context-aware behaviors
(seek-water, forage, anchor-leash, wander) in the surface turn loop;
speed gating; surface bounds; and the no-double-simulation contract
with the Phase 5 hydration machinery.
"""

from __future__ import annotations

import numpy as np

from common.constants import Material
from game.world.game_map import GameMap
from game.world.lod_hydration import (
    ACTOR_ID_KEY,
    ChunkHydrationManager,
    EvictionLocks,
    InMemoryActorStore,
)
from game.world.save_diff_journal import SaveDiffJournal
from game.world.surface_context import (
    SurfaceContext,
    SurfaceSpawnProfile,
    WATER_SPAWN_MATERIALS,
)
from game.world.surface_materializer import (
    InMemoryPromiseSource,
    RegionalPromise,
    SurfaceFeatureKind,
    SurfaceMaterializer,
    apply_materialized_chunk,
)
from game.world.surface_population import (
    TEMPLATE_LIBRARY,
    SeedStream,
    SurfacePopulationPlanner,
    derive_population_roster,
    run_surface_turn,
)
from worldgen.overland.schema import (
    HydroRole,
    OverlandMapMetadata,
    TraversalClass,
    Wetness,
)

_WIDTH = 12
_HEIGHT = 12
_CHUNK = 16
_WORLD_SEED = "phase-six"

_WATER_MATERIALS = frozenset(
    {
        Material.SHALLOW_WATER,
        Material.DEEP_WATER,
        Material.FLOWING_WATER,
        Material.SPRING_WATER,
    }
)


def _build_surface_map(
    materials: dict[tuple[int, int], Material],
    *,
    width: int = _WIDTH,
    height: int = _HEIGHT,
) -> GameMap:
    """Build a runtime map with an overland metadata sidecar."""
    game_map = GameMap(width=width, height=height)
    material_grid = np.full((height, width), int(Material.GRASS), dtype=np.int16)
    traversal_grid = np.full(
        (height, width), int(TraversalClass.NORMAL), dtype=np.int16
    )
    wetness_grid = np.full((height, width), int(Wetness.DRY), dtype=np.int16)
    cost_grid = np.ones((height, width), dtype=np.float32)
    hydro_grid = np.zeros((height, width), dtype=np.int16)

    for (x, y), material in materials.items():
        material_grid[y, x] = int(material)
        if material in _WATER_MATERIALS:
            traversal_grid[y, x] = int(TraversalClass.SWIM_OR_BOAT)
            wetness_grid[y, x] = int(Wetness.DEEP_FLOODED)

    sidecar = OverlandMapMetadata(
        material_grid=material_grid,
        biome_grid=np.zeros((height, width), dtype=np.int16),
        hydro_grid=hydro_grid,
        wetness_grid=wetness_grid,
        movement_cost_grid=cost_grid,
        traversal_class_grid=traversal_grid,
        route_segments=[],
        evidence_tags={},
        transitions={},
        affordances={},
        starting_contract={},
    )
    game_map.overland_metadata = sidecar
    return game_map


def _actor(template_id: str, x: int, y: int, **overrides) -> dict:
    """Build a behavior snapshot from a template, with overrides."""
    template = TEMPLATE_LIBRARY[template_id]
    snapshot = {
        ACTOR_ID_KEY: 1,
        "template_id": template.template_id,
        "name": template.name,
        "glyph": template.glyph,
        "color_fg_r": template.color_fg[0],
        "color_fg_g": template.color_fg[1],
        "color_fg_b": template.color_fg[2],
        "species": template.species,
        "faction": template.faction,
        "behavior": template.behavior,
        "hp": template.hp,
        "max_hp": template.max_hp,
        "intelligence": template.intelligence,
        "blocks_movement": template.blocks_movement,
        "leash_radius": template.leash_radius,
        "move_every": template.move_every,
        "seek_radius": template.seek_radius,
        "traversal": int(template.traversal),
        "spawn_profile": int(template.spawn_profile),
        "home_x": x,
        "home_y": y,
        "x": x,
        "y": y,
        "chunk_id": "chunk_0_0_0",
    }
    snapshot.update(overrides)
    return snapshot


def _positions(store: InMemoryActorStore, actor_id: int) -> tuple[int, int]:
    snapshot = store.actor(actor_id)
    assert snapshot is not None
    return int(snapshot["x"]), int(snapshot["y"])


def _trajectory(
    store: InMemoryActorStore, context: SurfaceContext, actor_id: int, turns: int
) -> list[tuple[int, int]]:
    path = [_positions(store, actor_id)]
    for turn in range(1, turns + 1):
        run_surface_turn(store, context, turn)
        path.append(_positions(store, actor_id))
    return path


# ---------------------------------------------------------------------------
# Templates and roster derivation
# ---------------------------------------------------------------------------


def test_actor_templates_cover_spawn_profiles() -> None:
    """Every spawn profile has templates with sane, complete fields."""
    profiles = {t.spawn_profile for t in TEMPLATE_LIBRARY.values()}
    assert profiles == {
        SurfaceSpawnProfile.HUMAN_SETTLEMENT,
        SurfaceSpawnProfile.WATER_WILDLIFE,
        SurfaceSpawnProfile.FORAGE_WILDLIFE,
        SurfaceSpawnProfile.CAVE_MONSTER,
    }
    for template in TEMPLATE_LIBRARY.values():
        assert 0 < template.hp <= template.max_hp
        assert template.move_every >= 1
        assert template.leash_radius >= 1
        # Humans wander, water and forage wildlife seek their biomes,
        # monsters stay leashed near their anchors.
        if template.species == "human":
            assert template.behavior == "wander"
        if template.faction == "monster":
            assert template.behavior == "anchor_leash"


def test_population_roster_is_deterministic() -> None:
    """Identical chunk and seed always derive the identical roster."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING, anchor_x=8, anchor_y=8
            )
        ],
        chunk_size=_CHUNK,
    )
    chunk = SurfaceMaterializer(
        source, world_seed=_WORLD_SEED, chunk_size=_CHUNK
    ).materialize_chunk(0, 0)
    assert chunk.spawn_anchors

    first = derive_population_roster(chunk, population_seed=1234)
    second = derive_population_roster(chunk, population_seed=1234)
    assert [(e.template_id, e.count) for e in first] == [
        (e.template_id, e.count) for e in second
    ]
    assert all(
        1 <= entry.count <= 3 and entry.template_id in TEMPLATE_LIBRARY
        for entry in first
    )

    # Different seeds produce different draws somewhere in the stream.
    stream_a = [SeedStream(1).next_int(997) for _ in range(8)]
    stream_b = [SeedStream(2).next_int(997) for _ in range(8)]
    assert stream_a != stream_b


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------


def test_populate_chunk_places_valid_anchored_actors() -> None:
    """Placed actors sit on valid spawn-anchor tiles with template state."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING, anchor_x=8, anchor_y=8
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = SurfaceMaterializer(
        source, world_seed=_WORLD_SEED, chunk_size=_CHUNK
    )
    chunk = materializer.materialize_chunk(0, 0)
    game_map = GameMap(width=_CHUNK, height=_CHUNK)
    apply_materialized_chunk(game_map, chunk)
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    planner = SurfacePopulationPlanner(
        store, context, world_seed=_WORLD_SEED
    )

    placed = planner.populate_chunk(chunk)
    assert placed, "the spring chunk should attract wildlife"
    assert len(set(placed)) == len(placed)
    tiles = set()
    for actor_id in placed:
        snapshot = store.actor(actor_id)
        assert snapshot is not None
        profile = SurfaceSpawnProfile(int(snapshot["spawn_profile"]))
        x, y = int(snapshot["x"]), int(snapshot["y"])
        assert context.is_valid_spawn_anchor(profile, x, y)
        assert (x, y) not in tiles
        tiles.add((x, y))
        template = TEMPLATE_LIBRARY[snapshot["template_id"]]
        assert snapshot["name"] == template.name
        assert snapshot["hp"] == template.hp
        assert snapshot["behavior"] == template.behavior
        assert snapshot["chunk_id"] == "chunk_0_0_0"
        assert snapshot["home_x"] == 8 and snapshot["home_y"] == 10


def test_populate_chunk_is_deterministic() -> None:
    """Identical worlds populate identically, including actor IDs."""
    def populate() -> list[tuple[int, str, int, int]]:
        source = InMemoryPromiseSource(
            [
                RegionalPromise(
                    kind=SurfaceFeatureKind.SPRING, anchor_x=8, anchor_y=8
                )
            ],
            chunk_size=_CHUNK,
        )
        materializer = SurfaceMaterializer(
            source, world_seed=_WORLD_SEED, chunk_size=_CHUNK
        )
        chunk = materializer.materialize_chunk(0, 0)
        game_map = GameMap(width=_CHUNK, height=_CHUNK)
        apply_materialized_chunk(game_map, chunk)
        store = InMemoryActorStore()
        planner = SurfacePopulationPlanner(
            store, context=SurfaceContext(game_map), world_seed=_WORLD_SEED
        )
        ids = planner.populate_chunk(chunk)
        rows = []
        for actor_id in ids:
            snapshot = store.actor(actor_id)
            assert snapshot is not None
            rows.append(
                (
                    actor_id,
                    snapshot["template_id"],
                    int(snapshot["x"]),
                    int(snapshot["y"]),
                )
            )
        return rows

    assert populate() == populate()


def test_populate_relocates_around_blocked_anchor() -> None:
    """An occupied anchor tile relocates actors to the nearest valid tile."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING, anchor_x=8, anchor_y=8
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = SurfaceMaterializer(
        source, world_seed=_WORLD_SEED, chunk_size=_CHUNK
    )
    chunk = materializer.materialize_chunk(0, 0)
    game_map = GameMap(width=_CHUNK, height=_CHUNK)
    apply_materialized_chunk(game_map, chunk)
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    planner = SurfacePopulationPlanner(
        store, context, world_seed=_WORLD_SEED, min_per_anchor=3, max_per_anchor=3
    )
    placed = planner.populate_chunk(chunk)
    assert len(placed) == 3
    # No two actors share a tile: the ring search stepped around the
    # occupied anchor and each other.
    tiles = [_positions(store, actor_id) for actor_id in placed]
    assert len(set(tiles)) == 3


def test_populate_skips_when_no_valid_tile() -> None:
    """Actors are simply not placed when no valid tile exists nearby."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING, anchor_x=8, anchor_y=8
            )
        ],
        chunk_size=_CHUNK,
    )
    chunk = SurfaceMaterializer(
        source, world_seed=_WORLD_SEED, chunk_size=_CHUNK
    ).materialize_chunk(0, 0)
    # Plain GameMap without an overland sidecar: water-anchor semantics
    # have nothing to validate against, so nothing can be placed.
    game_map = GameMap(width=_CHUNK, height=_CHUNK)
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    planner = SurfacePopulationPlanner(
        store, context, world_seed=_WORLD_SEED, placement_radius=0
    )
    assert planner.populate_chunk(chunk) == []
    assert store.active_actor_ids() == []


# ---------------------------------------------------------------------------
# Behaviors and the surface turn loop
# ---------------------------------------------------------------------------


def test_seek_water_reaches_water() -> None:
    """A heron walks to the nearest water tile and then stays put."""
    game_map = _build_surface_map({(9, 2): Material.SHALLOW_WATER})
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    store.add_actor(_actor("heron", 2, 2, actor_id=7))

    for turn in range(1, 8):
        run_surface_turn(store, context, turn)
    x, y = _positions(store, 7)
    assert context.material_at(x, y) in WATER_SPAWN_MATERIALS

    # Water reached: the heron holds position instead of pacing.
    stats = run_surface_turn(store, context, 8)
    assert stats == {"moved": 0, "waited": 1, "blocked": 0}
    assert _positions(store, 7) == (x, y)


def test_forage_moves_toward_forage() -> None:
    """A deer on barren road walks to the nearest forage tile."""
    materials = {
        (x, y): Material.ROAD
        for x in range(_WIDTH)
        for y in range(_HEIGHT)
    }
    materials[(0, 0)] = Material.FOREST_FLOOR
    game_map = _build_surface_map(materials)
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    store.add_actor(_actor("deer", 5, 5, actor_id=3))

    assert not context.can_forage(5, 5)
    for turn in range(1, 7):
        run_surface_turn(store, context, turn)
    x, y = _positions(store, 3)
    assert context.can_forage(x, y)


def test_anchor_leash_bounds_monsters() -> None:
    """A cave creeper never wanders beyond its leash radius from home."""
    game_map = _build_surface_map({(6, 6): Material.CAVE_FLOOR})
    context = SurfaceContext(game_map)
    store = InMemoryActorStore()
    store.add_actor(
        _actor("cave_creeper", 6, 6, actor_id=11, leash_radius=5)
    )

    for x, y in _trajectory(store, context, 11, turns=60):
        assert max(abs(x - 6), abs(y - 6)) <= 5, (x, y)


def test_wander_deterministic_and_bounded() -> None:
    """Wandering actors stay in bounds and follow identical trajectories."""
    def wander_path() -> list[tuple[int, int]]:
        context = SurfaceContext(_build_surface_map({}))
        store = InMemoryActorStore()
        store.add_actor(_actor("villager", 0, 0, actor_id=42))
        return _trajectory(store, context, 42, turns=100)

    first, second = wander_path(), wander_path()
    assert first == second
    for x, y in first:
        assert 0 <= x < _WIDTH and 0 <= y < _HEIGHT


def test_move_every_gates_actions() -> None:
    """A boar (move_every=2) only acts on every second turn."""
    context = SurfaceContext(_build_surface_map({}))
    store = InMemoryActorStore()
    store.add_actor(
        _actor("boar", 6, 6, actor_id=5, behavior="wander")
    )

    assert run_surface_turn(store, context, 1) == {
        "moved": 0, "waited": 1, "blocked": 0,
    }
    assert _positions(store, 5) == (6, 6)
    assert run_surface_turn(store, context, 2) == {
        "moved": 1, "waited": 0, "blocked": 0,
    }
    assert _positions(store, 5) != (6, 6)


def test_turn_loop_respects_hydration_no_double_simulation() -> None:
    """The turn loop steps active actors only; records stay frozen."""
    context = SurfaceContext(_build_surface_map({}))
    store = InMemoryActorStore()
    store.add_actor(_actor("otter", 5, 5, actor_id=21))
    journal = SaveDiffJournal(0, 0)
    manager = ChunkHydrationManager(
        store, chunk_size=64, locks=EvictionLocks()
    )

    dehydrated = manager.dehydrate_chunk_entities(journal, 0, 0)
    assert dehydrated == [21]
    assert journal.entity_snapshots["21"]["x"] == 5

    # Dehydrated: the actor is not active, so the turn loop touches
    # nothing -- no double simulation while it is a frozen record.
    assert run_surface_turn(store, context, 1) == {
        "moved": 0, "waited": 0, "blocked": 0,
    }
    assert journal.entity_snapshots["21"]["x"] == 5
    assert journal.entity_snapshots["21"]["y"] == 5

    hydrated = manager.hydrate_chunk_entities(journal, 0, 0)
    assert hydrated == [21]
    assert not journal.has_entity_snapshot("21")
    assert run_surface_turn(store, context, 2)["moved"] == 1
    assert _positions(store, 21) != (5, 5)
