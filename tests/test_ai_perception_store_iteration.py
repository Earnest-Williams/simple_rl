from __future__ import annotations

import pytest
import numpy as np
import polars as pl

from game.ai.perception import (
    PerceptionFact,
    PerceptionSnapshot,
    apply_perception_memory_updates,
    gather_perception_snapshot,
)
from game.game_state import GameState
from game.world.game_map import TILE_ID_FLOOR, GameMap
from pathfinding.perception_systems import FlowType


def _make_game_state() -> GameState:
    game_map = GameMap(8, 8)
    game_map.tiles.fill(TILE_ID_FLOOR)
    game_map.update_tile_transparency()
    return GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=8,
        item_templates={},
        enable_sound=False,
        enable_ai=False,
    )


def test_gather_perception_snapshot_does_not_materialize_entities_df(monkeypatch) -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=2,
        y=2,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Hunter",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    game_state.entity_registry.create_entity(
        x=4,
        y=2,
        glyph=64,
        color_fg=(255, 255, 255),
        name="Target",
        faction="heroes",
    )
    game_state.update_fov()
    game_state.game_map.visible[:] = True

    # Patch to_polars on EntityStore to raise an error if called
    monkeypatch.setattr(
        game_state.entity_registry._store,
        "to_polars",
        lambda: (_ for _ in ()).throw(
            AssertionError("perception must not materialize entities_df")
        ),
    )

    # Trigger perception updates
    game_state.update_perception_fields()
    snapshot = gather_perception_snapshot(game_state)

    assert actor_id in snapshot.entity_facts


def test_visible_enemy_detection_uses_store_and_spatial_index() -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=2,
        y=2,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Hunter",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    # Target 1 (enemy faction, visible)
    target1_id = game_state.entity_registry.create_entity(
        x=3,
        y=2,
        glyph=64,
        color_fg=(255, 255, 255),
        name="Target 1",
        faction="heroes",
    )
    # Target 2 (same faction, visible, should be ignored)
    game_state.entity_registry.create_entity(
        x=2,
        y=3,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Ally 1",
        faction="monsters",
    )
    # Target 3 (enemy faction, invisible because of LOS map)
    game_state.entity_registry.create_entity(
        x=7,
        y=7,
        glyph=64,
        color_fg=(255, 255, 255),
        name="Target 3",
        faction="heroes",
    )

    # Initialize spatial index
    game_state.spatial_index.clear()
    registry = game_state.entity_registry
    for idx in registry.active_indices():
        eid = registry.entity_id_at(idx)
        x, y = registry.position_at(idx)
        game_state.spatial_index.insert(eid, x, y, registry.kind_at(idx))

    game_state.update_fov()
    # Mock player's FOV (the los_map parameter in gather_perception_snapshot is derived from FOV)
    los_map = np.zeros((8, 8), dtype=bool)
    los_map[2, 3] = True  # make (3, 2) visible (y, x order)

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]

    assert len(fact.visible_targets) == 1
    assert fact.visible_targets[0]["entity_id"] == target1_id


def test_visual_audio_scent_memory_priority_survives_store_iteration() -> None:
    # Test prioritizations in new perception snapshot loop
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=3,
        y=3,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Tracker",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    
    # Target (enemy) is at (5, 3) (visible)
    target_id = game_state.entity_registry.create_entity(
        x=5,
        y=3,
        glyph=64,
        color_fg=(255, 255, 255),
        name="Target",
        faction="heroes",
    )

    # Populate spatial index
    game_state.spatial_index.clear()
    registry = game_state.entity_registry
    for idx in registry.active_indices():
        eid = registry.entity_id_at(idx)
        x, y = registry.position_at(idx)
        game_state.spatial_index.insert(eid, x, y, registry.kind_at(idx))

    game_state.update_fov()
    game_state.game_map.visible[:] = True

    # 1. Visual wins
    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]
    assert fact.signal_type == "visual"
    assert fact.last_known_position == (5, 3)

    # 2. Audio wins if no visual
    # Move target out of visual range or make it invisible
    game_state.game_map.visible[:] = False
    flow_idx = int(FlowType.REAL_NOISE)
    game_state.perception_flow_centers[flow_idx, 0] = 4
    game_state.perception_flow_centers[flow_idx, 1] = 4
    game_state.perception_alerted_monster_ids = [actor_id]

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]
    assert fact.signal_type == "audio"
    assert fact.last_known_position == (4, 4)

    # 3. Scent wins if no visual/audio
    game_state.perception_alerted_monster_ids = []
    game_state.perception_cave_when[3, 3] = 1
    game_state.perception_cave_when[3, 4] = 10  # scent at (4, 3) (y, x)

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]
    assert fact.signal_type == "scent"
    assert fact.last_known_position is None
