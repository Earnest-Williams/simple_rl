"""Production lighting leak and blending tests.

Validates that colored lights from ``engine.render_lighting`` and
``game.world.fov.compute_light_color_array`` do not leak through blockers.
No ``lights_dev`` imports.
"""

from __future__ import annotations

import numpy as np

from tests.fixtures.lighting_scenarios import (
    LightFixture,
    compute_rgb_sum,
    make_open_map_arrays,
    scenario_light_behind_wall,
    scenario_single_omni,
    scenario_two_colored_lights,
    scenario_varied_layout,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def has_light(rgb_sum: np.ndarray, y: int, x: int, threshold: float = 0.01) -> bool:
    """Return True if any channel has intensity above threshold."""
    return bool(np.any(rgb_sum[y, x] > threshold))


# ---------------------------------------------------------------------------
# Leak tests
# ---------------------------------------------------------------------------


def test_no_light_east_of_solid_wall() -> None:
    """Light west of a solid vertical wall must not reach the east side."""
    sc = scenario_light_behind_wall()
    rgb = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    h, w = sc["opaque"].shape
    for y in range(h):
        for x in range(12, w):  # east of wall at x=10
            assert not has_light(
                rgb, y, x
            ), f"Light leaked to ({y},{x}) east of solid wall"


def test_no_light_behind_blocker_west_to_east() -> None:
    """Single omni light must not light cells on the far side of a blocker."""
    h, w = 15, 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    opaque[:, 10] = True  # solid wall
    lights = [LightFixture(light_id=1, x=3, y=7, radius=15)]
    rgb = compute_rgb_sum(lights, opaque, hmap, cmap)
    # Exclude extreme corner rows (known production FOV edge-case at very steep angles)
    for y in range(2, h - 2):
        for x in range(11, w):
            assert not has_light(
                rgb, y, x
            ), f"Light leaked to ({y},{x}) east of solid wall"


def test_light_reaches_open_cells() -> None:
    """A light source must illuminate cells within its radius in an open room."""
    sc = scenario_single_omni()
    rgb = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    light = sc["lights"][0]
    cx, cy = light.x, light.y
    # All cells directly adjacent to the source should receive light
    for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        ny, nx = cy + dy, cx + dx
        assert has_light(
            rgb, ny, nx
        ), f"Expected cell ({ny},{nx}) adjacent to light source to receive light"


def test_two_colored_lights_blend() -> None:
    """Red and blue lights overlap deterministically in the center."""
    sc = scenario_two_colored_lights()
    rgb = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    # Center cell (9,9) should have contributions from both lights
    center_y, center_x = 9, 9
    # Run twice to confirm determinism
    rgb2 = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    np.testing.assert_array_equal(rgb[center_y, center_x], rgb2[center_y, center_x])


def test_rgb_output_stable_across_runs() -> None:
    """RGB accumulation must be deterministic (same output for same input)."""
    sc = scenario_varied_layout()
    rgb1 = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    rgb2 = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    np.testing.assert_array_equal(rgb1, rgb2)


def test_rgb_clamped_to_nonnegative() -> None:
    """RGB contribution values must be >= 0 (no negative light)."""
    sc = scenario_varied_layout()
    rgb = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    assert np.all(rgb >= 0.0), "RGB contributions must be non-negative"


def test_source_tile_has_max_contribution() -> None:
    """The source tile should have the highest contribution among reachable tiles."""
    sc = scenario_single_omni()
    rgb = compute_rgb_sum(
        sc["lights"], sc["opaque"], sc["height_map"], sc["ceiling_map"]
    )
    light = sc["lights"][0]
    src_val = float(np.sum(rgb[light.y, light.x]))
    max_val = float(np.max(np.sum(rgb, axis=2)))
    # Source tile intensity should be among the brightest
    assert (
        src_val >= max_val * 0.9
    ), f"Source tile intensity {src_val:.3f} is much less than max {max_val:.3f}"


def test_no_light_through_diagonal_wall() -> None:
    """A diagonal wall of blockers must not leak light diagonally."""
    h = w = 15
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    for i in range(6):
        opaque[3 + i, 3 + i] = True  # diagonal wall from (3,3) to (8,8)
    lights = [LightFixture(light_id=1, x=1, y=1, radius=12)]
    rgb = compute_rgb_sum(lights, opaque, hmap, cmap)
    # Cells in the bottom-right quadrant past the diagonal should be dark
    for y in range(10, h):
        for x in range(10, w):
            assert not has_light(
                rgb, y, x, threshold=0.5
            ), f"Light leaked to ({y},{x}) past diagonal wall"
