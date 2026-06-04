from __future__ import annotations

from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from common.constants import Material
from settlegen import TerrainCode
from worldgen.overland.rules import (
    derive_blocks_sight,
    derive_movement_cost,
    derive_traversal_class,
    derive_walkable,
    surface_flag_mask,
)
from worldgen.overland.schema import (
    Biome,
    ElevationBand,
    HydroRole,
    Substrate,
    SurfaceFlag,
    Wetness,
)


class SettlementTile(IntEnum):
    VOID = 0
    GROUND = 1
    WOODS = 2
    FARM = 3
    HIGH_GROUND = 4
    ROAD = 5
    PLAZA = 6
    WATER = 7
    SHORE = 8
    BRIDGE = 9
    WALL = 10
    GATE = 11
    BUILDING = 12
    RUIN = 13
    CEMETERY = 14
    DOCK = 15
    MAGIC = 16
    MOAT = 17


_SETTLEMENT_TILE_BY_TERRAIN: dict[TerrainCode, SettlementTile] = {
    TerrainCode.VOID: SettlementTile.VOID,
    TerrainCode.GRASS: SettlementTile.GROUND,
    TerrainCode.FOREST: SettlementTile.WOODS,
    TerrainCode.DENSE_FOREST: SettlementTile.WOODS,
    TerrainCode.FARMLAND: SettlementTile.FARM,
    TerrainCode.ORCHARD: SettlementTile.FARM,
    TerrainCode.PASTURE: SettlementTile.FARM,
    TerrainCode.FIELD: SettlementTile.FARM,
    TerrainCode.HILL: SettlementTile.HIGH_GROUND,
    TerrainCode.MOUNTAIN: SettlementTile.HIGH_GROUND,
    TerrainCode.ROAD: SettlementTile.ROAD,
    TerrainCode.PLAZA: SettlementTile.PLAZA,
    TerrainCode.WATER: SettlementTile.WATER,
    TerrainCode.DEEP_WATER: SettlementTile.WATER,
    TerrainCode.SHORE: SettlementTile.SHORE,
    TerrainCode.MARSH: SettlementTile.SHORE,
    TerrainCode.SWAMP: SettlementTile.SHORE,
    TerrainCode.BRIDGE: SettlementTile.BRIDGE,
    TerrainCode.WALL: SettlementTile.WALL,
    TerrainCode.PALISADE: SettlementTile.WALL,
    TerrainCode.GATE: SettlementTile.GATE,
    TerrainCode.BUILDING: SettlementTile.BUILDING,
    TerrainCode.RUIN: SettlementTile.RUIN,
    TerrainCode.CEMETERY: SettlementTile.CEMETERY,
    TerrainCode.DOCK: SettlementTile.DOCK,
    TerrainCode.DYKE: SettlementTile.WALL,
    TerrainCode.MAGIC: SettlementTile.MAGIC,
    TerrainCode.EMPTY_LOT: SettlementTile.GROUND,
    TerrainCode.MOAT: SettlementTile.MOAT,
}

_OPAQUE_TILES: set[SettlementTile] = {
    SettlementTile.VOID,
    SettlementTile.HIGH_GROUND,
    SettlementTile.WATER,
    SettlementTile.WALL,
    SettlementTile.BUILDING,
    SettlementTile.RUIN,
    SettlementTile.MOAT,
}

_WALKABLE_TILES: set[SettlementTile] = {
    SettlementTile.GROUND,
    SettlementTile.WOODS,
    SettlementTile.FARM,
    SettlementTile.ROAD,
    SettlementTile.PLAZA,
    SettlementTile.SHORE,
    SettlementTile.BRIDGE,
    SettlementTile.GATE,
    SettlementTile.CEMETERY,
    SettlementTile.DOCK,
    SettlementTile.MAGIC,
}


def terrain_to_settlement_tile(code: int | TerrainCode) -> SettlementTile:
    terrain = code if isinstance(code, TerrainCode) else TerrainCode(int(code))
    return _SETTLEMENT_TILE_BY_TERRAIN[terrain]


