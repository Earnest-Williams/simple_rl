from __future__ import annotations

import heapq

import numpy as np
from PIL import Image
from engine.renderer import ViewportParams, _draw_first_playable_route_overlay

from game.entities.components import Position
from game.systems.overland_movement import human_on_foot_can_enter
from game.expedition.resolvers import (
    first_playable_objective_text,
    first_playable_route_points,
    first_playable_route_target,
    is_player_at_starting_port,
    resolve_first_playable_blockage,
    resolve_first_playable_cave,
    resolve_first_playable_route,
    resolve_first_playable_route_endpoints,
    resolve_first_playable_route_segment,
    resolve_first_playable_target,
    resolve_starting_contract,
)
from tools.play_game import create_gamestate_from_overland, print_viewport


def _build_human_passable_map(gs) -> np.ndarray:
    metadata = getattr(gs.game_map, "overland_metadata", None)
    height = gs.game_map.height
    width = gs.game_map.width
    passable = np.zeros((height, width), dtype=bool)
    if metadata is None:
        for y in range(height):
            for x in range(width):
                passable[y, x] = gs.game_map.is_walkable(x, y)
    else:
        for y in range(height):
            for x in range(width):
                passable[y, x] = human_on_foot_can_enter(gs, x, y)
    return passable


def _find_path(gs, start: tuple[int, int], target: tuple[int, int]) -> list[tuple[int, int]]:
    if start == target:
        return [start]

    passable = _build_human_passable_map(gs)
    height_map = np.asarray(gs.game_map.height_map, dtype=np.int16)
    width = gs.game_map.width
    height = gs.game_map.height

    def heuristic(x: int, y: int) -> float:
        return max(abs(x - target[0]), abs(y - target[1]))

    frontier: list[tuple[float, int, int]] = []
    heapq.heappush(frontier, (heuristic(*start), start[0], start[1]))
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], float] = {start: 0.0}

    directions = (
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    )

    while frontier:
        _, current_x, current_y = heapq.heappop(frontier)
        current = (current_x, current_y)
        if current == target:
            break

        current_h = int(height_map[current_y, current_x])
        for dx, dy in directions:
            next_x = current_x + dx
            next_y = current_y + dy
            next_pt = (next_x, next_y)
            if not (0 <= next_x < width and 0 <= next_y < height):
                continue
            if not passable[next_y, next_x]:
                continue
            if abs(int(height_map[next_y, next_x]) - current_h) > 1:
                continue

            step_cost = 1.41421356237 if dx != 0 and dy != 0 else 1.0
            new_cost = cost_so_far[current] + step_cost
            if next_pt not in cost_so_far or new_cost < cost_so_far[next_pt]:
                cost_so_far[next_pt] = new_cost
                priority = new_cost + heuristic(next_x, next_y)
                heapq.heappush(frontier, (priority, next_x, next_y))
                came_from[next_pt] = current

    if target not in came_from:
        raise AssertionError(f"No path found from {start} to {target}")

    path: list[tuple[int, int]] = []
    current: tuple[int, int] | None = target
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def _move_step_towards(gs, target: tuple[int, int]) -> bool:
    player_pos = gs.player_position
    if player_pos is None:
        return False

    px, py = player_pos
    path = _find_path(gs, (px, py), target)
    if len(path) < 2:
        return True

    next_x, next_y = path[1]
    flow_dx = next_x - px
    flow_dy = next_y - py

    from engine.action_handler import process_player_action

    return process_player_action(
        {"type": "move", "dx": int(flow_dx), "dy": int(flow_dy)},
        gs,
        max_traversable_step=1,
    )


def _walk_to(gs, target: tuple[int, int], *, max_steps: int = 500) -> None:
    for _ in range(max_steps):
        player_pos = gs.player_position
        assert player_pos is not None
        if (player_pos.x, player_pos.y) == target:
            return
        acted = _move_step_towards(gs, target)
        assert acted is True
    raise AssertionError(f"Failed to reach {target} within {max_steps} steps")


