from __future__ import annotations

import math
from typing import Final

import numba
import numpy as np

from lights_dev import constants
from lights_dev.dungeon_data import Dungeon

slope_spec: Final = [("y", numba.int64), ("x", numba.int64)]


@numba.experimental.jitclass(slope_spec)
class Slope:
    def __init__(self, y: int, x: int):
        self.y = y
        self.x = x

    def greater(self, y: int, x: int) -> bool:
        return self.y * x > self.x * y

    def greater_or_equal(self, y: int, x: int) -> bool:
        return self.y * x >= self.x * y

    def less(self, y: int, x: int) -> bool:
        return self.y * x < self.x * y


@numba.jit(nopython=True)
def _update_memory_fade_internal(
    current_time: np.float32,
    last_seen_time: np.ndarray,
    memory_intensity: np.ndarray,
    visible: np.ndarray,
    height: int,
    width: int,
) -> None:
    steepness = constants.MEMORY_SIGMOID_STEEPNESS
    midpoint = constants.MEMORY_SIGMOID_MIDPOINT
    for y in range(height):
        for x in range(width):
            intensity = memory_intensity[y, x]
            if intensity > 0.0 and not visible[y, x]:
                elapsed_time = current_time - last_seen_time[y, x]
                if elapsed_time < 0.0:
                    elapsed_time = 0.0
                exponent = steepness * (elapsed_time - midpoint)
                if exponent < 70.0:
                    denominator = 1.0 + math.exp(exponent)
                    new_intensity = 1.0 / denominator if denominator > 1e-9 else 0.0
                else:
                    new_intensity = 0.0
                memory_intensity[y, x] = max(0.0, new_intensity)


@numba.jit(nopython=True)
def _transform_coordinate(
    x: int, y: int, octant: int, origin: tuple[int, int]
) -> tuple[int, int]:
    ox, oy = origin
    nx, ny = ox, oy
    if octant == 0:
        nx += x
        ny -= y
    elif octant == 1:
        nx += y
        ny -= x
    elif octant == 2:
        nx -= y
        ny -= x
    elif octant == 3:
        nx -= x
        ny -= y
    elif octant == 4:
        nx -= x
        ny += y
    elif octant == 5:
        nx -= y
        ny += x
    elif octant == 6:
        nx += y
        ny += x
    elif octant == 7:
        nx += x
        ny += y
    return nx, ny


@numba.jit(nopython=True)
def _blocks_light_in_octant(
    x: int, y: int, octant: int, origin: tuple[int, int], dungeon_instance: Dungeon
) -> bool:
    nx, ny = _transform_coordinate(x, y, octant, origin)
    return dungeon_instance.blocks_light(nx, ny)


@numba.jit(nopython=True, fastmath=True)
def _calculate_top_y(
    x: int, top: Slope, octant: int, origin: tuple[int, int], dungeon_instance: Dungeon
) -> int:
    if top.x == 1:
        return x
    top_y = ((x * 2 - 1) * top.y + top.x) // (top.x * 2)
    if _blocks_light_in_octant(x, top_y, octant, origin, dungeon_instance):
        if top.greater_or_equal(top_y * 2 + 1, x * 2) and not _blocks_light_in_octant(
            x, top_y + 1, octant, origin, dungeon_instance
        ):
            top_y += 1
    else:
        ax = x * 2
        if _blocks_light_in_octant(x + 1, top_y + 1, octant, origin, dungeon_instance):
            ax += 1
        if top.greater(top_y * 2 + 1, ax):
            top_y += 1
    return top_y


@numba.jit(nopython=True, fastmath=True)
def _calculate_bottom_y(
    x: int,
    bottom: Slope,
    octant: int,
    origin: tuple[int, int],
    dungeon_instance: Dungeon,
) -> int:
    if bottom.y == 0:
        return 0
    bottom_y = ((x * 2 - 1) * bottom.y + bottom.x) // (bottom.x * 2)
    if (
        bottom.greater_or_equal(bottom_y * 2 + 1, x * 2)
        and _blocks_light_in_octant(x, bottom_y, octant, origin, dungeon_instance)
        and not _blocks_light_in_octant(
            x, bottom_y + 1, octant, origin, dungeon_instance
        )
    ):
        bottom_y += 1
    return bottom_y


