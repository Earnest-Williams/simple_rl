"""Production-facing regressions for stable surface identity and geometry."""

from __future__ import annotations

from common.constants import Material
from game.entities.registry import EntityRegistry
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from game.world.lod_hydration import ChunkHydrationManager
from game.world.registry_actor_store import EntityRegistryActorStore
from game.world.save_diff_journal import SaveDiffJournal
from game.world.surface_context import SurfaceContext
from game.world.surface_materializer import (
    InMemoryPromiseSource,
    RegionalPromise,
    SurfaceFeatureKind,
    SurfaceMaterializer,
    apply_materialized_chunk,
)
from game.world.surface_population import run_surface_turn
from worldgen.overland.actor_traversal import ActorTraversalProfile


def test_production_registry_reuses_slots_across_dehydration() -> None:
    registry = EntityRegistry()
    store = EntityRegistryActorStore(registry)
    actor_id = 42
    store.spawn_actor({
        "actor_id": actor_id, "x": 3, "y": 4, "name": "deer",
        "glyph": 100, "color_fg_r": 1, "color_fg_g": 2,
        "color_fg_b": 3, "blocks_movement": True, "hp": 5,
        "max_hp": 8, "behavior": "forage", "move_every": 2,
        "traversal": int(ActorTraversalProfile.PACK_ANIMAL),
        "home_x": 3, "home_y": 4, "template_id": "deer",
    })
    initial_index = registry.index_of_entity(actor_id)
    assert initial_index is not None
    manager = ChunkHydrationManager(store, chunk_size=16)
    journal = SaveDiffJournal(0, 0)
    assert manager.dehydrate_chunk_entities(journal, 0, 0) == [actor_id]
    assert registry.index_of_entity(actor_id) is None
    assert journal.entity_snapshots["42"]["behavior"] == "forage"
    assert manager.hydrate_chunk_entities(journal, 0, 0) == [actor_id]
    assert registry.index_of_entity(actor_id) == initial_index
    assert store.snapshot_actor(actor_id)["traversal"] == int(
        ActorTraversalProfile.PACK_ANIMAL
    )
    assert store.snapshot_actor(actor_id)["move_every"] == 2
    assert registry.create_entity(
        x=1, y=1, glyph=64, color_fg=(1, 2, 3), name="another",
    ) != actor_id
    for _ in range(5):
        assert manager.dehydrate_chunk_entities(journal, 0, 0) == [actor_id]
        assert manager.hydrate_chunk_entities(journal, 0, 0) == [actor_id]
    assert registry._store.count == 2


def test_surface_turn_does_not_move_unrelated_player() -> None:
    registry = EntityRegistry()
    player = registry.create_entity(
        x=2, y=2, glyph=64, color_fg=(1, 2, 3), name="player"
    )
    game_map = GameMap(width=8, height=8)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    assert run_surface_turn(EntityRegistryActorStore(registry),
                            SurfaceContext(game_map), 1) == {
        "moved": 0, "waited": 0, "blocked": 0,
    }
    assert registry.get_position(player).x == 2


def test_nonzero_viewport_and_wall_gate_walkability() -> None:
    game_map = GameMap(width=8, height=8)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.tiles[1, 1] = TILE_ID_WALL
    context = SurfaceContext(
        game_map, viewport_origin_x=-32, viewport_origin_y=64
    )
    profile = ActorTraversalProfile.HUMAN_ON_FOOT
    assert context.in_bounds(-31, 65)
    assert context.can_walk(profile, -31, 65) is False
    assert context.can_walk(profile, -30, 65) is True
    assert context.in_bounds(0, 0) is False


def test_spring_crosses_chunk_boundary() -> None:
    source = InMemoryPromiseSource(
        [RegionalPromise(kind=SurfaceFeatureKind.SPRING,
                         anchor_x=15, anchor_y=8)], chunk_size=16
    )
    materializer = SurfaceMaterializer(
        source, world_seed=50, chunk_size=16, debris_fraction=0.0
    )
    west = materializer.materialize_chunk(0, 0)
    east = materializer.materialize_chunk(1, 0)
    assert int(west.materials[8, 15]) == int(Material.DEEP_WATER)
    assert int(east.materials[8, 0]) == int(Material.DEEP_WATER)
    game_map = GameMap(width=32, height=16)
    apply_materialized_chunk(game_map, west)
    apply_materialized_chunk(game_map, east)
    context = SurfaceContext(game_map)
    assert context.material_at(15, 8) == context.material_at(16, 8)


def test_hydration_relocation_respects_chunk_and_terrain() -> None:
    from game.world.lod_hydration import InMemoryActorStore

    store = InMemoryActorStore(blocked_tiles={(0, 0)})
    journal = SaveDiffJournal(0, 0)
    journal.record_entity_snapshot("500", {"actor_id": 500, "x": 0, "y": 0})
    manager = ChunkHydrationManager(
        store, chunk_size=2, relocation_radius=2,
        can_occupy=lambda x, y: (x, y) == (1, 1),
    )
    assert manager.hydrate_chunk_entities(journal, 0, 0) == [500]
    assert (store.actor(500)["x"], store.actor(500)["y"]) == (1, 1)
