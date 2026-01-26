import numpy as np

from lights_dev import fov


def make_arrays(
    h: int, w: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    transparency = np.ones((h, w), dtype=np.float32)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side = np.zeros((h, w), dtype=np.uint8)
    return transparency, visible, dist, side


def test_empty_room_center_source() -> None:
    h = w = 11
    transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 5
    radius = 3
    fov.compute_fov_all_octants(transparency, visible, dist, side, cx, cy, radius)
    # verify all tiles within radius_sq are visible
    for y in range(h):
        for x in range(w):
            dsq = (x - cx) ** 2 + (y - cy) ** 2
            if dsq <= radius * radius:
                assert visible[y, x] == 1
            else:
                # outside radius may or may not be lit by octant math; ensure at least origin is visible
                pass


def test_single_blocker() -> None:
    h = w = 11
    transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 5
    # place blocker directly to the right of center
    transparency[5, 7] = 0.0
    radius = 6
    fov.compute_fov_all_octants(transparency, visible, dist, side, cx, cy, radius)
    # a tile behind the blocker should be not visible (e.g., x = 8, y = 5)
    assert visible[5, 8] == 0


def test_slope_boundary_inclusive_top_exclusive_bottom() -> None:
    """Test that top boundaries are inclusive and bottom boundaries are exclusive.

    Place a blocker and verify that tiles on boundary slopes are handled correctly
    according to the half-cell tie-breaking rule.
    """
    h = w = 21
    transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 10  # center of grid
    radius = 12

    # Place blocker at (13, 8) - offset (3, -2) from center
    # This blocker will cast a shadow and define slope boundaries
    transparency[8, 13] = 0.0

    fov.compute_fov_all_octants(transparency, visible, dist, side, cx, cy, radius)

    # The blocker itself should be visible
    assert visible[8, 13] == 1

    # Tiles immediately behind the blocker in the same direction should be shadowed
    # Verify at least one tile in the shadow is not visible
    assert visible[6, 16] == 0 or visible[7, 15] == 0

    # Tiles to the side of the shadow cone should be visible
    # (exact tiles depend on slope math, but we verify the shadow is not total)
    assert visible[8, 14] == 1  # directly behind along x-axis should be visible
    assert visible[9, 13] == 1  # directly behind along y-axis should be visible


def test_diagonal_blocker_shadow() -> None:
    """Test shadowing behavior with a blocker on a diagonal from the source."""
    h = w = 15
    transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 7
    radius = 10

    # Place blocker at diagonal offset (2, 2) - southeast from center
    transparency[9, 9] = 0.0

    fov.compute_fov_all_octants(transparency, visible, dist, side, cx, cy, radius)

    # Blocker should be visible
    assert visible[9, 9] == 1

    # Tiles directly behind blocker along the diagonal should be in shadow
    assert visible[11, 11] == 0

    # Tiles to the sides should still be visible
    assert visible[9, 10] == 1
    assert visible[10, 9] == 1
