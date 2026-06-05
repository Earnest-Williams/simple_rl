from __future__ import annotations

import pytest
import numpy as np

from game.entities.components import Position
from game.entities.registry import EntityRegistry
from game.entities.store import EntityStore
from game.game_state import GameState
from game.world.game_map import GameMap, TILE_ID_FLOOR, TILE_ID_WALL
from game.systems.movement_system import try_move


def test_try_move_entity_updates_position_and_occupancy() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity_id = 1
    store.create_entity(
        entity_id=entity_id,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Blocker",
        blocks_movement=True,
    )

    # Move to (3, 2)
    success, dest_x, dest_y = store.try_move_entity(
        entity_id=entity_id,
        dx=1,
        dy=0,
        width=10,
        height=10,
        is_walkable=lambda x, y: True,
    )

    assert success
    assert dest_x == 3
    assert dest_y == 2
    assert store.get_position(entity_id) == Position(3, 2)

    # Check occupancy grid updates
    assert store.get_blocking_entity_at(2, 2) is None
    assert store.get_blocking_entity_at(3, 2) == entity_id


def test_try_move_entity_rejects_blocked_destination() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity1 = 1
    store.create_entity(
        entity_id=entity1,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Blocker 1",
        blocks_movement=True,
    )

    entity2 = 2
    store.create_entity(
        entity_id=entity2,
        x=3,
        y=2,
        glyph=2,
        color_fg=(255, 0, 0),
        name="Blocker 2",
        blocks_movement=True,
    )

    # Try to move entity1 to (3, 2), which is occupied by entity2
    success, dest_x, dest_y = store.try_move_entity(
        entity_id=entity1,
        dx=1,
        dy=0,
        width=10,
        height=10,
        is_walkable=lambda x, y: True,
    )

    assert not success
    assert store.get_position(entity1) == Position(2, 2)
    assert store.get_blocking_entity_at(2, 2) == entity1
    assert store.get_blocking_entity_at(3, 2) == entity2


def test_try_move_entity_rejects_unwalkable_tile() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity_id = 1
    store.create_entity(
        entity_id=entity_id,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Walker",
    )

    # Attempt to move to an unwalkable tile
    success, _, _ = store.try_move_entity(
        entity_id=entity_id,
        dx=0,
        dy=1,
        width=10,
        height=10,
        is_walkable=lambda x, y: False,
    )

    assert not success
    assert store.get_position(entity_id) == Position(2, 2)


def test_try_move_entity_allows_nonblocking_entity_overlap() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity1 = 1
    store.create_entity(
        entity_id=entity1,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Non-Blocker",
        blocks_movement=False,
    )

    entity2 = 2
    store.create_entity(
        entity_id=entity2,
        x=3,
        y=2,
        glyph=2,
        color_fg=(255, 0, 0),
        name="Blocker",
        blocks_movement=True,
    )

    # Try to move non-blocking entity1 to (3, 2), which is occupied by entity2.
    # Non-blocking entity should be allowed to overlap.
    success, dest_x, dest_y = store.try_move_entity(
        entity_id=entity1,
        dx=1,
        dy=0,
        width=10,
        height=10,
        is_walkable=lambda x, y: True,
    )

    assert success
    assert dest_x == 3
    assert dest_y == 2
    assert store.get_position(entity1) == Position(3, 2)
    # The blocking entity should still dominate the occupancy grid at (3, 2)
    assert store.get_blocking_entity_at(3, 2) == entity2


def test_set_position_updates_occupancy_for_teleport() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity_id = 1
    store.create_entity(
        entity_id=entity_id,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Teleporter",
        blocks_movement=True,
    )

    assert store.get_blocking_entity_at(2, 2) == entity_id

    # Teleport to (8, 8) using set_position
    success = store.set_position(entity_id, Position(8, 8))
    assert success
    assert store.get_position(entity_id) == Position(8, 8)
    assert store.get_blocking_entity_at(2, 2) is None
    assert store.get_blocking_entity_at(8, 8) == entity_id


def test_delete_entity_clears_occupancy() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity_id = 1
    store.create_entity(
        entity_id=entity_id,
        x=2,
        y=2,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Deletable Blocker",
        blocks_movement=True,
    )

    assert store.get_blocking_entity_at(2, 2) == entity_id

    # Delete entity
    success = store.delete_entity(entity_id)
    assert success
    assert store.get_blocking_entity_at(2, 2) is None


def test_create_entity_updates_occupancy_after_grid_initialized() -> None:
    store = EntityStore()
    store.ensure_occupancy_shape(10, 10)

    entity_id = 1
    store.create_entity(
        entity_id=entity_id,
        x=3,
        y=3,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Late Creator",
        blocks_movement=True,
    )

    # It should automatically occupy the grid
    assert store.get_blocking_entity_at(3, 3) == entity_id


def test_try_move_emits_noise_after_fast_registry_move() -> None:
    game_map = GameMap(width=10, height=10)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()

    state = GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=42,
        enable_sound=False,
        enable_ai=False,
    )

    entity_id = state.player_id
    new_x, new_y = 3, 2

    # Move Player (dx=1, dy=0)
    moved = try_move(entity_id, 1, 0, state)

    assert moved
    assert state.entity_registry.get_position(entity_id) == Position(new_x, new_y)
    assert state.entity_registry.get_blocking_entity_at(new_x, new_y) == entity_id
    assert state.noise_events[-1].source_id == entity_id
    assert state.noise_events[-1].x == new_x
    assert state.noise_events[-1].y == new_y