def test_first_playable_resolvers_are_consistent() -> None:
    gs = create_gamestate_from_overland(seed=20260604, width=128, height=96)

    contract = resolve_starting_contract(gs)
    assert "harbor" in contract

    segment = resolve_first_playable_route_segment(gs)
    assert segment is not None

    cave = resolve_first_playable_cave(gs)
    assert cave is not None

    target = resolve_first_playable_target(gs)
    assert target == tuple(cave["point"])

    route = resolve_first_playable_route(gs)
    endpoints = resolve_first_playable_route_endpoints(gs)
    assert route
    assert endpoints == [tuple(segment["from_point"]), target]
    assert route[0] == tuple(segment["from_point"])
    assert first_playable_route_target(gs) == target

    blockage = resolve_first_playable_blockage(gs)
    expected_blockage = contract["blockages"][0]
    assert blockage == tuple(expected_blockage["point"])
    assert expected_blockage["blocks_route"] == segment["route_id"]


def test_is_player_at_starting_port_uses_harbor_radius() -> None:
    gs = create_gamestate_from_overland(seed=20260604, width=128, height=96)

    spawn = gs.player_position
    assert spawn is not None
    assert is_player_at_starting_port(gs)

    sx, sy = spawn
    gs.entity_registry.set_position(gs.player_id, Position(sx + 50, sy + 50))
    assert not is_player_at_starting_port(gs)

    gs.entity_registry.set_position(gs.player_id, Position(sx, sy))
    assert is_player_at_starting_port(gs)


