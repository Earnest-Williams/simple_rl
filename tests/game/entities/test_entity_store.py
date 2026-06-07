from __future__ import annotations

import polars as pl

from game.entities.components import Position
from game.entities.registry import EntityRegistry
from game.entities.store import EntityStore


def test_create_entity_round_trips_hot_components() -> None:
    store = EntityStore()
    entity_id = 123
    store.create_entity(
        entity_id=entity_id,
        x=10,
        y=20,
        glyph=42,
        color_fg=(255, 0, 0),
        name="Test Entity",
        blocks_movement=True,
        ai_type="basic_ai",
        species="human",
        intelligence=3,
        faction="player_faction",
        strategy_state="idle",
        hp=50,
        max_hp=100,
        fullness=80.0,
        fuel=5.0,
        status_effects=[],
    )

    assert store.has_active(entity_id)
    assert store.index_of(entity_id) == 0
    assert store.get_component(entity_id, "x") == 10
    assert store.get_component(entity_id, "y") == 20
    assert store.get_component(entity_id, "glyph") == 42
    assert store.get_component(entity_id, "name") == "Test Entity"
    assert store.get_component(entity_id, "blocks_movement") is True
    assert store.get_component(entity_id, "hp") == 50
    assert store.get_component(entity_id, "max_hp") == 100
    assert store.get_component(entity_id, "intelligence") == 3
    assert store.get_component(entity_id, "fullness") == 80.0
    assert store.get_component(entity_id, "fuel") == 5.0


def test_set_position_updates_x_and_y_without_dataframe_mutation() -> None:
    store = EntityStore()
    entity_id = 456
    store.create_entity(
        entity_id=entity_id,
        x=5,
        y=5,
        glyph=1,
        color_fg=(255, 255, 255),
        name="Mobile Entity",
    )

    # Cache is marked dirty upon creation, let's clear it
    df1 = store.to_polars()
    store.dirty_polars_snapshot = False

    success = store.set_position(entity_id, Position(15, 25))
    assert success
    assert store.get_position(entity_id) == Position(15, 25)
    assert store.dirty_polars_snapshot is True  # marked dirty

    # Verify directly in array fields
    idx = store.index_of(entity_id)
    assert store.x[idx] == 15
    assert store.y[idx] == 25


def test_entities_df_snapshot_reflects_store_updates() -> None:
    registry = EntityRegistry()
    entity_id = registry.create_entity(
        x=2,
        y=3,
        glyph=10,
        color_fg=(100, 100, 100),
        name="Snapshot Entity",
    )

    # Initial df contains the entity
    df = registry.entities_df
    assert df.height == 1
    assert df.filter(pl.col("entity_id") == entity_id).row(0, named=True)["x"] == 2

    # Mutate position
    registry.set_position(entity_id, Position(9, 9))

    # The cached df should be rebuilt and reflect the update
    df2 = registry.entities_df
    assert df2.filter(pl.col("entity_id") == entity_id).row(0, named=True)["x"] == 9


def test_entities_df_setter_rebuilds_store_for_compatibility() -> None:
    registry = EntityRegistry()
    entity_id = registry.create_entity(
        x=1,
        y=1,
        glyph=1,
        color_fg=(0, 0, 0),
        name="Compatibility Entity",
    )

    # Read, modify DataFrame column directly, and re-assign
    df = registry.entities_df
    df_modified = df.with_columns(pl.lit(99).alias("x"))
    registry.entities_df = df_modified

    # Registry store should be rebuilt and reflect x = 99
    assert registry.get_position(entity_id) == Position(99, 1)


def test_get_entity_components_reads_hot_and_extra_components() -> None:
    registry = EntityRegistry()
    entity_id = registry.create_entity(
        x=4,
        y=4,
        glyph=2,
        color_fg=(0, 255, 0),
        name="Multi Component Entity",
        strength=12,
        defense=5,
    )

    components = registry.get_entity_components(
        entity_id, ["name", "x", "y", "strength", "defense"]
    )
    assert components == {
        "name": "Multi Component Entity",
        "x": 4,
        "y": 4,
        "strength": 12,
        "defense": 5,
    }


def test_delete_entity_marks_inactive() -> None:
    store = EntityStore()
    entity_id = 999
    store.create_entity(
        entity_id=entity_id,
        x=1,
        y=1,
        glyph=1,
        color_fg=(0, 0, 0),
        name="Deletable Entity",
    )

    assert store.has_active(entity_id)
    success = store.delete_entity(entity_id)
    assert success
    assert not store.has_active(entity_id)
    assert store.get_component(entity_id, "x") is None  # inactive entity returns None
