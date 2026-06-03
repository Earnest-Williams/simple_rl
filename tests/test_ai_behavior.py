from __future__ import annotations

from typing import Any, cast
import numpy as np

from game.ai.perception import PerceptionFact, PerceptionSnapshot
from game.ai.goap import _action_move_attack
from game.game_state import GameState
from game.world.game_map import GameMap, TILE_ID_FLOOR
from utils.game_rng import GameRNG


class MockEntityRow(dict[str, Any]):
    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class MockRNG:
    def get_int(self, low: int, high: int) -> int:
        return 0


def test_goap_behavior_priority() -> None:
    # Setup minimal game state
    game_map = GameMap(8, 8)
    game_map.tiles.fill(TILE_ID_FLOOR)
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=4,
        item_templates={},
        enable_sound=False,
        enable_ai=False,
    )

    entity_id = game_state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    row = MockEntityRow({"entity_id": entity_id, "x": 4, "y": 4})
    rng = cast(GameRNG, MockRNG())

    # 1. Visual priority
    fact = PerceptionFact(
        signal_type="visual",
        confidence=1.0,
        visible_targets=[{"x": 6, "y": 4}],
        heard_source=None,
        heard_flow=None,
        scent_strength=0.0,
        scent_position=None,
        last_known_position=(6, 4),
    )
    snapshot = PerceptionSnapshot(
        los_map=np.zeros((8, 8), dtype=bool),
        entity_facts={entity_id: fact},
        debug_noise_map=np.zeros((8, 8)),
        debug_scent_map=np.zeros((8, 8)),
    )

    # Run GOAP behavior
    _action_move_attack(row, game_state, rng, snapshot)

    # Check if moved towards (6, 4) -> x should become 5
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 5
    assert pos.y == 4

    # 2. Audio priority (with no visual target)
    fact.visible_targets = []
    fact.signal_type = "audio"
    fact.heard_source = (5, 6)  # x=5, y=6
    fact.last_known_position = (5, 6)

    # reset pos
    game_state.entity_registry.set_entity_component(entity_id, "x", 4)
    game_state.entity_registry.set_entity_component(entity_id, "y", 4)
    row["x"] = 4
    row["y"] = 4

    _action_move_attack(row, game_state, rng, snapshot)

    pos = game_state.entity_registry.get_position(entity_id)
    # Expected movement: flow field towards (5, 6) from (4, 4)
    assert pos is not None
    assert pos.x >= 4 and pos.y > 4

    # 3. Scent priority
    fact.heard_source = None
    fact.signal_type = "scent"
    fact.scent_position = (3, 4)
    fact.last_known_position = None

    game_state.entity_registry.set_entity_component(entity_id, "x", 4)
    game_state.entity_registry.set_entity_component(entity_id, "y", 4)
    row["x"] = 4
    row["y"] = 4

    _action_move_attack(row, game_state, rng, snapshot)

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 3
    assert pos.y == 4

    # 4. Memory priority
    fact.scent_position = None
    fact.signal_type = "memory"
    fact.last_known_position = (4, 1)

    game_state.entity_registry.set_entity_component(entity_id, "x", 4)
    game_state.entity_registry.set_entity_component(entity_id, "y", 4)
    row["x"] = 4
    row["y"] = 4

    _action_move_attack(row, game_state, rng, snapshot)

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 4
    assert pos.y == 3
