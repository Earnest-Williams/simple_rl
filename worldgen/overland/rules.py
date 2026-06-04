from __future__ import annotations

from common.constants import Material
from worldgen.overland.schema import SurfaceFlag, Wetness

_NON_WALKABLE: set[Material] = {
    Material.VOID,
    Material.DEEP_WATER,
    Material.UNDERGROUND_WATER,
    Material.LIMESTONE_CLIFF,
    Material.CAVE_WALL,
    Material.BASALT_CLIFF,
    Material.LAVA_TUBE_WALL,
    Material.WOOD_WALL,
    Material.STONE_WALL,
    Material.RUIN_WALL,
    Material.CLIFF_EDGE,
    Material.DOOR_CLOSED,
}

_SIGHT_BLOCKERS: set[Material] = {
    Material.LIMESTONE_CLIFF,
    Material.CAVE_WALL,
    Material.BASALT_CLIFF,
    Material.LAVA_TUBE_WALL,
    Material.WOOD_WALL,
    Material.STONE_WALL,
    Material.RUIN_WALL,
    Material.CLIFF_EDGE,
    Material.DOOR_CLOSED,
}

_DENSE_VEGETATION: set[Material] = {
    Material.FOREST_FLOOR,
    Material.FERN_UNDERSTORY,
    Material.REEDBED,
}


def surface_flag_mask(*flags: SurfaceFlag) -> int:
    value = 0
    for flag in flags:
        if flag != SurfaceFlag.NONE:
            value |= 1 << (int(flag) - 1)
    return value


def has_surface_flag(mask: int, flag: SurfaceFlag) -> bool:
    if flag == SurfaceFlag.NONE:
        return mask == 0
    return bool(mask & (1 << (int(flag) - 1)))


def derive_walkable(material: Material, wetness: Wetness, flags: int = 0) -> bool:
    if material in _NON_WALKABLE:
        return False
    if wetness == Wetness.DEEP_FLOODED:
        return material in {
            Material.BRIDGE,
            Material.BOARDWALK,
            Material.DOCK,
            Material.SHALLOW_WATER,
        }
    if material == Material.DEEP_MUD:
        return has_surface_flag(flags, SurfaceFlag.SEASONAL)
    return True


def derive_blocks_sight(material: Material, flags: int = 0) -> bool:
    return material in _SIGHT_BLOCKERS or material in _DENSE_VEGETATION or has_surface_flag(
        flags, SurfaceFlag.VEGETATION_DENSE
    )
