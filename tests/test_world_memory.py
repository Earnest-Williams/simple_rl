from __future__ import annotations

import numpy as np
import numpy.typing as npt
import pytest

from engine.render_base_layers import prepare_base_layers
from game.game_state import GameState
from game.world.game_map import GameMap
from game.world.memory import update_memory_fade


def test_game_map_owns_tile_shaped_memory_arrays() -> None:
    game_map: GameMap = GameMap(4, 3)
    expected_shape: tuple[int, int] = (3, 4)

    assert game_map.memory_intensity.shape == expected_shape
    assert game_map.memory_strength.shape == expected_shape
    assert game_map.last_seen_time.shape == expected_shape
    assert game_map.memory_fade_mask.shape == expected_shape
    assert game_map.prev_visible.shape == expected_shape
    assert game_map.tile_memory_modifiers.shape == expected_shape


def test_update_memory_fade_tracks_newly_hidden_tiles() -> None:
    last_seen_time: npt.NDArray[np.int32] = np.zeros((2, 2), dtype=np.int32)
    memory_intensity: npt.NDArray[np.float32] = np.zeros((2, 2), dtype=np.float32)
    visible: npt.NDArray[np.bool_] = np.zeros((2, 2), dtype=np.bool_)
    needs_update_mask: npt.NDArray[np.bool_] = np.zeros((2, 2), dtype=np.bool_)
    prev_visible: npt.NDArray[np.bool_] = np.zeros((2, 2), dtype=np.bool_)
    memory_strength: npt.NDArray[np.float32] = np.zeros((2, 2), dtype=np.float32)
    tile_modifiers: npt.NDArray[np.float32] = np.ones((2, 2), dtype=np.float32)

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


def test_compute_fov_only_updates_visible_and_explored() -> None:
    game_map: GameMap = GameMap(5, 5)
    game_map.create_test_room()
    game_map.memory_intensity[:] = 0.25
    game_map.memory_strength[:] = 2.0
    game_map.last_seen_time[:] = 7
    expected_memory_intensity: npt.NDArray[np.float32] = (
        game_map.memory_intensity.copy()
    )
    expected_memory_strength: npt.NDArray[np.float32] = game_map.memory_strength.copy()
    expected_last_seen_time: npt.NDArray[np.int32] = game_map.last_seen_time.copy()

    game_map.compute_fov(2, 2, 2)

    np.testing.assert_array_equal(game_map.memory_intensity, expected_memory_intensity)
    np.testing.assert_array_equal(game_map.memory_strength, expected_memory_strength)
    np.testing.assert_array_equal(game_map.last_seen_time, expected_last_seen_time)
    assert np.any(game_map.visible)
    assert np.any(game_map.explored)


def test_refresh_visible_memory_updates_only_visible_tiles() -> None:
    game_map: GameMap = GameMap(3, 2)
    game_map.visible[0, 0] = True
    game_map.visible[1, 2] = True
    game_map.memory_intensity[:] = 0.25
    game_map.last_seen_time[:] = 3
    game_map.memory_strength[:] = 4.5

    game_map.refresh_visible_memory(11)

    assert game_map.memory_intensity[0, 0] == 1.0
    assert game_map.memory_intensity[1, 2] == 1.0
    assert game_map.memory_intensity[0, 1] == 0.25
    assert game_map.last_seen_time[0, 0] == 11
    assert game_map.last_seen_time[1, 2] == 11
    assert game_map.last_seen_time[0, 1] == 3
    assert game_map.memory_strength[0, 0] == 5.0
    assert game_map.memory_strength[1, 2] == 5.0
    assert game_map.memory_strength[0, 1] == 3.5


def _make_memory_state(memory_fade_enabled: bool = True) -> GameState:
    game_map = GameMap(5, 5)
    game_map.create_test_room()
    return GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=3,
        item_templates={},
        memory_fade_config={"enabled": memory_fade_enabled},
        enable_sound=False,
        enable_ai=False,
    )


