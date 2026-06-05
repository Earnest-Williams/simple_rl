from __future__ import annotations

import polars as pl

from game.game_state import GameState
from game.systems.movement_system import try_move
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from pathfinding.perception_systems import FlowType


def _make_bent_corridor_state() -> tuple[GameState, int]:
    game_map = GameMap(28, 8)
    game_map.tiles.fill(TILE_ID_WALL)

    for x in range(10, 23):
        game_map.tiles[5, x] = TILE_ID_FLOOR
    for y in range(1, 6):
        game_map.tiles[y, 10] = TILE_ID_FLOOR

    game_map.update_tile_transparency()

    state = GameState(
        existing_map=game_map,
        player_start_pos=(10, 5),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=15,
        item_templates={},
        rng_seed=7,
        enable_sound=False,
        enable_ai=True,
    )
    state.entity_registry.set_entity_component(state.player_id, "faction", "heroes")

    monster_id = state.entity_registry.create_entity(
        x=22,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Hunter",
        ai_type="goap",
        species="enemy",
        faction="monsters",
    )

    state.entity_registry.entities_df = state.entity_registry.entities_df.with_columns(
        pl.when(pl.col("entity_id") == monster_id)
        .then(pl.lit(500))
        .otherwise(pl.lit(10))
        .alias("perception_stat")
    )
    return state, monster_id


def test_advance_turn_investigates_noise_then_preserves_memory_until_expiry(
    monkeypatch,
) -> None:
    state, monster_id = _make_bent_corridor_state()
    monkeypatch.setattr(state.community_manager, "step", lambda: None)

    state.advance_turn()

    first_pos = state.entity_registry.get_position(monster_id)
    assert first_pos is not None
    assert (first_pos.x, first_pos.y) == (21, 5)
    assert state.ai_memory[monster_id].pos == (10, 5)
    assert state.ai_memory[monster_id].source == "visual"

    assert try_move(state.player_id, 0, -1, state)

    state.advance_turn()

    investigate_pos = state.entity_registry.get_position(monster_id)
    assert investigate_pos is not None
    assert (investigate_pos.x, investigate_pos.y) == (20, 5)
    assert tuple(state.perception_flow_centers[int(FlowType.REAL_NOISE)]) == (4, 10)
    assert state.game_map.noise_map[4, 10] == 10.0
    assert state.perception_noise_source_id == state.player_id
    assert state.noise_events

    remembered = state.ai_memory[monster_id]
    assert remembered.pos == (10, 4)
    assert remembered.source == "audio"
    assert remembered.expires_at_turn == 7

    for expected_turn, expected_x in ((3, 19), (4, 18), (5, 17), (6, 16)):
        state.advance_turn()

        pos = state.entity_registry.get_position(monster_id)
        assert pos is not None
        assert (pos.x, pos.y) == (expected_x, 5)

        memory = state.ai_memory[monster_id]
        assert memory.pos == (10, 4)
        assert memory.source == "audio"
        assert memory.expires_at_turn == 7
        assert state.perception_noise_source_id == monster_id
        assert state.turn_count == expected_turn

    state.advance_turn()

    assert state.turn_count == 7
    assert monster_id not in state.ai_memory
