from __future__ import annotations

from game.expedition.resolvers import (
    is_player_at_starting_port,
    resolve_first_playable_blockage,
    resolve_first_playable_route,
    resolve_first_playable_target,
    resolve_starting_contract,
)
from tools.play_game import create_gamestate_from_overland


def test_first_playable_resolvers() -> None:
    # Use the documented first-playable seed
    gs = create_gamestate_from_overland(seed=20260604, width=128, height=96)

    # 1. Verify contract exists
    contract = resolve_starting_contract(gs)
    assert contract is not None, "Starting contract should exist"
    assert "harbor" in contract, "Contract should have a harbor"

    # 2. Verify spawn is valid and at starting port
    spawn = gs.player_position
    assert spawn is not None, "Player should have a spawn position"
    assert is_player_at_starting_port(gs), "Player should spawn at the starting port"

    # Move player far away and check distance resolution
    sx, sy = spawn
    from game.entities.components import Position

    gs.entity_registry.set_position(gs.player_id, Position(sx + 50, sy + 50))
    assert not is_player_at_starting_port(
        gs
    ), "Player should no longer be at starting port"

    # Restore position
    gs.entity_registry.set_position(gs.player_id, Position(sx, sy))
    assert is_player_at_starting_port(gs), "Player should be at starting port again"

    # 3. Verify route target exists (cave or inland site)
    target = resolve_first_playable_target(gs)
    assert target is not None, "Route target should be discoverable"
    assert len(target) == 2, "Target should be a coordinate tuple"

    # 4. Verify route extraction
    route = resolve_first_playable_route(gs)
    assert route is not None, "Route list should be returned"
    assert len(route) > 0, "Route list should not be empty"
    assert len(route[0]) == 2, "Route should contain coordinates"

    # 5. Verify blockage is discoverable
    blockage = resolve_first_playable_blockage(gs)
    assert blockage is not None, "Blockage should be discoverable"
    assert len(blockage) == 2, "Blockage should be a coordinate tuple"
