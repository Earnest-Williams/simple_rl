from __future__ import annotations

import pytest
import numpy as np
import polars as pl

from game.game_state import GameState
from game.world.game_map import GameMap, TILE_ID_FLOOR


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
        enable_ai=False,
    )


def test_process_turn_does_not_materialize_entities_df(monkeypatch) -> None:
    state = _make_state()
    state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    def fail_entities_df() -> object:
        raise AssertionError("process_turn must not materialize entities_df")

    monkeypatch.setattr(
        type(state.entity_registry),
        "entities_df",
        property(lambda self: fail_entities_df()),
    )

    active_ids, ai_ids = state.process_turn()

    assert active_ids
    assert ai_ids


def test_process_turn_populates_spatial_index_from_store() -> None:
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


def test_process_turn_returns_ai_entity_ids() -> None:
    state = _make_state()
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
        faction="monsters",
    )

    _active_ids, ai_ids = state.process_turn()

    assert enemy_id in ai_ids


def test_resolve_monster_perception_does_not_materialize_entities_df(monkeypatch) -> None:
    """Test that resolve_monster_perception uses array-based API, not Polars."""
    state = _make_state()
    
    # Create a monster
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )
    # Set perception_stat as an extra component using the store directly
    state.entity_registry._store.set_component(enemy_id, "perception_stat", 10)

    # Monkeypatch to_polars to raise if called
    def fail_to_polars() -> object:
        raise AssertionError("resolve_monster_perception must not call to_polars()")

    monkeypatch.setattr(state.entity_registry._store, "to_polars", fail_to_polars)

    # This should not raise
    state.resolve_monster_perception()
    
    # Should have run without error
    assert isinstance(state.perception_alerted_monster_ids, list)


def test_resolve_monster_perception_does_not_use_entities_df(monkeypatch) -> None:
    """Test that resolve_monster_perception doesn't access entities_df property."""
    state = _make_state()
    
    # Create a monster
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )
    # Set perception_stat as an extra component using the store directly
    state.entity_registry._store.set_component(enemy_id, "perception_stat", 10)

    # Monkeypatch entities_df property to raise if accessed
    def fail_entities_df() -> object:
        raise AssertionError("resolve_monster_perception must not access entities_df")

    monkeypatch.setattr(
        type(state.entity_registry),
        "entities_df",
        property(lambda self: fail_entities_df()),
    )

    # This should not raise
    state.resolve_monster_perception()
    
    # Should have run without error
    assert isinstance(state.perception_alerted_monster_ids, list)


def test_update_sound_context_does_not_materialize_entities_df(monkeypatch) -> None:
    """Test that _update_sound_context uses store accessors, not Polars."""
    # Enable sound manager for this test
    state = _make_state()
    state.sound_manager = type('MockSoundManager', (), {
        'set_context': lambda self, ctx: None
    })()
    
    # Create a monster
    state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    # Monkeypatch to_polars to raise if called
    def fail_to_polars() -> object:
        raise AssertionError("_update_sound_context must not call to_polars()")

    monkeypatch.setattr(state.entity_registry._store, "to_polars", fail_to_polars)

    # This should not raise
    state._update_sound_context()


def test_update_sound_context_does_not_use_entities_df(monkeypatch) -> None:
    """Test that _update_sound_context doesn't access entities_df property."""
    # Enable sound manager for this test
    state = _make_state()
    state.sound_manager = type('MockSoundManager', (), {
        'set_context': lambda self, ctx: None
    })()
    
    # Create a monster
    state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    # Monkeypatch entities_df property to raise if accessed
    def fail_entities_df() -> object:
        raise AssertionError("_update_sound_context must not access entities_df")

    monkeypatch.setattr(
        type(state.entity_registry),
        "entities_df",
        property(lambda self: fail_entities_df()),
    )

    # This should not raise
    state._update_sound_context()


def test_update_sound_context_combat_detection(monkeypatch) -> None:
    """Test that _update_sound_context still correctly detects combat."""
    state = _make_state()
    
    # Mock sound manager to capture context
    captured_contexts = []
    mock_sound_manager = type('MockSoundManager', (), {
        'enabled': True,
        'update_background_music': lambda self, ctx: captured_contexts.append(ctx)
    })()
    state.sound_manager = mock_sound_manager
    
    # Mock get_sound_manager to return our mock
    def mock_get_sound_manager():
        return mock_sound_manager
    
    from game.systems import sound
    monkeypatch.setattr(sound, "get_sound_manager", mock_get_sound_manager)
    
    # Create a visible enemy nearby
    state.entity_registry.create_entity(
        x=3,
        y=3,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
        blocks_movement=True,
    )
    
    # Make sure the enemy is visible
    state.game_map.visible[:] = True

    state._update_sound_context()
    
    # Should have detected combat
    assert len(captured_contexts) > 0
    assert captured_contexts[-1]["game_state"] == "combat"


def test_update_sound_context_elite_boss_detection(monkeypatch) -> None:
    """Test that _update_sound_context still correctly detects elite/boss enemies."""
    state = _make_state()
    
    # Mock sound manager to capture context
    captured_contexts = []
    mock_sound_manager = type('MockSoundManager', (), {
        'enabled': True,
        'update_background_music': lambda self, ctx: captured_contexts.append(ctx)
    })()
    state.sound_manager = mock_sound_manager
    
    # Mock get_sound_manager to return our mock
    def mock_get_sound_manager():
        return mock_sound_manager
    
    from game.systems import sound
    monkeypatch.setattr(sound, "get_sound_manager", mock_get_sound_manager)
    
    # Create elite and boss enemies
    state.entity_registry.create_entity(
        x=3,
        y=3,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Elite Enemy",
        ai_type="goap",
        species="enemy",
    )
    
    state.entity_registry.create_entity(
        x=4,
        y=4,
        glyph=102,
        color_fg=(255, 0, 0),
        name="Dragon Boss",
        ai_type="goap",
        species="enemy",
    )
    
    # Make sure enemies are visible
    state.game_map.visible[:] = True

    state._update_sound_context()
    
    # Should have detected enemy types
    assert len(captured_contexts) > 0
    context = captured_contexts[-1]
    assert "enemy_type" in context
    assert "elite" in context["enemy_type"]
    assert "boss" in context["enemy_type"]


