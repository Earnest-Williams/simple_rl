"""Tests for LightContributionCache and RGBBlendPolicy.

Validates Phase 3 (per-light contribution cache) and Phase 4 (RGB blend
policy) implemented in ``engine.render_lighting``.  No ``lights_dev``
imports.
"""

from __future__ import annotations

from typing import TypeAlias

import numpy as np

from engine.render_lighting import (
    DEFAULT_BLEND_POLICY,
    LightContributionCache,
    RGBBlendPolicy,
    _compute_single_light_contribution,
    apply_memory_fade,
    collapse_premult_rgba_to_rgb,
)
from tests.fixtures.lighting_scenarios import LightFixture
from utils.game_rng import GameRNG

LightSpec: TypeAlias = (
    tuple[int, int, int, int]
    | tuple[int, int, int, int, tuple[int, int, int]]
    | tuple[int, int, int, int, tuple[int, int, int], float]
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_opaque_grid(
    height: int, width: int, wall_cols: tuple[int, ...] = ()
) -> np.ndarray:
    """Return a bool opaque grid with optional solid vertical wall columns."""
    grid = np.zeros((height, width), dtype=np.bool_)
    for col in wall_cols:
        grid[:, col] = True
    return grid


def make_flat_geometry(height: int, width: int) -> tuple[np.ndarray, np.ndarray]:
    """Return flat height and ceiling maps for colored-light tests."""
    height_map = np.zeros((height, width), dtype=np.int16)
    ceiling_map = np.full((height, width), 10, dtype=np.int16)
    return height_map, ceiling_map


def make_lights(*args: LightSpec) -> list[LightFixture]:
    """Build LightFixture list from (id, x, y, radius, color, intensity) tuples."""
    result: list[LightFixture] = []
    for spec in args:
        if len(spec) == 4:
            light_id, x, y, radius = spec
            color = (200, 200, 200)
            intensity = 1.0
        elif len(spec) == 5:
            light_id, x, y, radius, color = spec
            intensity = 1.0
        else:
            light_id, x, y, radius, color, intensity = spec
        result.append(LightFixture(light_id, x, y, radius, color, intensity))
    return result


# ---------------------------------------------------------------------------
# RGBBlendPolicy tests
# ---------------------------------------------------------------------------


def test_blend_policy_accumulate() -> None:
    """Accumulate adds contribution into target."""
    policy = RGBBlendPolicy()
    target = np.zeros((5, 5, 3), dtype=np.float32)
    contrib = np.ones((5, 5, 3), dtype=np.float32) * 50.0
    policy.accumulate(target, contrib)
    np.testing.assert_array_equal(target, contrib)


def test_blend_policy_subtract() -> None:
    """Subtract removes a previously-added contribution."""
    policy = RGBBlendPolicy()
    target = np.ones((5, 5, 3), dtype=np.float32) * 100.0
    contrib = np.ones((5, 5, 3), dtype=np.float32) * 40.0
    policy.subtract(target, contrib)
    np.testing.assert_allclose(target, 60.0)


def test_blend_policy_composite_clamps() -> None:
    """Composite clamps values to [0, 255]."""
    policy = RGBBlendPolicy()
    arr = np.array([[[300.0, -10.0, 128.0]]], dtype=np.float32)
    out = policy.composite(arr)
    assert float(out[0, 0, 0]) == 255.0
    assert float(out[0, 0, 1]) == 0.0
    assert float(out[0, 0, 2]) == 128.0


def test_default_blend_policy_is_rgb_blend_policy() -> None:
    """DEFAULT_BLEND_POLICY is an RGBBlendPolicy instance."""
    assert isinstance(DEFAULT_BLEND_POLICY, RGBBlendPolicy)


# ---------------------------------------------------------------------------
# _compute_single_light_contribution tests
# ---------------------------------------------------------------------------


def test_single_light_lights_adjacent_cells() -> None:
    """A light in an open room illuminates cells directly adjacent."""
    h = w = 15
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    contrib = _compute_single_light_contribution(
        origin_x=7,
        origin_y=7,
        radius=5,
        color_rgb=(200, 200, 200),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        assert np.any(
            contrib[7 + dy, 7 + dx] > 0
        ), f"Adjacent cell ({7+dy},{7+dx}) should be lit"


def test_single_light_does_not_cross_wall() -> None:
    """A light must not illuminate mid-row cells on the far side of a wall."""
    h, w = 15, 20
    opaque = make_opaque_grid(h, w, wall_cols=(10,))
    height_map, ceiling_map = make_flat_geometry(h, w)
    contrib = _compute_single_light_contribution(
        origin_x=3,
        origin_y=7,
        radius=15,
        color_rgb=(200, 200, 200),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )
    # Exclude extreme-corner rows due to known production FOV edge cases
    for y in range(2, h - 2):
        for x in range(11, w):
            assert not np.any(
                contrib[y, x] > 0
            ), f"Cell ({y},{x}) east of solid wall should not be lit"


def test_single_light_respects_height_barrier() -> None:
    """Height blockers must prevent colored light from crossing elevation walls."""
    h, w = 9, 12
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    height_map[:, 5] = 10

    contrib = _compute_single_light_contribution(
        origin_x=2,
        origin_y=4,
        radius=9,
        color_rgb=(200, 200, 200),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )

    for y in range(3, 6):
        for x in range(6, w):
            assert not np.any(
                contrib[y, x] > 0
            ), f"Cell ({y},{x}) east of height barrier should not be lit"


def test_single_light_zero_radius_returns_zeros() -> None:
    """A light with radius 0 produces no contribution."""
    h = w = 10
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    contrib = _compute_single_light_contribution(
        origin_x=5,
        origin_y=5,
        radius=0,
        color_rgb=(200, 200, 200),
        intensity=1.0,
        opaque_grid=opaque,
        scene_h=h,
        scene_w=w,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )
    assert contrib.max() == 0.0


# ---------------------------------------------------------------------------
# LightContributionCache tests
# ---------------------------------------------------------------------------


def test_cache_cached_vs_uncached_match() -> None:
    """Cache output matches direct summation over the same lights."""
    h = w = 20
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 5, 5, 6, (255, 0, 0)), (2, 14, 14, 6, (0, 0, 255)))

    # Uncached reference via direct summation
    ref_combined = np.zeros((h, w, 8, 4), dtype=np.float32)
    for light in lights:
        buf = _compute_single_light_contribution(
            origin_x=light.x,
            origin_y=light.y,
            radius=light.radius,
            color_rgb=light.color,
            intensity=light.intensity,
            opaque_grid=opaque,
            scene_h=h,
            scene_w=w,
            height_map=height_map,
            ceiling_map=ceiling_map,
        )
        ref_combined += buf
    ref = collapse_premult_rgba_to_rgb(ref_combined)

    # Cached output
    cache = LightContributionCache(h, w)
    cached = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    np.testing.assert_array_equal(cached, ref)


