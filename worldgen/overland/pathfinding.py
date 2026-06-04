from __future__ import annotations

import heapq
from dataclasses import dataclass
from math import hypot, isfinite, sqrt

import numpy as np

from worldgen.overland.actor_traversal import (
    ActorTraversalProfile,
    build_actor_cost_grid,
)
from worldgen.overland.schema import OverlandBundle


@dataclass(frozen=True, slots=True)
class OverlandRoute:
    profile: ActorTraversalProfile
    start: tuple[int, int]
    goal: tuple[int, int]
    path: tuple[tuple[int, int], ...]
    total_cost: float
    failure_reason: str | None = None

    @property
    def found(self) -> bool:
        return self.failure_reason is None


_NEIGHBORS: tuple[tuple[int, int, float], ...] = (
    (-1, 0, 1.0),
    (1, 0, 1.0),
    (0, -1, 1.0),
    (0, 1, 1.0),
    (-1, -1, sqrt(2.0)),
    (1, -1, sqrt(2.0)),
    (-1, 1, sqrt(2.0)),
    (1, 1, sqrt(2.0)),
)


def find_overland_path(
    bundle: OverlandBundle,
    start: tuple[int, int],
    goal: tuple[int, int],
    profile: ActorTraversalProfile,
) -> OverlandRoute:
    cost_grid = build_actor_cost_grid(bundle.tiles_df, profile)
    height, width = cost_grid.shape
    if not _in_bounds(start, width, height):
        return _failed(profile, start, goal, "start_out_of_bounds")
    if not _in_bounds(goal, width, height):
        return _failed(profile, start, goal, "goal_out_of_bounds")
    if not isfinite(float(cost_grid[start[1], start[0]])):
        return _failed(profile, start, goal, "start_blocked")
    if not isfinite(float(cost_grid[goal[1], goal[0]])):
        return _failed(profile, start, goal, "goal_blocked")

    frontier: list[tuple[float, float, tuple[int, int]]] = []
    heapq.heappush(frontier, (_heuristic(start, goal), 0.0, start))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], float] = {start: 0.0}

    while frontier:
        _priority, current_cost, current = heapq.heappop(frontier)
        if current == goal:
            return OverlandRoute(
                profile=profile,
                start=start,
                goal=goal,
                path=tuple(_reconstruct_path(came_from, goal)),
                total_cost=current_cost,
            )
        if current_cost > cost_so_far[current]:
            continue
        cx, cy = current
        for dx, dy, step_multiplier in _NEIGHBORS:
            nx = cx + dx
            ny = cy + dy
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            tile_cost = float(cost_grid[ny, nx])
            if not isfinite(tile_cost):
                continue
            next_coord = (nx, ny)
            new_cost = current_cost + tile_cost * step_multiplier
            if new_cost < cost_so_far.get(next_coord, np.inf):
                cost_so_far[next_coord] = new_cost
                priority = new_cost + _heuristic(next_coord, goal)
                came_from[next_coord] = current
                heapq.heappush(frontier, (priority, new_cost, next_coord))

    return _failed(profile, start, goal, "no_path")


def _failed(
    profile: ActorTraversalProfile,
    start: tuple[int, int],
    goal: tuple[int, int],
    reason: str,
) -> OverlandRoute:
    return OverlandRoute(
        profile=profile,
        start=start,
        goal=goal,
        path=tuple(),
        total_cost=float("inf"),
        failure_reason=reason,
    )


def _in_bounds(coord: tuple[int, int], width: int, height: int) -> bool:
    x, y = coord
    return 0 <= x < width and 0 <= y < height


def _heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
    return hypot(a[0] - b[0], a[1] - b[1])


def _reconstruct_path(
    came_from: dict[tuple[int, int], tuple[int, int] | None],
    goal: tuple[int, int],
) -> list[tuple[int, int]]:
    path = [goal]
    current = goal
    while came_from[current] is not None:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path