def test_game_state_update_fov_owns_turn_memory_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = _make_memory_state()
    events: list[str] = []

    def compute_fov_spy(x: int, y: int, radius: int) -> None:
        events.append("compute")
        state.game_map.visible.fill(False)

    def refresh_visible_memory_spy(current_time: int) -> None:
        events.append("refresh")
        assert current_time == state.turn_count
        assert state.game_map.visible[2, 2]
        assert state.game_map.explored[2, 2]

    def fade_memory_spy(current_time: int, steepness: float, midpoint: float) -> None:
        events.append("fade")
        assert current_time == state.turn_count
        assert steepness == state.memory_fade_steepness
        assert midpoint == state.memory_fade_midpoint

    original_sync = state._sync_player_light_source

    def sync_player_light_source_spy(px: int, py: int) -> None:
        events.append("sync")
        original_sync(px, py)

    def flush_message_queue_spy() -> None:
        events.append("flush")

    monkeypatch.setattr(state.game_map, "compute_fov", compute_fov_spy)
    monkeypatch.setattr(
        state.game_map,
        "refresh_visible_memory",
        refresh_visible_memory_spy,
    )
    monkeypatch.setattr(state.game_map, "fade_memory", fade_memory_spy)
    monkeypatch.setattr(
        state, "_sync_player_light_source", sync_player_light_source_spy
    )
    monkeypatch.setattr(state, "flush_message_queue", flush_message_queue_spy)

    state.update_fov()

    assert events == ["compute", "refresh", "fade", "sync", "flush"]
    assert state.light_sources[state.player_light_index].x == 2
    assert state.light_sources[state.player_light_index].y == 2


def test_prepare_base_layers_returns_read_only_memory_snapshots() -> None:
    game_map = GameMap(4, 4)
    game_map.visible[1, 1] = True
    game_map.explored[1, 1] = True
    game_map.memory_intensity[1, 1] = 0.5
    max_tile_id = int(game_map.tiles.max())
    tile_fg_colors = np.full((max_tile_id + 1, 3), 200, dtype=np.uint8)
    tile_bg_colors = np.full((max_tile_id + 1, 3), 20, dtype=np.uint8)
    tile_indices_render = np.arange(max_tile_id + 1, dtype=np.uint16)

    result = prepare_base_layers(
        game_map=game_map,
        viewport_x=0,
        viewport_y=0,
        viewport_width=4,
        viewport_height=4,
        max_defined_tile_id=max_tile_id,
        tile_fg_colors=tile_fg_colors,
        tile_bg_colors=tile_bg_colors,
        tile_indices_render=tile_indices_render,
    )
    visible_snapshot = result[3]
    map_visible_snapshot = result[6]
    memory_snapshot = result[7]
    tiles_snapshot = result[8]

    assert not visible_snapshot.flags.writeable
    assert not map_visible_snapshot.flags.writeable
    assert not memory_snapshot.flags.writeable
    assert not tiles_snapshot.flags.writeable
    with pytest.raises(ValueError, match="read-only"):
        visible_snapshot[1, 1] = False
    with pytest.raises(ValueError, match="read-only"):
        memory_snapshot[1, 1] = 0.0

    assert game_map.visible[1, 1]
    assert game_map.memory_intensity[1, 1] == 0.5
    assert game_map.last_seen_time[1, 1] == 0
    assert game_map.memory_strength[1, 1] == 0.0
    assert not game_map.memory_fade_mask[1, 1]
    assert not game_map.prev_visible[1, 1]


def test_game_state_memory_traits_update() -> None:
    """Verify that GameState updates memory_traits from player status effects and intelligence."""
    state = _make_memory_state()

    # Set player intelligence and add some status effects
    state.entity_registry.set_entity_component(state.player_id, "intelligence", 15)
    state.entity_registry.set_entity_component(
        state.player_id,
        "status_effects",
        [
            {"id": "confusion", "duration": 5, "intensity": 1.0},
            {"id": "fatigue", "duration": 10, "intensity": 0.5},
        ],
    )

    # Trigger update_fov which runs memory traits updates
    state.update_fov()

    # Check that traits were resolved correctly
    traits = state.memory_traits
    assert traits.intelligence == 15
    assert traits.has_confusion is True
    assert traits.has_illness is False
    assert traits.fatigue_level == 0.5
