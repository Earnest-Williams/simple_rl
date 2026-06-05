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


def _move(entity_id: int, dx: int, dy: int, game_state: GameState) -> None:
    movement_system.try_move(entity_id, dx, dy, game_state)


def _get_priority_signal(
    entity_id: int, perception: StructuredPerceptionLike | None
) -> tuple[str, tuple[int, int]] | None:
    """Return the highest priority signal type and its target coordinate."""
    return priority_signal(int(entity_id), perception)


def charge_behavior(
    entity_id: int | EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    if not isinstance(entity_id, int):
        entity_id = int(entity_id["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    _signal_type, target_pos = signal
    registry = game_state.entity_registry
    pos = registry.xy_of(entity_id)
    if pos is None:
        return
    x, y = pos
    dx, dy = _step_towards((x, y), target_pos)
    _move(entity_id, dx, dy, game_state)


def home_behavior(entity_id: int | EntityRow, game_state: GameState) -> None:
    if not isinstance(entity_id, int):
        entity_id = int(entity_id["entity_id"])
    registry = game_state.entity_registry
    pos = registry.xy_of(entity_id)
    if pos is None:
        return
    x, y = pos
    home_x = registry.get_entity_component(entity_id, "home_x") or 0
    home_y = registry.get_entity_component(entity_id, "home_y") or 0
    dx, dy = _step_towards((x, y), (home_x, home_y))
    _move(entity_id, dx, dy, game_state)


def flee_behavior(
    entity_id: int | EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    if not isinstance(entity_id, int):
        entity_id = int(entity_id["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    _signal_type, target_pos = signal
    registry = game_state.entity_registry
    pos = registry.xy_of(entity_id)
    if pos is None:
        return
    sx, sy = pos
    tx, ty = target_pos
    dx = 0 if tx == sx else (-1 if tx > sx else 1)
    dy = 0 if ty == sy else (-1 if ty > sy else 1)
    _move(entity_id, dx, dy, game_state)


def smart_kobold_behavior(
    entity_id: int | EntityRow,
    game_state: GameState,
    perception: StructuredPerceptionLike | None,
) -> None:
    if not isinstance(entity_id, int):
        entity_id = int(entity_id["entity_id"])
    registry = game_state.entity_registry
    hp = registry.hp_of(entity_id)
    if hp is None:
        hp = 1
    max_hp = registry.max_hp_of(entity_id)
    if max_hp is None or max_hp <= 0:
        max_hp = hp
    if hp / max_hp < 0.3:
        flee_behavior(entity_id, game_state, perception)
    else:
        charge_behavior(entity_id, game_state, perception)


def dispatch_strategy(
    entity_id: int | EntityRow,
    game_state: GameState,
    rng: GameRNG,
    perception: StructuredPerceptionLike | None,
    **kwargs: object,
) -> None:
    """Dispatch behaviour based on the entity's ``strategy_state``."""
    del rng, kwargs
    if not isinstance(entity_id, int):
        entity_id = int(entity_id["entity_id"])
    registry = game_state.entity_registry
    state = registry.strategy_state_of(entity_id)
    if state is None:
        return
    try:
        strat = StrategyState[state.upper()]
    except KeyError:
        log.debug("Unknown strategy state", state=state)
        return
    if strat is StrategyState.CHARGE:
        charge_behavior(entity_id, game_state, perception)
    elif strat is StrategyState.HOME:
        home_behavior(entity_id, game_state)
    elif strat is StrategyState.SMART_KOBOLD:
        smart_kobold_behavior(entity_id, game_state, perception)
    elif strat is StrategyState.FLEE:
        flee_behavior(entity_id, game_state, perception)


__all__ = ["StrategyState", "dispatch_strategy"]
