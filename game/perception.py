from __future__ import annotations

import numpy as np

from game.world.game_map import GameMap


def apply_radius_perception(
    *,
    map_arr: np.ndarray,
    x: int,
    y: int,
    r: int,
    base_intensity: float,
    game_map: GameMap,
) -> None:
    """Apply a simple radial gradient.

    Note: This helper is for simple radial/debug/effect maps.
    It is NOT used for production sound/scent flow, which is managed
    by the pathfinding perception systems.
    """
    min_x, max_x = max(0, x - r), min(game_map.width, x + r + 1)
    min_y, max_y = max(0, y - r), min(game_map.height, y + r + 1)
    y_coords, x_coords = np.ogrid[min_y:max_y, min_x:max_x]
    dist = np.abs(x_coords - x) + np.abs(y_coords - y)
    value = np.maximum(base_intensity - dist, 0)
    map_arr[min_y:max_y, min_x:max_x] += value
