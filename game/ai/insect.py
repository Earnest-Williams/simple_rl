"""Swarming insect AI adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np

    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()

_DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _nearest_ally(
    entity_id: int, x: int, y: int, gs: GameState
) -> tuple[int, int] | None:
    """Return direction towards nearest allied insect if any."""
    registry = gs.entity_registry
    
    # Find nearest insect ally using store accessors
    nearest_dist = float("inf")
    nearest_x = x
    nearest_y = y
    
    for idx in registry.active_indices():
        other_id = registry.entity_id_at(int(idx))
        if other_id == entity_id:
            continue
        
        other_ai_type = registry.ai_type_of(other_id)
        if other_ai_type != "insect":
            continue
        
        ox, oy = registry.xy_at(int(idx))
        dist = abs(ox - x) + abs(oy - y)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_x = ox
            nearest_y = oy
    
    if nearest_dist == float("inf"):
        return None
    
    dx = 0 if nearest_x == x else (1 if nearest_x > x else -1)
    dy = 0 if nearest_y == y else (1 if nearest_y > y else -1)
    return dx, dy


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
    """Execute one turn for a swarming insect."""
    pos = game_state.entity_registry.xy_of(entity_id)
    if pos is None:
        return
    x, y = pos

    dir_to_ally = _nearest_ally(entity_id, x, y, game_state)
    if dir_to_ally is not None:
        dx, dy = dir_to_ally
    else:
        dx, dy = _random_direction(rng)

    moved = movement_system.try_move(entity_id, dx, dy, game_state)
    log.debug(
        "Insect AI entity processed",
        entity_id=entity_id,
        dx=dx,
        dy=dy,
        moved=moved,
    )
