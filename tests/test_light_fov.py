import math
import numpy as np
import pytest

from game.world.light_fov import (
    SIDE_N,
    SIDE_E,
    SIDE_S,
    SIDE_W,
    SIDE_NE,
    SIDE_SE,
    SIDE_SW,
    SIDE_NW,
    compute_fov_all_octants,
)

def test_source_tile_sets_all_side_bits() -> None:
    h, w = 3, 3
    transparency = np.ones((h, w), dtype=np.float32)
    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        1,  # cx
        1,  # cy
        2,  # radius
    )

    all_sides = SIDE_N | SIDE_E | SIDE_S | SIDE_W | SIDE_NE | SIDE_SE | SIDE_SW | SIDE_NW
    assert side_bits_out[1, 1] == all_sides
    assert visible_out[1, 1] == 1


def test_cardinal_exposure_directions() -> None:
    h, w = 5, 5
    transparency = np.ones((h, w), dtype=np.float32)
    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        2,  # cx
        2,  # cy
        2,  # radius
    )

    # East (2, 3) relative to (2, 2)
    assert (side_bits_out[2, 3] & SIDE_E) != 0
    # West (2, 1)
    assert (side_bits_out[2, 1] & SIDE_W) != 0
    # South (3, 2)
    assert (side_bits_out[3, 2] & SIDE_S) != 0
    # North (1, 2)
    assert (side_bits_out[1, 2] & SIDE_N) != 0


def test_diagonal_exposure_directions() -> None:
    h, w = 5, 5
    transparency = np.ones((h, w), dtype=np.float32)
    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        2,  # cx
        2,  # cy
        2,  # radius
    )

    # Southeast diagonal (3, 3) relative to (2, 2)
    # dx = 1, dy = 1 -> diagonal SE + card E + card S
    expected = SIDE_SE | SIDE_E | SIDE_S
    assert (side_bits_out[3, 3] & expected) == expected


def test_adjacent_blocker_clears_cardinal_side_bit() -> None:
    h, w = 5, 5
    transparency = np.ones((h, w), dtype=np.float32)
    # Block east of the target diagonal cell (3, 3) -> cell (3, 4)
    # Note: cx = 2, cy = 2. Southeast diagonal = (3, 3).
    # East of (3, 3) is mx + 1 = 4, my = 3 -> cell (3, 4).
    transparency[3, 4] = 0.0

    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        2,  # cx
        2,  # cy
        2,  # radius
    )

    # Southeast diagonal (3, 3). SIDE_E should be cleared because transparency[3, 4] == 0.
    assert (side_bits_out[3, 3] & SIDE_SE) != 0
    assert (side_bits_out[3, 3] & SIDE_S) != 0
    assert (side_bits_out[3, 3] & SIDE_E) == 0


def test_directional_cone_constraints() -> None:
    h, w = 10, 10
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    # Cone pointing East (0 rad) with angle math.pi/2
    start_angle = -math.pi / 4
    end_angle = math.pi / 4

    compute_fov_all_octants(
        opaque,
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        5,  # cx
        5,  # cy
        4,  # radius
        start_angle,
        end_angle,
    )

    # East (5, 7) should be visible
    assert visible_out[5, 7] == 1
    # West (5, 3) should NOT be visible
    assert visible_out[5, 3] == 0


def test_channel_masks_passthrough() -> None:
    h, w = 5, 5
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    cell_mask = np.zeros((h, w), dtype=np.uint32)

    # Put a blocker at (2, 3) but mask it so it belongs to channel 1.
    opaque[2, 3] = 1
    transparency[2, 3] = 0.0
    cell_mask[2, 3] = 1

    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)

    # Run with light channel 2 (non-overlapping with 1) -> blocker (2, 3) is transparent.
    compute_fov_all_octants(
        opaque,
        transparency,
        cell_mask,
        2,  # light channels
        visible_out,
        dist_out,
        side_bits_out,
        2,  # cx
        2,  # cy
        3,  # radius
    )

    # The tile behind the blocker (2, 4) should be visible
    assert visible_out[2, 4] == 1


def test_subtractive_visibility() -> None:
    h, w = 5, 5
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)

    # Put a translucent tile at (2, 3) that is above the threshold (0.999999)
    transparency[2, 3] = 0.9999995

    visible_out = np.zeros((h, w), dtype=np.uint8)
    dist_out = -np.ones((h, w), dtype=np.int32)
    side_bits_out = np.zeros((h, w), dtype=np.uint8)
    visibility_out = np.zeros((h, w), dtype=np.float32)

    compute_fov_all_octants(
        opaque,
        transparency,
        visible_out,
        dist_out,
        side_bits_out,
        visibility_out,
        2,  # cx
        2,  # cy
        3,  # radius
    )

    # Source tile visibility is 1.0
    assert visibility_out[2, 2] == 1.0
    # Target tile (2, 4) visibility should be 1.0 - (1.0 - 0.9999995) = 0.9999995
    assert visibility_out[2, 4] == pytest.approx(0.9999995)




