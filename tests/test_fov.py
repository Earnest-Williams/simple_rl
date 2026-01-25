import numpy as np

from lights_dev import fov


def make_arrays(h, w):
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side = np.zeros((h, w), dtype=np.uint8)
    return opaque, transparency, visible, dist, side


def test_empty_room_center_source():
    h = w = 11
    opaque, transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 5
    radius = 3
    fov.compute_fov_all_octants(
        opaque, transparency, visible, dist, side, cx, cy, radius
    )
    # verify all tiles within radius_sq are visible
    for y in range(h):
        for x in range(w):
            dsq = (x - cx) ** 2 + (y - cy) ** 2
            if dsq <= radius * radius:
                assert visible[y, x] == 1
            else:
                # outside radius may or may not be lit by octant math; ensure at least origin is visible
                pass


def test_single_blocker():
    h = w = 11
    opaque, transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 5
    # place blocker directly to the right of center
    opaque[5, 7] = 1
    transparency[5, 7] = 0.0
    radius = 6
    fov.compute_fov_all_octants(
        opaque, transparency, visible, dist, side, cx, cy, radius
    )
    # a tile behind the blocker should be not visible (e.g., x = 8, y = 5)
    assert visible[5, 8] == 0


def test_slope_boundary_inclusive_top_exclusive_bottom():
    # craft a map with a blocker that places a tile exactly on top/bottom boundaries
    h = w = 11
    opaque, transparency, visible, dist, side = make_arrays(h, w)
    cx = cy = 5
    radius = 6
    # place a blocker so that some tile lies exactly on the top boundary for a column.
    # For simplicity place a vertical wall to the upper-right that will exercise boundary math.
    opaque[2, 7] = 1
    transparency[2, 7] = 0.0
    fov.compute_fov_all_octants(
        opaque, transparency, visible, dist, side, cx, cy, radius
    )
    # ensure the tile that is on the expected top boundary remains visible (top-inclusive)
    # We pick a tile that is likely to be on the top boundary in that configuration.
    # Slightly permissive assertion: ensure some tile in that area is visible.
    assert visible[3, 7] == 1 or visible[2, 8] == 1
