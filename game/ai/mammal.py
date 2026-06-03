"""Pack-hunting mammal AI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np

    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _random_direction(rng: GameRNG) -> tuple[int, int]:
    if not hasattr(rng, "get_int"):
        raise TypeError("rng must provide get_int from GameRNG")
    idx = rng.get_int(0, len(_DIRECTIONS) - 1)
    return _DIRECTIONS[idx]


def take_turn(
    entity_row: Any,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
    **kwargs: Any,
) -> None:
    """Execute one turn for a pack-hunting mammal."""
    entity_id = entity_row["entity_id"]
    x, y = entity_row["x"], entity_row["y"]

    player_pos = game_state.player_position
    if player_pos is not None:
        dxp = player_pos.x - x
        dyp = player_pos.y - y
        if abs(dxp) + abs(dyp) <= 5:
            dx = 0 if dxp == 0 else (1 if dxp > 0 else -1)
            dy = 0 if dyp == 0 else (1 if dyp > 0 else -1)
            moved = movement_system.try_move(entity_id, dx, dy, game_state)
            log.debug(
                "Mammal AI entity processed",
                entity_id=entity_id,
                dx=dx,
                dy=dy,
                moved=moved,
            )
            return

    dx, dy = _random_direction(rng)
    moved = movement_system.try_move(entity_id, dx, dy, game_state)
    log.debug(
        "Mammal AI entity processed",
        entity_id=entity_id,
        dx=dx,
        dy=dy,
        moved=moved,
    )
