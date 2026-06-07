"""game/world/los.py

Numba-accelerated Bresenham line of sight helper.
This routine is shared by AI and pathfinding modules to check
if two points on a grid have a clear view between them.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray
from utils.los.los_wrapper import los_many as _los_many

try:  # Optional Numba acceleration
    import numba

    njit = numba.njit
except Exception:  # pragma: no cover - fallback when Numba isn't available

    def njit(*args, **kwargs):  # type: ignore
        def wrapper(func):
            return func

        return wrapper


@njit(cache=True)
def line_of_sight(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    transparency_map: np.ndarray,
) -> bool:
    """Return ``True`` if a clear line exists between two points.

    The function expects coordinates in ``(x, y)`` order to align with
    typical Cartesian usage elsewhere in the codebase and tests.

    """

    height, width = transparency_map.shape
    if not (
        0 <= x0 < width and 0 <= y0 < height and 0 <= x1 < width and 0 <= y1 < height
    ):
        return False

    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy

    xi, yi = x0, y0
    n_steps = max(dx, -dy)

    for _ in range(n_steps):
        e2 = 2 * err
        next_xi, next_yi = xi, yi
        step_x = False
        step_y = False

        if e2 >= dy:
            if xi == x1:
                break
            err += dy
            next_xi += sx
            step_x = True

        if e2 <= dx:
            if yi == y1:
                break
            err += dx
            next_yi += sy
            step_y = True

        check_x, check_y = xi, yi
        if step_x:
            check_x += sx
        if step_y:
            check_y += sy

        if not transparency_map[check_y, check_x]:
            return False

        xi, yi = check_x, check_y
        if xi == x1 and yi == y1:
            break

    return True


def line_of_sight_many_u8(
    starts_x: NDArray[np.int32],
    starts_y: NDArray[np.int32],
    ends_x: NDArray[np.int32],
    ends_y: NDArray[np.int32],
    transparency_map: NDArray[np.bool_] | NDArray[np.uint8],
) -> NDArray[np.uint8]:
    """Return batched line-of-sight results as uint8 values.

    Output uses 0 for blocked/not visible and 1 for clear/visible.
    Coordinates are in x/y order, matching line_of_sight().
    """
    return _los_many(
        starts_x,
        starts_y,
        ends_x,
        ends_y,
        np.ascontiguousarray(transparency_map, dtype=np.uint8),
    )


__all__ = ["line_of_sight", "line_of_sight_many_u8"]
