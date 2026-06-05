"""State-driven AI strategies.

Provides a small state machine that dispatches to behaviour functions
based on an entity's ``StrategyState``.  Strategies rely on perception
helpers to select targets and can be executed in parallel by the AI
scheduler.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING

import structlog

from game.ai.contracts import (
    EntityRow,
    StructuredPerceptionLike,
    priority_signal,
    require_row_int,
    row_int,
    row_str,
)
from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()


class StrategyState(Enum):
    """Simple behaviour state machine for AI entities."""

    HOME = auto()
    CHARGE = auto()
    SMART_KOBOLD = auto()
    FLEE = auto()


def _step_towards(src: tuple[int, int], dst: tuple[int, int]) -> tuple[int, int]:
    """Return a single step from ``src`` towards ``dst``."""
    sx, sy = src
    dx = 0 if dst[0] == sx else (1 if dst[0] > sx else -1)
    dy = 0 if dst[1] == sy else (1 if dst[1] > sy else -1)
    return dx, dy


def _move(entity_row: EntityRow, dx: int, dy: int, game_state: GameState) -> None:
    movement_system.try_move(
        require_row_int(entity_row, "entity_id"), dx, dy, game_state
    )


def _get_priority_signal(
    entity_id: int, perception: StructuredPerceptionLike | None
) -> tuple[str, tuple[int, int]] | None:
    """Return the highest priority signal type and its target coordinate."""
    return priority_signal(int(entity_id), perception)


def charge_behavior(
    entity_row: EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    entity_id = require_row_int(entity_row, "entity_id")
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    _signal_type, target_pos = signal
    x = require_row_int(entity_row, "x")
    y = require_row_int(entity_row, "y")
    dx, dy = _step_towards((x, y), target_pos)
    _move(entity_row, dx, dy, game_state)


def home_behavior(entity_row: EntityRow, game_state: GameState) -> None:
    x = require_row_int(entity_row, "x")
    y = require_row_int(entity_row, "y")
    home_x = row_int(entity_row, "home_x") or 0
    home_y = row_int(entity_row, "home_y") or 0
    dx, dy = _step_towards((x, y), (home_x, home_y))
    _move(entity_row, dx, dy, game_state)


def flee_behavior(
    entity_row: EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    entity_id = require_row_int(entity_row, "entity_id")
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    _signal_type, target_pos = signal
    sx = require_row_int(entity_row, "x")
    sy = require_row_int(entity_row, "y")
    tx, ty = target_pos
    dx = 0 if tx == sx else (-1 if tx > sx else 1)
    dy = 0 if ty == sy else (-1 if ty > sy else 1)
    _move(entity_row, dx, dy, game_state)


def smart_kobold_behavior(
    entity_row: EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    hp = row_int(entity_row, "hp") or 1
    max_hp = row_int(entity_row, "max_hp") or hp
    if hp / max_hp < 0.3:
        flee_behavior(entity_row, game_state, perception)
    else:
        charge_behavior(entity_row, game_state, perception)


def dispatch_strategy(
    entity_row: EntityRow,
    game_state: GameState,
    rng: GameRNG,
    perception: StructuredPerceptionLike | None,
    **kwargs: object,
) -> None:
    """Dispatch behaviour based on the entity's ``strategy_state``."""
    del rng, kwargs
    state = row_str(entity_row, "strategy_state")
    if state is None:
        return
    try:
        strat = StrategyState[state.upper()]
    except KeyError:
        log.debug("Unknown strategy state", state=state)
        return
    if strat is StrategyState.CHARGE:
        charge_behavior(entity_row, game_state, perception)
    elif strat is StrategyState.HOME:
        home_behavior(entity_row, game_state)
    elif strat is StrategyState.SMART_KOBOLD:
        smart_kobold_behavior(entity_row, game_state, perception)
    elif strat is StrategyState.FLEE:
        flee_behavior(entity_row, game_state, perception)


__all__ = ["StrategyState", "dispatch_strategy"]
