"""Shared constants and enums for map materials and features."""

from enum import IntEnum


class Material(IntEnum):
    """Material identifiers for dungeon tiles and geometry."""

    SOLID_ROCK = 0
    CAVE_FLOOR = 1
    SHAFT_OPENING = 2
    CLIFF_EDGE = 3
    DOOR_CLOSED = 4
    DOOR_OPEN = 5


class FeatureType(IntEnum):
    """Map feature identifiers used across the game."""

    FLOOR = 0
    WALL = 1
    CLOSED_DOOR = 2
    OPEN_DOOR = 3
    SECRET_DOOR = 4


__all__ = ["FeatureType", "Material"]
