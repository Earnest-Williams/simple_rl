"""Production lighting test scenarios and helpers.

Uses production ``engine.render_lighting`` functions. No ``lights_dev`` imports.
"""

from __future__ import annotations

from typing import TypeAlias, TypedDict

import numpy as np
from numpy.typing import NDArray

from engine.render_lighting import _compute_single_light_contribution


class LightingScenario(TypedDict):
    """Typed dictionary for production lighting test scenes."""

    opaque: NDArray[np.bool_]
    height_map: NDArray[np.int16]
    ceiling_map: NDArray[np.int16]
    lights: list[LightFixture]


LightCacheKey: TypeAlias = tuple[int, int, int, int, int, int, float]


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

    def cache_key(self) -> LightCacheKey:
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
    ceiling_map = np.full((height, width), 10, dtype=np.int16)
    return opaque, height_map, ceiling_map


def compute_rgb_sum(
    lights: list[LightFixture],
    opaque: NDArray[np.bool_],
    height_map: NDArray[np.int16],
    ceiling_map: NDArray[np.int16],
) -> NDArray[np.float32]:
    """Accumulate production RGB contributions from all lights."""
    h, w = opaque.shape
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    for light in lights:
        contribution = _compute_single_light_contribution(
            origin_x=light.x,
            origin_y=light.y,
            radius=light.radius,
            color_rgb=light.color,
            intensity=light.intensity,
            opaque_grid=opaque,
            scene_h=h,
            scene_w=w,
            height_map=height_map,
            ceiling_map=ceiling_map,
        )
        rgb += contribution
    return rgb


# ---------------------------------------------------------------------------
# Named scenarios
# ---------------------------------------------------------------------------


def scenario_single_omni() -> LightingScenario:
    """20x20 open room, single white omni light at (10, 10)."""
    h = w = 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    lights = [TestLight(light_id=1, x=10, y=10, radius=6)]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_two_colored_lights() -> LightingScenario:
    """20x20 open room, red light at (5,5) and blue at (14,14)."""
    h = w = 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    lights = [
        TestLight(light_id=1, x=5, y=5, radius=8, color=(255, 0, 0)),
        TestLight(light_id=2, x=14, y=14, radius=8, color=(0, 0, 255)),
    ]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_light_behind_wall() -> LightingScenario:
    """20x20 room with a vertical wall at x=10, light on west side."""
    h, w = 20, 20
    opaque, hmap, cmap = make_open_map_arrays(h, w)
    opaque[:, 10] = True  # solid wall at x=10
    lights = [TestLight(light_id=1, x=5, y=10, radius=8)]
    return {"opaque": opaque, "height_map": hmap, "ceiling_map": cmap, "lights": lights}


def scenario_varied_layout() -> LightingScenario:
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