def test_advance_turn_does_not_use_row_dicts(monkeypatch) -> None:
    """Test that advance_turn does not use row dictionaries in AI dispatch."""
    state = _make_state()
    
    # Create an AI entity
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    # Monkeypatch row_dict_at to raise if called
    def fail_row_dict_at(idx: int) -> object:
        raise AssertionError("advance_turn must not call row_dict_at()")

    monkeypatch.setattr(state.entity_registry._store, "row_dict_at", fail_row_dict_at)

    # Enable AI
    state.ai_enabled = True

    # This should not raise
    state.advance_turn()


def test_dispatch_ai_receives_only_entity_ids(monkeypatch) -> None:
    """Test that dispatch_ai receives only integer entity IDs."""
    state = _make_state()
    
    # Create an AI entity
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Enemy",
        ai_type="goap",
        species="enemy",
    )

    # Track what dispatch_ai receives
    received_entities = []
    
    def mock_dispatch_ai(entities, *, game_state, rng, perception=None, **kwargs):
        received_entities.append(entities)
        # Don't actually do anything
        return
    
    # Patch the function in the game_state module where it's imported
    import game.game_state as game_state_module
    monkeypatch.setattr(game_state_module, "dispatch_ai", mock_dispatch_ai)

    # Enable AI
    state.ai_enabled = True

    state.advance_turn()

    # Check that all received entities are integers or iterables of integers
    assert len(received_entities) > 0
    for entities in received_entities:
        if isinstance(entities, int):
            assert isinstance(entities, int)
        else:
            # Should be an iterable
            for entity in entities:
                assert isinstance(entity, int), f"Expected int, got {type(entity)}"


def test_get_entities_in_aoe_does_not_materialize_entities_df(monkeypatch) -> None:
    """Test that _get_entities_in_aoe uses store accessors, not Polars."""
    from game.effects.handlers import _get_entities_in_aoe
    
    state = _make_state()
    
    # Create some entities
    for i in range(3):
        state.entity_registry.create_entity(
            x=4 + i,
            y=5 + i,
            glyph=101 + i,
            color_fg=(255, 0, 0),
            name=f"Enemy {i}",
            ai_type="goap",
            species="enemy",
        )

    # Monkeypatch to_polars to raise if called
    def fail_to_polars() -> object:
        raise AssertionError("_get_entities_in_aoe must not call to_polars()")

    monkeypatch.setattr(state.entity_registry._store, "to_polars", fail_to_polars)

    # This should not raise
    result = _get_entities_in_aoe((5, 5), 3, state)
    
    # Should have found entities within radius 3 of (5,5)
    assert isinstance(result, list)
    assert len(result) > 0


def test_community_adapter_step_does_not_materialize_entities_df(monkeypatch) -> None:
    """Test that CommunityAdapter.step uses store accessors, not Polars."""
    from game.ai.community_adapter import CommunityManager
    
    state = _make_state()
    
    # Create a community entity
    state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Community Member",
        ai_type="community",
        species="human",
    )

    # Monkeypatch to_polars to raise if called
    def fail_to_polars() -> object:
        raise AssertionError("CommunityAdapter.step must not call to_polars()")

    monkeypatch.setattr(state.entity_registry._store, "to_polars", fail_to_polars)

    # This should not raise
    state.community_manager.step()


def test_insect_ai_does_not_materialize_entities_df(monkeypatch) -> None:
    """Test that insect AI uses store accessors, not Polars."""
    from game.ai.insect import take_turn as insect_take_turn
    
    state = _make_state()
    
    # Create an insect entity
    enemy_id = state.entity_registry.create_entity(
        x=4,
        y=5,
        glyph=101,
        color_fg=(255, 0, 0),
        name="Insect",
        ai_type="insect",
        species="insect",
    )

    # Monkeypatch to_polars to raise if called
    def fail_to_polars() -> object:
        raise AssertionError("Insect AI must not call to_polars()")

    monkeypatch.setattr(state.entity_registry._store, "to_polars", fail_to_polars)

    # Mock rng
    from utils.game_rng import GameRNG
    rng = GameRNG()

    # This should not raise
    insect_take_turn(enemy_id, state, rng, None)


def test_all_ai_adapters_accept_entity_ids() -> None:
    """Test that all AI adapters accept entity_id as int."""
    from game.ai import get_adapter
    from utils.game_rng import GameRNG
    
    state = _make_state()
    rng = GameRNG()
    
    # Test all adapters that should accept entity_id
    adapters_to_test = ["simple", "bird", "mammal", "reptile", "plant", "ml_policy", "community"]
    
    for ai_type in adapters_to_test:
        adapter = get_adapter(ai_type)
        # Check that the adapter accepts entity_id as first parameter
        # We can't easily test the signature, but we can check it doesn't raise TypeError
        # when called with an int
        try:
            # This will fail for various reasons (missing perception, etc.) but shouldn't
            # fail due to wrong parameter type
            adapter(1, state, rng, None)
        except TypeError as e:
            if "entity_row" in str(e) or "argument" in str(e):
                raise AssertionError(f"Adapter {ai_type} doesn't accept entity_id as int: {e}")
        except Exception:
            # Other exceptions are fine - we just care about the signature
            pass
