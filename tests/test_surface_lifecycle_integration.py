"""Real-registry regressions for complete surface unload/reload cycles."""

from __future__ import annotations

import tempfile

import numpy as np
import polars as pl
import pytest

from common.constants import Material
from game.entities.components import Position
from game.entities.registry import EntityRegistry
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from game.world.lod_hydration import ChunkHydrationManager
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
    ensure_surface_metadata,
)
from game.world.surface_population import SurfacePopulationPlanner, run_surface_turn
from skills.registry_integration import SKILL_TABLE_SCHEMA
from worldgen.overland.actor_traversal import ActorTraversalProfile
from worldgen.overland.schema import TraversalClass


def _position(registry: EntityRegistry, actor_id: int) -> Position:
    position = registry.get_position(actor_id)
    assert position is not None
    return position


def _minimal_actor(actor_id: int, x: int, y: int) -> dict[str, object]:
    return {
        "actor_id": actor_id,
        "x": x,
        "y": y,
        "glyph": 65,
        "color_fg_r": 20,
        "color_fg_g": 30,
        "color_fg_b": 40,
        "name": "otter",
        "hp": 6,
        "max_hp": 7,
        "blocks_movement": True,
        "template_id": "otter",
        "behavior": "seek_water",
        "traversal": int(ActorTraversalProfile.SMALL_AMPHIBIOUS),
    }


def test_high_bit_id_occupancy_and_reusable_slot() -> None:
    registry = EntityRegistry()
    registry.ensure_occupancy_shape(8, 8)
    store = EntityRegistryActorStore(registry)
    actor_id = 0xE56A1234
    store.spawn_actor(_minimal_actor(actor_id, 3, 4))
    assert registry._store.blocking_entity_at.dtype == np.dtype("int64")
    assert registry.get_blocking_entity_at(3, 4) == actor_id
    assert store.move_actor(actor_id, 4, 4)
    assert registry.get_blocking_entity_at(3, 4) is None
    assert registry.get_blocking_entity_at(4, 4) == actor_id
    slot = registry.index_of_entity(actor_id)
    store.despawn_actor(actor_id)
    assert registry.get_blocking_entity_at(4, 4) is None
    assert registry.index_of_entity(actor_id) is None
    store.spawn_actor(_minimal_actor(actor_id, 5, 4))
    assert registry.index_of_entity(actor_id) == slot
    assert registry.get_blocking_entity_at(5, 4) == actor_id


def test_registry_hydration_requires_terrain_and_excludes_player() -> None:
    registry = EntityRegistry()
    registry.ensure_occupancy_shape(16, 16)
    player_id = registry.create_entity(
        x=1,
        y=1,
        glyph=64,
        color_fg=(1, 2, 3),
        name="player",
    )
    store = EntityRegistryActorStore(registry)
    store.spawn_actor(_minimal_actor(0x80000001, 8, 8))
    with pytest.raises(ValueError, match="requires SurfaceContext"):
        ChunkHydrationManager(store, chunk_size=16)

    game_map = GameMap(width=16, height=16)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.tiles[8, 7] = TILE_ID_WALL
    context = SurfaceContext(game_map)
    manager = ChunkHydrationManager(store, context=context, chunk_size=16)
    journal = SaveDiffJournal(0, 0)
    assert manager.dehydrate_chunk_entities(journal, 0, 0) == [0x80000001]
    assert _position(registry, player_id).x == 1
    assert not journal.has_entity_snapshot(str(player_id))
    # All nearby free terrain except (9, 9) becomes forbidden.
    for yy in range(16):
        for xx in range(16):
            if (xx, yy) not in {(1, 1), (9, 9)}:
                game_map.tiles[yy, xx] = TILE_ID_WALL
    assert manager.hydrate_chunk_entities(journal, 0, 0) == [0x80000001]
    assert _position(registry, 0x80000001).x == 9
    assert _position(registry, 0x80000001).y == 9


