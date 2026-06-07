from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from game.game_state import GameState
from worldgen.overland.schema import RouteSegmentState

Point = tuple[int, int]


def _as_point(value: object) -> Point | None:
    if (
        isinstance(value, list | tuple)
        and len(value) == 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    ):
        return int(value[0]), int(value[1])
    return None


def _iter_dicts(value: object) -> Sequence[Mapping[str, Any]]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _route_state(value: object) -> RouteSegmentState | None:
    if isinstance(value, str):
        try:
            return RouteSegmentState[value]
        except KeyError:
            return None

    try:
        return RouteSegmentState(value)
    except (TypeError, ValueError):
        return None


def resolve_starting_contract(gs: GameState) -> Mapping[str, Any]:
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if metadata is None:
        return {}

    contract = getattr(metadata, "starting_contract", None)
    if isinstance(contract, Mapping):
        return contract

    return {}


def resolve_first_playable_route_segment(gs: GameState) -> Mapping[str, Any] | None:
    """Return the first playable route segment from the starting contract."""
    contract = resolve_starting_contract(gs)
    route_segments = _iter_dicts(contract.get("route_segments"))

    for segment in route_segments:
        if segment.get("route_id") == "ancient_road_harbor_to_inland_site":
            return segment

    return route_segments[0] if route_segments else None


def resolve_first_playable_target(gs: GameState) -> Point | None:
    """Resolve the target of the first playable route."""
    segment = resolve_first_playable_route_segment(gs)
    if segment is not None:
        point = _as_point(segment.get("to_point"))
        if point is not None:
            return point

    contract = resolve_starting_contract(gs)
    for site in _iter_dicts(contract.get("inland_sites")):
        point = _as_point(site.get("point"))
        if point is not None:
            return point

    for cave in _iter_dicts(contract.get("cave_refs")):
        point = _as_point(cave.get("point"))
        if point is not None:
            return point

    return None


def resolve_first_playable_route_endpoints(gs: GameState) -> list[Point]:
    """Return route endpoints when a full route path is unavailable."""
    segment = resolve_first_playable_route_segment(gs)
    if segment is None:
        return []

    route: list[Point] = []
    from_point = _as_point(segment.get("from_point"))
    to_point = _as_point(segment.get("to_point"))

    if from_point is not None:
        route.append(from_point)
    if to_point is not None and to_point != from_point:
        route.append(to_point)

    return route


def resolve_first_playable_route(gs: GameState) -> list[Point]:
    """Return the full route path, or endpoints if no full path is stored."""
    segment = resolve_first_playable_route_segment(gs)
    if segment is None:
        return []

    path = segment.get("path")
    if isinstance(path, list):
        route = [_as_point(point) for point in path]
        return [point for point in route if point is not None]

    return resolve_first_playable_route_endpoints(gs)


def resolve_first_playable_blockage(gs: GameState) -> Point | None:
    """Find the blockage associated with the first playable route."""
    contract = resolve_starting_contract(gs)
    segment = resolve_first_playable_route_segment(gs)
    route_id = segment.get("route_id") if segment is not None else None
    blockage_id = segment.get("blockage") if segment is not None else None

    for blockage in _iter_dicts(contract.get("blockages")):
        blocks_route = blockage.get("blocks_route")
        current_blockage_id = blockage.get("blockage_id")

        matches_route = route_id is not None and blocks_route == route_id
        matches_blockage = (
            blockage_id is not None and current_blockage_id == blockage_id
        )

        if matches_route or matches_blockage:
            point = _as_point(blockage.get("point"))
            if point is not None:
                return point

    for blockage in _iter_dicts(contract.get("blockages")):
        point = _as_point(blockage.get("point"))
        if point is not None:
            return point

    if (
        segment is not None
        and _route_state(segment.get("state")) == RouteSegmentState.BLOCKED
    ):
        path = segment.get("path")
        if isinstance(path, list) and path:
            point = _as_point(path[0])
            if point is not None:
                return point

        return _as_point(segment.get("from_point"))

    return None


def is_player_at_starting_port(gs: GameState, radius_squared: int = 100) -> bool:
    contract = resolve_starting_contract(gs)
    harbor = contract.get("harbor")
    if not isinstance(harbor, Mapping):
        return False

    harbor_point = _as_point(harbor.get("point"))
    if harbor_point is None:
        return False

    player_pos = gs.player_position
    if player_pos is None:
        return False

    hx, hy = harbor_point
    px, py = player_pos
    return (px - hx) ** 2 + (py - hy) ** 2 <= radius_squared


def resolve_cave_metadata_at(gs: GameState, x: int, y: int) -> Mapping[str, Any] | None:
    """Find and return cave metadata from the starting contract at the given coordinate."""
    contract = resolve_starting_contract(gs)
    for cave in _iter_dicts(contract.get("cave_refs")):
        point = _as_point(cave.get("point"))
        if point == (x, y):
            return cave
    return None


def first_playable_objective_text(gs: GameState) -> str | None:
    expedition = getattr(gs, "expedition", None)
    if expedition is None or not expedition.route_revealed:
        return None
    if expedition.active_objective_id != "follow_ancient_road":
        return None
    return "Objective: follow the ancient road to the first cave."


def first_playable_route_points(gs: GameState) -> list[Point]:
    expedition = getattr(gs, "expedition", None)
    if expedition is None or not expedition.route_revealed:
        return []
    route = resolve_first_playable_route(gs)
    if route:
        return route
    return resolve_first_playable_route_endpoints(gs)


def first_playable_route_target(gs: GameState) -> Point | None:
    route = first_playable_route_points(gs)
    if not route:
        return resolve_first_playable_target(gs)
    return route[-1]
