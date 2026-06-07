from __future__ import annotations

import numpy as np

from game.game_state import GameState
from worldgen.overland.schema import TraversalClass, Wetness


def human_on_foot_can_enter(gs: GameState, x: int, y: int) -> bool:
    game_map = gs.game_map
    if not game_map.in_bounds(x, y):
        return False

    metadata = getattr(game_map, "overland_metadata", None)
    if metadata is None:
        return game_map.is_walkable(x, y)

    traversal = int(metadata.traversal_class_grid[y, x])
    if traversal in {
        int(TraversalClass.BLOCKED),
        int(TraversalClass.SWIM_OR_BOAT),
    }:
        return False

    wetness = int(metadata.wetness_grid[y, x])
    if wetness == int(Wetness.DEEP_FLOODED):
        return False

    cost = float(metadata.movement_cost_grid[y, x])
    if not np.isfinite(cost):
        return False

    return game_map.is_walkable(x, y)
