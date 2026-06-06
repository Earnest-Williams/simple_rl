"""Stationary attacking plant AI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np

    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()


def take_turn(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
    **kwargs,
) -> None:
    """Execute one turn for a stationary attacking plant."""
    pos = game_state.entity_registry.xy_of(entity_id)
    if pos is None:
        return
    x, y = pos
    player_pos = game_state.player_position

    acted = False
    if (
        player_pos is not None
        and abs(player_pos.x - x) <= 1
        and abs(player_pos.y - y) <= 1
    ):
        from game.systems import combat_system

        combat_system.handle_melee_attack(entity_id, game_state.player_id, game_state)
        acted = True

    log.debug("Plant AI entity processed", entity_id=entity_id, acted=acted)
