from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from game.game_state import GameState


def resolve_starting_contract(gs: GameState) -> Mapping[str, Any]:
    """Extract the starting_contract dictionary from the overland_metadata."""
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if not metadata:
        return {}
    contract: Mapping[str, Any] | None = getattr(metadata, "starting_contract", None)
    return contract or {}


def resolve_first_playable_target(gs: GameState) -> tuple[int, int] | None:
    """Find the cave or inland site objective."""
    contract = resolve_starting_contract(gs)

    # Priority 1: Cave references
    cave_refs = contract.get("cave_refs")
    if isinstance(cave_refs, list) and cave_refs:
        first_cave = cave_refs[0]
        if isinstance(first_cave, dict) and "point" in first_cave:
            point = first_cave["point"]
            if isinstance(point, (list, tuple)) and len(point) == 2:
                return int(point[0]), int(point[1])

    # Fallback: Inland sites
    inland_sites = contract.get("inland_sites")
    if isinstance(inland_sites, list) and inland_sites:
        first_inland = inland_sites[0]
        if isinstance(first_inland, dict) and "point" in first_inland:
            point = first_inland["point"]
            if isinstance(point, (list, tuple)) and len(point) == 2:
                return int(point[0]), int(point[1])

    return None


def resolve_first_playable_route(gs: GameState) -> list[tuple[int, int]]:
    """Return the list of coordinates for the route to the first playable target."""
    contract = resolve_starting_contract(gs)
    route_segments = contract.get("route_segments")

    if not isinstance(route_segments, list) or not route_segments:
        return []

    # For the first playable loop, we simply take the path of the first segment
    # connected to the starting port. The contract structure guarantees the road exists.
    first_segment = route_segments[0]
    if isinstance(first_segment, dict):
        if "path" in first_segment and isinstance(first_segment["path"], list):
            path = first_segment["path"]
            return [(int(p[0]), int(p[1])) for p in path]
        # Fallback to from_point and to_point
        from_p = first_segment.get("from_point")
        to_p = first_segment.get("to_point")
        route = []
        if isinstance(from_p, (list, tuple)) and len(from_p) == 2:
            route.append((int(from_p[0]), int(from_p[1])))
        if isinstance(to_p, (list, tuple)) and len(to_p) == 2:
            route.append((int(to_p[0]), int(to_p[1])))
        return route

    return []


def resolve_first_playable_blockage(gs: GameState) -> tuple[int, int] | None:
    """Find a clearable blockage coordinate on the route."""
    contract = resolve_starting_contract(gs)

    # Try explicit feature references first
    clearable_blockage = contract.get("clearable_blockage")
    if isinstance(clearable_blockage, dict) and "point" in clearable_blockage:
        point = clearable_blockage["point"]
        if isinstance(point, (list, tuple)) and len(point) == 2:
            return int(point[0]), int(point[1])

    blockages = contract.get("blockages")
    if isinstance(blockages, list) and blockages:
        first = blockages[0]
        if isinstance(first, dict) and "point" in first:
            point = first["point"]
            if isinstance(point, (list, tuple)) and len(point) == 2:
                return int(point[0]), int(point[1])

    # Fallback: iterate over route segments to find a BLOCKED segment endpoint
    route_segments = contract.get("route_segments")
    if isinstance(route_segments, list):
        for segment in route_segments:
            if isinstance(segment, dict) and segment.get("state") == "BLOCKED":
                if (
                    "path" in segment
                    and isinstance(segment["path"], list)
                    and segment["path"]
                ):
                    point = segment["path"][0]
                    return int(point[0]), int(point[1])
                from_p = segment.get("from_point")
                if isinstance(from_p, (list, tuple)) and len(from_p) == 2:
                    return int(from_p[0]), int(from_p[1])

    return None


def is_player_at_starting_port(gs: GameState, radius_squared: int = 100) -> bool:
    """Check if the player is within the starting port (harbor)."""
    contract = resolve_starting_contract(gs)
    harbor = contract.get("harbor")

    if not isinstance(harbor, dict) or "point" not in harbor:
        return False

    point = harbor["point"]
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        return False

    hx, hy = int(point[0]), int(point[1])

    player_pos = gs.player_position
    if player_pos is None:
        return False

    px, py = player_pos
    dist2 = (px - hx) ** 2 + (py - hy) ** 2

    return dist2 <= radius_squared
