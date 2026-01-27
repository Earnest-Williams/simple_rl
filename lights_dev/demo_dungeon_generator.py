"""
Demo dungeon generator for the lights_dev testbed.

This module is intentionally a small, deterministic, and clearly-labeled
temporary/demo generator used only by the R&D harness. It implements
dungeon_generate_map_u_shape(dungeon, rng) which main_game.py expects.

When integrating with the production pipeline, replace this with the
real production generator; this file is a convenience for local testing.
"""

from __future__ import annotations

from lights_dev import constants
from lights_dev.dungeon_data import Dungeon
from utils.game_rng import GameRNG

import numpy as np


def dungeon_generate_map_u_shape(dungeon: Dungeon, rng: GameRNG) -> Dungeon:
    """
    Fills `dungeon.tiles` with a simple deterministic U-shaped room for demo/testing.
    - Outer perimeter walls
    - Two vertical side walls and a bottom connecting wall produce a 'U'
    - A small top-center opening provides entrance to the U
    """
    _ = rng
    h, w = dungeon.height, dungeon.width

    # Make everything floor, then add intentional walls
    dungeon.tiles[:, :] = constants.FLOOR_ID

    # Perimeter walls
    dungeon.tiles[0, :] = constants.WALL_ID
    dungeon.tiles[-1, :] = constants.WALL_ID
    dungeon.tiles[:, 0] = constants.WALL_ID
    dungeon.tiles[:, -1] = constants.WALL_ID

    # Vertical side walls (a bit in from the sides)
    left = 2
    right = max(3, w - 3)
    for y in range(2, h - 2):
        dungeon.tiles[y, left] = constants.WALL_ID
        dungeon.tiles[y, right] = constants.WALL_ID

    # Bottom connecting wall to make the 'U' bottom
    dungeon.tiles[h - 3, left : right + 1] = constants.WALL_ID

    # Clear a small gap at top-center so the U is open upwards
    midx = w // 2
    dungeon.tiles[2, max(1, midx - 1) : min(w - 1, midx + 2)] = constants.FLOOR_ID

    return dungeon
