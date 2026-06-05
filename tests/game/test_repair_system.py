# tests/game/test_repair_system.py
from __future__ import annotations

import numpy as np
from common.constants import FeatureType, Material
from game.game_state import GameState
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from worldgen.overland.schema import OverlandMapMetadata, RouteSegmentState, TraversalClass, EvidenceTag
from game.systems.repair import clear_blockage_at
from engine.action_handler import process_player_action


def _setup_test_state() -> GameState:
    game_map = GameMap(width=5, height=5)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    # Place a blockage tile on the map (marked as non-walkable wall)
    game_map.tiles[3, 2] = TILE_ID_WALL
    game_map.update_tile_transparency()
    
    gs = GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=12,
        enable_sound=False,
        enable_ai=False,
    )
    
    # Attach mock overland metadata sidecar
    sidecar = OverlandMapMetadata(
        material_grid=np.full((5, 5), int(Material.DIRT), dtype=np.int16),
        biome_grid=np.zeros((5, 5), dtype=np.int16),
        hydro_grid=np.zeros((5, 5), dtype=np.int16),
        wetness_grid=np.zeros((5, 5), dtype=np.int16),
        movement_cost_grid=np.full((5, 5), 1.0, dtype=np.float32),
        traversal_class_grid=np.full((5, 5), int(TraversalClass.NORMAL), dtype=np.int16),
        route_segments=[
            {
                "route_id": "test_road",
                "from_point": [1, 1],
                "to_point": [3, 3],
                "state": int(RouteSegmentState.BLOCKED),
                "evidence_tags": [int(EvidenceTag.ROAD_ENGINEERING)],
            }
        ],
        evidence_tags={},
        transitions={},
        affordances={},
        starting_contract={
            "blockages": [
                {
                    "blockage_id": "road_landslip_01",
                    "point": [2, 3],
                    "state": "clearable",
                    "blocks_route": "test_road",
                    "evidence_tags": [
                        int(EvidenceTag.RECENT_COLLAPSE),
                    ],
                }
            ]
        }
    )
    # Mark blockage tile as non-walkable and high cost in sidecar grids
    sidecar.material_grid[3, 2] = int(Material.LIMESTONE)
    sidecar.movement_cost_grid[3, 2] = np.inf
    sidecar.traversal_class_grid[3, 2] = int(TraversalClass.BLOCKED)
    
    gs.game_map.overland_metadata = sidecar
    return gs


def test_clear_blockage_updates_state_and_grids() -> None:
    gs = _setup_test_state()
    sidecar = gs.game_map.overland_metadata
    
    # Verify initial blocked state
    assert gs.game_map.tiles[3, 2] == TILE_ID_WALL
    assert not gs.game_map.is_walkable(2, 3)
    assert sidecar.movement_cost_grid[3, 2] == np.inf
    assert sidecar.route_segments[0]["state"] == int(RouteSegmentState.BLOCKED)
    
    # Clear the blockage
    success = clear_blockage_at(gs, 2, 3)
    assert success is True
    
    # Verify cleared state
    assert gs.game_map.tiles[3, 2] == TILE_ID_FLOOR
    assert gs.game_map.is_walkable(2, 3)
    assert sidecar.movement_cost_grid[3, 2] == 1.0
    assert sidecar.material_grid[3, 2] == int(Material.ROAD)
    assert sidecar.traversal_class_grid[3, 2] == int(TraversalClass.NORMAL)
    
    # Route segment should be marked as repaired
    assert sidecar.route_segments[0]["state"] == int(RouteSegmentState.REPAIRED)
    assert int(EvidenceTag.RECENT_REPAIR) in sidecar.route_segments[0]["evidence_tags"]
    
    # Check that log message was added
    messages = [msg for msg, color in gs.message_log]
    assert any("successfully clear the blockage" in msg for msg in messages)
    
    # Clearing again should return False
    success_again = clear_blockage_at(gs, 2, 3)
    assert success_again is False


def test_repair_action_integration() -> None:
    gs = _setup_test_state()
    action = {
        "type": "repair",
        "x": 2,
        "y": 3,
    }
    
    # Processing the repair action should consume a turn (True)
    acted = process_player_action(action, gs, max_traversable_step=1)
    assert acted is True
    assert gs.game_map.tiles[3, 2] == TILE_ID_FLOOR
