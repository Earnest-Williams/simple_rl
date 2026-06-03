"""Advanced lighting tests for directional/cone behavior, cone softness, channel masking, per-side RGBA, premultiplied normalization, and cache invalidation.

Conforms to Phase 2 requirements of the retire lights_dev plan.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from engine.render_lighting import (
    LightContributionCache,
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
    """Test that cells with non-matching channel mask are transparent to the light and receive no light."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)
    # Put an opaque blocker at (7, 8)
    opaque[7, 8] = True

    # Cell mask initialized to 0xFFFFFFFF (all channels match)
    cell_mask = np.full((h, w), fill_value=0xFFFFFFFF, dtype=np.uint32)
    # Cell mask at (7, 8) has channel 2 (binary 10)
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
    # The masked cell (7, 8) must receive exactly zero light
    assert np.all(rgb[7, 8] == 0.0)


def test_channel_masked_no_accumulation_floor() -> None:
    """Test that open floor cells with a non-matching channel mask receive zero light."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)

    # Cell mask initialized to 0xFFFFFFFF (all channels match)
    cell_mask = np.full((h, w), fill_value=0xFFFFFFFF, dtype=np.uint32)
    # Cell mask at (7, 8) has channel 2 (binary 10) (no blocker, just a floor tile with a different mask)
    cell_mask[7, 8] = 2

    # A light with channel 1 (binary 01)
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

    # (7, 9) is matched, so it receives light
    assert rgb[7, 9, 0] > 0.0
    # (7, 8) is a floor cell but doesn't match channels, so it must receive exactly zero light
    assert np.all(rgb[7, 8] == 0.0)


def test_per_side_rgba() -> None:
    """Validate side-aware (h, w, 8, 4) premultiplied RGBA buffer binning."""
    h = w = 15
    opaque = np.zeros((h, w), dtype=np.bool_)

    # White light at (7, 7)
    light = LightSource(
        x=7,
        y=7,
        radius=5,
        color=(255, 255, 255),
        intensity=1.0,
        id=1,
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
        channels=light.channels,
        height=light.height,
    )

    # East of source at (7, 9): side bits should be in bin index 1 (SIDE_E)
    # y=7, x=9
    val_east_bin_1 = contribution[7, 9, 1]  # SIDE_E bin
    val_east_bin_3 = contribution[7, 9, 3]  # SIDE_W bin

    assert np.any(val_east_bin_1 > 0.0)
    assert np.all(val_east_bin_3 == 0.0)


def test_premultiplied_normalization() -> None:
    """Validate that composite blending correctly clamps and normalizes oversaturated alpha."""
    # Create an oversaturated 4D buffer manually
    buf = np.zeros((2, 2, 8, 4), dtype=np.float32)
    # Fill one cell with super intense lights that add up to > 255.0 alpha
    # Side 0: R=200, G=100, B=50, A=150
    # Side 1: R=150, G=150, B=100, A=200
    buf[0, 0, 0] = [200.0, 100.0, 50.0, 150.0]
    buf[0, 0, 1] = [150.0, 150.0, 100.0, 200.0]

    # Total alpha at [0, 0] = 350.0 (> 255.0)
    rgb = collapse_premult_rgba_to_rgb(buf)

    # Check that output is clamped to [0, 255]
    assert np.all(rgb[0, 0] <= 255.0)
    assert np.all(rgb[0, 0] >= 0.0)

    # Check scaling logic: total_rgba is (350, 250, 150, 350)
    # scale = 255.0 / 350.0
    # expected rgb is approx: (350 * 255/350, 250 * 255/350, 150 * 255/350) = (255, 182.14, 109.28)
    expected_r = 255.0
    expected_g = 250.0 * (255.0 / 350.0)
    expected_b = 150.0 * (255.0 / 350.0)

    assert rgb[0, 0, 0] == pytest.approx(expected_r, abs=1e-3)
    assert rgb[0, 0, 1] == pytest.approx(expected_g, abs=1e-3)
    assert rgb[0, 0, 2] == pytest.approx(expected_b, abs=1e-3)


def test_cache_invalidation_advanced() -> None:
    """Validate that the LightContributionCache updates/invalidates on param changes."""
    h = w = 10
    opaque = np.zeros((h, w), dtype=np.bool_)
    # Add a blocker at (5, 6) with mask channel 0xFFFF0000
    opaque[5, 6] = True
    cell_mask = np.full((h, w), fill_value=0xFFFFFFFF, dtype=np.uint32)
    cell_mask[5, 6] = 0xFFFF0000

    # Start with a directional cone pointing East (0.0)
    light = LightSource(
        x=5,
        y=5,
        radius=4,
        color=(255, 0, 0),
        intensity=1.0,
        direction=0.0,
        cone_angle=math.pi / 2,
        cone_softness=0.0,
        channels=0xFFFFFFFF,
        id=42,
        height=0.0,
    )

    cache = LightContributionCache(h, w)

    # 1. First frame (channels = 0xFFFFFFFF, blocks)
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_initial = cache._contributions[42].copy()

    # 2. Change direction to facing North (math.pi * 1.5) -> cache key changes & buffer changes
    light.direction = math.pi * 1.5
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_direction = cache._contributions[42].copy()
    assert not np.array_equal(buf_initial, buf_direction)

    # 3. Change cone_angle -> cache key changes & buffer changes
    light.cone_angle = math.pi / 4
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_cone = cache._contributions[42].copy()
    assert not np.array_equal(buf_direction, buf_cone)

    # 4. Change cone_softness -> cache key changes & buffer changes
    light.cone_softness = 0.5
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_soft = cache._contributions[42].copy()
    assert not np.array_equal(buf_cone, buf_soft)

    # 5. Change channels -> cache key changes & blocker becomes transparent
    # Reset direction to None and cone_angle to math.tau so blocker (5,6) is inside range
    light.direction = None
    light.cone_angle = math.tau
    # And run once to establish a baseline for omni channels change
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_omni = cache._contributions[42].copy()

    light.channels = 0x0000FFFF
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_chan = cache._contributions[42].copy()
    assert not np.array_equal(buf_omni, buf_chan)

    # 6. Change height -> cache key changes & buffer changes
    light.height = 2.0
    cache.update([light], opaque, scene_seq=1, cell_mask=cell_mask)
    buf_height = cache._contributions[42].copy()
    assert not np.array_equal(buf_chan, buf_height)
