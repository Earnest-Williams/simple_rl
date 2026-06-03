"""Production FOV test scenarios and helpers.

Uses ``game.world.fov.compute_visibility`` — the production shadowcasting
implementation.  No ``lights_dev`` imports.
"""

from __future__ import annotations

import math as _math
from collections.abc import Iterator

import numpy as np
from numpy.typing import NDArray

# Fallback removed
from game.world.fov import compute_visibility


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_open_room(height: int, width: int) -> NDArray[np.bool_]:
    """Return an all-transparent (no walls) boolean opaque grid."""
    return np.zeros((height, width), dtype=np.bool_)


def make_walled_room(height: int, width: int) -> NDArray[np.bool_]:
    """Return a grid whose border cells are opaque walls."""
    opaque = np.zeros((height, width), dtype=np.bool_)
    opaque[0, :] = True
    opaque[-1, :] = True
    opaque[:, 0] = True
    opaque[:, -1] = True
    return opaque


def fov_from_transparency(
    transparency: NDArray[np.float32],
    cy: int,
    cx: int,
    radius: int,
) -> set[tuple[int, int]]:
    """Run production FOV given a transparency grid (1.0=open, 0.0=wall).

    Returns the set of visible ``(y, x)`` pairs, including the origin.
    """
    h, w = transparency.shape

    def is_opaque(y: int, x: int) -> bool:
        return bool(transparency[y, x] < 0.5)

    return compute_visibility(
        h, w, origin_y=cy, origin_x=cx, radius=radius, is_opaque=is_opaque
    )


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
    """Yield intermediate ``(x, y)`` cells along a Bresenham line.

    The endpoint ``(x1, y1)`` is **not** yielded; the origin ``(x0, y0)`` is
    also not yielded.  This is useful for detecting blockers between two cells.
    """
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    x, y = x0, y0
    if dy <= dx:
        err = dx // 2
        while True:
            x += sx
            err -= dy
            if err < 0:
                y += sy
                err += dx
            if x == x1 and y == y1:
                break
            yield x, y
    else:
        err = dy // 2
        while True:
            y += sy
            err -= dx
            if err < 0:
                x += sx
                err += dy
            if x == x1 and y == y1:
                break
            yield x, y


# ---------------------------------------------------------------------------
# Named scenarios (data only — no lights_dev dependency)
# ---------------------------------------------------------------------------


def scenario_empty_room() -> dict:
    """11x11 open room with source at center, radius 3."""
    h = w = 11
    transparency = np.ones((h, w), dtype=np.float32)
    return {"transparency": transparency, "cy": 5, "cx": 5, "radius": 3}


def scenario_single_blocker() -> dict:
    """11x11 room with one blocker directly east of source; source at (5,5)."""
    h = w = 11
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[5, 7] = 0.0  # wall at (y=5, x=7)
    return {"transparency": transparency, "cy": 5, "cx": 5, "radius": 6}


def scenario_diagonal_blocker() -> dict:
    """15x15 room with a blocker at the southeast diagonal from source."""
    h = w = 15
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[9, 9] = 0.0  # southeast blocker from (7,7)
    return {"transparency": transparency, "cy": 7, "cx": 7, "radius": 10}


def scenario_u_shaped_corridor() -> dict:
    """A U-shaped room that tests indirect lighting paths."""
    h, w = 20, 30
    transparency = np.ones((h, w), dtype=np.float32)
    # Vertical wall in the middle with a gap at the bottom
    for y in range(0, 15):
        transparency[y, 15] = 0.0
    return {"transparency": transparency, "cy": 5, "cx": 5, "radius": 20}


def scenario_overlapping_lights() -> list[dict]:
    """Two light sources in the same open room for multi-source tests."""
    h, w = 20, 20
    transparency = np.ones((h, w), dtype=np.float32)
    return [
        {"transparency": transparency, "cy": 5, "cx": 5, "radius": 8},
        {"transparency": transparency, "cy": 14, "cx": 14, "radius": 8},
    ]


def scenario_thin_wall_gap() -> dict:
    """Room with a thin vertical wall that has a single-cell gap."""
    h, w = 15, 20
    transparency = np.ones((h, w), dtype=np.float32)
    for y in range(h):
        if y != 7:  # gap at y=7
            transparency[y, 10] = 0.0
    return {"transparency": transparency, "cy": 7, "cx": 3, "radius": 15}