def test_expedition_survey_at_starting_port() -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    assert gs.expedition is not None
    assert not gs.expedition.survey_completed

    # First survey at starting port
    action = {"type": "survey"}
    acted = process_player_action(action, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.survey_completed is True
    assert gs.expedition.route_revealed is True
    assert gs.expedition.active_objective_id == "follow_ancient_road"
    assert gs.expedition.discovery_recorded is False
    assert "first_cave_survey" not in gs.expedition.discovery_ids
    assert (
        first_playable_objective_text(gs)
        == "Objective: follow the ancient road to the first cave."
    )
    assert first_playable_route_points(gs)

    # Verify message log
    messages = [msg for msg, color in gs.message_log]
    assert any(
        "Survey complete: harbor, road, water, blockage, and first cave marked." in msg
        for msg in messages
    )

    # Clear message log to check for the repeated warning
    gs.message_log.clear()

    # Repeated survey at starting port
    acted_again = process_player_action(action, gs, max_traversable_step=1)
    assert acted_again is False  # No turn consumed
    messages_again = [msg for msg, color in gs.message_log]
    assert any(
        "You have already completed the starting-region survey." in msg
        for msg in messages_again
    )


def test_expedition_survey_away_from_starting_port() -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    assert gs.expedition is not None
    assert not gs.expedition.survey_completed

    # Move player away from port
    spawn = gs.player_position
    assert spawn is not None
    sx, sy = spawn
    gs.entity_registry.set_position(gs.player_id, Position(sx + 50, sy + 50))
    assert not is_player_at_starting_port(gs)

    # Perform survey action
    action = {"type": "survey"}
    acted = process_player_action(action, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.survey_completed is False
    assert gs.expedition.discovery_recorded is False
    assert "first_cave_survey" not in gs.expedition.discovery_ids


def test_ascii_viewport_shows_objective_marker_after_survey(capsys) -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    process_player_action({"type": "survey"}, gs, max_traversable_step=1)

    print_viewport(gs, radius_x=6, radius_y=4)
    output = capsys.readouterr().out

    assert "Objective: follow the ancient road to the first cave." in output
    assert "*" in output or "!" in output


def test_gui_route_overlay_draws_marker_after_survey() -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    process_player_action({"type": "survey"}, gs, max_traversable_step=1)

    route_points = first_playable_route_points(gs)
    assert route_points
    target_x, target_y = route_points[-1]

    viewport = ViewportParams(
        viewport_x=max(0, target_x - 2),
        viewport_y=max(0, target_y - 2),
        viewport_width=5,
        viewport_height=5,
        tile_arrays={},
        tile_fg_colors=np.zeros((1, 3), dtype=np.uint8),
        tile_bg_colors=np.zeros((1, 3), dtype=np.uint8),
        tile_indices_render=np.zeros((1,), dtype=np.uint16),
        max_defined_tile_id=0,
        tile_w=4,
        tile_h=4,
        coord_arrays={
            "tile_coord_y": np.zeros((20, 20), dtype=np.int32),
            "tile_coord_x": np.zeros((20, 20), dtype=np.int32),
        },
    )
    image = Image.new("RGBA", (20, 20), (0, 0, 0, 255))
    _draw_first_playable_route_overlay(image, gs, viewport, 4, 4)

    center_pixel = image.getpixel((10, 10))
    assert center_pixel != (0, 0, 0, 255)


def test_gui_route_overlay_is_hidden_before_survey() -> None:
    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )

    viewport = ViewportParams(
        viewport_x=20,
        viewport_y=8,
        viewport_width=8,
        viewport_height=8,
        tile_arrays={},
        tile_fg_colors=np.zeros((1, 3), dtype=np.uint8),
        tile_bg_colors=np.zeros((1, 3), dtype=np.uint8),
        tile_indices_render=np.zeros((1,), dtype=np.uint16),
        max_defined_tile_id=0,
        tile_w=4,
        tile_h=4,
        coord_arrays={
            "tile_coord_y": np.zeros((32, 32), dtype=np.int32),
            "tile_coord_x": np.zeros((32, 32), dtype=np.int32),
        },
    )
    image = Image.new("RGBA", (32, 32), (0, 0, 0, 255))
    _draw_first_playable_route_overlay(image, gs, viewport, 4, 4)

    assert image.getpixel((16, 16)) == (0, 0, 0, 255)


def test_first_playable_overland_visibility_is_not_radius_limited() -> None:
    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )

    assert gs.first_playable_lights_on is True
    assert gs.fov_radius == gs.base_fov_radius
    assert gs.game_map.visible[0, 0]
    assert gs.game_map.visible[gs.game_map.height - 1, gs.game_map.width - 1]
    assert np.all(gs.game_map.explored)


def test_first_playable_overland_memory_is_not_faded() -> None:
    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )

    gs.advance_turn()

    assert np.all(gs.game_map.visible)
    assert np.all(gs.game_map.explored)
    assert np.all(gs.game_map.memory_intensity == 1.0)
    assert gs.player_fuel == gs.player_max_fuel
    assert gs.fov_radius == gs.base_fov_radius


def test_expedition_repair_clears_blockage() -> None:
    from engine.action_handler import process_player_action
    from game.expedition.resolvers import resolve_first_playable_blockage

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    assert gs.expedition is not None
    assert not gs.expedition.blockage_cleared

    blockage_pt = resolve_first_playable_blockage(gs)
    assert blockage_pt is not None
    bx, by = blockage_pt

    # Perform repair action
    action = {"type": "repair", "x": bx, "y": by}
    acted = process_player_action(action, gs, max_traversable_step=1)

    assert acted is True
    assert gs.expedition.blockage_cleared is True

    # Verify message log
    messages = [msg for msg, color in gs.message_log]
    assert any(
        "You clear enough of the blockage to reopen the road." in msg
        for msg in messages
    )


def test_expedition_repair_defaults_to_player_position() -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    blockage_pt = resolve_first_playable_blockage(gs)
    assert blockage_pt is not None

    gs.entity_registry.set_position(gs.player_id, Position(*blockage_pt))

    acted = process_player_action({"type": "repair"}, gs, max_traversable_step=1)

    assert acted is True
    assert gs.expedition is not None
    assert gs.expedition.blockage_cleared is True


