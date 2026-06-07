from __future__ import annotations

from game.ai.perception import gather_perception_snapshot
from game.game_state import GameState
from game.systems.ai_system import dispatch_ai
from game.world.game_map import TILE_ID_FLOOR, GameMap
from utils.game_rng import GameRNG


def _make_state() -> GameState:
    game_map = GameMap(width=10, height=10)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()

    return GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=42,
        enable_sound=False,
        enable_ai=True,
    )


def test_dispatch_ai_accepts_entity_id() -> None:
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
    rng = GameRNG(seed=123)

    # Just verify that running it with a single int does not crash
    dispatch_ai(enemy_id, game_state=state, rng=rng, perception=None)


def test_dispatch_ai_accepts_entity_id_list_deterministically() -> None:
    state = _make_state()
    enemy_id_1 = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy 1",
        ai_type="goap",
        species="enemy",
    )
    enemy_id_2 = state.entity_registry.create_entity(
        x=5,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy 2",
        ai_type="goap",
        species="enemy",
    )
    rng = GameRNG(seed=123)

    # Verify it accepts a list and sorts it internally if deterministic is True
    dispatch_ai(
        [enemy_id_2, enemy_id_1],
        game_state=state,
        rng=rng,
        perception=None,
        deterministic=True,
    )


def test_goap_move_attack_reads_position_from_registry() -> None:
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
    rng = GameRNG(seed=42)
    state.update_fov()
    perception = gather_perception_snapshot(state)

    old_pos = state.entity_registry.xy_of(enemy_id)
    dispatch_ai(enemy_id, game_state=state, rng=rng, perception=perception)
    new_pos = state.entity_registry.xy_of(enemy_id)

    assert old_pos == (4, 5)
    assert new_pos != old_pos


def test_strategy_charge_and_flee_read_registry_fields() -> None:
    state = _make_state()
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Kobold",
        ai_type="strategy",
        strategy_state="charge",
        species="kobold",
        hp=10,
        max_hp=10,
    )
    rng = GameRNG(seed=42)
    state.update_fov()
    perception = gather_perception_snapshot(state)

    # Test charging: should move towards player
    old_pos = state.entity_registry.xy_of(enemy_id)
    dispatch_ai(enemy_id, game_state=state, rng=rng, perception=perception)
    new_pos = state.entity_registry.xy_of(enemy_id)
    assert new_pos != old_pos

    # Test fleeing
    state.entity_registry.set_entity_component(enemy_id, "strategy_state", "flee")
    from game.entities.components import Position

    state.entity_registry.set_position(enemy_id, Position(4, 5))

    dispatch_ai(enemy_id, game_state=state, rng=rng, perception=perception)
    flee_pos = state.entity_registry.xy_of(enemy_id)
    assert flee_pos != (4, 5)


def test_advance_turn_dispatches_ai_without_row_dicts(monkeypatch) -> None:
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

    monkeypatch.setattr(
        state.entity_registry,
        "row_dict_at",
        lambda idx: (_ for _ in ()).throw(
            AssertionError("AI hot loop must not build row dicts")
        ),
    )

    state.advance_turn()
