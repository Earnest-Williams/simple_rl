# tests/game/test_survey_system.py
from __future__ import annotations

import numpy as np
from common.constants import FeatureType
from game.game_state import GameState
from game.world.game_map import TILE_ID_FLOOR, GameMap
from worldgen.overland.schema import OverlandMapMetadata, EvidenceTag
from game.systems.survey import survey_coordinate, check_automatic_survey
from engine.action_handler import process_player_action


def _setup_test_state() -> GameState:
    game_map = GameMap(width=5, height=5)
    game_map.tiles[:, :] = TILE_ID_FLOOR
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
        material_grid=np.zeros((5, 5), dtype=np.int16),
        biome_grid=np.zeros((5, 5), dtype=np.int16),
        hydro_grid=np.zeros((5, 5), dtype=np.int16),
        wetness_grid=np.zeros((5, 5), dtype=np.int16),
        movement_cost_grid=np.ones((5, 5), dtype=np.float32),
        traversal_class_grid=np.zeros((5, 5), dtype=np.int16),
        route_segments=[
            {
                "route_id": "test_road",
                "from_point": [1, 1],
                "to_point": [3, 3],
                "state": 1,
                "evidence_tags": [int(EvidenceTag.ROAD_ENGINEERING)],
            }
        ],
        evidence_tags={},
        transitions={
            (2, 2): [
                {
                    "transition_type": 1,
                    "evidence_tags": [int(EvidenceTag.PRIOR_EXPEDITION)],
                }
            ]
        },
        affordances={},
        starting_contract={
            "harbor": {
                "point": [0, 0],
                "evidence_tags": [int(EvidenceTag.RUINED)],
            }
        }
    )
    gs.game_map.overland_metadata = sidecar
    return gs


def test_survey_coordinate_reveals_evidence() -> None:
    gs = _setup_test_state()
    
    # Survey transition at (2, 2)
    tags = survey_coordinate(gs, 2, 2, gs.player_id)
    assert int(EvidenceTag.PRIOR_EXPEDITION) in tags
    assert gs.discovered_evidence["2,2"] == [int(EvidenceTag.PRIOR_EXPEDITION)]
    
    # Check that a log message was added
    messages = [msg for msg, color in gs.message_log]
    assert any("Prior expedition" in msg for msg in messages)
    
    # Survey route endpoint at (1, 1)
    tags2 = survey_coordinate(gs, 1, 1, gs.player_id)
    assert int(EvidenceTag.ROAD_ENGINEERING) in tags2
    
    # Survey starting contract feature at (0, 0)
    tags3 = survey_coordinate(gs, 0, 0, gs.player_id)
    assert int(EvidenceTag.RUINED) in tags3


def test_automatic_survey_on_visibility() -> None:
    gs = _setup_test_state()
    
    # Make coordinates visible
    gs.game_map.visible.fill(False)
    gs.game_map.visible[2, 2] = True  # Player coordinate has transition evidence
    
    # Trigger check_automatic_survey (which is also called in GameState.update_fov)
    check_automatic_survey(gs)
    
    # Verify transition evidence was automatically discovered
    assert gs.discovered_evidence.get("2,2") == [int(EvidenceTag.PRIOR_EXPEDITION)]
    
    # Now make (0, 0) visible
    gs.game_map.visible[0, 0] = True
    check_automatic_survey(gs)
    
    # Verify harbor evidence was automatically discovered
    assert int(EvidenceTag.RUINED) in gs.discovered_evidence.get("0,0", [])


def test_active_survey_action_turn_consumption() -> None:
    gs = _setup_test_state()
    
    action = {
        "type": "survey",
        "x": 2,
        "y": 2,
    }
    
    # Processing the survey action should return True (turn consumed)
    acted = process_player_action(action, gs, max_traversable_step=1)
    assert acted is True
    assert gs.discovered_evidence.get("2,2") == [int(EvidenceTag.PRIOR_EXPEDITION)]