@numba.jit(nopython=True)
def _mark_color_in_octant_array(
    x: int,
    y: int,
    octant: int,
    origin: tuple[int, int],
    dungeon_instance: Dungeon,
    target_rgb_sum_array: np.ndarray,
    weighted_r: float,
    weighted_g: float,
    weighted_b: float,
) -> None:
    nx, ny = _transform_coordinate(x, y, octant, origin)
    if 0 <= nx < dungeon_instance.width and 0 <= ny < dungeon_instance.height:
        target_rgb_sum_array[ny, nx, 0] += weighted_r
        target_rgb_sum_array[ny, nx, 1] += weighted_g
        target_rgb_sum_array[ny, nx, 2] += weighted_b


@numba.jit(nopython=True, fastmath=True, cache=True)
def _compute_octant_for_color(
    octant: int,
    origin: tuple[int, int],
    range_limit: int,
    x: int,
    top: Slope,
    bottom: Slope,
    dungeon_instance: Dungeon,
    target_rgb_sum_array: np.ndarray,
    base_r: int,
    base_g: int,
    base_b: int,
) -> None:
    current_top = Slope(top.y, top.x)
    current_bottom = Slope(bottom.y, bottom.x)
    effective_range = float(max(1.0, range_limit))
    effective_range_sq = effective_range * effective_range
    no_range = range_limit <= 0
    f_base_r = float(base_r)
    f_base_g = float(base_g)
    f_base_b = float(base_b)
    while x <= range_limit:
        if no_range:
            break
        top_y = _calculate_top_y(x, current_top, octant, origin, dungeon_instance)
        bottom_y = _calculate_bottom_y(
            x, current_bottom, octant, origin, dungeon_instance
        )
        was_opaque = -1
        world_check_x, _ = _transform_coordinate(x, 0, octant, origin)
        if not (0 <= world_check_x < dungeon_instance.width):
            break
        for y in range(top_y, bottom_y - 1, -1):
            distance = dungeon_instance.get_distance(x, y)
            if distance <= range_limit:
                is_opaque = _blocks_light_in_octant(
                    x, y, octant, origin, dungeon_instance
                )
                is_visible_in_los = is_opaque or (
                    (y != top_y or current_top.greater(y * 4 - 1, x * 4 + 1))
                    and (y != bottom_y or current_bottom.less(y * 4 + 1, x * 4 - 1))
                )
                if is_visible_in_los:
                    distance_sq = distance * distance
                    intensity_at_tile = max(
                        0.0, 1.0 - (distance_sq / effective_range_sq)
                    )
                    if intensity_at_tile > 0.0:
                        weighted_r = f_base_r * intensity_at_tile
                        weighted_g = f_base_g * intensity_at_tile
                        weighted_b = f_base_b * intensity_at_tile
                        _mark_color_in_octant_array(
                            x,
                            y,
                            octant,
                            origin,
                            dungeon_instance,
                            target_rgb_sum_array,
                            weighted_r,
                            weighted_g,
                            weighted_b,
                        )
                if is_opaque:
                    if was_opaque == 0:
                        nx, ny = x * 2, y * 2 + 1
                        if _blocks_light_in_octant(
                            x, y + 1, octant, origin, dungeon_instance
                        ):
                            nx -= 1
                        new_bottom = Slope(ny, nx)
                        if current_top.greater(ny, nx):
                            if y == bottom_y:
                                current_bottom = new_bottom
                                break
                            else:
                                _compute_octant_for_color(
                                    octant,
                                    origin,
                                    range_limit,
                                    x + 1,
                                    current_top,
                                    new_bottom,
                                    dungeon_instance,
                                    target_rgb_sum_array,
                                    base_r,
                                    base_g,
                                    base_b,
                                )
                        elif y == bottom_y:
                            break
                    was_opaque = 1
                else:
                    if was_opaque > 0:
                        nx, ny = x * 2, y * 2 + 1
                        if _blocks_light_in_octant(
                            x + 1, y + 1, octant, origin, dungeon_instance
                        ):
                            nx += 1
                        new_top = Slope(ny, nx)
                        if current_bottom.greater_or_equal(ny, nx):
                            return
                        current_top = new_top
                    was_opaque = 0
        if was_opaque != 0:
            break
        x += 1


