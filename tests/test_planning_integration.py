from __future__ import annotations

from game.ai import goap_adapter
from game.ai.perception import gather_perception
from game.game_state import GameState
from game.planning.spatial_hash import SpatialHashTable
from game.world.game_map import GameMap


def _make_state() -> GameState:
    game_map = GameMap(8, 8)
    return GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=4,
        item_templates={},
        enable_sound=False,
        enable_ai=False,
    )


def test_gather_perception_uses_shared_radius_helper() -> None:
    state = _make_state()
    state.noise_events.append((3, 3, 5.0))
    state.scent_events.append((4, 4, 6.0))

    noise_map, scent_map, los_map = gather_perception(state)

    assert noise_map[3, 3] == 5.0
    assert noise_map[3, 4] == 4.0
    assert noise_map[0, 0] == 0.0
    assert scent_map[4, 4] == 6.0
    assert scent_map[4, 5] == 5.0
    assert los_map.shape == state.game_map.visible.shape
    assert state.noise_events == []
    assert state.scent_events == []


def test_process_turn_populates_spatial_index() -> None:
    state = _make_state()
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    state.process_turn()

    assert state.spatial_index.query_radius((4, 5), radius=0, kind="enemy") == [
        (enemy_id, 4, 5)
    ]


def test_goap_world_adapter_prefers_spatial_index() -> None:
    state = _make_state()
    state.spatial_index = SpatialHashTable(cell_size=4)
    state.spatial_index.insert(42, 2, 3, "enemy")
    agent = goap_adapter._GameAgentAdapter(
        entity_id=1,
        health=10.0,
        hunger=0.0,
        max_inventory=0,
        inventory=[],
        equipped_weapon=None,
        _position=(1, 1),
    )
    world = goap_adapter._GameStateWorldAdapter(state)
    world.entity_df = state.entity_registry.entities_df.clear()

    entity_id, distance = world.get_nearest_entity(agent, "enemy")

    assert entity_id == 42
    assert distance == 3.0
