"""State-driven AI strategies.

Provides a small state machine that dispatches to behaviour functions
based on an entity's ``StrategyState``.  Strategies rely on perception
helpers to select targets and can be executed in parallel by the AI
scheduler.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Any

import structlog

from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from polars import series

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


def _move(entity_row: series, dx: int, dy: int, game_state: GameState) -> None:
    movement_system.try_move(entity_row["entity_id"], dx, dy, game_state)


def _get_priority_signal(
    entity_id: int, perception: Any
) -> tuple[str, tuple[int, int]] | None:
    """Return the highest priority signal type and its target coordinate."""
    if not hasattr(perception, "entity_facts"):
        return None

    fact = perception.entity_facts.get(int(entity_id))
    if not fact:
        return None

    if fact.visible_targets:
        first = fact.visible_targets[0]
        return "visual", (int(first.get("x")), int(first.get("y")))
    if fact.heard_source:
        return "audio", fact.heard_source
    if fact.scent_position:
        return "scent", fact.scent_position
    if fact.last_known_position:
        return "memory", fact.last_known_position

    return None


def charge_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    entity_id = int(entity_row["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    signal_type, target_pos = signal
    dx, dy = _step_towards(
        (int(entity_row.get("x")), int(entity_row.get("y"))), target_pos
    )
    _move(entity_row, dx, dy, game_state)


def home_behavior(entity_row: series, game_state: GameState) -> None:
    home_x = entity_row.get("home_x", 0)
    home_y = entity_row.get("home_y", 0)
    dx, dy = _step_towards((entity_row.get("x"), entity_row.get("y")), (home_x, home_y))
    _move(entity_row, dx, dy, game_state)


def flee_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    entity_id = int(entity_row["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    signal_type, target_pos = signal
    sx, sy = int(entity_row.get("x")), int(entity_row.get("y"))
    tx, ty = target_pos
    dx = 0 if tx == sx else (-1 if tx > sx else 1)
    dy = 0 if ty == sy else (-1 if ty > sy else 1)
    _move(entity_row, dx, dy, game_state)


def smart_kobold_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    hp = entity_row.get("hp", 1)
    max_hp = entity_row.get("max_hp", hp)
    if hp / max_hp < 0.3:
        flee_behavior(entity_row, game_state, perception)
    else:
        charge_behavior(entity_row, game_state, perception)


def dispatch_strategy(
    entity_row: series,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
    **kwargs,
) -> None:
    """Dispatch behaviour based on the entity's ``strategy_state``."""
    state = entity_row.get("strategy_state")
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
