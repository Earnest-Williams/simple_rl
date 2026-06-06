"""Tests for the lighting/FOV ambient spill post-pass."""

import numpy as np

from tools.lighting_fov_tool.ambient_spill import (
    AmbientSpillLight,
    compute_ambient_spill_rgb,
)
from tools.lighting_fov_tool.exporter import export_configuration, load_configuration
from tools.lighting_fov_tool.scene import LightSourceDef
from tools.lighting_fov_tool.tile_config import TileConfigState


def _spill_light(
    *,
    color: tuple[int, int, int] = (100, 80, 60),
    reach_mask: np.ndarray,
    enabled: bool = True,
    extra_radius: int = 2,
    strength: float = 0.5,
    decay: float = 0.5,
    max_rgb: float = 255.0,
) -> AmbientSpillLight:
    return AmbientSpillLight(
        color=color,
        reach_mask=reach_mask,
        shape_mask=reach_mask.astype(np.float32),
        visibility_out=reach_mask.astype(np.float32),
        enabled=enabled,
        extra_radius=extra_radius,
        strength=strength,
        decay=decay,
        max_rgb=max_rgb,
    )


def test_spill_does_not_cross_walls() -> None:
    opaque_grid = np.zeros((5, 5), dtype=bool)
    opaque_grid[:, 2] = True
    player_visible = np.ones((5, 5), dtype=bool)
    reach_mask = np.zeros((5, 5), dtype=bool)
    reach_mask[2, 1] = True

    spill = compute_ambient_spill_rgb(
        [_spill_light(reach_mask=reach_mask, extra_radius=3)],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )

    assert np.any(spill[:, :2] > 0.0)
    assert np.all(spill[:, 3:] == 0.0)


def test_spill_reaches_walkable_cells_beyond_direct_radius() -> None:
    opaque_grid = np.zeros((1, 5), dtype=bool)
    player_visible = np.ones((1, 5), dtype=bool)
    reach_mask = np.zeros((1, 5), dtype=bool)
    reach_mask[0, 1] = True

    spill = compute_ambient_spill_rgb(
        [_spill_light(reach_mask=reach_mask, extra_radius=2)],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )

    assert np.all(spill[0, 1] == 0.0)
    assert spill[0, 2, 0] > 0.0
    assert spill[0, 3, 0] > 0.0
    assert np.all(spill[0, 4] == 0.0)


def test_spill_is_zero_when_per_light_disabled() -> None:
    opaque_grid = np.zeros((1, 3), dtype=bool)
    player_visible = np.ones((1, 3), dtype=bool)
    reach_mask = np.zeros((1, 3), dtype=bool)
    reach_mask[0, 1] = True

    spill = compute_ambient_spill_rgb(
        [_spill_light(reach_mask=reach_mask, enabled=False)],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )

    assert np.all(spill == 0.0)


def test_spill_is_zero_when_globally_disabled() -> None:
    opaque_grid = np.zeros((1, 3), dtype=bool)
    player_visible = np.ones((1, 3), dtype=bool)
    reach_mask = np.zeros((1, 3), dtype=bool)
    reach_mask[0, 1] = True

    spill = compute_ambient_spill_rgb(
        [_spill_light(reach_mask=reach_mask)],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=False,
    )

    assert np.all(spill == 0.0)


def test_spill_is_clipped_to_player_visible_unless_showing_full_field() -> None:
    opaque_grid = np.zeros((1, 3), dtype=bool)
    player_visible = np.array([[True, True, False]])
    reach_mask = np.zeros((1, 3), dtype=bool)
    reach_mask[0, 1] = True
    light = _spill_light(reach_mask=reach_mask, extra_radius=1)

    clipped = compute_ambient_spill_rgb(
        [light],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )
    full_field = compute_ambient_spill_rgb(
        [light],
        opaque_grid,
        player_visible,
        show_full_light_field=True,
        enabled=True,
    )

    assert clipped[0, 0, 0] > 0.0
    assert np.all(clipped[0, 2] == 0.0)
    assert full_field[0, 2, 0] > 0.0


def test_spill_max_rgb_clamps_contribution() -> None:
    opaque_grid = np.zeros((1, 3), dtype=bool)
    player_visible = np.ones((1, 3), dtype=bool)
    reach_mask = np.zeros((1, 3), dtype=bool)
    reach_mask[0, 1] = True

    spill = compute_ambient_spill_rgb(
        [
            _spill_light(
                color=(255, 255, 255),
                reach_mask=reach_mask,
                extra_radius=1,
                strength=1.0,
                decay=1.0,
                max_rgb=10.0,
            )
        ],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )

    assert np.array_equal(spill[0, 0], np.array([10.0, 10.0, 10.0]))
    assert np.array_equal(spill[0, 2], np.array([10.0, 10.0, 10.0]))


def test_spill_does_not_mutate_reach_mask_or_player_visible() -> None:
    opaque_grid = np.zeros((3, 3), dtype=bool)
    player_visible = np.ones((3, 3), dtype=bool)
    player_visible[0, 0] = False
    reach_mask = np.zeros((3, 3), dtype=bool)
    reach_mask[1, 1] = True
    original_reach = reach_mask.copy()
    original_visible = player_visible.copy()

    compute_ambient_spill_rgb(
        [_spill_light(reach_mask=reach_mask, extra_radius=1)],
        opaque_grid,
        player_visible,
        show_full_light_field=False,
        enabled=True,
    )

    assert np.array_equal(reach_mask, original_reach)
    assert np.array_equal(player_visible, original_visible)


def test_ambient_spill_config_exports_and_loads(tmp_path) -> None:
    light_source = LightSourceDef(
        name="test_light",
        x=1,
        y=1,
        radius=4,
        color=(10, 20, 30),
        intensity=0.4,
    )
    config_state = TileConfigState()
    config_state.initialize_defaults([light_source])
    config_state.ambient_spill_enabled = False
    config_state.ambient_spill_debug_show_only = True

    config_state.set_light_ambient_spill_enabled("test_light", False)
    config_state.set_light_ambient_spill_extra_radius("test_light", 6)
    config_state.set_light_ambient_spill_strength("test_light", 0.42)
    config_state.set_light_ambient_spill_decay("test_light", 0.33)
    config_state.set_light_ambient_spill_max_rgb("test_light", 44.0)

    config_path = tmp_path / "lighting_config.txt"
    export_configuration(config_state, config_path)

    text = config_path.read_text(encoding="utf-8")
    assert "[tool.render]" in text
    assert "ambient_spill_debug_show_only = True" in text
    assert "ambient_spill_extra_radius = 6" in text

    loaded_state = TileConfigState()
    loaded_state.initialize_defaults([light_source])
    load_configuration(loaded_state, config_path)

    loaded_light = loaded_state.lights["test_light"]
    assert loaded_state.ambient_spill_enabled is False
    assert loaded_state.ambient_spill_debug_show_only is True
    assert loaded_light.ambient_spill_enabled is False
    assert loaded_light.ambient_spill_extra_radius == 6
    assert loaded_light.ambient_spill_strength == 0.42
    assert loaded_light.ambient_spill_decay == 0.33
    assert loaded_light.ambient_spill_max_rgb == 44.0
