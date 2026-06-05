from __future__ import annotations

from typing import Any, cast

import numpy as np

from game.ai.goap import _action_move_attack
from game.ai.perception import (
    PerceptionFact,
    PerceptionSnapshot,
    apply_perception_memory_updates,
    gather_perception_snapshot,
)
from game.ai.strategy import charge_behavior, flee_behavior
from game.game_state import GameState
from game.perception_events import AIMemoryFact
from game.world.game_map import TILE_ID_FLOOR, GameMap
from pathfinding.perception_systems import FlowType
from utils.game_rng import GameRNG


class MockEntityRow(dict[str, Any]):
    def get(self, key: str, default: Any = None) -> Any:
        return super().get(key, default)


class MockRNG:
    def get_int(self, low: int, high: int) -> int:
        return 0


def _make_game_state() -> GameState:
    game_map = GameMap(8, 8)
    game_map.tiles.fill(TILE_ID_FLOOR)
    game_map.update_tile_transparency()
    return GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=8,
        item_templates={},
        enable_sound=False,
        enable_ai=False,
    )


def _set_position(
    game_state: GameState, entity_id: int, row: MockEntityRow, x: int, y: int
) -> None:
    game_state.entity_registry.set_entity_component(entity_id, "x", x)
    game_state.entity_registry.set_entity_component(entity_id, "y", y)
    row["x"] = x
    row["y"] = y


def _make_priority_snapshot(entity_id: int) -> PerceptionSnapshot:
    fact = PerceptionFact(
        signal_type="visual",
        confidence=1.0,
        visible_targets=[{"entity_id": 999, "x": 6, "y": 4}],
        heard_source=(4, 6),
        heard_flow="real_noise",
        scent_strength=5.0,
        scent_position=(3, 4),
        last_known_position=(4, 1),
    )
    return PerceptionSnapshot(
        los_map=np.zeros((8, 8), dtype=bool),
        entity_facts={entity_id: fact},
        debug_noise_map=np.zeros((8, 8)),
        debug_scent_map=np.zeros((8, 8)),
    )


def test_visual_signal_becomes_visual_and_refreshes_memory() -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=2,
        y=2,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Hunter",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    game_state.entity_registry.create_entity(
        x=4,
        y=2,
        glyph=64,
        color_fg=(255, 255, 255),
        name="Target",
        faction="heroes",
    )
    game_state.update_fov()
    game_state.game_map.visible[:] = True

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]

    assert fact.signal_type == "visual"
    assert fact.visible_targets[0]["x"] == 4
    assert fact.last_known_position == (4, 2)

    apply_perception_memory_updates(game_state, snapshot)

    memory = game_state.ai_memory[actor_id]
    assert memory.pos == (4, 2)
    assert memory.source == "visual"
    assert memory.expires_at_turn == (
        game_state.turn_count + game_state.ai_memory_duration_turns
    )


def test_audio_signal_becomes_audio_and_refreshes_memory() -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Listener",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )

    flow_idx = int(FlowType.REAL_NOISE)
    game_state.perception_flow_centers[flow_idx, 0] = 6
    game_state.perception_flow_centers[flow_idx, 1] = 5
    game_state.perception_alerted_monster_ids = [actor_id]

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]

    assert fact.signal_type == "audio"
    assert fact.heard_source == (5, 6)
    assert fact.last_known_position == (5, 6)

    apply_perception_memory_updates(game_state, snapshot)

    memory = game_state.ai_memory[actor_id]
    assert memory.pos == (5, 6)
    assert memory.source == "audio"
    assert memory.expires_at_turn == (
        game_state.turn_count + game_state.ai_memory_duration_turns
    )


def test_scent_signal_does_not_overwrite_last_known_memory() -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Tracker",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    game_state.ai_memory[actor_id] = AIMemoryFact(
        pos=(1, 1),
        expires_at_turn=game_state.turn_count + 3,
        source="audio",
    )
    game_state.perception_cave_when[4, 4] = 1
    game_state.perception_cave_when[4, 5] = 10

    snapshot = gather_perception_snapshot(game_state)
    fact = snapshot.entity_facts[actor_id]

    assert fact.signal_type == "scent"
    assert fact.scent_position == (5, 4)
    assert fact.last_known_position == (1, 1)

    apply_perception_memory_updates(game_state, snapshot)

    memory = game_state.ai_memory[actor_id]
    assert memory.pos == (1, 1)
    assert memory.source == "audio"


def test_memory_persists_by_turn_without_snapshot_decay() -> None:
    game_state = _make_game_state()
    actor_id = game_state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Rememberer",
        ai_type="goap",
        species="hunter",
        faction="monsters",
    )
    expiry_turn = game_state.turn_count + 2
    game_state.ai_memory[actor_id] = AIMemoryFact(
        pos=(6, 4),
        expires_at_turn=expiry_turn,
        source="visual",
    )

    first = gather_perception_snapshot(game_state).entity_facts[actor_id]
    second = gather_perception_snapshot(game_state).entity_facts[actor_id]

    assert first.signal_type == "memory"
    assert first.last_known_position == (6, 4)
    assert second.signal_type == "memory"
    assert second.last_known_position == (6, 4)
    assert game_state.ai_memory[actor_id].expires_at_turn == expiry_turn

    game_state.turn_count = expiry_turn - 1
    before_expiry = gather_perception_snapshot(game_state).entity_facts[actor_id]
    assert before_expiry.signal_type == "memory"
    assert before_expiry.last_known_position == (6, 4)

    game_state.turn_count = expiry_turn
    expired = gather_perception_snapshot(game_state).entity_facts[actor_id]
    assert expired.signal_type == "idle"
    assert expired.last_known_position is None


def test_goap_chooses_visual_then_audio_then_scent_then_memory() -> None:
    game_state = _make_game_state()
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
    snapshot = _make_priority_snapshot(entity_id)
    fact = snapshot.entity_facts[entity_id]

    _action_move_attack(row, game_state, rng, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (5, 4)

    fact.visible_targets = []
    _set_position(game_state, entity_id, row, 4, 4)
    _action_move_attack(row, game_state, rng, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (4, 5)

    fact.heard_source = None
    fact.heard_flow = None
    _set_position(game_state, entity_id, row, 4, 4)
    _action_move_attack(row, game_state, rng, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (3, 4)

    fact.scent_position = None
    _set_position(game_state, entity_id, row, 4, 4)
    _action_move_attack(row, game_state, rng, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (4, 3)


def test_strategy_charge_and_flee_follow_signal_priority() -> None:
    game_state = _make_game_state()
    entity_id = game_state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Strategist",
        ai_type="strategy",
        species="enemy",
    )
    row = MockEntityRow({"entity_id": entity_id, "x": 4, "y": 4})
    snapshot = _make_priority_snapshot(entity_id)
    fact = snapshot.entity_facts[entity_id]

    charge_behavior(row, game_state, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (5, 4)

    _set_position(game_state, entity_id, row, 4, 4)
    flee_behavior(row, game_state, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (3, 4)

    fact.visible_targets = []
    _set_position(game_state, entity_id, row, 4, 4)
    charge_behavior(row, game_state, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (4, 5)

    _set_position(game_state, entity_id, row, 4, 4)
    flee_behavior(row, game_state, snapshot)
    pos = game_state.entity_registry.get_position(entity_id)
    assert pos is not None
    assert (pos.x, pos.y) == (4, 3)
