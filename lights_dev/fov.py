#!/usr/bin/env python
# Numba-based integer-slope shadowcasting FOV with per-tile side-bits.
# - integer slope comparisons (cross-multiplication)
# - half-cell slope representation for top-inclusive / bottom-exclusive tie-break
# - early exit when top <= bottom
# - simple transparency threshold model (t < 1 => treated as blocker for slope updates)
# - side bits per tile (N/NE/E/SE/S/SW/W/NW) accumulated across octants
from __future__ import annotations

import math
from typing import Final

import numba
import numpy as np
from numba import boolean, float32, uint8, uint32
from numpy.typing import NDArray

from lights_dev._numba_fov import (
    Slope,
    _compute_octant_for_boolean_array,
)
from lights_dev.dungeon_data import Dungeon

# Side bit definitions
# Must match lighting accumulator mapping:
# 1:N, 2:E, 4:S, 8:W, 16:NE, 32:SE, 64:SW, 128:NW
SIDE_N: Final[int] = 1 << 0  # North (bit 0)
SIDE_E: Final[int] = 1 << 1  # East (bit 1)
SIDE_S: Final[int] = 1 << 2  # South (bit 2)
SIDE_W: Final[int] = 1 << 3  # West (bit 3)
SIDE_NE: Final[int] = 1 << 4  # Northeast (bit 4)
SIDE_SE: Final[int] = 1 << 5  # Southeast (bit 5)
SIDE_SW: Final[int] = 1 << 6  # Southwest (bit 6)
SIDE_NW: Final[int] = 1 << 7  # Northwest (bit 7)

INT = numba.int64
_DUMMY_CELL_MASK: Final[NDArray[np.uint32]] = np.zeros((1, 1), dtype=np.uint32)


