"""Advanced lighting tests for cones, softness, height, and channels.

Conforms to Phase 2 requirements of the retire lights_dev plan.
"""

from __future__ import annotations

import math
import numpy as np

from engine.render_lighting import (
    _compute_single_light_contribution,
    collapse_premult_rgba_to_rgb,
)
from game.world.game_map import LightSource


def test_directional_cone_constraints() -> None:
    """Test that directional cone angles constrain the FOV and lighting."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)

    # Place a light at center, facing East (direction = 0.0) with a 90 degree cone (pi/2)
    light = LightSource(
        x=7,
        y=7,
        radius=5,
        color=(255, 255, 255),
        intensity=1.0,
        direction=0.0,
        cone_angle=math.pi / 2,
        cone_softness=0.0,
        channels=0xFFFFFFFF,
        id=1,
        height=0.0,
    )

    contribution = _compute_single_light_contribution(
        origin_x=light.x,
        origin_y=light.y,
        radius=light.radius,
        color_rgb=light.color,
        intensity=light.intensity,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        direction=light.direction,
        cone_angle=light.cone_angle,
        cone_softness=light.cone_softness,
        channels=light.channels,
        height=light.height,
    )
    rgb = collapse_premult_rgba_to_rgb(contribution)

    # Check that cells directly to the West (e.g. at x=3, y=7) are not lit (rgb = 0)
    assert np.all(rgb[7, 3] == 0.0)
    # Check that cells to the East (e.g. at x=10, y=7) are lit (rgb > 0)
    assert np.any(rgb[7, 10] > 0.0)


def test_directional_cone_softness() -> None:
    """Test that cone softness results in a gradient of light attenuation."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)

    # Light facing East, 90 deg cone, with full softness (1.0)
    light = LightSource(
        x=7,
        y=7,
        radius=5,
        color=(255, 255, 255),
        intensity=1.0,
        direction=0.0,
        cone_angle=math.pi / 2,
        cone_softness=1.0,
        channels=0xFFFFFFFF,
        id=1,
        height=0.0,
    )

    contribution = _compute_single_light_contribution(
        origin_x=light.x,
        origin_y=light.y,
        radius=light.radius,
        color_rgb=light.color,
        intensity=light.intensity,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        direction=light.direction,
        cone_angle=light.cone_angle,
        cone_softness=light.cone_softness,
        channels=light.channels,
        height=light.height,
    )
    rgb = collapse_premult_rgba_to_rgb(contribution)

    # A cell directly on the axis (e.g. x=9, y=7) should be brighter than a cell
    # at the edge of the cone (e.g. x=9, y=9) because of the soft gradient.
    brightness_center = rgb[7, 9, 0]
    brightness_edge = rgb[9, 9, 0]
    assert brightness_center > brightness_edge


def test_height_incidence_attenuation() -> None:
    """Test that height incidence dampens intensity based on distance/angle."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)

    # Flat light
    contribution_flat = _compute_single_light_contribution(
        origin_x=7,
        origin_y=7,
        radius=5,
        color_rgb=(255, 255, 255),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height=0.0,
    )
    rgb_flat = collapse_premult_rgba_to_rgb(contribution_flat)

    # High light
    contribution_high = _compute_single_light_contribution(
        origin_x=7,
        origin_y=7,
        radius=5,
        color_rgb=(255, 255, 255),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height=3.0,
    )
    rgb_high = collapse_premult_rgba_to_rgb(contribution_high)

    # The high light should have lower brightness on the floor due to height incidence
    assert rgb_high[7, 9, 0] < rgb_flat[7, 9, 0]


def test_channel_masked_transparency() -> None:
    """Test that cells with non-matching channel mask are transparent to the light."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)
    # Put an opaque blocker at (7, 8)
    opaque[7, 8] = True

    # Cell mask at (7, 8) has channel 2 (binary 10)
    cell_mask = np.zeros((h, w), dtype=np.uint32)
    cell_mask[7, 8] = 2

    # A light with channel 1 (binary 01) -> no overlap, so blocker is transparent
    contribution = _compute_single_light_contribution(
        origin_x=7,
        origin_y=7,
        radius=5,
        color_rgb=(255, 255, 255),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        channels=1,
        cell_mask=cell_mask,
    )
    rgb = collapse_premult_rgba_to_rgb(contribution)

    # Light should pass through the blocker and reach (7, 9)
    assert rgb[7, 9, 0] > 0.0
