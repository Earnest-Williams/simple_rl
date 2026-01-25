#!/usr/bin/env python
# Numba-based integer-slope shadowcasting FOV
# - integer slope comparisons (cross-multiplication)
# - half-cell slope representation for top-inclusive / bottom-exclusive tie-break
# - early exit when top <= bottom
# - simple transparency threshold model (t < 1 => treated as blocker for slope logic)
from __future__ import annotations
import numpy as np
import numba
from numba import int64, int32, uint8, float32, boolean

INT = numba.int64


@numba.njit(inline="always")
def _slope_ge(a_n: INT, a_d: INT, b_n: INT, b_d: INT) -> boolean:
    # true iff a_n/a_d >= b_n/b_d
    return a_n * b_d >= b_n * a_d


@numba.njit(inline="always")
def _slope_le(a_n: INT, a_d: INT, b_n: INT, b_d: INT) -> boolean:
    # true iff a_n/a_d <= b_n/b_d
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
        return cx + x, cy + y


@numba.njit(nogil=True, cache=True)
def _compute_octant_core(
    opaque: np.uint8[:, :],
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
    Core integer-slope octant scan.
    - opaque: 2D uint8 array (1 = opaque), used only for bounds/fast checks (optional)
    - transparency: 2D float32 0..1 (1 = fully transparent). Tiles with transparency < 1
      are treated as blocking for slope updates (deterministic simple model).
    - visible: output uint8 mask written in-place (1 = visible)
    - dist: output int32 squared distance in tiles, -1 if not visible
    - side_bits: placeholder bitmask (currently not computed fully here)
    - cx, cy: origin coordinates
    - radius: integer radius (Euclidean)
    - octant: 0..7 octant index
    - opacity_threshold: float threshold; transparency <= threshold treated as blocker
    """
    h, w = opaque.shape
    radius_sq = radius * radius

    # initial integer slope pairs
    top_n = INT(1)
    top_d = INT(1)
    bottom_n = INT(0)
    bottom_d = INT(1)

    # source visible
    if 0 <= cx < w and 0 <= cy < h:
        visible[cy, cx] = 1
        dist[cy, cx] = 0

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
                visible[my, mx] = 1
                if dist[my, mx] == -1 or d < dist[my, mx]:
                    dist[my, mx] = d

            # treat tile as blocking for slope updates if transparency <= threshold
            if transparency[my, mx] <= opacity_threshold:
                # update top: half-cell top boundary (2*y + 1) / (2*x - 1)
                new_top_n = INT(2 * y + 1)
                new_top_d = INT(2 * x - 1) if (2 * x - 1) != 0 else INT(1)
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
    opaque: np.uint8[:, :],
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
    - Precondition: visible_out, dist_out, side_bits_out are preallocated and C-contiguous.
    - dist_out is initialized to -1 before call if desired (function leaves previously set negative).
    """
    # initialize outputs for this source (writing only positions we discover)
    h, w = opaque.shape
    # mark the origin
    if 0 <= cx < w and 0 <= cy < h:
        visible_out[cy, cx] = 1
        dist_out[cy, cx] = 0

    for octant in range(8):
        _compute_octant_core(
            opaque,
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
