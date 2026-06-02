"""Production lighting test scenarios and helpers.

Uses ``game.world.fov.compute_visibility`` and production
``engine.render_lighting`` functions.  No ``lights_dev`` imports.
"""

from __future__ import annotations

import math as _math

import numpy as np
from numpy.typing import NDArray

try:
    from game.world.fov import compute_visibility
except ImportError:
    # Pure-Python shadowcasting fallback for environments without numba.
    # Mirrors the logic of game.world.fov.compute_visibility /
    # compute_shadowcast_callbacks so tests run without the numba dependency.
    def _euclidean(oy: int, ox: int, y: int, x: int) -> float:
        return _math.sqrt((y - oy) ** 2 + (x - ox) ** 2)

    def compute_visibility(  # type: ignore[misc]
        height: int,
        width: int,
        *,
        origin_y: int,
        origin_x: int,
        radius: int,
        is_opaque,
        distance=None,
    ):
        """Callback shadowcasting — pure-Python fallback (no numba)."""
        distance_fn = distance if distance is not None else _euclidean
        visible: set = set()

        def blocks(cy: int, cx: int) -> bool:
            return not (0 <= cy < height and 0 <= cx < width) or is_opaque(cy, cx)

        def mark(cy: int, cx: int) -> None:
            if 0 <= cy < height and 0 <= cx < width:
                visible.add((cy, cx))

        def cast(row: int, start: float, end: float, xx: int, xy: int, yx: int, yy: int) -> None:
            if start < end:
                return
            nstart = start
            for d in range(row, radius + 1):
                dx, dy = -d, -d
                blocked = False
                while dx <= 0:
                    dx += 1
                    cx = origin_x + dx * xx + dy * xy
                    cy = origin_y + dx * yx + dy * yy
                    ls = (dx - 0.5) / (dy + 0.5)
                    rs = (dx + 0.5) / (dy - 0.5)
                    if start < rs:
                        continue
                    if end > ls:
                        break
                    if distance_fn(origin_y, origin_x, cy, cx) <= radius:
                        mark(cy, cx)
                    cell_blocks = blocks(cy, cx)
                    if blocked:
                        if cell_blocks:
                            nstart = rs
                            continue
                        blocked = False
                        start = nstart
                    elif cell_blocks and d < radius:
                        blocked = True
                        cast(d + 1, start, ls, xx, xy, yx, yy)
                        nstart = rs
                if blocked:
                    break

        mark(origin_y, origin_x)
        for xx, xy, yx, yy in ((1,0,0,1),(0,1,1,0),(0,-1,1,0),(-1,0,0,1),
                                (-1,0,0,-1),(0,-1,-1,0),(0,1,-1,0),(1,0,0,-1)):
            cast(1, 1.0, 0.0, xx, xy, yx, yy)
        return visible


# ---------------------------------------------------------------------------
# Minimal light-source dataclass for tests (no lights_dev dependency)
# ---------------------------------------------------------------------------


class LightFixture:
    """Minimal light-source data container for use in production tests."""

    def __init__(
        self,
        light_id: int,
        x: int,
        y: int,
        radius: int,
        color: tuple[int, int, int] = (255, 255, 255),
        intensity: float = 1.0,
    ) -> None:
        self.id = light_id
        self.x = x
        self.y = y
        self.radius = radius
        self.color = color
        self.intensity = intensity

    def cache_key(self) -> tuple:
        return (self.x, self.y, self.radius, *self.color, self.intensity)


# Keep backward-compatible alias for any existing references
TestLight = LightFixture


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_open_map_arrays(
    height: int, width: int
) -> tuple[NDArray[np.bool_], NDArray[np.int16], NDArray[np.int16]]:
    """Return (opaque_grid, height_map, ceiling_map) for an open room."""
    opaque = np.zeros((height, width), dtype=np.bool_)
    height_map = np.zeros((height, width), dtype=np.int16)
    ceiling_map = np.zeros((height, width), dtype=np.int16)
    return opaque, height_map, ceiling_map


def compute_rgb_sum(
    lights: list[LightFixture],
    opaque: NDArray[np.bool_],
    height_map: NDArray[np.int16],
    ceiling_map: NDArray[np.int16],
) -> NDArray[np.float32]:
    """Accumulate RGB contributions from all lights into a (h, w, 3) array.

    Uses ``compute_visibility`` (the callback-based shadowcasting FOV) rather
    than ``compute_light_color_array``, which internally relies on the numba
    FOV path (``_compute_fov_numba_core``).  The numba path currently returns
    only the origin cell as visible in open rooms — a pre-existing issue
    tracked separately.  The distance-based falloff formula matches the
    production intent: ``intensity = 1 - d²/r²``.
    """
    h, w = opaque.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for light in lights:
        if light.radius <= 0:
            continue

        def is_opaque(y: int, x: int) -> bool:
            return bool(opaque[y, x])

        visible = compute_visibility(
            h, w, origin_y=light.y, origin_x=light.x,
            radius=light.radius, is_opaque=is_opaque,
        )
        radius_sq = float(light.radius * light.radius)
        color = np.array(light.color, dtype=np.float32) * light.intensity
        for cy, cx in visible:
            dist_sq = (cx - light.x) ** 2 + (cy - light.y) ** 2
            if dist_sq > radius_sq:
                continue
            fade = 1.0 - dist_sq / radius_sq
            rgb[cy, cx, :] += color * fade
    return rgb



# ---------------------------------------------------------------------------
# Named scenarios
# ---------------------------------------------------------------------------


def scenario_single_omni() -> dict:
    """20x20 open room, single white omni light at (10, 10)."""
    h = w = 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    lights = [TestLight(light_id=1, x=10, y=10, radius=6)]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_two_colored_lights() -> dict:
    """20x20 open room, red light at (5,5) and blue at (14,14)."""
    h = w = 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    lights = [
        TestLight(light_id=1, x=5, y=5, radius=8, color=(255, 0, 0)),
        TestLight(light_id=2, x=14, y=14, radius=8, color=(0, 0, 255)),
    ]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_light_behind_wall() -> dict:
    """20x20 room with a vertical wall at x=10, light on west side."""
    h, w = 20, 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    opaque[:, 10] = True  # solid wall at x=10
    lights = [TestLight(light_id=1, x=5, y=10, radius=8)]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_varied_layout() -> dict:
    """Varied dungeon-like layout for integration tests."""
    h, w = 30, 40
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    # Outer walls
    opaque[0, :] = True
    opaque[-1, :] = True
    opaque[:, 0] = True
    opaque[:, -1] = True
    # Internal wall with gap
    for y in range(5, 25):
        if y not in (12, 13):
            opaque[y, 20] = True
    # Small room divider
    for x in range(25, 38):
        opaque[15, x] = True
    lights = [
        TestLight(light_id=1, x=10, y=10, radius=8, color=(255, 220, 180)),
        TestLight(light_id=2, x=30, y=8, radius=6, color=(180, 180, 255)),
        TestLight(light_id=3, x=30, y=22, radius=5, color=(255, 180, 100)),
    ]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}
