import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))


def _make_game_state(templates):
    from game.game_state import GameState
    from game.world.game_map import TILE_ID_FLOOR, GameMap

    game_map = GameMap(5, 5)
    game_map.tiles[:] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    return GameState(
        existing_map=game_map,
        player_start_pos=(0, 0),
        player_glyph=ord("@"),
        player_start_hp=10,
        player_fov_radius=4,
        item_templates={},
        entity_templates=templates,
        effect_definitions={},
        rng_seed=1,
        memory_fade_config={"enabled": False},
        enable_ai=False,
    )


def test_community_adapter_drink_and_wander():
    pytest.importorskip("numpy")
    pytest.importorskip("structlog")

    from game.ai.community_adapter import spawn_community_agent

    templates = {
        "villager": {
            "glyph": ord("v"),
            "color": [200, 180, 120],
            "name": "Villager",
            "community": {
                "traits": {"endurance": 1.2, "ingenuity": 1.1},
                "home": {"water_storage": 2, "raw_inventory": {}},
                "state": {"thirst": 0.9},
            },
        },
        "wanderer": {
            "glyph": ord("w"),
            "color": [150, 150, 150],
            "name": "Wanderer",
        },
    }
    gs = _make_game_state(templates)

    villager_id = spawn_community_agent(gs, "villager", 2, 2)
    wanderer_id = spawn_community_agent(gs, "wanderer", 3, 3)

    villager = gs.entity_registry.get_entity_component(villager_id, "community_ai")
    assert villager is not None
    assert villager.home.water_storage == 2

    wanderer_start = gs.entity_registry.get_position(wanderer_id)
    gs.community_manager.step()

    assert villager.home.water_storage == 1
    assert villager.daily_behavior_log[-1][1] == "drink"

    wanderer_end = gs.entity_registry.get_position(wanderer_id)
    assert wanderer_start != wanderer_end
    wanderer = gs.entity_registry.get_entity_component(wanderer_id, "community_ai")
    assert wanderer.daily_behavior_log[-1][1] == "wander"
