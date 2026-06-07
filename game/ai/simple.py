"""Simple heuristic AI adapter.

Provides a very lightweight behaviour for entities that do not require
complex planning.  The entity simply attempts to move in a random
cardinal direction each turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def take_turn(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
    **kwargs,
) -> None:
    """Execute one turn for an entity using a simple heuristic."""
    if not hasattr(rng, "get_int"):
        raise TypeError("rng must provide get_int from GameRNG")
    dx, dy = _DIRECTIONS[rng.get_int(0, len(_DIRECTIONS) - 1)]

    moved = movement_system.try_move(entity_id, dx, dy, game_state)
    log.debug(
        "Simple AI entity processed",
        entity_id=entity_id,
        dx=dx,
        dy=dy,
        moved=moved,
    )
