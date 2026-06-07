# game/systems/survey.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from worldgen.overland.schema import EvidenceTag

if TYPE_CHECKING:
    from game.game_state import GameState

log = structlog.get_logger()


def get_all_evidence_coords(metadata: Any) -> set[tuple[int, int]]:
    """Collect all coordinates on the map that have evidence tags associated with them."""
    coords = set()
    if metadata is None:
        return coords

    # 1. Transitions
    if hasattr(metadata, "transitions") and metadata.transitions:
        for x, y in metadata.transitions:
            coords.add((x, y))

    # 2. Starting contract features
    contract = getattr(metadata, "starting_contract", {}) or {}

    # harbor
    harbor_pt = contract.get("harbor", {}).get("point")
    if harbor_pt:
        coords.add((int(harbor_pt[0]), int(harbor_pt[1])))

    # blockages
    for blockage in contract.get("blockages", []):
        pt = blockage.get("point")
        if pt:
            coords.add((int(pt[0]), int(pt[1])))

    # resource sites
    for site in contract.get("resource_sites", []):
        pt = site.get("point")
        if pt:
            coords.add((int(pt[0]), int(pt[1])))

    # waystation candidates
    for site in contract.get("waystation_candidates", []):
        pt = site.get("point")
        if pt:
            coords.add((int(pt[0]), int(pt[1])))

    # inland sites
    for site in contract.get("inland_sites", []):
        pt = site.get("point")
        if pt:
            coords.add((int(pt[0]), int(pt[1])))

    # cave refs
    for ref in contract.get("cave_refs", []):
        pt = ref.get("point")
        if pt:
            coords.add((int(pt[0]), int(pt[1])))

    # 3. Route segments endpoints
    for seg in getattr(metadata, "route_segments", []) or []:
        from_pt = seg.get("from_point")
        if from_pt:
            coords.add((int(from_pt[0]), int(from_pt[1])))
        to_pt = seg.get("to_point")
        if to_pt:
            coords.add((int(to_pt[0]), int(to_pt[1])))

    return coords


def survey_coordinate(gs: GameState, x: int, y: int, actor_id: int) -> list[int]:
    """Inspect the given coordinate for evidence tags and reveal them to the player.

    Discovered tags are added to the player's message log and saved to discovered_evidence.
    """
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if metadata is None:
        return []

    revealed_tags: list[int] = []

    # 1. Transitions
    if hasattr(metadata, "transitions") and metadata.transitions:
        for payload in metadata.transitions.get((x, y), []):
            revealed_tags.extend(payload.get("evidence_tags", []))

    # 2. Starting contract features
    contract = getattr(metadata, "starting_contract", {}) or {}

    # harbor
    harbor = contract.get("harbor", {})
    if harbor.get("point") == [x, y]:
        revealed_tags.extend(harbor.get("evidence_tags", []))

    # blockages
    for blockage in contract.get("blockages", []):
        if blockage.get("point") == [x, y]:
            revealed_tags.extend(blockage.get("evidence_tags", []))

    # waystation candidates
    for site in contract.get("waystation_candidates", []):
        if site.get("point") == [x, y]:
            revealed_tags.extend(site.get("evidence_tags", []))

    # inland sites
    for site in contract.get("inland_sites", []):
        if site.get("point") == [x, y]:
            revealed_tags.extend(site.get("evidence_tags", []))

    # cave refs
    for ref in contract.get("cave_refs", []):
        if ref.get("point") == [x, y]:
            revealed_tags.extend(ref.get("evidence_tags", []))

    # 3. Route segments endpoints
    for seg in getattr(metadata, "route_segments", []) or []:
        if seg.get("from_point") == [x, y] or seg.get("to_point") == [x, y]:
            revealed_tags.extend(seg.get("evidence_tags", []))

    # Deduplicate
    revealed_tags = sorted(list(set(revealed_tags)))

    if not revealed_tags:
        return []

    # Initialize discovered_evidence if not present
    if not hasattr(gs, "discovered_evidence") or gs.discovered_evidence is None:
        gs.discovered_evidence = {}

    coord_key = f"{x},{y}"
    if coord_key not in gs.discovered_evidence:
        gs.discovered_evidence[coord_key] = []

    already_discovered = gs.discovered_evidence[coord_key]
    new_tags = [t for t in revealed_tags if t not in already_discovered]

    if new_tags:
        gs.discovered_evidence[coord_key].extend(new_tags)
        for tag_val in new_tags:
            try:
                tag_name = EvidenceTag(tag_val).name.replace("_", " ").capitalize()
            except ValueError:
                tag_name = f"Unknown evidence tag {tag_val}"

            # Print a premium gold discovery message for the player
            msg = f"Discovered: {tag_name} at ({x}, {y})!"
            gs.add_message(msg, (255, 215, 0))
            log.info("Evidence tag discovered", x=x, y=y, tag=tag_name, val=tag_val)

    return revealed_tags


def check_automatic_survey(gs: GameState) -> None:
    """Automatically survey any visible tile containing evidence tags that has not been fully discovered yet."""
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if metadata is None:
        return

    # Use a cached/lazy collection of evidence coordinates on GameState
    if not hasattr(gs, "_evidence_coords"):
        gs._evidence_coords = get_all_evidence_coords(metadata)

    evidence_coords: set[tuple[int, int]] = gs._evidence_coords
    if not evidence_coords:
        return

    # Initialize discovered_evidence if not present
    if not hasattr(gs, "discovered_evidence") or gs.discovered_evidence is None:
        gs.discovered_evidence = {}

    for x, y in evidence_coords:
        if gs.game_map.in_bounds(x, y) and gs.game_map.visible[y, x]:
            # Even if we have already fully surveyed this coordinate, if there are new tags (e.g. from state change), we want to reveal them
            survey_coordinate(gs, x, y, gs.player_id)


def expedition_survey(gs: GameState) -> bool:
    """Execute the special starting-region survey for the first playable expedition."""
    expedition = getattr(gs, "expedition", None)
    if expedition is not None and expedition.survey_completed:
        gs.add_message(
            "You have already completed the starting-region survey.", (150, 150, 150)
        )
        return False

    from game.expedition.resolvers import (
        _as_point,
        _iter_dicts,
        resolve_first_playable_blockage,
        resolve_first_playable_route,
        resolve_first_playable_target,
        resolve_starting_contract,
    )

    points_to_survey = set()
    contract = resolve_starting_contract(gs)

    # 1. Harbor
    harbor = contract.get("harbor")
    if harbor:
        pt = _as_point(harbor.get("point"))
        if pt:
            points_to_survey.add(pt)

    # 2. Road
    for point in resolve_first_playable_route(gs):
        points_to_survey.add(point)

    # 3. Blockage
    blockage = resolve_first_playable_blockage(gs)
    if blockage:
        points_to_survey.add(blockage)

    # 4. Target (first cave / inland site)
    target = resolve_first_playable_target(gs)
    if target:
        points_to_survey.add(target)

    # 5. Water / Resource Sites
    for site in _iter_dicts(contract.get("resource_sites")):
        pt = _as_point(site.get("point"))
        if pt:
            points_to_survey.add(pt)

    for x, y in points_to_survey:
        survey_coordinate(gs, x, y, gs.player_id)

    # Update Expedition State
    if expedition is not None:
        expedition.survey_completed = True
        expedition.route_revealed = True
        expedition.active_objective_id = "follow_ancient_road"

    # Emit acceptance target message
    gs.add_message(
        "Survey complete: harbor, road, water, blockage, and first cave marked.",
        (200, 200, 255),
    )
    return True
