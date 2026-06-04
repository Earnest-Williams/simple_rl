"""Shared constants and enums for map materials and features."""

from enum import IntEnum, auto


class Material(IntEnum):
    """Material identifiers for dungeon, settlement, and overland surfaces."""

    VOID = 0
    SOLID_ROCK = 0

    # Vegetation and organic surface
    GRASS = auto()
    FOREST_FLOOR = auto()
    FERN_UNDERSTORY = auto()
    MOSS = auto()
    REEDBED = auto()
    HEATH = auto()

    # Mud, soil, and unstable ground
    DIRT = auto()
    CLAY = auto()
    MUD = auto()
    DEEP_MUD = auto()
    MUDFLAT = auto()
    CRACKED_MUD = auto()
    SILT = auto()
    GRAVEL = auto()
    SCREE = auto()

    # Water surfaces
    SHALLOW_WATER = auto()
    DEEP_WATER = auto()
    FLOWING_WATER = auto()
    SPRING_WATER = auto()
    SINKING_WATER = auto()
    ESTAVELLE_WATER = auto()
    STAGNANT_WATER = auto()
    BOG_WATER = auto()
    UNDERGROUND_WATER = auto()

    # Karst and caves
    LIMESTONE = auto()
    LIMESTONE_PAVEMENT = auto()
    LIMESTONE_CLIFF = auto()
    CAVE_FLOOR = auto()
    CAVE_WALL = auto()
    CAVE_MOUTH = auto()
    FLOWSTONE = auto()
    PONOR = auto()
    SINKHOLE_EDGE = auto()

    # Volcanic and lava-tube terrain
    BASALT = auto()
    BASALT_PAVEMENT = auto()
    BASALT_CLIFF = auto()
    SCORIA = auto()
    VOLCANIC_ASH = auto()
    LAVA_TUBE_FLOOR = auto()
    LAVA_TUBE_WALL = auto()
    LAVA_TUBE_SKYLIGHT = auto()
    COLLAPSED_LAVA_TUBE = auto()

    # Peatland and highland wetland
    PEAT = auto()
    PEAT_BOG = auto()
    SPHAGNUM = auto()
    BOG_POOL = auto()
    TARN = auto()
    BUTTON_GRASS = auto()

    # Built and modified
    ROAD = auto()
    TRACK = auto()
    TRAIL = auto()
    ANIMAL_TRAIL = auto()
    FISH_TRAIL = auto()
    BOARDWALK = auto()
    BRIDGE = auto()
    DOCK = auto()
    BUILDING_FLOOR = auto()
    WOOD_WALL = auto()
    STONE_WALL = auto()
    RUIN_FLOOR = auto()
    RUIN_WALL = auto()
    FIELD = auto()
    ORCHARD = auto()
    PASTURE = auto()
    CLEARCUT = auto()

    # Legacy dungeon and door material names retained for existing systems.
    SHAFT_OPENING = auto()
    CLIFF_EDGE = auto()
    DOOR_CLOSED = auto()
    DOOR_OPEN = auto()


class FeatureType(IntEnum):
    """Map feature identifiers used across the game."""

    FLOOR = 0
    WALL = 1
    CLOSED_DOOR = 2
    OPEN_DOOR = 3
    SECRET_DOOR = 4


__all__ = ["FeatureType", "Material"]
