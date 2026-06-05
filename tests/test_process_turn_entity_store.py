from __future__ import annotations

import pytest
import numpy as np
import polars as pl

from game.game_state import GameState
from game.world.game_map import GameMap, TILE_ID_FLOOR


def _make_state() -> GameState:
    game_map = GameMap(width=10, height=10)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()

    return GameState(
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


def test_process_turn_does_not_materialize_entities_df(monkeypatch) -> None:
    state = _make_state()
    state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    def fail_entities_df() -> object:
        raise AssertionError("process_turn must not materialize entities_df")

    monkeypatch.setattr(
        type(state.entity_registry),
        "entities_df",
        property(lambda self: fail_entities_df()),
    )

    active_ids, ai_ids = state.process_turn()

    assert active_ids
    assert ai_ids


def test_process_turn_populates_spatial_index_from_store() -> None:
    state = _make_state()
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    state.process_turn()

    assert state.spatial_index.query_radius((4, 5), radius=0, kind="enemy") == [
        (enemy_id, 4, 5)
    ]


def test_process_turn_returns_ai_entity_ids() -> None:
    state = _make_state()
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
        faction="monsters",
    )

    _active_ids, ai_ids = state.process_turn()

    assert enemy_id in ai_ids