def test_expedition_cave_handoff() -> None:
    from engine.action_handler import process_player_action
    from game.expedition.resolvers import (
        resolve_first_playable_blockage,
        resolve_starting_contract,
    )
    from game.entities.components import Position

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    assert gs.expedition is not None
    assert not gs.expedition.cave_entered

    contract = resolve_starting_contract(gs)
    cave_refs = contract.get("cave_refs", [])
    assert len(cave_refs) > 0
    cave_pt = tuple(cave_refs[0].get("point"))
    cx, cy = cave_pt
    blockage_pt = resolve_first_playable_blockage(gs)
    assert blockage_pt is not None

    gs.entity_registry.set_position(gs.player_id, Position(*blockage_pt))
    acted_repair = process_player_action({"type": "repair"}, gs, max_traversable_step=1)
    assert acted_repair is True

    # Teleport player to the cave
    gs.entity_registry.set_position(gs.player_id, Position(cx, cy))

    overland_map_ref = gs.game_map

    # Perform enter action
    action = {"type": "enter", "x": cx, "y": cy}
    acted = process_player_action(action, gs, max_traversable_step=1)

    assert acted is True
    assert gs.expedition.cave_entered is True
    assert gs.game_map is not overland_map_ref

    # Verify player is at the interior spawn point
    player_pos = gs.player_position
    assert player_pos is not None
    assert player_pos.x == 10 and player_pos.y == 10

    # Verify message log
    messages = [msg for msg, color in gs.message_log]
    assert any("Cave entered:" in msg for msg in messages)

    # Perform enter again to exit
    action_exit = {"type": "enter", "x": 10, "y": 10}
    acted_exit = process_player_action(action_exit, gs, max_traversable_step=1)

    assert acted_exit is True
    assert gs.game_map is overland_map_ref

    # Verify player is back at the transition
    player_pos_return = gs.player_position
    assert player_pos_return is not None
    assert player_pos_return.x == cx and player_pos_return.y == cy

    messages = [msg for msg, color in gs.message_log]
    assert any("You return to the surface." in msg for msg in messages)


def test_first_playable_cave_interior_uses_normal_visibility() -> None:
    from engine.action_handler import process_player_action
    from game.entities.components import Position

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    contract = resolve_starting_contract(gs)
    cave_pt = tuple(contract["cave_refs"][0]["point"])
    blockage_pt = resolve_first_playable_blockage(gs)
    assert blockage_pt is not None

    gs.entity_registry.set_position(gs.player_id, Position(*blockage_pt))
    assert process_player_action({"type": "repair"}, gs, max_traversable_step=1)

    gs.entity_registry.set_position(gs.player_id, Position(*cave_pt))
    assert process_player_action({"type": "enter"}, gs, max_traversable_step=1)

    assert getattr(gs.game_map, "overland_metadata", None) is None
    assert not np.all(gs.game_map.visible)
    assert not gs.game_map.visible[0, 0]


def test_expedition_enter_defaults_to_player_position_after_repair() -> None:
    from engine.action_handler import process_player_action
    from game.entities.components import Position

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    contract = resolve_starting_contract(gs)
    cave_pt = tuple(contract["cave_refs"][0]["point"])
    blockage_pt = resolve_first_playable_blockage(gs)
    assert blockage_pt is not None

    gs.entity_registry.set_position(gs.player_id, Position(*blockage_pt))
    acted_repair = process_player_action({"type": "repair"}, gs, max_traversable_step=1)
    assert acted_repair is True

    gs.entity_registry.set_position(gs.player_id, Position(*cave_pt))
    overland_map_ref = gs.game_map

    acted_enter = process_player_action({"type": "enter"}, gs, max_traversable_step=1)
    assert acted_enter is True
    assert gs.game_map is not overland_map_ref

    acted_exit = process_player_action({"type": "enter"}, gs, max_traversable_step=1)
    assert acted_exit is True
    assert gs.game_map is overland_map_ref


