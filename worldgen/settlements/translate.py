from __future__ import annotations

from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from common.constants import Material
from settlegen import TerrainCode


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
