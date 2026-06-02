from __future__ import annotations

import numpy as np

from game.world.game_map import GameMap
from game.world.memory import update_memory_fade


def test_game_map_owns_tile_shaped_memory_arrays() -> None:
    game_map = GameMap(4, 3)
    expected_shape = (3, 4)

    assert game_map.memory_intensity.shape == expected_shape
    assert game_map.memory_strength.shape == expected_shape
    assert game_map.last_seen_time.shape == expected_shape
    assert game_map.memory_fade_mask.shape == expected_shape
    assert game_map.prev_visible.shape == expected_shape
    assert game_map.tile_memory_modifiers.shape == expected_shape


def test_update_memory_fade_tracks_newly_hidden_tiles() -> None:
    last_seen_time = np.zeros((2, 2), dtype=np.int32)
    memory_intensity = np.zeros((2, 2), dtype=np.float32)
    visible = np.zeros((2, 2), dtype=np.bool_)
    needs_update_mask = np.zeros((2, 2), dtype=np.bool_)
    prev_visible = np.zeros((2, 2), dtype=np.bool_)
    memory_strength = np.zeros((2, 2), dtype=np.float32)
    tile_modifiers = np.ones((2, 2), dtype=np.float32)

    memory_intensity[0, 0] = 1.0
    last_seen_time[0, 0] = 0
    prev_visible[0, 0] = True

    update_memory_fade(
        10,
        last_seen_time=last_seen_time,
        memory_intensity=memory_intensity,
        visible=visible,
        needs_update_mask=needs_update_mask,
        prev_visible=prev_visible,
        memory_strength=memory_strength,
        tile_modifiers=tile_modifiers,
        steepness=1.0,
        midpoint=5.0,
    )

    assert needs_update_mask[0, 0]
    assert not prev_visible[0, 0]
    assert 0.0 < memory_intensity[0, 0] < 1.0
    assert memory_intensity[1, 1] == 0.0
