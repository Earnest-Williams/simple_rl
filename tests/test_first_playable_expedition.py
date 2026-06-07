from __future__ import annotations

from game.entities.components import Position
from game.expedition.resolvers import (
    is_player_at_starting_port,
    resolve_first_playable_blockage,
    resolve_first_playable_route,
    resolve_first_playable_route_endpoints,
    resolve_first_playable_route_segment,
    resolve_first_playable_target,
    resolve_starting_contract,
)
from tools.play_game import create_gamestate_from_overland


def test_first_playable_resolvers_are_consistent() -> None:
    gs = create_gamestate_from_overland(seed=20260604, width=128, height=96)

    contract = resolve_starting_contract(gs)
    assert "harbor" in contract

    segment = resolve_first_playable_route_segment(gs)
    assert segment is not None

    target = resolve_first_playable_target(gs)
    assert target == tuple(segment["to_point"])

    route = resolve_first_playable_route(gs)
    endpoints = resolve_first_playable_route_endpoints(gs)
    assert route
    assert endpoints == [tuple(segment["from_point"]), tuple(segment["to_point"])]
    assert route[0] == tuple(segment["from_point"])
    assert route[-1] == tuple(segment["to_point"])

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
