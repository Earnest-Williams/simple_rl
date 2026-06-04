from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Any

import polars as pl

SCHEMA_VERSION = "overland-1"


class Biome(IntEnum):
    COASTAL_RAIN_FOREST = auto()
    KARST_WET_FOREST = auto()
    SINKING_LAKE_BASIN = auto()
    ESTAVELLE_MARSH = auto()
    SPRING_GARDEN = auto()
    LIMESTONE_GORGE = auto()
    FOOTHILL_HARDWOOD_FOREST = auto()
    VOLCANIC_CLOUD_FOREST = auto()
    LAVA_TUBE_FOREST = auto()
    BASALT_BARRENS = auto()
    HIGHLAND_PEAT_MOOR = auto()
    SUBALPINE_HEATH = auto()


class HydroRole(IntEnum):
    NONE = 0
    SURFACE_CHANNEL = auto()
    UNDERGROUND_CHANNEL = auto()
    SPRING = auto()
    SEEP = auto()
    PONOR = auto()
    ESTAVELLE = auto()
    TEMPORARY_POOL = auto()
    PERMANENT_POOL = auto()
    SINKING_LAKE = auto()
    KARST_WINDOW = auto()


class Wetness(IntEnum):
    DRY = auto()
    DAMP = auto()
    WET = auto()
    SATURATED = auto()
    SHALLOW_FLOODED = auto()
    DEEP_FLOODED = auto()


class Substrate(IntEnum):
    SOIL = auto()
    CLAY = auto()
    MUD = auto()
    PEAT = auto()
    LIMESTONE = auto()
    BASALT = auto()
    WOOD = auto()
    BUILT_STONE = auto()


class ElevationBand(IntEnum):
    LOWLAND = auto()
    BASIN = auto()
    FOOTHILL = auto()
    MOUNTAIN = auto()
    HIGHLAND = auto()


class HydroState(IntEnum):
    WET_SEASON = auto()
    DRAINING = auto()
    MUD_SEASON = auto()
    DRY_SEASON = auto()


class SurfaceFlag(IntEnum):
    NONE = 0
    SLOWS_MOVEMENT = auto()
    HAZARD = auto()
    TRANSITION = auto()
    BUILT = auto()
    VEGETATION_DENSE = auto()
    SEASONAL = auto()


class FeatureType(IntEnum):
    CAVE_MOUTH = auto()
    PONOR = auto()
    ESTAVELLE = auto()
    SPRING = auto()
    KARST_WINDOW = auto()
    LAVA_TUBE_SKYLIGHT = auto()
    COLLAPSED_LAVA_TUBE = auto()
    FISH_TRAIL = auto()
    TRAIL_EXIT = auto()


class TransitionType(IntEnum):
    CAVE_ENTRANCE = auto()
    PONOR_DESCENT = auto()
    KARST_WINDOW = auto()
    SPRING_SOURCE = auto()
    LAVA_TUBE_SKYLIGHT = auto()
    COLLAPSED_LAVA_TUBE = auto()
    SETTLEMENT_ENTRANCE = auto()
    DOCK_ROUTE = auto()
    TRAIL_EXIT = auto()


class Affordance(IntEnum):
    FISH_MIGRATION = auto()
    MUDFLAT_SUNNING = auto()
    BURROWING_MUD = auto()
    MUSTELID_HUNTING = auto()
    OCTOPUS_REFUGE = auto()
    SPRING_REFUGE = auto()
    CAVE_REFUGE = auto()
    AMPHIBIOUS_CORRIDOR = auto()


@dataclass(frozen=True, slots=True)
class OverlandBundle:
    tiles_df: pl.DataFrame
    hydrology_df: pl.DataFrame
    features_df: pl.DataFrame
    affordances_df: pl.DataFrame
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SurfaceTransitionRequest:
    source_x: int
    source_y: int
    transition_type: TransitionType
    target_kind: str
    hydro_role: HydroRole
    biome: Biome
    material: int
    seed: int
    tags: tuple[str, ...] = ()
