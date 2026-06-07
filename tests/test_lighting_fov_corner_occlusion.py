import numpy as np

from game.world.light_fov import compute_fov_all_octants


def test_diagonal_corner_occlusion():
    """Verify that a single blocking cardinal corner prevents diagonal line of sight squeezing."""
    h = w = 4
    transparency = np.ones((h, w), dtype=np.float32)
    # blocker at (2, 1)
    transparency[1, 2] = 0.0  # y=1, x=2 blocker

    opaque = (transparency <= 0.0).astype(np.uint8)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)

    # Origin at (1, 1), Target at (2, 2)
    # Under strict 'or' policy, a blocker at (2, 1) blocks the diagonal LOS from (1, 1) to (2, 2).
    # In y-x coordinates: origin_y=1, origin_x=1, target_y=2, target_x=2.
    # Blocker is at y=1, x=2.
    compute_fov_all_octants(
        opaque,
        transparency,
        visible,
        dist,
        side_bits,
        1,  # cx
        1,  # cy
        3,  # radius
    )

    # Target (2, 2) should not be visible
    assert visible[2, 2] == 0
