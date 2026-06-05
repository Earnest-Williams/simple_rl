# game/systems/seasons.py
from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np
import structlog

from common.constants import Material
from worldgen.overland.schema import (
    HydroRole,
    Wetness,
    TraversalClass,
    HydroState,
    SurfaceFlag,
)
from worldgen.overland.rules import (
    derive_walkable,
    derive_blocks_sight,
    derive_traversal_class,
    derive_movement_cost,
    surface_flag_mask,
)
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL

if TYPE_CHECKING:
    from game.game_state import GameState

log = structlog.get_logger()

WATER_HYDRO_MATERIALS = {
    int(Material.SHALLOW_WATER),
    int(Material.DEEP_WATER),
    int(Material.FLOWING_WATER),
    int(Material.SPRING_WATER),
    int(Material.SINKING_WATER),
    int(Material.ESTAVELLE_WATER),
    int(Material.STAGNANT_WATER),
    int(Material.BOG_WATER),
    int(Material.UNDERGROUND_WATER),
    int(Material.BOG_POOL),
    int(Material.TARN),
}

ROAD_BRIDGE_MATERIALS = {
    int(Material.ROAD),
    int(Material.TRACK),
    int(Material.TRAIL),
    int(Material.ANIMAL_TRAIL),
    int(Material.BOARDWALK),
    int(Material.BRIDGE),
    int(Material.DOCK),
}


def apply_seasonal_state(gs: GameState, state: HydroState) -> None:
    """Transform runtime map tiles and metadata sidecar to reflect a new seasonal state.

    Recalculates walkability, sight blocking, traversal classes, and movement costs.
    """
    metadata = getattr(gs.game_map, "overland_metadata", None)
    if metadata is None:
        log.warning("Cannot apply seasonal state: OverlandMapMetadata sidecar is missing.")
        return

    # Cache base grids on GameState if not already done
    if not hasattr(gs, "_base_material_grid"):
        gs._base_material_grid = metadata.material_grid.copy()
    if not hasattr(gs, "_base_wetness_grid"):
        gs._base_wetness_grid = metadata.wetness_grid.copy()

    base_material = gs._base_material_grid
    base_wetness = gs._base_wetness_grid
    hydro_grid = metadata.hydro_grid

    # Define masks based on base attributes and role definitions
    is_sinking_lake = (hydro_grid == int(HydroRole.SINKING_LAKE))
    is_estavelle = (hydro_grid == int(HydroRole.ESTAVELLE))
    is_ponor = (hydro_grid == int(HydroRole.PONOR))
    is_fish_trail = (base_material == int(Material.FISH_TRAIL))

    # Initialize transformed grids from base
    new_material = base_material.copy()
    new_wetness = base_wetness.copy()

    # Apply seasonal logic to material and wetness
    if state == HydroState.WET_SEASON:
        new_material[is_sinking_lake] = int(Material.SHALLOW_WATER)
        new_material[is_estavelle] = int(Material.SPRING_WATER)
        new_material[is_ponor] = int(Material.SINKING_WATER)
        new_material[is_fish_trail] = int(Material.SHALLOW_WATER)

        new_wetness[is_sinking_lake] = int(Wetness.DEEP_FLOODED)
        new_wetness[is_estavelle | is_ponor | is_fish_trail] = int(Wetness.SHALLOW_FLOODED)

    elif state == HydroState.DRAINING:
        new_material[is_sinking_lake | is_ponor] = int(Material.SINKING_WATER)
        new_material[is_estavelle] = int(Material.ESTAVELLE_WATER)
        new_material[is_fish_trail] = int(Material.MUDFLAT)

        new_wetness[is_sinking_lake | is_estavelle | is_ponor] = int(Wetness.WET)
        new_wetness[is_fish_trail] = int(Wetness.SATURATED)

    elif state == HydroState.MUD_SEASON:
        new_material[is_sinking_lake] = int(Material.MUDFLAT)
        new_material[is_estavelle] = int(Material.MUD)
        new_material[is_ponor] = int(Material.PONOR)
        new_material[is_fish_trail] = int(Material.FISH_TRAIL)

        new_wetness[is_sinking_lake | is_estavelle | is_ponor | is_fish_trail] = int(Wetness.WET)

    elif state == HydroState.DRY_SEASON:
        new_material[is_sinking_lake] = int(Material.CRACKED_MUD)
        new_material[is_estavelle | is_ponor] = int(Material.CAVE_MOUTH)
        new_material[is_fish_trail] = int(Material.FISH_TRAIL)

        new_wetness[is_sinking_lake | is_estavelle | is_ponor | is_fish_trail] = int(Wetness.DRY)

    # Protect built structures (roads, bridges, docks, boardwalks) from being overwritten
    current_material = metadata.material_grid
    is_built_road_bridge = (
        np.isin(base_material, list(ROAD_BRIDGE_MATERIALS)) |
        np.isin(current_material, list(ROAD_BRIDGE_MATERIALS))
    )

    non_built = ~is_built_road_bridge
    metadata.material_grid[non_built] = new_material[non_built]
    metadata.wetness_grid[:, :] = new_wetness

    # Recompute runtime tile attributes and update GameMap
    height, width = metadata.material_grid.shape
    for y in range(height):
        for x in range(width):
            mat = Material(int(metadata.material_grid[y, x]))
            wet = Wetness(int(metadata.wetness_grid[y, x]))
            
            # Retrieve flags from grid if available
            flags = int(metadata.surface_flags_grid[y, x]) if getattr(metadata, "surface_flags_grid", None) is not None else 0

            walkable = derive_walkable(mat, wet, flags)
            cost = derive_movement_cost(mat, wet, flags)
            t_class = derive_traversal_class(mat, wet, flags)

            # Update GameMap tiles (affects is_walkable, transparent maps, and AI flowfield version)
            gs.game_map.tiles[y, x] = TILE_ID_FLOOR if walkable else TILE_ID_WALL

            # Update metadata sidecar grids
            metadata.movement_cost_grid[y, x] = cost
            metadata.traversal_class_grid[y, x] = int(t_class)

    # Set new state and log event
    gs.hydro_state = state
    gs.game_map.update_tile_transparency()
    gs.add_message(f"The season changes to: {state.name.replace('_', ' ').title()}.", (0, 191, 255))
    log.info("Seasonal state applied", state=state.name)


def cycle_season(gs: GameState) -> None:
    """Cycle the seasonal state to the next state in order."""
    current = getattr(gs, "hydro_state", HydroState.DRY_SEASON)
    next_val = (int(current) % 4) + 1
    new_state = HydroState(next_val)
    apply_seasonal_state(gs, new_state)
