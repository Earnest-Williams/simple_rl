# game/systems/repair.py
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from common.constants import Material
from game.world.game_map import TILE_ID_FLOOR
from worldgen.overland.schema import EvidenceTag, RouteSegmentState, TraversalClass

if TYPE_CHECKING:
    from game.game_state import GameState

log = structlog.get_logger()


def clear_blockage_at(gs: GameState, x: int, y: int) -> bool:
    """Clear a route blockage at the specified coordinate.

    Mutates GameMap walkability, updates sidecar metadata route state,
    and updates movement cost and material grids.
    """
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if metadata is None:
        gs.add_message(
            "No overland metadata available to perform repairs.", (255, 100, 100)
        )
        return False

    contract = getattr(metadata, "starting_contract", {}) or {}
    blockages = contract.get("blockages", [])

    blockage = None
    for blk in blockages:
        if blk.get("point") == [x, y]:
            blockage = blk
            break

    if blockage is None:
        gs.add_message("There is no clearable blockage here.", (150, 150, 150))
        return False

    if blockage.get("state") == "cleared":
        gs.add_message("This blockage has already been cleared.", (150, 150, 150))
        return False

    # Mark blockage as cleared
    blockage["state"] = "cleared"

    # Propagate to route segment
    route_id = blockage.get("blocks_route")
    if route_id:
        for seg in getattr(metadata, "route_segments", []) or []:
            if seg.get("route_id") == route_id:
                seg["state"] = int(RouteSegmentState.REPAIRED)
                seg["evidence_tags"] = seg.get("evidence_tags", []) + [
                    int(EvidenceTag.RECENT_REPAIR)
                ]
                seg["last_modified"] = gs.turn_count
                log.info(
                    "Route segment repaired", route_id=route_id, turn=gs.turn_count
                )

    # Update GameMap walkability and transparency
    gs.game_map.tiles[y, x] = TILE_ID_FLOOR
    gs.game_map.update_tile_transparency()

    # Update sidecar grids
    if hasattr(metadata, "material_grid") and metadata.material_grid is not None:
        metadata.material_grid[y, x] = int(Material.ROAD)
    if (
        hasattr(metadata, "movement_cost_grid")
        and metadata.movement_cost_grid is not None
    ):
        metadata.movement_cost_grid[y, x] = 1.0
    if (
        hasattr(metadata, "traversal_class_grid")
        and metadata.traversal_class_grid is not None
    ):
        metadata.traversal_class_grid[y, x] = int(TraversalClass.NORMAL)

    # Update Expedition State if this was the first playable blockage
    if hasattr(gs, "expedition") and gs.expedition:
        from game.expedition.resolvers import resolve_first_playable_blockage

        blockage_pt = resolve_first_playable_blockage(gs)
        if blockage_pt is not None and blockage_pt == (x, y):
            gs.expedition.blockage_cleared = True

    # Print success message to log
    gs.add_message(
        "You clear enough of the blockage to reopen the road.", (100, 255, 100)
    )

    # Trigger rediscovery of the updated coordinate (to log new repair tags)
    from game.systems.survey import survey_coordinate

    survey_coordinate(gs, x, y, gs.player_id)

    return True
