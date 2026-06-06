"""Tests for light-aware FOV shadowcasting.

Validates:
- Side bits (cardinal and diagonal mapping)
- Cone constraints
- Channel masks
- Subtractive visibility
- Endpoint opacity thresholds
- Repeated-call stability
- Leak cases (diagonal wall blockers)
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from game.world.light_fov import (
    SIDE_E,
    SIDE_N,
    SIDE_NE,
    SIDE_NW,
    SIDE_S,
    SIDE_SE,
    SIDE_SW,
    SIDE_W,
    compute_fov_all_octants,
)


def test_side_bits() -> None:
    """Validate that side bits are correctly set for cardinal and diagonal directions."""
    h = w = 5
    transparency = np.ones((h, w), dtype=np.float32)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible,
        dist,
        side_bits,
        2,  # cx
        2,  # cy
        2,  # radius
    )

    # Center must have all side bits set
    all_sides = (
        SIDE_N | SIDE_E | SIDE_S | SIDE_W | SIDE_NE | SIDE_SE | SIDE_SW | SIDE_NW
    )
    assert side_bits[2, 2] == all_sides

    # Cardinal positions relative to center
    assert (side_bits[1, 2] & SIDE_S) != 0
    assert (side_bits[2, 3] & SIDE_W) != 0
    assert (side_bits[3, 2] & SIDE_N) != 0
    assert (side_bits[2, 1] & SIDE_E) != 0

    # Diagonal positions relative to center
    assert (side_bits[1, 3] & SIDE_SW) != 0
    assert (side_bits[3, 3] & SIDE_NW) != 0
    assert (side_bits[3, 1] & SIDE_NE) != 0
    assert (side_bits[1, 1] & SIDE_SE) != 0


def test_directional_cones() -> None:
    """Validate directional cone constraints on FOV."""
    h = w = 7
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)

    # Point East (0 radians) with a 90 degree total angle (pi/2)
    # Range is [-pi/4, pi/4]
    start_angle = -math.pi / 4
    end_angle = math.pi / 4

    compute_fov_all_octants(
        opaque,
        transparency,
        visible,
        dist,
        side_bits,
        3,  # cx
        3,  # cy
        3,  # radius
        start_angle,
        end_angle,
    )

    # (3, 5) is directly to the East -> should be visible
    assert visible[3, 5] == 1
    # (3, 1) is directly to the West -> should NOT be visible
    assert visible[3, 1] == 0
    # (1, 3) is directly to the North -> should NOT be visible
    assert visible[1, 3] == 0


def test_channel_masks() -> None:
    """Validate channel mask checking for transparency and blocking."""
    h = w = 5
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    cell_mask = np.zeros((h, w), dtype=np.uint32)

    # Blocker at (2, 3) with channel 1
    opaque[2, 3] = 1
    transparency[2, 3] = 0.0
    cell_mask[2, 3] = 1

    # First case: light has channel 2 (mismatch -> passes through)
    visible_pass = np.zeros((h, w), dtype=np.uint8)
    dist_pass = -np.ones((h, w), dtype=np.int32)
    side_bits_pass = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        opaque,
        transparency,
        cell_mask,
        2,  # light channels (0b10)
        visible_pass,
        dist_pass,
        side_bits_pass,
        2,  # cx
        2,  # cy
        3,  # radius
    )
    # Blocker at (2, 3) was transparent to this light -> cell (2, 4) is visible
    assert visible_pass[2, 4] == 1

    # Second case: light has channel 1 (overlap -> blocks light)
    visible_block = np.zeros((h, w), dtype=np.uint8)
    dist_block = -np.ones((h, w), dtype=np.int32)
    side_bits_block = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        opaque,
        transparency,
        cell_mask,
        1,  # light channels (0b01)
        visible_block,
        dist_block,
        side_bits_block,
        2,  # cx
        2,  # cy
        3,  # radius
    )
    # Blocker at (2, 3) blocks this light -> cell (2, 4) is NOT visible
    assert visible_block[2, 4] == 0


def test_subtractive_visibility() -> None:
    """Validate subtractive visibility calculations along raycast path."""
    h = w = 5
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)

    # Translucent tile at (2, 3) which allows light pass-through (transparency > threshold)
    transparency[2, 3] = 0.9999995

    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)
    visibility = np.zeros((h, w), dtype=np.float32)

    compute_fov_all_octants(
        opaque,
        transparency,
        visible,
        dist,
        side_bits,
        visibility,
        2,  # cx
        2,  # cy
        3,  # radius
    )

    # Source tile has 1.0 visibility
    assert visibility[2, 2] == 1.0
    # Cell (2, 3) has 1.0 visibility (light enters it)
    assert visibility[2, 3] == 1.0
    # Cell (2, 4) gets light that passed through (2, 3) -> 1.0 - (1.0 - 0.9999995) = 0.9999995
    assert visibility[2, 4] == pytest.approx(0.9999995, abs=1e-7)


def test_endpoint_opacity() -> None:
    """Validate behavior around the opacity threshold boundary."""
    h = w = 5
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)

    # Case A: Transparency slightly above threshold (0.9999995 > 0.999999) -> allows pass-through
    transparency[2, 3] = 0.9999995
    visible_a = np.zeros((h, w), dtype=np.uint8)
    dist_a = -np.ones((h, w), dtype=np.int32)
    side_bits_a = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        opaque,
        transparency,
        visible_a,
        dist_a,
        side_bits_a,
        2,
        2,
        3,
    )
    assert visible_a[2, 4] == 1

    # Case B: Transparency slightly below threshold (0.999998 < 0.999999) -> acts as blocker
    transparency[2, 3] = 0.999998
    visible_b = np.zeros((h, w), dtype=np.uint8)
    dist_b = -np.ones((h, w), dtype=np.int32)
    side_bits_b = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        opaque,
        transparency,
        visible_b,
        dist_b,
        side_bits_b,
        2,
        2,
        3,
    )
    assert visible_b[2, 4] == 0


def test_repeated_call_stability() -> None:
    """Ensure that calling compute_fov_all_octants repeatedly with the same arrays is stable."""
    h = w = 5
    transparency = np.ones((h, w), dtype=np.float32)
    visible_1 = np.zeros((h, w), dtype=np.uint8)
    dist_1 = -np.ones((h, w), dtype=np.int32)
    side_bits_1 = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible_1,
        dist_1,
        side_bits_1,
        2,
        2,
        2,
    )

    visible_2 = np.zeros((h, w), dtype=np.uint8)
    dist_2 = -np.ones((h, w), dtype=np.int32)
    side_bits_2 = np.zeros((h, w), dtype=np.uint8)

    # Call again with clean target arrays
    compute_fov_all_octants(
        transparency,
        visible_2,
        dist_2,
        side_bits_2,
        2,
        2,
        2,
    )

    assert np.array_equal(visible_1, visible_2)
    assert np.array_equal(dist_1, dist_2)
    assert np.array_equal(side_bits_1, side_bits_2)


def test_diagonal_leak_cases() -> None:
    """Ensure light doesn't leak diagonally through a diagonal blocker wall."""
    h = w = 9
    transparency = np.ones((h, w), dtype=np.float32)
    # Diagonal wall from (2, 4) to (6, 0)
    for i in range(5):
        transparency[2 + i, 4 - i] = 0.0

    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)

    compute_fov_all_octants(
        transparency,
        visible,
        dist,
        side_bits,
        1,  # cx
        1,  # cy
        6,  # radius
    )

    # (5, 5) is on the other side of the diagonal wall from (1, 1).
    # The wall is: (2, 4), (3, 3), (4, 2), (5, 1), (6, 0).
    # The source is at (1, 1). So (5, 5) is behind the wall and should not be visible.
    assert visible[5, 5] == 0


def test_adjacent_blocker_clears_diagonal_cardinal_face_bit() -> None:
    """A blocker adjacent to a diagonal target clears that target's cardinal face."""
    from game.world.light_fov import _compute_octant_core_legacy
    h = w = 7
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[2, 3] = 0.0

    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)

    _compute_octant_core_legacy(
        transparency,
        visible,
        dist,
        side_bits,
        2,
        2,
        4,
        0,
        0.999999,
    )
    assert visible[1, 3] == 1
    assert (side_bits[1, 3] & SIDE_SW) != 0
    assert (side_bits[1, 3] & SIDE_W) != 0
    assert (side_bits[1, 3] & SIDE_S) == 0
