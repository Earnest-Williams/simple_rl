"""
Demo dungeon generator for the lights_dev testbed.

This module is intentionally a small, deterministic, and clearly-labeled
temporary/demo generator used only by the R&D harness. It implements
`dungeon_generate_map_u_shape(dungeon, rng)` which main_game.py expects.

When integrating with the production pipeline, replace this with the
real production generator; this file is a convenience for local testing.

This is a demo module, so it is acceptable to keep its layout constants
here; they are defined at the top of the file for easy tuning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lights_dev import constants

# Layout constants (module-level; tweakable for the demo)
LEFT_WALL_OFFSET = 2
RIGHT_WALL_MARGIN = 3
BOTTOM_WALL_INSET = 3
TOP_OPENING_HALF_WIDTH = 1

# Minimum dimensions so the demo never indexes out of bounds
MIN_WIDTH = 7
MIN_HEIGHT = 5

if TYPE_CHECKING:
    from lights_dev.dungeon_data import Dungeon
    from utils.game_rng import GameRNG


def dungeon_generate_map_u_shape(dungeon: Dungeon, rng: GameRNG) -> Dungeon:
    """
    Deterministic demo U-shaped generator.

    The function is intentionally deterministic and does not use `rng`. The
    `rng` parameter is accepted only to match the production generator
    interface; if we later want small random variations, we can use rng to
    introduce them (e.g., small offsets in wall placement).
    """
    _ = rng
    w = int(dungeon.width)
    h = int(dungeon.height)

    if w < MIN_WIDTH or h < MIN_HEIGHT:
        message = (
            f"demo_dungeon_generator requires width >= {MIN_WIDTH} and height "
            f">= {MIN_HEIGHT}; got width={w} height={h}"
        )
        raise ValueError(message)

    # Compute side indices with clamping to keep them in [1, w-2]
    left = max(1, min(LEFT_WALL_OFFSET, w - 3))
    right = max(left + 1, min(w - RIGHT_WALL_MARGIN, w - 2))

    # Bottom connecting wall row, clamped to valid interior rows
    bottom_y = max(3, h - BOTTOM_WALL_INSET)

    # Make everything floor, then add intentional walls
    dungeon.tiles[:, :] = constants.FLOOR_ID

    # Perimeter walls
    dungeon.tiles[0, :] = constants.WALL_ID
    dungeon.tiles[-1, :] = constants.WALL_ID
    dungeon.tiles[:, 0] = constants.WALL_ID
    dungeon.tiles[:, -1] = constants.WALL_ID

    # Vertical side walls (a bit in from the sides)
    for y in range(2, h - 2):
        dungeon.tiles[y, left] = constants.WALL_ID
        dungeon.tiles[y, right] = constants.WALL_ID

    # Bottom connecting wall to make the 'U' bottom
    dungeon.tiles[bottom_y, left : right + 1] = constants.WALL_ID

    # Clear a small gap at top-center so the U is open upwards
    midx = w // 2
    open_from = max(1, midx - TOP_OPENING_HALF_WIDTH)
    open_to = min(w - 2, midx + TOP_OPENING_HALF_WIDTH)
    dungeon.tiles[2, open_from : open_to + 1] = constants.FLOOR_ID

    return dungeon
