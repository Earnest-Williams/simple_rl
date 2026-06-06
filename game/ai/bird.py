"""Flying bird AI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np

    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()

# Allow diagonal flight directions
_DIRECTIONS = [
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (1, -1),
    (-1, 1),
    (-1, -1),
]


def _random_direction(rng: GameRNG) -> tuple[int, int]:
    if not hasattr(rng, "get_int"):
        raise TypeError("rng must provide get_int from GameRNG")
    idx = rng.get_int(0, len(_DIRECTIONS) - 1)
    return _DIRECTIONS[idx]


def take_turn(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
    **kwargs,
) -> None:
    """Execute one turn for a flying bird.

    Birds move quickly, attempting to traverse two tiles in the same
    direction each turn to simulate flight.
    """

    dx, dy = _random_direction(rng)
    moved = movement_system.try_move(entity_id, dx, dy, game_state)
    if moved:
        movement_system.try_move(entity_id, dx, dy, game_state)
    log.debug(
        "Bird AI entity processed",
        entity_id=entity_id,
        dx=dx,
        dy=dy,
        moved=moved,
    )