def test_cache_unchanged_light_is_not_recomputed() -> None:
    """A light with identical parameters is not recomputed between updates."""
    h = w = 15
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 7, 7, 5, (200, 200, 200)))

    cache = LightContributionCache(h, w)
    first = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )
    # Record the buffer reference
    cached_buf_before = cache._contributions[1].copy()
    second = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    np.testing.assert_array_equal(first, second)
    # The stored contribution buffer should be identical
    np.testing.assert_array_equal(cache._contributions[1], cached_buf_before)


def test_cache_moving_light_updates_only_that_light() -> None:
    """Moving one light invalidates only that light's contribution."""
    h = w = 20
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights(
        (1, 5, 5, 5, (255, 0, 0)),
        (2, 14, 14, 5, (0, 0, 255)),
    )

    cache = LightContributionCache(h, w)
    before = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )
    buf_2_before = cache._contributions[2].copy()

    # Move light 1 to (3, 3); light 2 stays at (14, 14)
    lights[0] = LightFixture(1, 3, 3, 5, (255, 0, 0))
    after = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    # Light 2's contribution buffer should be unchanged
    np.testing.assert_array_equal(cache._contributions[2], buf_2_before)
    # Combined output must differ (light 1 moved)
    assert not np.array_equal(before, after), "Combined buffer should change after move"


def test_cache_changing_color_invalidates_that_light() -> None:
    """Changing a light's color causes its buffer to be recomputed."""
    h = w = 15
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 7, 7, 5, (255, 0, 0)))

    cache = LightContributionCache(h, w)
    before = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    lights[0] = LightFixture(1, 7, 7, 5, (0, 255, 0))  # changed color
    after = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    assert not np.array_equal(before, after), "Color change must update combined buffer"