@numba.jit(nopython=True)
def _mark_visible_boolean_in_octant_array(
    x: int,
    y: int,
    octant: int,
    origin: tuple[int, int],
    dungeon_instance: Dungeon,
    target_los_array: np.ndarray,
) -> None:
    nx, ny = _transform_coordinate(x, y, octant, origin)
    if 0 <= nx < dungeon_instance.width and 0 <= ny < dungeon_instance.height:
        target_los_array[ny, nx] = True


@numba.jit(nopython=True, fastmath=True, cache=True)
def _compute_octant_for_boolean_array(
    octant: int,
    origin: tuple[int, int],
    range_limit: int,
    x: int,
    top: Slope,
    bottom: Slope,
    dungeon_instance: Dungeon,
    target_los_array: np.ndarray,
) -> None:
    current_top = Slope(top.y, top.x)
    current_bottom = Slope(bottom.y, bottom.x)
    unlimited_range = range_limit < 0
    while unlimited_range or x <= range_limit:
        top_y = _calculate_top_y(x, current_top, octant, origin, dungeon_instance)
        bottom_y = _calculate_bottom_y(
            x, current_bottom, octant, origin, dungeon_instance
        )
        was_opaque = -1
        world_check_x, _ = _transform_coordinate(x, 0, octant, origin)
        if not (0 <= world_check_x < dungeon_instance.width):
            break
        for y in range(top_y, bottom_y - 1, -1):
            distance = dungeon_instance.get_distance(x, y)
            if unlimited_range or distance <= range_limit:
                is_opaque = _blocks_light_in_octant(
                    x, y, octant, origin, dungeon_instance
                )
                is_visible_in_los = is_opaque or (
                    (y != top_y or current_top.greater(y * 4 - 1, x * 4 + 1))
                    and (y != bottom_y or current_bottom.less(y * 4 + 1, x * 4 - 1))
                )
                if is_visible_in_los:
                    _mark_visible_boolean_in_octant_array(
                        x, y, octant, origin, dungeon_instance, target_los_array
                    )
                if is_opaque:
                    if was_opaque == 0:
                        nx, ny = x * 2, y * 2 + 1
                        if _blocks_light_in_octant(
                            x, y + 1, octant, origin, dungeon_instance
                        ):
                            nx -= 1
                        new_bottom = Slope(ny, nx)
                        if current_top.greater(ny, nx):
                            if y == bottom_y:
                                current_bottom = new_bottom
                                break
                            else:
                                _compute_octant_for_boolean_array(
                                    octant,
                                    origin,
                                    range_limit,
                                    x + 1,
                                    current_top,
                                    new_bottom,
                                    dungeon_instance,
                                    target_los_array,
                                )
                        elif y == bottom_y:
                            break
                    was_opaque = 1
                else:
                    if was_opaque > 0:
                        nx, ny = x * 2, y * 2 + 1
                        if _blocks_light_in_octant(
                            x + 1, y + 1, octant, origin, dungeon_instance
                        ):
                            nx += 1
                        new_top = Slope(ny, nx)
                        if current_bottom.greater_or_equal(ny, nx):
                            return
                        current_top = new_top
                    was_opaque = 0
        if was_opaque != 0:
            break
        x += 1