def test_expedition_cave_entry_requires_blockage_clearance() -> None:
    from engine.action_handler import process_player_action
    from game.entities.components import Position

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    contract = resolve_starting_contract(gs)
    cave_pt = tuple(contract["cave_refs"][0]["point"])
    gs.entity_registry.set_position(gs.player_id, Position(*cave_pt))

    acted = process_player_action({"type": "enter"}, gs, max_traversable_step=1)

    assert acted is False
    assert gs.expedition is not None
    assert gs.expedition.cave_entered is False
    messages = [msg for msg, _ in gs.message_log]
    assert any("blocked road must be cleared" in msg for msg in messages)

def test_expedition_end_to_end_smoke_without_teleportation() -> None:
    from engine.action_handler import process_player_action

    gs = create_gamestate_from_overland(
        seed=20260604, width=128, height=96, first_playable=True
    )
    assert gs.expedition is not None

    contract = resolve_starting_contract(gs)
    route = resolve_first_playable_route(gs)
    blockage_pt = resolve_first_playable_blockage(gs)
    cave_refs = contract.get("cave_refs", [])
    assert route
    assert blockage_pt is not None
    assert len(cave_refs) > 0

    harbor = contract.get("harbor")
    assert harbor is not None
    harbor_pt = tuple(harbor.get("point"))
    cave_pt = tuple(cave_refs[0].get("point"))
    path_to_cave_from_harbor = _find_path(gs, harbor_pt, cave_pt)
    assert path_to_cave_from_harbor
    assert blockage_pt not in path_to_cave_from_harbor

    # Survey at port.
    acted = process_player_action({"type": "survey"}, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.survey_completed is True
    assert gs.expedition.route_revealed is True
    assert gs.expedition.active_objective_id == "follow_ancient_road"
    assert first_playable_route_target(gs) == cave_pt

    # Walk to the blockage and repair it in place.
    _walk_to(gs, blockage_pt)
    player_pos = gs.player_position
    assert player_pos is not None
    assert (player_pos.x, player_pos.y) == blockage_pt

    acted = process_player_action({"type": "repair"}, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.blockage_cleared is True

    # Continue to the cave transition and enter without teleporting.
    _walk_to(gs, cave_pt)
    player_pos = gs.player_position
    assert player_pos is not None
    assert (player_pos.x, player_pos.y) == cave_pt

    overland_map_ref = gs.game_map
    acted = process_player_action({"type": "enter"}, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.cave_entered is True
    assert gs.game_map is not overland_map_ref

    # Record the discovery from the cave context.
    acted = process_player_action({"type": "survey"}, gs, max_traversable_step=1)
    assert acted is True
    assert "first_cave_survey" in gs.expedition.discovery_ids
    assert gs.expedition.discovery_recorded is True

    messages = [msg for msg, color in gs.message_log]
    assert any("Discovery recorded: first cave surveyed." in msg for msg in messages)

    # Exit and walk back to port without teleporting.
    acted = process_player_action({"type": "enter"}, gs, max_traversable_step=1)
    assert acted is True
    assert gs.game_map is overland_map_ref

    _walk_to(gs, harbor_pt)
    player_pos = gs.player_position
    assert player_pos is not None
    assert (player_pos.x, player_pos.y) == harbor_pt

    # Trigger completion from the real port context and ensure the message only appears once.
    gs.message_log.clear()
    acted = process_player_action({"type": "wait"}, gs, max_traversable_step=1)
    assert acted is True
    assert gs.expedition.returned_to_port is True
    assert gs.expedition.loop_completed is True

    completion_message = (
        "Expedition complete: first cave surveyed and route back to port confirmed."
    )
    messages = [msg for msg, color in gs.message_log]
    assert messages.count(completion_message) == 1
