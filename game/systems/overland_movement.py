from __future__ import annotations

from typing import TYPE_CHECKING

from game.world.overland_traversal import human_on_foot_can_enter_map

if TYPE_CHECKING:
    from game.game_state import GameState


def human_on_foot_can_enter(gs: GameState, x: int, y: int) -> bool:
    return human_on_foot_can_enter_map(gs.game_map, x, y)