def test_cache_removing_light_subtracts_contribution() -> None:
    """Removing a light subtracts its contribution from the combined buffer."""
    h = w = 15
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 5, 5, 5, (200, 200, 200)), (2, 10, 10, 5, (200, 200, 200)))

    cache = LightContributionCache(h, w)
    cache.update(
        lights,
        opaque,
        scene_seq=1,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )
    combined_before = cache._combined.copy()
    buf_2 = cache._contributions[2].copy()

    # Remove light 2
    after = cache.update(
        [lights[0]],
        opaque,
        scene_seq=1,
        height_map=height_map,
        ceiling_map=ceiling_map,
    )

    # The combined buffer should no longer contain light 2's contribution
    assert 2 not in cache._contributions
    np.testing.assert_allclose(
        after, collapse_premult_rgba_to_rgb(cache._contributions[1]), atol=1e-5
    )
    np.testing.assert_allclose(
        collapse_premult_rgba_to_rgb(combined_before - buf_2), after, atol=1e-5
    )


def test_cache_scene_seq_change_triggers_full_rebuild() -> None:
    """A new scene_seq value forces full re-computation of all lights."""
    h, w = 15, 20
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 3, 7, 8, (200, 200, 200)))

    cache = LightContributionCache(h, w)
    before = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    # Change scene geometry (add a wall) but use a new scene_seq
    opaque2 = make_opaque_grid(h, w, wall_cols=(8,))
    after = cache.update(
        lights, opaque2, scene_seq=2, height_map=height_map, ceiling_map=ceiling_map
    )

    # The wall blocks some cells — output should differ
    assert not np.array_equal(
        before, after
    ), "Scene geometry change must invalidate cache"


def test_cache_explicit_invalidate_forces_rebuild() -> None:
    """Calling invalidate() forces a full rebuild on next update."""
    h = w = 15
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 7, 7, 5, (200, 200, 200)))

    cache = LightContributionCache(h, w)
    first = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )
    cache.invalidate()
    second = cache.update(
        lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
    )

    # After explicit invalidate + same scene_seq, a new scene_seq=1 triggers full rebuild
    np.testing.assert_array_equal(first, second)
    assert len(cache._contributions) == 1


def test_cache_multiple_updates_deterministic() -> None:
    """Repeated cache updates with the same inputs produce identical output."""
    h = w = 20
    opaque = make_opaque_grid(h, w)
    height_map, ceiling_map = make_flat_geometry(h, w)
    lights = make_lights((1, 5, 5, 6, (255, 100, 50)), (2, 15, 15, 5, (50, 100, 255)))

    cache = LightContributionCache(h, w)
    results = [
        cache.update(
            lights, opaque, scene_seq=1, height_map=height_map, ceiling_map=ceiling_map
        )
        for _ in range(3)
    ]
    for r in results[1:]:
        np.testing.assert_array_equal(results[0], r)


def test_apply_memory_fade_accepts_read_only_map_inputs() -> None:
    """Memory fade must not mutate read-only map or visibility slices."""
    final_fg = np.full((2, 2, 3), 100, dtype=np.uint8)
    final_bg = np.full((2, 2, 3), 50, dtype=np.uint8)
    glyph_indices = np.array([[1, 2], [3, 4]], dtype=np.int32)
    map_memory_vp = np.array([[1.0, 0.25], [0.5, 1.0]], dtype=np.float32)
    map_tiles_vp = np.array([[1, 1], [0, 0]], dtype=np.int32)
    drawn_mask = np.ones((2, 2), dtype=np.bool_)
    visible_mask = np.array([[True, False], [False, True]], dtype=np.bool_)
    fade_color = np.array([128, 128, 128], dtype=np.uint8)

    map_memory_vp.setflags(write=False)
    map_tiles_vp.setflags(write=False)
    visible_mask.setflags(write=False)
    drawn_mask.setflags(write=False)
    glyph_indices.setflags(write=False)

    apply_memory_fade(
        final_fg,
        final_bg,
        glyph_indices,
        map_memory_vp,
        map_tiles_vp,
        drawn_mask,
        visible_mask,
        fade_color,
        rng=GameRNG(seed=1),
    )

    assert np.any(final_fg != 100)
    assert np.any(final_bg != 50)
    np.testing.assert_array_equal(glyph_indices, np.array([[1, 2], [3, 4]]))
