"""Ambient spill lighting helpers for the lighting/FOV tool."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AmbientSpillLight:
    """Light data needed to compute the ambient spill post-pass."""

    color: tuple[int, int, int]
    reach_mask: np.ndarray
    shape_mask: np.ndarray | None
    visibility_out: np.ndarray
    enabled: bool = True
    extra_radius: int = 2
    strength: float = 0.15
    decay: float = 0.55
    max_rgb: float = 30.0


def compute_ambient_spill_rgb(
    lights: list[AmbientSpillLight],
    opaque_grid: np.ndarray,
    player_visible: np.ndarray,
    *,
    show_full_light_field: bool,
    enabled: bool,
) -> np.ndarray:
    """Compute weak room-aware floor spill from direct-lit floor cells."""
    height, width = opaque_grid.shape
    spill_rgb = np.zeros((height, width, 3), dtype=np.float32)
    if not enabled:
        return spill_rgb

    walkable = ~opaque_grid.astype(bool)
    player_visible_bool = player_visible.astype(bool, copy=False)

    for light in lights:
        if not light.enabled:
            continue
        if light.shape_mask is None:
            continue

        extra_radius = max(0, int(light.extra_radius))
        strength = max(0.0, min(1.0, float(light.strength)))
        if extra_radius <= 0 or strength <= 0.0:
            continue

        shape_mask = light.shape_mask.astype(np.float32, copy=False)
        visibility_out = light.visibility_out.astype(np.float32, copy=False)
        direct_floor = (
            walkable
            & light.reach_mask.astype(bool, copy=False)
            & (shape_mask > 0.0)
            & (visibility_out > 0.0)
        )
        if not bool(np.any(direct_floor)):
            continue

        visited = np.zeros((height, width), dtype=bool)
        distance = np.full((height, width), -1, dtype=np.int16)
        queue: deque[tuple[int, int]] = deque()

        ys, xs = np.nonzero(direct_floor)
        for y, x in zip(ys.tolist(), xs.tolist(), strict=True):
            visited[y, x] = True
            distance[y, x] = 0
            queue.append((x, y))

        while queue:
            x, y = queue.popleft()
            dist = int(distance[y, x])
            if dist >= extra_radius:
                continue

            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if nx < 0 or ny < 0 or nx >= width or ny >= height:
                    continue
                if visited[ny, nx] or not walkable[ny, nx]:
                    continue

                visited[ny, nx] = True
                distance[ny, nx] = dist + 1
                queue.append((nx, ny))

        lit = distance > 0
        if not show_full_light_field:
            lit &= player_visible_bool

        falloff = np.zeros((height, width), dtype=np.float32)
        falloff[lit] = strength * (
            max(0.0, min(1.0, float(light.decay)))
            ** distance[lit].astype(np.float32)
        )

        add = falloff[..., None] * np.array(light.color, dtype=np.float32)
        max_rgb = max(0.0, min(255.0, float(light.max_rgb)))
        if max_rgb > 0.0:
            np.clip(add, 0.0, max_rgb, out=add)
        else:
            add.fill(0.0)

        spill_rgb += add

    return spill_rgb