def test_real_population_refuses_missing_journal() -> None:
    source = InMemoryPromiseSource(
        [RegionalPromise(SurfaceFeatureKind.SPRING, 8, 8)],
        chunk_size=16,
    )
    chunk = SurfaceMaterializer(
        source, world_seed=1, chunk_size=16, debris_fraction=0.0
    ).materialize_chunk(0, 0)
    game_map = GameMap(width=16, height=16)
    apply_materialized_chunk(game_map, chunk)
    registry = EntityRegistry()
    planner = SurfacePopulationPlanner(
        EntityRegistryActorStore(registry),
        SurfaceContext(game_map),
        world_seed=1,
    )
    with pytest.raises(ValueError, match="requires its chunk journal"):
        planner.populate_chunk(chunk)


def test_complete_actor_components_and_skill_rows_survive() -> None:
    registry = EntityRegistry()
    registry.ensure_occupancy_shape(16, 16)
    store = EntityRegistryActorStore(registry)
    actor_id = 0x80000002
    store.spawn_actor(_minimal_actor(actor_id, 6, 6))
    registry.set_body_plan(actor_id, {"tail": 1, "head": 1})
    registry.set_entity_component(actor_id, "resistances", {"cold": 0.5})
    skill_row = {
        "entity_id": actor_id,
        "skill": 0,
        "level": 3,
        "xp": 100,
        "aptitude": 1,
        "weight": 2.0,
        "training_state": 1,
        "target_level": 255,
        "usage_count": 17,
    }
    registry.skills_df = pl.DataFrame([skill_row], schema=SKILL_TABLE_SCHEMA)
    game_map = GameMap(width=16, height=16)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    manager = ChunkHydrationManager(
        store, context=SurfaceContext(game_map), chunk_size=16
    )
    journal = SaveDiffJournal(0, 0)
    assert manager.dehydrate_chunk_entities(journal, 0, 0) == [actor_id]
    assert registry.skills_df.height == 0
    with tempfile.TemporaryDirectory() as directory:
        journal.write_atomic(directory)
        reloaded = SaveDiffJournal.load_or_create(directory, 0, 0)
        assert manager.hydrate_chunk_entities(reloaded, 0, 0) == [actor_id]
    assert registry.get_body_plan(actor_id) == {"tail": 1, "head": 1}
    assert registry.get_entity_component(actor_id, "resistances") == {"cold": 0.5}
    assert registry.skills_df.to_dicts() == [skill_row]


def test_unsupported_component_stays_active_instead_of_being_lost() -> None:
    registry = EntityRegistry()
    store = EntityRegistryActorStore(registry)
    actor_id = 0x80000003
    store.spawn_actor(_minimal_actor(actor_id, 4, 4))
    registry.set_entity_component(actor_id, "community_profile", object())
    game_map = GameMap(width=16, height=16)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    manager = ChunkHydrationManager(
        store, context=SurfaceContext(game_map), chunk_size=16
    )
    journal = SaveDiffJournal(0, 0)
    assert manager.dehydrate_chunk_entities(journal, 0, 0) == []
    assert registry._store.has_active(actor_id)
    assert not journal.entity_snapshots


def test_world_ledger_collision_probe_persists_reserved_id() -> None:
    class CollidingLedger(SurfaceIdentityLedger):
        @staticmethod
        def _candidate(birth_key: str, salt: int) -> int:
            if salt == 0:
                return 0x80000000
            return 0x80001000 + (ord(birth_key[0]) * 10) + salt

    with tempfile.TemporaryDirectory() as directory:
        ledger = CollidingLedger(directory=directory)
        a = ledger.reserve("alpha")
        b = ledger.reserve("bravo")
        assert a != b
        assert ledger.id_for("alpha") == a
        assert ledger.owner_of(b) == "bravo"
        restored = SurfaceIdentityLedger.load_or_create(directory)
        assert restored.reserve("alpha") == a
        assert restored.reserve("bravo") == b
        assert restored.reserve("charlie", occupied_ids={0x80000000}) not in {a, b}
        with pytest.raises(ValueError, match="Duplicate"):
            SurfaceIdentityLedger.from_dict(
                {
                    "version": 1,
                    "assignments": {"alpha": a, "bravo": a},
                }
            )


