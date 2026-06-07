# tests/game/test_seasons_system.py
from __future__ import annotations

import numpy as np

from common.constants import Material
from engine.action_handler import process_player_action
from game.game_state import GameState
from game.systems.seasons import apply_seasonal_state, cycle_season
from game.world.game_map import TILE_ID_FLOOR, GameMap
from worldgen.overland.schema import (
    HydroRole,
    HydroState,
    OverlandMapMetadata,
    Wetness,
)


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
    # Coordinate (3, 3) will be a sinking lake
    # Coordinate (4, 4) will be a built road
    material_grid = np.full((5, 5), int(Material.DIRT), dtype=np.int16)
    material_grid[3, 3] = int(Material.CRACKED_MUD)
    material_grid[4, 4] = int(Material.ROAD)

    hydro_grid = np.zeros((5, 5), dtype=np.int16)
    hydro_grid[3, 3] = int(HydroRole.SINKING_LAKE)

    wetness_grid = np.full((5, 5), int(Wetness.DRY), dtype=np.int16)

    sidecar = OverlandMapMetadata(
        material_grid=material_grid,
        biome_grid=np.zeros((5, 5), dtype=np.int16),
        hydro_grid=hydro_grid,
        wetness_grid=wetness_grid,
        movement_cost_grid=np.ones((5, 5), dtype=np.float32),
        traversal_class_grid=np.zeros((5, 5), dtype=np.int16),
        route_segments=[],
        evidence_tags={},
        transitions={},
        affordances={},
        starting_contract={"seasonal_state": "dry_season"},
        surface_flags_grid=np.zeros((5, 5), dtype=np.uint32),
    )
    gs.game_map.overland_metadata = sidecar
    return gs


def test_initial_season_loading() -> None:
    gs = _setup_test_state()
    # verify initial season is loaded from starting contract
    assert gs.hydro_state == HydroState.DRY_SEASON


def test_seasonal_transition_updates_walkability_and_costs() -> None:
    from worldgen.overland.actor_traversal import (
        ActorTraversalProfile,
        movement_cost_for_actor,
    )

    gs = _setup_test_state()
    metadata = gs.game_map.overland_metadata

    # 1. Start in DRY_SEASON: Sinking lake at (3, 3) should be CRACKED_MUD
    apply_seasonal_state(gs, HydroState.DRY_SEASON)
    assert metadata.material_grid[3, 3] == int(Material.CRACKED_MUD)
    assert metadata.wetness_grid[3, 3] == int(Wetness.DRY)
    assert gs.game_map.is_walkable(3, 3) is True

    tile_row_dry = {
        "material": metadata.material_grid[3, 3],
        "wetness": metadata.wetness_grid[3, 3],
        "traversal_class": metadata.traversal_class_grid[3, 3],
        "movement_cost": metadata.movement_cost_grid[3, 3],
    }
    # Human on foot can walk over cracked mud, but boat cannot
    assert movement_cost_for_actor(
        tile_row_dry, ActorTraversalProfile.HUMAN_ON_FOOT, metadata=metadata
    ) < float("inf")
    assert movement_cost_for_actor(
        tile_row_dry, ActorTraversalProfile.BOAT, metadata=metadata
    ) == float("inf")

    # 2. Change to WET_SEASON: Sinking lake should flood and become SHALLOW_WATER (DEEP_FLOODED)
    apply_seasonal_state(gs, HydroState.WET_SEASON)
    assert metadata.material_grid[3, 3] == int(Material.SHALLOW_WATER)
    assert metadata.wetness_grid[3, 3] == int(Wetness.DEEP_FLOODED)
    assert (
        gs.game_map.is_walkable(3, 3) is True
    )  # physically passable for boats/swimmers

    tile_row_wet = {
        "material": metadata.material_grid[3, 3],
        "wetness": metadata.wetness_grid[3, 3],
        "traversal_class": metadata.traversal_class_grid[3, 3],
        "movement_cost": metadata.movement_cost_grid[3, 3],
    }
    # Human on foot is blocked by deep flooded tiles, but boat can traverse them
    assert movement_cost_for_actor(
        tile_row_wet, ActorTraversalProfile.HUMAN_ON_FOOT, metadata=metadata
    ) == float("inf")
    assert movement_cost_for_actor(
        tile_row_wet, ActorTraversalProfile.BOAT, metadata=metadata
    ) < float("inf")

    # 3. Built structures (ROAD at 4, 4) should NOT be overwritten by material changes
    assert metadata.material_grid[4, 4] == int(Material.ROAD)


def test_cycle_season() -> None:
    gs = _setup_test_state()
    assert gs.hydro_state == HydroState.DRY_SEASON

    # DRY_SEASON (4) -> WET_SEASON (1)
    cycle_season(gs)
    assert gs.hydro_state == HydroState.WET_SEASON

    # WET_SEASON (1) -> DRAINING (2)
    cycle_season(gs)
    assert gs.hydro_state == HydroState.DRAINING


def test_change_season_action_integration() -> None:
    gs = _setup_test_state()

    # Process action with specific season parameter
    action = {"type": "change_season", "season": "wet_season"}
    acted = process_player_action(action, gs, max_traversable_step=1)
    assert acted is True
    assert gs.hydro_state == HydroState.WET_SEASON

    # Process action to cycle season (without parameters)
    action_cycle = {"type": "change_season"}
    acted_cycle = process_player_action(action_cycle, gs, max_traversable_step=1)
    assert acted_cycle is True
    assert gs.hydro_state == HydroState.DRAINING
