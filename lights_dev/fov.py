#!/usr/bin/env python
# Numba-based integer-slope shadowcasting FOV with per-tile side-bits.
# - integer slope comparisons (cross-multiplication)
# - half-cell slope representation for top-inclusive / bottom-exclusive tie-break
# - early exit when top <= bottom
# - simple transparency threshold model (t < 1 => treated as blocker for slope updates)
# - side bits per tile (N/E/S/W) accumulated across octants
from __future__ import annotations

import numba
import numpy as np
from numba import boolean, float32, uint8

# Side bit definitions
SIDE_N: Final[int] = 1  # North
SIDE_E: Final[int] = 2  # East
SIDE_S: Final[int] = 4  # South
SIDE_W: Final[int] = 8  # West

INT = numba.int64


@numba.njit(inline="always")
def _slope_ge(a_n: INT, a_d: INT, b_n: INT, b_d: INT) -> boolean:
    # true iff a_n/a_d >= b_n/b_d without dividing (cross-multiply)
    return a_n * b_d >= b_n * a_d


@numba.njit(inline="always")
def _slope_le(a_n: INT, a_d: INT, b_n: INT, b_d: INT) -> boolean:
    # true iff a_n/a_d <= b_n/b_d without dividing
    return a_n * b_d <= b_n * a_d


@numba.njit(inline="always")
def _octant_map_coords(
    cx: int, cy: int, x: int, y: int, octant: int
) -> tuple[int, int]:
    # map (x,y) in octant coords (x >= 1, 0 <= y <= x) to map coordinates
    if octant == 0:
        return cx + x, cy - y
    elif octant == 1:
        return cx + y, cy - x
    elif octant == 2:
        return cx - y, cy - x
    elif octant == 3:
        return cx - x, cy - y
    elif octant == 4:
        return cx - x, cy + y
    elif octant == 5:
        return cx - y, cy + x
    elif octant == 6:
        return cx + y, cy + x
    else:
        # octant == 7
        return cx + x, cy + y


@numba.njit(inline="always")
def _compute_side_mask_from_vector(dx: int, dy: int) -> uint8:
    """
    Compute a 4-bit mask for which side(s) of the target cell face the source.
    Bits: N=1, E=2, S=4, W=8.
    Rule:
      - if |dx| > |dy| => horizontal side (E if dx>0 else W)
      - if |dy| > |dx| => vertical side (S if dy>0 else N)
      - if |dx| == |dy| => set both corresponding horizontal and vertical sides
    """
    absdx = dx if dx >= 0 else -dx
    absdy = dy if dy >= 0 else -dy
    mask = uint8(0)
    if absdx > absdy:
        # horizontal
        if dx > 0:
            mask |= SIDE_E
        elif dx < 0:
            mask |= SIDE_W
    elif absdy > absdx:
        # vertical
        if dy > 0:
            mask |= SIDE_S
        elif dy < 0:
            mask |= SIDE_N
    else:
        # diagonal: set both corresponding sides if nonzero; if both zero (origin) set all sides
        if dx == 0 and dy == 0:
            # source tile: set all sides
            mask = uint8(SIDE_N | SIDE_E | SIDE_S | SIDE_W)
        else:
            if dx > 0:
                mask |= SIDE_E
            elif dx < 0:
                mask |= SIDE_W
            if dy > 0:
                mask |= SIDE_S
            elif dy < 0:
                mask |= SIDE_N
    return mask


@numba.njit(nogil=True, cache=True)
def _compute_octant_core(
    transparency: np.float32[:, :],
    visible: np.uint8[:, :],
    dist: np.int32[:, :],
    side_bits: np.uint8[:, :],
    cx: int,
    cy: int,
    radius: int,
    octant: int,
    opacity_threshold: float32,
) -> None:
    """
    Core integer-slope octant scan with side-bit accumulation.

    Parameters:
    - transparency: 2D float32 0..1 (1 = fully transparent). Tiles with transparency <= opacity_threshold
      are treated as blocking for slope updates.
    - visible: output uint8 mask written in-place (1 = visible)
    - dist: output int32 squared distance in tiles, -1 if not visible
    - side_bits: output uint8 per-tile ORed mask of N/E/S/W bits
    - cx, cy: origin coordinates
    - radius: integer radius (Euclidean)
    - octant: 0..7 octant index
    - opacity_threshold: float threshold
    """
    h, w = transparency.shape
    radius_sq = radius * radius

    # initial integer slope pairs
    top_n = INT(1)
    top_d = INT(1)
    bottom_n = INT(0)
    bottom_d = INT(1)

    # scan columns x = 1..radius
    for x in range(1, radius + 1):
        # compute integer bounds for y using cross-multiplied ceil/floor
        # y_min = ceil((bottom_n/bottom_d) * x)
        y_min = int((bottom_n * x + bottom_d - 1) // bottom_d)
        # y_max = floor((top_n/top_d) * x)
        y_max = int((top_n * x) // top_d)
        if y_min > y_max:
            continue

        for y in range(y_min, y_max + 1):
            mx, my = _octant_map_coords(cx, cy, x, y, octant)
            if mx < 0 or my < 0 or mx >= w or my >= h:
                continue

            d = x * x + y * y
            if d <= radius_sq:
                # mark visible and distance
                visible[my, mx] = 1
                if dist[my, mx] == -1 or d < dist[my, mx]:
                    dist[my, mx] = d

                # compute and accumulate side mask
                dx = mx - cx
                dy = my - cy
                mask = _compute_side_mask_from_vector(dx, dy)
                side_bits[my, mx] |= mask

            # treat tile as blocking for slope updates if transparency <= threshold
            if transparency[my, mx] <= opacity_threshold:
                # update top: half-cell top boundary (2*y + 1) / (2*x - 1)
                new_top_n = INT(2 * y + 1)
                new_top_d = INT(2 * x - 1)
                if _slope_ge(new_top_n, new_top_d, top_n, top_d):
                    top_n = new_top_n
                    top_d = new_top_d
                # update bottom: half-cell bottom boundary (2*y - 1) / (2*x + 1)
                new_bottom_n = INT(2 * y - 1)
                new_bottom_d = INT(2 * x + 1)
                if _slope_le(new_bottom_n, new_bottom_d, bottom_n, bottom_d):
                    bottom_n = new_bottom_n
                    bottom_d = new_bottom_d

        # early-exit if top <= bottom (no further visible columns)
        if top_n * bottom_d <= bottom_n * top_d:
            break


@numba.njit(nogil=True, cache=True)
def compute_fov_all_octants(
    transparency: np.float32[:, :],
    visible_out: np.uint8[:, :],
    dist_out: np.int32[:, :],
    side_bits_out: np.uint8[:, :],
    cx: int,
    cy: int,
    radius: int,
    opacity_threshold: float32 = 0.999999,
) -> None:
    """
    Top-level API: compute FOV for all 8 octants.

    Precondition: visible_out, dist_out, side_bits_out are preallocated and C-contiguous.
    dist_out should be initialized to -1 by the caller if desired; this routine will only
    overwrite distances for discovered tiles.
    """
    h, w = transparency.shape
    # mark the origin
    if 0 <= cx < w and 0 <= cy < h:
        visible_out[cy, cx] = 1
        dist_out[cy, cx] = 0
        side_bits_out[cy, cx] |= uint8(SIDE_N | SIDE_E | SIDE_S | SIDE_W)

    for octant in range(8):
        _compute_octant_core(
            transparency,
            visible_out,
            dist_out,
            side_bits_out,
            cx,
            cy,
            radius,
            octant,
            opacity_threshold,
        )
