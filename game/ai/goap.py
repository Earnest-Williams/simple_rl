"""Adapter for Goal-Oriented Action Planning (GOAP) based AI."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, TypeAlias

import numpy as np
import structlog

from game.ai.contracts import (
    GOAPPerception,
    is_structured_perception,
    priority_signal,
)
from game.systems import movement_system
from game.systems.pathfinding.flowfield import FlowFieldPathfinder
from game.world.game_map import TILE_TYPES

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()


# Cardinal directions used for simple movement heuristics when planning
# cannot determine a better action.

# Possible movement directions (x, y offsets)

DIRECTIONS: TypeAlias = list[tuple[int, int]]
GOAPAction: TypeAlias = Callable[
    [int, "GameState", "GameRNG", GOAPPerception], bool
]

directions: DIRECTIONS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _ensure_pathfinder(game_state: GameState) -> FlowFieldPathfinder:
    """Return a cached FlowFieldPathfinder for the current map.

    The pathfinder is (re)created if one does not exist yet or if the map
    tiles have changed. This ensures the flow field reflects current terrain
    whenever movement or targets change.
    """

    game_map = game_state.game_map
    tiles_hash = hash(game_map.tiles.tobytes())
    pf = getattr(game_state, "_pathfinder", None)
    if pf is None or getattr(game_state, "_pf_tiles_hash", None) != tiles_hash:
        walkable_ids = [tid for tid, t in TILE_TYPES.items() if t.walkable]
        passable = np.isin(game_map.tiles, walkable_ids)
        terrain_cost = np.ones(passable.shape, dtype=np.float32)
        pf = FlowFieldPathfinder(
            passable,
            terrain_cost,
            game_map.height_map,
            max_traversable_step=1,
        )
        game_state._pathfinder = pf
        game_state._pf_tiles_hash = tiles_hash
    return pf


def _action_move_attack(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: GOAPPerception,
) -> bool:
    """Basic behaviour: move toward priority signal or wander."""
    pos = game_state.entity_registry.xy_of(entity_id)
    if pos is None:
        return False
    x, y = pos

    move: tuple[int, int] | None = None
    target_pos: tuple[int, int] | None = None
    active_signal: str = "none"

    # Consume structured perception facts based on strict priority
    structured = perception if is_structured_perception(perception) else None
    signal = priority_signal(entity_id, structured)
    if signal is not None:
        active_signal, target_pos = signal

    # 1. Move towards highest-priority target
    if target_pos is not None:
        tx, ty = target_pos
        pathfinder = _ensure_pathfinder(game_state)
        # Note: compute_field expects (y, x) tuples
        pathfinder.compute_field([(ty, tx)])
        pdx, pdy = pathfinder.get_flow_vector(y, x)

        nx, ny = x + pdx, y + pdy
        if (pdx, pdy) == (0, 0) and (x, y) != (tx, ty):
            pdx, pdy = _fallback_cardinal_step(x, y, tx, ty, game_state)
        elif not (0 <= nx < game_state.map_width and 0 <= ny < game_state.map_height):
            pdx, pdy = _fallback_cardinal_step(x, y, tx, ty, game_state)
        move = (pdx, pdy)

    # 2. Else: Idle/Wander/Patrol
    if move is None:
        if not hasattr(rng, "get_int"):
            raise TypeError("rng must provide get_int from GameRNG")
        idx = rng.get_int(0, len(directions) - 1)
        move = directions[idx]

    dx, dy = move
    moved = movement_system.try_move(entity_id, dx, dy, game_state)

    log.debug(
        "GOAP AI entity processed",
        entity_id=entity_id,
        pos=(x, y),
        target_pos=target_pos,
        signal=active_signal,
        dx=dx,
        dy=dy,
        moved=moved,
    )
    return True


def _fallback_cardinal_step(
    x: int,
    y: int,
    tx: int,
    ty: int,
    game_state: GameState,
) -> tuple[int, int]:
    """Choose a simple cardinal step toward ``(tx, ty)`` when flow data stalls."""
    step_x = 0 if tx == x else (-1 if tx < x else 1)
    step_y = 0 if ty == y else (-1 if ty < y else 1)

    primary: list[tuple[int, int]]
    if abs(tx - x) >= abs(ty - y):
        primary = [(step_x, 0), (0, step_y)]
    else:
        primary = [(0, step_y), (step_x, 0)]

    for dx, dy in primary:
        nx = x + dx
        ny = y + dy
        if dx == dy == 0:
            continue
        if game_state.game_map.in_bounds(nx, ny) and game_state.game_map.is_walkable(
            nx, ny
        ):
            return dx, dy

    return 0, 0


def _action_seek_cover(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: GOAPPerception,
) -> bool:
    """Intermediate behaviour: attempt to move to a tile out of sight."""
    del rng
    pos = game_state.entity_registry.xy_of(entity_id)
    if pos is None:
        return False
    x, y = pos
    if is_structured_perception(perception):
        los_map = perception.los_map
    else:
        if perception is None:
            return False
        _noise_map, _scent_map, los_map = perception
    if not los_map[y, x]:
        return False
    for dx, dy in directions:
        nx, ny = x + dx, y + dy
        if (
            0 <= nx < los_map.shape[1]
            and 0 <= ny < los_map.shape[0]
            and not los_map[ny, nx]
        ):
            movement_system.try_move(entity_id, dx, dy, game_state)
            return True
    return False


def _action_coordinate(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: GOAPPerception,
) -> bool:
    """Advanced behaviour: coordinate with allies (placeholder)."""
    del rng, perception
    # For now we simply record that coordination was attempted.
    game_state.last_coordination = entity_id
    return True


ACTION_TIERS: list[list[GOAPAction]] = [
    [_action_move_attack],
    [_action_seek_cover, _action_move_attack],
    [_action_coordinate, _action_seek_cover, _action_move_attack],
]


def take_turn(
    entity_id: int,
    game_state: GameState,
    rng: GameRNG,
    perception: GOAPPerception,
    plan_depth: int = 1,
    **kwargs: object,
) -> None:
    """Execute one turn for an entity using the GOAP AI system.

    Parameters
    ----------
    plan_depth:
        Determines the level of intelligence available to the agent. Higher
        values unlock more sophisticated actions.
    """
    tier = ACTION_TIERS[min(max(plan_depth, 1), len(ACTION_TIERS)) - 1]
    for action in tier:
        if action(entity_id, game_state, rng, perception):
            game_state._last_goap_action = action.__name__
            return


def get_goap_adapter(level: int) -> Callable:
    """Return a GOAP adapter function bound to ``plan_depth`` ``level``."""

    return partial(take_turn, plan_depth=level)