def test_spring_density_uses_anchor_owner_not_neighbor() -> None:
    source = InMemoryPromiseSource(
        [
            RegionalPromise(SurfaceFeatureKind.SPRING, 2, 2),
            RegionalPromise(SurfaceFeatureKind.SPRING, 7, 13),
            RegionalPromise(SurfaceFeatureKind.SPRING, 12, 5),
            RegionalPromise(SurfaceFeatureKind.SPRING, 16, 8),
        ],
        chunk_size=16,
    )
    materializer = SurfaceMaterializer(
        source, world_seed=1234, chunk_size=16, debris_fraction=0.0
    )
    west = materializer.materialize_chunk(0, 0)
    east = materializer.materialize_chunk(1, 0)
    for x, y in ((2, 2), (7, 13), (12, 5)):
        assert int(west.materials[y, x]) == int(Material.DEEP_WATER)
    assert int(west.materials[8, 15]) == int(Material.DEEP_WATER)
    assert int(east.materials[8, 0]) == int(Material.DEEP_WATER)


def test_journal_preserves_water_and_restores_explicit_passages() -> None:
    source = InMemoryPromiseSource(
        [RegionalPromise(SurfaceFeatureKind.SPRING, 8, 8)], chunk_size=16
    )
    materializer = SurfaceMaterializer(
        source, world_seed=91, chunk_size=16, debris_fraction=0.0
    )
    chunk = materializer.materialize_chunk(0, 0)
    game_map = GameMap(width=16, height=16)
    apply_materialized_chunk(game_map, chunk)
    metadata = ensure_surface_metadata(game_map)
    before = (
        int(metadata.material_grid[8, 8]),
        int(metadata.traversal_class_grid[8, 8]),
        float(metadata.movement_cost_grid[8, 8]),
    )
    journal = SaveDiffJournal(0, 0)
    for new_tile in (TILE_ID_FLOOR, TILE_ID_WALL, TILE_ID_FLOOR):
        journal.record_tile_mutation(8, 8, new_tile)
        journal.apply_tile_mutations(game_map)
    assert before == (
        int(metadata.material_grid[8, 8]),
        int(metadata.traversal_class_grid[8, 8]),
        float(metadata.movement_cost_grid[8, 8]),
    )

    # A deliberately opened *generated* wall requires semantic overrides.
    metadata.traversal_class_grid[2, 2] = int(TraversalClass.BLOCKED)
    game_map.tiles[2, 2] = TILE_ID_WALL
    journal.record_tile_mutation(
        2,
        2,
        TILE_ID_FLOOR,
        material=int(Material.DOOR_OPEN),
        traversal=int(TraversalClass.NORMAL),
        movement_cost=1.0,
    )
    journal.apply_tile_mutations(game_map)
    assert SurfaceContext(game_map).can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 2, 2)
    with tempfile.TemporaryDirectory() as directory:
        journal.write_atomic(directory)
        reloaded = SaveDiffJournal.load_or_create(directory, 0, 0)
        assert reloaded.tile_metadata[(2, 2)]["material"] == int(Material.DOOR_OPEN)


