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
