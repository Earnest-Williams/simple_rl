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
    rng = cast(GameRNG, MockRNG())

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

    def set_enemy_position(x: int, y: int) -> None:
        game_state.entity_registry.set_entity_component(entity_id, "x", x)
        game_state.entity_registry.set_entity_component(entity_id, "y", y)

    # 1. Visual priority.
    moved = _action_move_attack(entity_id, game_state, rng, snapshot)
    assert moved is True

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 5
    assert pos.y == 4

    # 2. Audio priority, when no visual target is available.
    fact.visible_targets = []
    fact.signal_type = "audio"
    fact.heard_source = (5, 6)
    fact.last_known_position = (5, 6)
    set_enemy_position(4, 4)

    moved = _action_move_attack(entity_id, game_state, rng, snapshot)
    assert moved is True

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x >= 4
    assert pos.y > 4

    # 3. Scent priority, when visual and audio signals are unavailable.
    fact.heard_source = None
    fact.signal_type = "scent"
    fact.scent_position = (3, 4)
    fact.last_known_position = None
    set_enemy_position(4, 4)

    moved = _action_move_attack(entity_id, game_state, rng, snapshot)
    assert moved is True

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 3
    assert pos.y == 4

    # 4. Memory priority, when direct sensory signals are unavailable.
    fact.scent_position = None
    fact.signal_type = "memory"
    fact.last_known_position = (4, 1)
    set_enemy_position(4, 4)

    moved = _action_move_attack(entity_id, game_state, rng, snapshot)
    assert moved is True

    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert pos.x == 4
    assert pos.y == 3