def terrain_to_shaped_columns(
    combined_grid: NDArray[np.integer],
) -> dict[str, NDArray[np.generic]]:
    vectorized = np.vectorize(terrain_to_settlement_tile, otypes=[np.uint16])
    settlement_tile = vectorized(combined_grid).astype(np.uint16)
    walkable = np.isin(
        settlement_tile,
        np.array([int(tile) for tile in _WALKABLE_TILES], dtype=np.uint16),
    )
    transparent = ~np.isin(
        settlement_tile,
        np.array([int(tile) for tile in _OPAQUE_TILES], dtype=np.uint16),
    )
    material_id = np.where(walkable, int(Material.CAVE_FLOOR), int(Material.SOLID_ROCK))
    return {
        "settlement_tile": settlement_tile,
        "material_id": material_id.astype(np.uint16),
        "walkable": walkable.astype(bool),
        "transparent": transparent.astype(bool),
    }


_OVERLAND_MATERIAL_BY_TERRAIN: dict[TerrainCode, Material] = {
    TerrainCode.VOID: Material.VOID,
    TerrainCode.GRASS: Material.GRASS,
    TerrainCode.FOREST: Material.FOREST_FLOOR,
    TerrainCode.DENSE_FOREST: Material.FERN_UNDERSTORY,
    TerrainCode.FARMLAND: Material.FIELD,
    TerrainCode.ORCHARD: Material.ORCHARD,
    TerrainCode.PASTURE: Material.PASTURE,
    TerrainCode.FIELD: Material.FIELD,
    TerrainCode.HILL: Material.GRAVEL,
    TerrainCode.MOUNTAIN: Material.SCREE,
    TerrainCode.ROAD: Material.ROAD,
    TerrainCode.PLAZA: Material.BUILDING_FLOOR,
    TerrainCode.WATER: Material.SHALLOW_WATER,
    TerrainCode.DEEP_WATER: Material.DEEP_WATER,
    TerrainCode.SHORE: Material.MUDFLAT,
    TerrainCode.MARSH: Material.REEDBED,
    TerrainCode.SWAMP: Material.BOG_WATER,
    TerrainCode.BRIDGE: Material.BRIDGE,
    TerrainCode.WALL: Material.STONE_WALL,
    TerrainCode.PALISADE: Material.WOOD_WALL,
    TerrainCode.GATE: Material.ROAD,
    TerrainCode.BUILDING: Material.BUILDING_FLOOR,
    TerrainCode.RUIN: Material.RUIN_FLOOR,
    TerrainCode.CEMETERY: Material.GRASS,
    TerrainCode.DOCK: Material.DOCK,
    TerrainCode.DYKE: Material.STONE_WALL,
    TerrainCode.MAGIC: Material.LIMESTONE_PAVEMENT,
    TerrainCode.EMPTY_LOT: Material.DIRT,
    TerrainCode.MOAT: Material.SHALLOW_WATER,
}

_OVERLAND_WETNESS_BY_TERRAIN: dict[TerrainCode, Wetness] = {
    TerrainCode.WATER: Wetness.SHALLOW_FLOODED,
    TerrainCode.DEEP_WATER: Wetness.DEEP_FLOODED,
    TerrainCode.SHORE: Wetness.WET,
    TerrainCode.MARSH: Wetness.SATURATED,
    TerrainCode.SWAMP: Wetness.SATURATED,
    TerrainCode.MOAT: Wetness.SHALLOW_FLOODED,
    TerrainCode.DOCK: Wetness.DAMP,
}

_OVERLAND_SUBSTRATE_BY_TERRAIN: dict[TerrainCode, Substrate] = {
    TerrainCode.WATER: Substrate.MUD,
    TerrainCode.DEEP_WATER: Substrate.MUD,
    TerrainCode.SHORE: Substrate.MUD,
    TerrainCode.MARSH: Substrate.MUD,
    TerrainCode.SWAMP: Substrate.PEAT,
    TerrainCode.ROAD: Substrate.BUILT_STONE,
    TerrainCode.PLAZA: Substrate.BUILT_STONE,
    TerrainCode.BRIDGE: Substrate.WOOD,
    TerrainCode.DOCK: Substrate.WOOD,
    TerrainCode.WALL: Substrate.BUILT_STONE,
    TerrainCode.PALISADE: Substrate.WOOD,
    TerrainCode.GATE: Substrate.BUILT_STONE,
    TerrainCode.BUILDING: Substrate.BUILT_STONE,
    TerrainCode.RUIN: Substrate.BUILT_STONE,
    TerrainCode.DYKE: Substrate.BUILT_STONE,
    TerrainCode.MAGIC: Substrate.LIMESTONE,
    TerrainCode.HILL: Substrate.SOIL,
    TerrainCode.MOUNTAIN: Substrate.LIMESTONE,
}