def _build_two_chunk_world(
    directory: str, *, reverse: bool
) -> tuple[dict[str, int], dict[str, int]]:
    """Exercise the whole loading lifecycle against the production ECS."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(SurfaceFeatureKind.SPRING, 8, 8),
            RegionalPromise(SurfaceFeatureKind.SPRING, 24, 8),
        ],
        chunk_size=16,
    )
    materializer = SurfaceMaterializer(
        source, world_seed="travel", chunk_size=16, debris_fraction=0.0
    )
    chunks = {
        0: materializer.materialize_chunk(0, 0),
        1: materializer.materialize_chunk(1, 0),
    }
    game_map = GameMap(width=32, height=16)
    for chunk in chunks.values():
        apply_materialized_chunk(game_map, chunk)
    context = SurfaceContext(game_map)
    registry = EntityRegistry()
    registry.ensure_occupancy_shape(32, 16)
    player = registry.create_entity(
        x=1, y=1, glyph=64, color_fg=(1, 2, 3), name="player"
    )
    store = EntityRegistryActorStore(registry)
    ledger = SurfaceIdentityLedger.load_or_create(directory)
    planner = SurfacePopulationPlanner(
        store,
        context,
        world_seed="travel",
        identity_ledger=ledger,
        min_per_anchor=2,
        max_per_anchor=2,
    )
    journals = {cx: SaveDiffJournal(cx, 0) for cx in chunks}
    order = (1, 0) if reverse else (0, 1)
    for cx in order:
        assert len(planner.populate_chunk(chunks[cx], journals[cx])) == 2
    births = {
        key: value
        for journal in journals.values()
        for key, value in journal.population_births.items()
    }
    assert len(births) == 4
    for actor_id in births.values():
        pos = registry.get_position(actor_id)
        assert pos is not None
        assert registry.get_blocking_entity_at(pos.x, pos.y) == actor_id

    manager = ChunkHydrationManager(store, context=context, chunk_size=16)
    for cx in order:
        assert len(manager.dehydrate_chunk_entities(journals[cx], cx, 0)) == 2
        journals[cx].write_atomic(directory)
    assert _position(registry, player).x == 1
    assert store.active_actor_ids() == [player]

    # Destroy and regenerate the viewport while journal records hold actors.
    replacement = GameMap(width=32, height=16)
    for chunk in chunks.values():
        apply_materialized_chunk(replacement, chunk)
    replacement_context = SurfaceContext(replacement)
    revisiting = SurfacePopulationPlanner(
        store,
        replacement_context,
        world_seed="travel",
        identity_ledger=SurfaceIdentityLedger.load_or_create(directory),
        min_per_anchor=2,
        max_per_anchor=2,
    )
    manager = ChunkHydrationManager(store, context=replacement_context, chunk_size=16)
    loaded = {cx: SaveDiffJournal.load_or_create(directory, cx, 0) for cx in chunks}
    loaded[0].record_tile_mutation(5, 5, TILE_ID_WALL)
    assert loaded[0].apply_tile_mutations(replacement) == 1
    assert not replacement_context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 5, 5)
    for cx in reversed(order):
        assert revisiting.populate_chunk(chunks[cx], loaded[cx]) == []
        assert len(manager.hydrate_chunk_entities(loaded[cx], cx, 0)) == 2
    assert _position(registry, player).x == 1
    assert len(set(store.active_actor_ids())) == 5
    for birth_key, actor_id in births.items():
        assert store.snapshot_actor(actor_id)["birth_key"] == birth_key
        position = registry.get_position(actor_id)
        assert position is not None
        assert registry.get_blocking_entity_at(position.x, position.y) == actor_id

    run_surface_turn(store, replacement_context, 2)
    assert _position(registry, player).x == 1

    # A permanent death must not cause the original NPC to be respawned.
    dead_key, dead_id = next(iter(loaded[0].population_births.items()))
    assert registry.delete_entity(dead_id)
    loaded[0].mark_population_death(dead_key)
    loaded[0].write_atomic(directory)
    assert revisiting.populate_chunk(chunks[0], loaded[0]) == []
    assert not registry._store.has_active(dead_id)
    return births, {
        str(cx): int(journal.population_initialized) for cx, journal in loaded.items()
    }


def test_multichunk_revisit_identity_independent_of_load_order() -> None:
    with tempfile.TemporaryDirectory() as first:
        births_one, markers_one = _build_two_chunk_world(first, reverse=False)
    with tempfile.TemporaryDirectory() as second:
        births_two, markers_two = _build_two_chunk_world(second, reverse=True)
    assert births_one == births_two
    assert markers_one == markers_two == {"0": 1, "1": 1}