@numba.njit(inline="always")
def _slope_ge(a_n: int, a_d: int, b_n: int, b_d: int) -> bool:
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
    Compute an 8-bit mask for the direction from source to target.
    Bits: N, NE, E, SE, S, SW, W, NW.
    Rule:
      - if |dx| > |dy| => horizontal side (E if dx>0 else W)
      - if |dy| > |dx| => vertical side (S if dy>0 else N)
      - if |dx| == |dy| => diagonal side (NE/SE/SW/NW)
    """
    if dx == 0 and dy == 0:
        # source tile: set all sides
        return uint8(
            SIDE_N | SIDE_NE | SIDE_E | SIDE_SE | SIDE_S | SIDE_SW | SIDE_W | SIDE_NW
        )

    mask = uint8(0)
    absdx = abs(dx)
    absdy = abs(dy)

    if absdx > absdy:
        if dx > 0:
            mask |= SIDE_E
        elif dx < 0:
            mask |= SIDE_W
    elif absdy > absdx:
        if dy > 0:
            mask |= SIDE_S
        elif dy < 0:
            mask |= SIDE_N
    else:
        if dx > 0 and dy > 0:
            mask |= SIDE_SE
        elif dx > 0 and dy < 0:
            mask |= SIDE_NE
        elif dx < 0 and dy > 0:
            mask |= SIDE_SW
        elif dx < 0 and dy < 0:
            mask |= SIDE_NW

    return mask


@numba.njit(inline="always")
def _in_cone(
    dx: int,
    dy: int,
    use_angle: int,
    dir_x: float32,
    dir_y: float32,
    cos_half: float32,
) -> boolean:
    if use_angle == 0:
        return True
    if dx == 0 and dy == 0:
        return True
    dd = dx * dx + dy * dy
    if dd <= 0:
        return True
    inv_len = 1.0 / math.sqrt(float(dd))
    dot = (float(dx) * dir_x + float(dy) * dir_y) * inv_len
    return dot >= cos_half


@numba.njit(inline="always")
def _is_masked_transparent_for_blocking(
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: uint32,
    x: int,
    y: int,
) -> boolean:
    if use_mask == 0:
        return False
    return (cell_mask[y, x] & light_channels) == uint32(0)


@numba.njit(nogil=True, cache=True)
def _compute_octant_core_legacy(
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
    Core integer-slope octant scan with side-bit accumulation (legacy).
    """
    h, w = transparency.shape
    radius_sq = radius * radius

    top_n = INT(1)
    top_d = INT(1)
    bottom_n = INT(0)
    bottom_d = INT(1)

    for x in range(1, radius + 1):
        y_min = int((bottom_n * x + bottom_d - 1) // bottom_d)
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

                dx = mx - cx
                dy = my - cy
                mask = _compute_side_mask_from_vector(dx, dy)
                side_bits[my, mx] |= mask

            if transparency[my, mx] <= opacity_threshold:
                new_top_n = INT(2 * y + 1)
                new_top_d = INT(2 * x - 1)
                if _slope_ge(new_top_n, new_top_d, top_n, top_d):
                    top_n = new_top_n
                    top_d = new_top_d
                new_bottom_n = INT(2 * y - 1)
                new_bottom_d = INT(2 * x + 1)
                if _slope_le(new_bottom_n, new_bottom_d, bottom_n, bottom_d):
                    bottom_n = new_bottom_n
                    bottom_d = new_bottom_d

        if top_n * bottom_d <= bottom_n * top_d:
            break


@numba.njit(nogil=True, cache=True)
def _compute_octant_core_ex(
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: uint32,
    use_angle: int,
    dir_x: float32,
    dir_y: float32,
    cos_half: float32,
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
    Core integer-slope octant scan with side-bit accumulation and angle/mask support.
    """
    h, w = transparency.shape
    radius_sq = radius * radius

    top_n = INT(1)
    top_d = INT(1)
    bottom_n = INT(0)
    bottom_d = INT(1)

    for x in range(1, radius + 1):
        y_min = int((bottom_n * x + bottom_d - 1) // bottom_d)
        y_max = int((top_n * x) // top_d)
        if y_min > y_max:
            continue

        for y in range(y_min, y_max + 1):
            mx, my = _octant_map_coords(cx, cy, x, y, octant)
            if mx < 0 or my < 0 or mx >= w or my >= h:
                continue

            d = x * x + y * y
            if d > radius_sq:
                continue

            dx = mx - cx
            dy = my - cy

            if not _in_cone(dx, dy, use_angle, dir_x, dir_y, cos_half):
                continue

            visible[my, mx] = 1
            if dist[my, mx] == -1 or d < dist[my, mx]:
                dist[my, mx] = d

            mask = _compute_side_mask_from_vector(dx, dy)
            side_bits[my, mx] |= mask

            if _is_masked_transparent_for_blocking(
                cell_mask, use_mask, light_channels, mx, my
            ):
                continue

            if opaque[my, mx] != uint8(0) or transparency[my, mx] <= opacity_threshold:
                new_top_n = INT(2 * y + 1)
                new_top_d = INT(2 * x - 1)
                if _slope_ge(new_top_n, new_top_d, top_n, top_d):
                    top_n = new_top_n
                    top_d = new_top_d

                new_bottom_n = INT(2 * y - 1)
                new_bottom_d = INT(2 * x + 1)
                if _slope_le(new_bottom_n, new_bottom_d, bottom_n, bottom_d):
                    bottom_n = new_bottom_n
                    bottom_d = new_bottom_d

        if top_n * bottom_d <= bottom_n * top_d:
            break


@numba.njit(nogil=True, cache=True)
def _compute_fov_all_octants_legacy(
    transparency: np.float32[:, :],
    visible_out: np.uint8[:, :],
    dist_out: np.int32[:, :],
    side_bits_out: np.uint8[:, :],
    cx: int,
    cy: int,
    radius: int,
    opacity_threshold: float32,
) -> None:
    """
    Top-level API: compute FOV for all 8 octants.

    Precondition: visible_out, dist_out, side_bits_out are preallocated and
    C-contiguous. dist_out should be initialized to -1 by the caller if desired;
    this routine will only
    overwrite distances for discovered tiles.
    """
    h, w = transparency.shape
    # mark the origin
    if 0 <= cx < w and 0 <= cy < h:
        visible_out[cy, cx] = 1
        dist_out[cy, cx] = 0
        side_bits_out[cy, cx] |= uint8(
            SIDE_N | SIDE_NE | SIDE_E | SIDE_SE | SIDE_S | SIDE_SW | SIDE_W | SIDE_NW
        )

    for octant in range(8):
        _compute_octant_core_legacy(
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


@numba.njit(nogil=True, cache=True)
def _compute_fov_all_octants_ex(
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: uint32,
    use_angle: int,
    dir_x: float32,
    dir_y: float32,
    cos_half: float32,
    visible_out: np.uint8[:, :],
    dist_out: np.int32[:, :],
    side_bits_out: np.uint8[:, :],
    cx: int,
    cy: int,
    radius: int,
    opacity_threshold: float32,
) -> None:
    h, w = transparency.shape
    if 0 <= cx < w and 0 <= cy < h:
        visible_out[cy, cx] = 1
        dist_out[cy, cx] = 0
        side_bits_out[cy, cx] |= uint8(
            SIDE_N | SIDE_NE | SIDE_E | SIDE_SE | SIDE_S | SIDE_SW | SIDE_W | SIDE_NW
        )

    for octant in range(8):
        _compute_octant_core_ex(
            opaque,
            transparency,
            cell_mask,
            use_mask,
            light_channels,
            use_angle,
            dir_x,
            dir_y,
            cos_half,
            visible_out,
            dist_out,
            side_bits_out,
            cx,
            cy,
            radius,
            octant,
            opacity_threshold,
        )


@numba.njit(inline="always")
def _opacity_for_visibility(
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: uint32,
    x: int,
    y: int,
) -> float32:
    if use_mask != 0 and (cell_mask[y, x] & light_channels) == uint32(0):
        return float32(0.0)
    if opaque[y, x] != uint8(0):
        return float32(1.0)
    t = transparency[y, x]
    return float32(1.0) - float32(t)


@numba.njit(nogil=True, cache=True)
def _compute_visibility_subtractive_ex(
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: uint32,
    visible: np.uint8[:, :],
    visibility_out: np.float32[:, :],
    cx: int,
    cy: int,
) -> None:
    h, w = visible.shape

    for ty in range(h):
        for tx in range(w):
            if visible[ty, tx] == uint8(0):
                continue

            if tx == cx and ty == cy:
                visibility_out[ty, tx] = float32(1.0)
                continue

            x0 = cx
            y0 = cy
            x1 = tx
            y1 = ty

            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1

            cur_vis = float32(1.0)

            if dy <= dx:
                err = dx // 2
                x = x0
                y = y0
                while True:
                    if x == x1 and y == y1:
                        break

                    err -= dy
                    if err < 0:
                        y += sy
                        err += dx
                    x += sx

                    if x == x1 and y == y1:
                        break

                    if x < 0 or y < 0 or x >= w or y >= h:
                        cur_vis = float32(0.0)
                        break

                    cur_vis -= _opacity_for_visibility(
                        opaque, transparency, cell_mask, use_mask, light_channels, x, y
                    )
                    if cur_vis <= float32(0.0):
                        cur_vis = float32(0.0)
                        break
            else:
                err = dy // 2
                x = x0
                y = y0
                while True:
                    if x == x1 and y == y1:
                        break

                    err -= dx
                    if err < 0:
                        x += sx
                        err += dy
                    y += sy

                    if x == x1 and y == y1:
                        break

                    if x < 0 or y < 0 or x >= w or y >= h:
                        cur_vis = float32(0.0)
                        break

                    cur_vis -= _opacity_for_visibility(
                        opaque, transparency, cell_mask, use_mask, light_channels, x, y
                    )
                    if cur_vis <= float32(0.0):
                        cur_vis = float32(0.0)
                        break

            visibility_out[ty, tx] = cur_vis


def compute_fov_all_octants(*args: object) -> None:
    if (
        len(args) >= 7
        and isinstance(args[0], np.ndarray)
        and getattr(args[0], "dtype", None) == np.float32
        and isinstance(args[1], np.ndarray)
        and getattr(args[1], "dtype", None) == np.uint8
    ):
        transparency = args[0].astype(np.float32, copy=False)
        visible_out = args[1].astype(np.uint8, copy=False)
        dist_out = args[2].astype(np.int32, copy=False)
        side_bits_out = args[3].astype(np.uint8, copy=False)
        cx = int(args[4])
        cy = int(args[5])
        radius = int(args[6])
        opacity_threshold = float(args[7]) if len(args) >= 8 else 0.999999
        _compute_fov_all_octants_legacy(
            transparency,
            visible_out,
            dist_out,
            side_bits_out,
            cx,
            cy,
            radius,
            float32(opacity_threshold),
        )
        return

    if len(args) < 8:
        raise TypeError("compute_fov_all_octants: unsupported argument list.")

    opaque = args[0]
    transparency = args[1]
    if not isinstance(opaque, np.ndarray) or not isinstance(transparency, np.ndarray):
        raise TypeError(
            "compute_fov_all_octants: opaque and transparency must be arrays."
        )

    opaque_u8 = opaque.astype(np.uint8, copy=False)
    transparency_f32 = transparency.astype(np.float32, copy=False)

    use_mask = 0
    cell_mask = _DUMMY_CELL_MASK
    light_channels_u32 = uint32(0)
    idx = 2

    if isinstance(args[2], np.ndarray) and (
        getattr(args[2], "dtype", None) == np.uint32
    ):
        use_mask = 1
        cell_mask = args[2].astype(np.uint32, copy=False)
        light_channels_u32 = uint32(int(args[3]))
        idx = 4

    visible_out = args[idx].astype(np.uint8, copy=False)
    dist_out = args[idx + 1].astype(np.int32, copy=False)
    side_bits_out = args[idx + 2].astype(np.uint8, copy=False)
    idx += 3

    has_visibility = 0
    visibility_out = np.zeros((1, 1), dtype=np.float32)
    if isinstance(args[idx], np.ndarray) and (
        getattr(args[idx], "dtype", None) == np.float32
    ):
        has_visibility = 1
        visibility_out = args[idx].astype(np.float32, copy=False)
        idx += 1

    cx = int(args[idx])
    cy = int(args[idx + 1])
    radius = int(args[idx + 2])
    idx += 3

    use_angle = 0
    dir_x = float32(0.0)
    dir_y = float32(0.0)
    cos_half = float32(-1.0)

    if len(args) >= idx + 2:
        start_angle = float(args[idx])
        end_angle = float(args[idx + 1])
        half = 0.5 * (end_angle - start_angle)
        if half < 0.0:
            half = -half
        if half < math.pi:
            use_angle = 1
            direction = 0.5 * (start_angle + end_angle)
            dir_x = float32(math.cos(direction))
            dir_y = float32(math.sin(direction))
            cos_half = float32(math.cos(half))

    opacity_threshold = float32(0.999999)

    _compute_fov_all_octants_ex(
        opaque_u8,
        transparency_f32,
        cell_mask,
        use_mask,
        light_channels_u32,
        use_angle,
        dir_x,
        dir_y,
        cos_half,
        visible_out,
        dist_out,
        side_bits_out,
        cx,
        cy,
        radius,
        opacity_threshold,
    )

    if has_visibility == 1:
        _compute_visibility_subtractive_ex(
            opaque_u8,
            transparency_f32,
            cell_mask,
            use_mask,
            light_channels_u32,
            visible_out,
            visibility_out,
            cx,
            cy,
        )


def compute_los_into_boolean_array(
    origin: tuple[int, int],
    range_limit: int,
    dungeon_instance: Dungeon,
    target_los_array: NDArray[np.bool_],
) -> None:
    ox, oy = origin
    if not (0 <= ox < dungeon_instance.width and 0 <= oy < dungeon_instance.height):
        return
    target_los_array[oy, ox] = True
    start_top = Slope(1, 1)
    start_bottom = Slope(0, 1)
    for octant in range(8):
        _compute_octant_for_boolean_array(
            octant,
            origin,
            range_limit,
            1,
            start_top,
            start_bottom,
            dungeon_instance,
            target_los_array,
        )


class FOVSystem:
    @staticmethod
    def compute_fov(
        dungeon: Dungeon, origin: tuple[int, int], radius: int
    ) -> NDArray[np.bool_]:
        visible: NDArray[np.bool_] = np.zeros(
            (dungeon.height, dungeon.width), dtype=np.bool_
        )
        compute_los_into_boolean_array(origin, radius, dungeon, visible)
        return visible

    @staticmethod
    def precompile(dungeon: Dungeon, origin: tuple[int, int]) -> None:
        dummy_visible: NDArray[np.bool_] = np.zeros(
            (dungeon.height, dungeon.width), dtype=np.bool_
        )
        compute_los_into_boolean_array(origin, 0, dungeon, dummy_visible)