_BUILT_TERRAIN: set[TerrainCode] = {
    TerrainCode.ROAD,
    TerrainCode.PLAZA,
    TerrainCode.BRIDGE,
    TerrainCode.WALL,
    TerrainCode.PALISADE,
    TerrainCode.GATE,
    TerrainCode.BUILDING,
    TerrainCode.RUIN,
    TerrainCode.CEMETERY,
    TerrainCode.DOCK,
    TerrainCode.DYKE,
    TerrainCode.MAGIC,
    TerrainCode.MOAT,
}


def terrain_to_overland_columns(
    combined_grid: NDArray[np.integer],
    *,
    biome: Biome = Biome.COASTAL_RAIN_FOREST,
    elevation_band: ElevationBand = ElevationBand.LOWLAND,
) -> dict[str, NDArray[np.generic]]:
    material = np.zeros(combined_grid.shape, dtype=np.int16)
    biome_grid = np.full(combined_grid.shape, int(biome), dtype=np.int16)
    elevation = np.full(combined_grid.shape, int(elevation_band), dtype=np.int16)
    hydro_role = np.zeros(combined_grid.shape, dtype=np.int16)
    wetness = np.full(combined_grid.shape, int(Wetness.DAMP), dtype=np.int16)
    substrate = np.full(combined_grid.shape, int(Substrate.SOIL), dtype=np.int16)
    flags = np.zeros(combined_grid.shape, dtype=np.uint32)
    walkable = np.zeros(combined_grid.shape, dtype=bool)
    blocks_sight = np.zeros(combined_grid.shape, dtype=bool)
    movement_cost = np.zeros(combined_grid.shape, dtype=np.float32)
    traversal_class = np.zeros(combined_grid.shape, dtype=np.int16)

    for y in range(combined_grid.shape[0]):
        for x in range(combined_grid.shape[1]):
            terrain = TerrainCode(int(combined_grid[y, x]))
            mat = _OVERLAND_MATERIAL_BY_TERRAIN[terrain]
            wet = _OVERLAND_WETNESS_BY_TERRAIN.get(terrain, Wetness.DAMP)
            sub = _OVERLAND_SUBSTRATE_BY_TERRAIN.get(terrain, Substrate.SOIL)
            flag_mask = _surface_flags_for_terrain(terrain)
            material[y, x] = int(mat)
            wetness[y, x] = int(wet)
            substrate[y, x] = int(sub)
            hydro_role[y, x] = int(_hydro_role_for_terrain(terrain))
            flags[y, x] = flag_mask
            walkable[y, x] = derive_walkable(mat, wet, flag_mask)
            blocks_sight[y, x] = derive_blocks_sight(mat, flag_mask)
            movement_cost[y, x] = derive_movement_cost(mat, wet, flag_mask)
            traversal_class[y, x] = int(derive_traversal_class(mat, wet, flag_mask))

    return {
        "material": material,
        "biome": biome_grid,
        "elevation_band": elevation,
        "hydro_role": hydro_role,
        "wetness": wetness,
        "substrate": substrate,
        "walkable": walkable,
        "blocks_sight": blocks_sight,
        "movement_cost": movement_cost,
        "traversal_class": traversal_class,
        "surface_flags": flags,
    }


def _surface_flags_for_terrain(terrain: TerrainCode) -> int:
    flags: list[SurfaceFlag] = []
    if terrain in _BUILT_TERRAIN:
        flags.append(SurfaceFlag.BUILT)
    if terrain in {
        TerrainCode.WATER,
        TerrainCode.DEEP_WATER,
        TerrainCode.SHORE,
        TerrainCode.MARSH,
        TerrainCode.SWAMP,
        TerrainCode.MOAT,
    }:
        flags.append(SurfaceFlag.SEASONAL)
    if terrain in {TerrainCode.MOAT, TerrainCode.MOUNTAIN}:
        flags.append(SurfaceFlag.HAZARD)
    if terrain in {TerrainCode.DENSE_FOREST, TerrainCode.SWAMP}:
        flags.append(SurfaceFlag.VEGETATION_DENSE)
    return surface_flag_mask(*flags)


def _hydro_role_for_terrain(terrain: TerrainCode) -> HydroRole:
    if terrain in {TerrainCode.WATER, TerrainCode.DEEP_WATER, TerrainCode.MOAT}:
        return HydroRole.PERMANENT_POOL
    if terrain in {TerrainCode.MARSH, TerrainCode.SWAMP}:
        return HydroRole.TEMPORARY_POOL
    if terrain == TerrainCode.SHORE:
        return HydroRole.SEEP
    return HydroRole.NONE
