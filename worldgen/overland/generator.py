from __future__ import annotations

from typing import Literal

import numpy as np
import polars as pl

from common.constants import Material
from utils.game_rng import GameRNG
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.rules import (
    derive_blocks_sight,
    derive_movement_cost,
    derive_traversal_class,
    derive_walkable,
    surface_flag_mask,
)
from worldgen.overland.schema import (
    SCHEMA_VERSION,
    Biome,
    ElevationBand,
    EvidenceTag,
    FeatureType,
    HydroRole,
    OverlandBundle,
    RouteSegmentState,
    Substrate,
    SurfaceFlag,
    Wetness,
)

OverlandProfile = Literal["KARST_TO_VOLCANIC_MOUNTAIN"]
KARST_FLOW_GROUP = 1
PERENNIAL_SURFACE_FLOW_GROUP = 2
STARTING_REGION_FEATURES = {
    "ruined_harbor": (0.18, 0.09),
    "fresh_water_site": (0.55, 0.34),
    "reed_resource_site": (0.40, 0.43),
    "timber_resource_site": (0.35, 0.21),
    "stone_resource_site": (0.64, 0.33),
    "road_coast": (0.18, 0.12),
    "road_inland": (0.62, 0.46),
    "clearable_blockage": (0.43, 0.31),
    "waystation_candidate": (0.50, 0.37),
    "inland_site": (0.62, 0.46),
    "ordinary_cave": (0.36, 0.24),
}


def generate_overland_region(
    *,
    seed: int,
    width: int,
    height: int,
    profile: OverlandProfile = "KARST_TO_VOLCANIC_MOUNTAIN",
) -> OverlandBundle:
    if profile != "KARST_TO_VOLCANIC_MOUNTAIN":
        raise ValueError(f"Unsupported overland profile: {profile}")
    if (
        width < 32 or height < 24
    ):  # relaxed for testing/small regions; production prefers >=48x40
        raise ValueError("width must be >= 32 and height must be >= 24")

    rng = GameRNG(seed=seed)
    y, x = np.indices((height, width))
    yn = y / max(1, height - 1)
    noise = np.array(
        rng.get_floats(0.0, 1.0, width * height), dtype=np.float32
    ).reshape(height, width)

    biome = np.full((height, width), int(Biome.KARST_WET_FOREST), dtype=np.int16)
    material = np.full((height, width), int(Material.FOREST_FLOOR), dtype=np.int16)
    elevation = np.full((height, width), int(ElevationBand.LOWLAND), dtype=np.int16)
    substrate = np.full((height, width), int(Substrate.SOIL), dtype=np.int16)
    wetness = np.full((height, width), int(Wetness.DAMP), dtype=np.int16)
    flags = np.zeros((height, width), dtype=np.uint32)
    hydro = np.zeros((height, width), dtype=np.int16)
    flow_group = np.zeros((height, width), dtype=np.int32)
    seasonal = np.full((height, width), "stable", dtype=object)
    underground = np.zeros((height, width), dtype=bool)

    _apply_base_bands(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        yn=yn,
        noise=noise,
    )
    _apply_karst_features(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
    )
    _apply_perennial_surface_water(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
    )
    _apply_volcanic_features(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        underground=underground,
        width=width,
        height=height,
    )
    starting_region = _starting_region_contract(width=width, height=height)
    _apply_starting_region_features(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        contract=starting_region,
    )

    walkable, blocks_sight, movement_cost, traversal_class = _derive_gameplay_layers(
        material, wetness, flags
    )
    tiles_df = _tiles_df(
        material=material,
        biome=biome,
        elevation=elevation,
        hydro=hydro,
        wetness=wetness,
        substrate=substrate,
        walkable=walkable,
        blocks_sight=blocks_sight,
        movement_cost=movement_cost,
        traversal_class=traversal_class,
        flags=flags,
    )
    hydrology_df = _hydrology_df(
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
    )
    features_df = _features_df(
        width=width, height=height, starting_region=starting_region
    )
    metadata = {
        "seed": seed,
        "width": width,
        "height": height,
        "profile": profile,
        "schema_version": SCHEMA_VERSION,
        "starting_region_contract": starting_region,
        "route_segments": starting_region.get("route_segments", []),
    }
    bundle = OverlandBundle(
        tiles_df=tiles_df,
        hydrology_df=hydrology_df,
        features_df=features_df,
        affordances_df=pl.DataFrame(),
        metadata=metadata,
    )
    return OverlandBundle(
        tiles_df=tiles_df,
        hydrology_df=hydrology_df,
        features_df=features_df,
        affordances_df=generate_affordances(bundle),
        metadata=metadata,
    )


def _apply_base_bands(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    yn: np.ndarray,
    noise: np.ndarray,
) -> None:
    coast = yn < 0.12
    biome[coast] = int(Biome.COASTAL_RAIN_FOREST)
    material[coast] = int(Material.MUDFLAT)
    wetness[coast] = int(Wetness.WET)
    substrate[coast] = int(Substrate.MUD)

    karst = (yn >= 0.12) & (yn < 0.43)
    material[karst & (noise > 0.62)] = int(Material.FERN_UNDERSTORY)
    wetness[karst] = int(Wetness.WET)
    substrate[karst] = int(Substrate.LIMESTONE)

    foothill = (yn >= 0.43) & (yn < 0.58)
    biome[foothill] = int(Biome.FOOTHILL_HARDWOOD_FOREST)
    elevation[foothill] = int(ElevationBand.FOOTHILL)
    material[foothill] = int(Material.GRAVEL)
    wetness[foothill] = int(Wetness.DAMP)

    volcanic = (yn >= 0.58) & (yn < 0.77)
    biome[volcanic] = int(Biome.VOLCANIC_CLOUD_FOREST)
    elevation[volcanic] = int(ElevationBand.MOUNTAIN)
    material[volcanic] = int(Material.MOSS)
    substrate[volcanic] = int(Substrate.BASALT)
    wetness[volcanic] = int(Wetness.WET)

    lava_forest = (yn >= 0.77) & (yn < 0.88)
    biome[lava_forest] = int(Biome.LAVA_TUBE_FOREST)
    elevation[lava_forest] = int(ElevationBand.MOUNTAIN)
    material[lava_forest] = int(Material.BASALT_PAVEMENT)
    substrate[lava_forest] = int(Substrate.BASALT)

    highland = yn >= 0.88
    biome[highland] = int(Biome.HIGHLAND_PEAT_MOOR)
    elevation[highland] = int(ElevationBand.HIGHLAND)
    material[highland] = int(Material.PEAT_BOG)
    substrate[highland] = int(Substrate.PEAT)
    wetness[highland] = int(Wetness.SATURATED)

    barrens = highland & (noise > 0.67)
    biome[barrens] = int(Biome.BASALT_BARRENS)
    material[barrens] = int(Material.BASALT)
    wetness[barrens] = int(Wetness.DRY)

    flags[material == int(Material.FERN_UNDERSTORY)] = surface_flag_mask(
        SurfaceFlag.VEGETATION_DENSE
    )


def _apply_karst_features(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
) -> None:
    basin = _ellipse_mask(width, height, 0.28, 0.29, 0.16, 0.10)
    biome[basin] = int(Biome.SINKING_LAKE_BASIN)
    elevation[basin] = int(ElevationBand.BASIN)
    material[basin] = int(Material.SHALLOW_WATER)
    wetness[basin] = int(Wetness.SHALLOW_FLOODED)
    substrate[basin] = int(Substrate.CLAY)
    hydro[basin] = int(HydroRole.SINKING_LAKE)
    flow_group[basin] = KARST_FLOW_GROUP
    seasonal[basin] = "seasonal"
    flags[basin] = surface_flag_mask(SurfaceFlag.SEASONAL)

    lake_core = _ellipse_mask(width, height, 0.28, 0.29, 0.08, 0.045)
    material[lake_core] = int(Material.DEEP_WATER)
    wetness[lake_core] = int(Wetness.DEEP_FLOODED)

    spring = _ellipse_mask(width, height, 0.55, 0.34, 0.10, 0.08)
    biome[spring] = int(Biome.SPRING_GARDEN)
    material[spring] = int(Material.MOSS)
    wetness[spring] = int(Wetness.SATURATED)
    substrate[spring] = int(Substrate.LIMESTONE)
    hydro[spring] = int(HydroRole.SEEP)
    flow_group[spring] = KARST_FLOW_GROUP
    spring_core = _ellipse_mask(width, height, 0.55, 0.34, 0.035, 0.025)
    material[spring_core] = int(Material.SPRING_WATER)
    hydro[spring_core] = int(HydroRole.SPRING)
    wetness[spring_core] = int(Wetness.SHALLOW_FLOODED)

    marsh = _ellipse_mask(width, height, 0.40, 0.43, 0.16, 0.09)
    biome[marsh] = int(Biome.ESTAVELLE_MARSH)
    material[marsh] = int(Material.REEDBED)
    wetness[marsh] = int(Wetness.SATURATED)
    substrate[marsh] = int(Substrate.MUD)
    hydro[marsh] = int(HydroRole.SEEP)
    flow_group[marsh] = KARST_FLOW_GROUP
    flags[marsh] = surface_flag_mask(SurfaceFlag.SEASONAL, SurfaceFlag.VEGETATION_DENSE)

    estavelle = _ellipse_mask(width, height, 0.40, 0.43, 0.035, 0.025)
    material[estavelle] = int(Material.ESTAVELLE_WATER)
    hydro[estavelle] = int(HydroRole.ESTAVELLE)
    flow_group[estavelle] = KARST_FLOW_GROUP
    wetness[estavelle] = int(Wetness.SHALLOW_FLOODED)
    underground[estavelle] = True

    ponor = _ellipse_mask(width, height, 0.20, 0.37, 0.035, 0.025)
    material[ponor] = int(Material.PONOR)
    hydro[ponor] = int(HydroRole.PONOR)
    flow_group[ponor] = KARST_FLOW_GROUP
    wetness[ponor] = int(Wetness.SHALLOW_FLOODED)
    substrate[ponor] = int(Substrate.LIMESTONE)
    underground[ponor] = True
    flags[ponor] = surface_flag_mask(
        SurfaceFlag.HAZARD, SurfaceFlag.TRANSITION, SurfaceFlag.SEASONAL
    )

    _apply_surface_hydrology_channel(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        width=width,
        height=height,
        start=(0.55, 0.34),
        end=(0.40, 0.43),
    )
    _apply_surface_hydrology_channel(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        width=width,
        height=height,
        start=(0.32, 0.36),
        end=(0.40, 0.43),
    )
    _apply_surface_hydrology_channel(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        width=width,
        height=height,
        start=(0.27, 0.36),
        end=(0.20, 0.37),
    )

    fish_trail = _line_mask(width, height, (0.28, 0.38), (0.47, 0.45), radius=1)
    material[fish_trail] = int(Material.FISH_TRAIL)
    hydro[fish_trail] = int(HydroRole.TEMPORARY_POOL)
    flow_group[fish_trail] = KARST_FLOW_GROUP
    wetness[fish_trail] = int(Wetness.WET)
    substrate[fish_trail] = int(Substrate.MUD)
    flags[fish_trail] = surface_flag_mask(
        SurfaceFlag.SEASONAL, SurfaceFlag.SLOWS_MOVEMENT
    )

    gorge = _line_mask(width, height, (0.66, 0.32), (0.62, 0.57), radius=2)
    biome[gorge] = int(Biome.LIMESTONE_GORGE)
    material[gorge] = int(Material.LIMESTONE_PAVEMENT)
    elevation[gorge] = int(ElevationBand.FOOTHILL)
    substrate[gorge] = int(Substrate.LIMESTONE)
    wetness[gorge] = int(Wetness.DAMP)
    hydro[gorge] = int(HydroRole.SURFACE_CHANNEL)
    flow_group[gorge] = KARST_FLOW_GROUP

    gorge_wall = _line_mask(width, height, (0.69, 0.32), (0.65, 0.57), radius=1)
    biome[gorge_wall] = int(Biome.LIMESTONE_GORGE)
    material[gorge_wall] = int(Material.LIMESTONE_CLIFF)
    hydro[gorge_wall] = int(HydroRole.NONE)

    cave = _ellipse_mask(width, height, 0.62, 0.55, 0.025, 0.018)
    material[cave] = int(Material.CAVE_MOUTH)
    hydro[cave] = int(HydroRole.KARST_WINDOW)
    flow_group[cave] = KARST_FLOW_GROUP
    underground[cave] = True
    flags[cave] = surface_flag_mask(SurfaceFlag.TRANSITION)

    _apply_underground_hydrology_channel(
        substrate=substrate,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        start=(0.20, 0.37),
        end=(0.40, 0.43),
    )
    _apply_underground_hydrology_channel(
        substrate=substrate,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        start=(0.40, 0.43),
        end=(0.62, 0.55),
    )


def _apply_surface_hydrology_channel(
    *,
    material: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    width: int,
    height: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    channel = _line_mask(width, height, start, end, radius=1)
    unassigned = channel & (hydro == int(HydroRole.NONE))
    material[unassigned] = int(Material.FLOWING_WATER)
    wetness[unassigned] = int(Wetness.SHALLOW_FLOODED)
    substrate[unassigned] = int(Substrate.LIMESTONE)
    hydro[unassigned] = int(HydroRole.SURFACE_CHANNEL)
    flow_group[unassigned] = KARST_FLOW_GROUP
    seasonal[unassigned] = "seasonal"
    flags[unassigned] = surface_flag_mask(SurfaceFlag.SEASONAL)

    flow_group[channel] = KARST_FLOW_GROUP


def _apply_underground_hydrology_channel(
    *,
    substrate: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    channel = _line_mask(width, height, start, end, radius=1)
    unassigned = channel & (hydro == int(HydroRole.NONE))
    substrate[unassigned] = int(Substrate.LIMESTONE)
    hydro[unassigned] = int(HydroRole.UNDERGROUND_CHANNEL)
    flow_group[unassigned] = KARST_FLOW_GROUP
    seasonal[unassigned] = "subsurface"
    underground[unassigned] = True

    flow_group[channel] = KARST_FLOW_GROUP
    underground[channel] = True


def _apply_perennial_surface_water(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
) -> None:
    pond = _ellipse_mask(width, height, 0.82, 0.50, 0.07, 0.045)
    biome[pond] = int(Biome.FOOTHILL_HARDWOOD_FOREST)
    elevation[pond] = int(ElevationBand.FOOTHILL)
    material[pond] = int(Material.SHALLOW_WATER)
    wetness[pond] = int(Wetness.SHALLOW_FLOODED)
    substrate[pond] = int(Substrate.CLAY)
    hydro[pond] = int(HydroRole.PERMANENT_POOL)
    flow_group[pond] = PERENNIAL_SURFACE_FLOW_GROUP
    seasonal[pond] = "stable"
    underground[pond] = False
    flags[pond] = 0

    pond_core = _ellipse_mask(width, height, 0.82, 0.50, 0.035, 0.02)
    material[pond_core] = int(Material.DEEP_WATER)
    wetness[pond_core] = int(Wetness.DEEP_FLOODED)

    _apply_perennial_surface_channel(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        start=(0.74, 0.45),
        end=(0.82, 0.50),
    )
    _apply_perennial_surface_channel(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        start=(0.82, 0.50),
        end=(0.93, 0.55),
    )


def _apply_perennial_surface_channel(
    *,
    material: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
    start: tuple[float, float],
    end: tuple[float, float],
) -> None:
    channel = _line_mask(width, height, start, end, radius=1)
    unassigned = channel & (hydro == int(HydroRole.NONE))
    material[unassigned] = int(Material.FLOWING_WATER)
    wetness[unassigned] = int(Wetness.SHALLOW_FLOODED)
    substrate[unassigned] = int(Substrate.CLAY)
    hydro[unassigned] = int(HydroRole.SURFACE_CHANNEL)
    flow_group[unassigned] = PERENNIAL_SURFACE_FLOW_GROUP
    seasonal[unassigned] = "stable"
    underground[unassigned] = False
    flags[unassigned] = 0

    flow_group[channel] = PERENNIAL_SURFACE_FLOW_GROUP
    underground[channel] = False


def _apply_volcanic_features(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
) -> None:
    tube = _line_mask(width, height, (0.30, 0.78), (0.80, 0.86), radius=2)
    biome[tube] = int(Biome.LAVA_TUBE_FOREST)
    material[tube] = int(Material.LAVA_TUBE_FLOOR)
    elevation[tube] = int(ElevationBand.MOUNTAIN)
    substrate[tube] = int(Substrate.BASALT)
    wetness[tube] = int(Wetness.DAMP)
    underground[tube] = True

    skylight = _ellipse_mask(width, height, 0.55, 0.82, 0.035, 0.025)
    material[skylight] = int(Material.LAVA_TUBE_SKYLIGHT)
    hydro[skylight] = int(HydroRole.NONE)
    underground[skylight] = True
    flags[skylight] = surface_flag_mask(SurfaceFlag.TRANSITION, SurfaceFlag.HAZARD)

    collapse = _ellipse_mask(width, height, 0.72, 0.86, 0.045, 0.03)
    material[collapse] = int(Material.COLLAPSED_LAVA_TUBE)
    underground[collapse] = True
    flags[collapse] = surface_flag_mask(SurfaceFlag.TRANSITION, SurfaceFlag.HAZARD)

    barrens = _ellipse_mask(width, height, 0.77, 0.72, 0.13, 0.08)
    biome[barrens] = int(Biome.BASALT_BARRENS)
    material[barrens] = int(Material.BASALT_PAVEMENT)
    substrate[barrens] = int(Substrate.BASALT)
    wetness[barrens] = int(Wetness.DRY)


def _starting_region_contract(*, width: int, height: int) -> dict[str, object]:
    points = {
        name: _point(width, height, *coords)
        for name, coords in STARTING_REGION_FEATURES.items()
    }
    return {
        "kind": "first_expedition_region",
        "player_spawn": list(points["road_coast"]),
        "player_spawn_kind": "starting_port_road_entrance",
        "harbor": {
            "point": list(points["ruined_harbor"]),
            "state": "ruined_dead_port",
            "evidence_tags": [
                int(EvidenceTag.LATE_COLONIAL_OCCUPATION),
                int(EvidenceTag.RUINED),
                int(EvidenceTag.OVERGROWN),
            ],
        },
        "local_survey_zone": {
            "center": list(points["ruined_harbor"]),
            "radius_tiles": max(6, min(width, height) // 8),
        },
        "route_segments": [
            {
                "route_id": "ancient_road_harbor_to_inland_site",
                "from": "ruined_harbor",
                "from_point": list(points["road_coast"]),
                "to": "inland_site",
                "to_point": list(points["road_inland"]),
                "state": int(RouteSegmentState.BLOCKED),
                "blockage": "road_landslip_01",
                "repair_cost": 45,  # base effort to clear/repair
                "evidence_tags": [
                    int(EvidenceTag.EARLY_COLONIAL_OCCUPATION),
                    int(EvidenceTag.ROAD_ENGINEERING),
                    int(EvidenceTag.RECENT_COLLAPSE),
                    int(EvidenceTag.PRIOR_EXPEDITION),
                    int(EvidenceTag.PARTIAL_REPAIR),
                ],
                "last_modified": 0,  # seed-relative timestamp for lifecycle
                "profile_costs": {
                    "HUMAN_ON_FOOT": 1.0,
                    "PACK_ANIMAL": 1.0,
                    "SMALL_AMPHIBIOUS": 1.0,
                    "SWIMMER": 1.25,
                    "BOAT": None,
                },
            }
        ],
        "blockages": [
            {
                "blockage_id": "road_landslip_01",
                "point": list(points["clearable_blockage"]),
                "state": "clearable",
                "blocks_route": "ancient_road_harbor_to_inland_site",
                "evidence_tags": [
                    int(EvidenceTag.RECENT_COLLAPSE),
                    int(EvidenceTag.SUBSIDENCE_DAMAGE),
                ],
            }
        ],
        "resource_sites": [
            {
                "site_id": "spring_water_01",
                "kind": "fresh_water",
                "point": list(points["fresh_water_site"]),
            },
            {
                "site_id": "reed_mudflat_01",
                "kind": "reeds_and_mud",
                "point": list(points["reed_resource_site"]),
            },
            {
                "site_id": "wet_forest_timber_01",
                "kind": "timber",
                "point": list(points["timber_resource_site"]),
            },
            {
                "site_id": "limestone_roadstone_01",
                "kind": "stone",
                "point": list(points["stone_resource_site"]),
            },
        ],
        "waystation_candidates": [
            {
                "site_id": "first_waystation_candidate",
                "point": list(points["waystation_candidate"]),
                "route": "ancient_road_harbor_to_inland_site",
                "evidence_tags": [
                    int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
                    int(EvidenceTag.WAYSTATION_REMAINS),
                    int(EvidenceTag.PARTIAL_REPAIR),
                ],
            }
        ],
        "inland_sites": [
            {
                "site_id": "first_inland_site",
                "point": list(points["inland_site"]),
                "kind": "ruin_or_settlement_candidate",
                "evidence_tags": [
                    int(EvidenceTag.PRECURSOR_OCCUPATION),
                    int(EvidenceTag.MAUSOLEUM_COMPLEX),
                    int(EvidenceTag.RUINED),
                    int(EvidenceTag.OVERGROWN),
                ],
            }
        ],
        "cave_refs": [
            {
                "site_id": "ordinary_limestone_cave_01",
                "point": list(points["ordinary_cave"]),
                "kind": "ordinary_cave",
                "transition": "cave_entrance",
                "evidence_tags": [
                    int(EvidenceTag.PRECURSOR_OCCUPATION),
                    int(EvidenceTag.PRIOR_EXPEDITION),
                ],
            }
        ],
    }


def _apply_starting_region_features(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
    contract: dict[str, object],
) -> None:
    _apply_ruined_harbor(
        biome=biome,
        material=material,
        elevation=elevation,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
    )
    _apply_ancient_road(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        width=width,
        height=height,
    )
    _apply_starting_region_sites(
        material=material,
        substrate=substrate,
        wetness=wetness,
        flags=flags,
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
        width=width,
        height=height,
        contract=contract,
    )


def _apply_ruined_harbor(
    *,
    biome: np.ndarray,
    material: np.ndarray,
    elevation: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
) -> None:
    harbor = _rect_mask(
        width, height, center=STARTING_REGION_FEATURES["ruined_harbor"], rx=3, ry=2
    )
    biome[harbor] = int(Biome.COASTAL_RAIN_FOREST)
    elevation[harbor] = int(ElevationBand.LOWLAND)
    material[harbor] = int(Material.RUIN_FLOOR)
    substrate[harbor] = int(Substrate.BUILT_STONE)
    wetness[harbor] = int(Wetness.DAMP)
    hydro[harbor] = int(HydroRole.NONE)
    flow_group[harbor] = 0
    seasonal[harbor] = "stable"
    underground[harbor] = False
    flags[harbor] = surface_flag_mask(SurfaceFlag.BUILT)

    dock = _rect_mask(width, height, center=(0.18, 0.06), rx=2, ry=1)
    material[dock] = int(Material.DOCK)
    substrate[dock] = int(Substrate.WOOD)
    wetness[dock] = int(Wetness.DAMP)
    hydro[dock] = int(HydroRole.NONE)
    flow_group[dock] = 0
    underground[dock] = False
    flags[dock] = surface_flag_mask(SurfaceFlag.BUILT)


def _apply_ancient_road(
    *,
    material: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    width: int,
    height: int,
) -> None:
    road = np.zeros((height, width), dtype=bool)
    road |= _line_mask(width, height, (0.18, 0.12), (0.35, 0.22), radius=1)
    road |= _line_mask(width, height, (0.35, 0.22), (0.50, 0.37), radius=1)
    road |= _line_mask(width, height, (0.50, 0.37), (0.62, 0.46), radius=1)
    material[road] = int(Material.ROAD)
    substrate[road] = int(Substrate.BUILT_STONE)
    wetness[road] = int(Wetness.DAMP)
    flags[road] = surface_flag_mask(SurfaceFlag.BUILT)


def _apply_starting_region_sites(
    *,
    material: np.ndarray,
    substrate: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
    width: int,
    height: int,
    contract: dict[str, object],
) -> None:
    blockage_x, blockage_y = _contract_point(contract, "blockages", 0, "point")
    material[blockage_y, blockage_x] = int(Material.SINKHOLE_EDGE)
    substrate[blockage_y, blockage_x] = int(Substrate.LIMESTONE)
    wetness[blockage_y, blockage_x] = int(Wetness.DAMP)
    flags[blockage_y, blockage_x] = surface_flag_mask(SurfaceFlag.HAZARD)

    waystation_x, waystation_y = _contract_point(
        contract,
        "waystation_candidates",
        0,
        "point",
    )
    material[waystation_y, waystation_x] = int(Material.RUIN_FLOOR)
    substrate[waystation_y, waystation_x] = int(Substrate.BUILT_STONE)
    wetness[waystation_y, waystation_x] = int(Wetness.DAMP)
    flags[waystation_y, waystation_x] = surface_flag_mask(SurfaceFlag.BUILT)

    inland_x, inland_y = _contract_point(contract, "inland_sites", 0, "point")
    material[inland_y, inland_x] = int(Material.RUIN_FLOOR)
    substrate[inland_y, inland_x] = int(Substrate.BUILT_STONE)
    wetness[inland_y, inland_x] = int(Wetness.DAMP)
    flags[inland_y, inland_x] = surface_flag_mask(SurfaceFlag.BUILT)

    cave_x, cave_y = _contract_point(contract, "cave_refs", 0, "point")
    material[cave_y, cave_x] = int(Material.CAVE_MOUTH)
    substrate[cave_y, cave_x] = int(Substrate.LIMESTONE)
    wetness[cave_y, cave_x] = int(Wetness.DAMP)
    hydro[cave_y, cave_x] = int(HydroRole.NONE)
    flow_group[cave_y, cave_x] = 0
    seasonal[cave_y, cave_x] = "stable"
    underground[cave_y, cave_x] = True
    flags[cave_y, cave_x] = surface_flag_mask(SurfaceFlag.TRANSITION)


def _contract_point(
    contract: dict[str, object],
    collection: str,
    index: int,
    key: str,
) -> tuple[int, int]:
    items = contract[collection]
    if not isinstance(items, list):
        raise TypeError(f"Expected {collection} to be a list")
    item = items[index]
    if not isinstance(item, dict):
        raise TypeError(f"Expected {collection}[{index}] to be a dict")
    point = item[key]
    if not isinstance(point, list | tuple) or len(point) != 2:
        raise TypeError(f"Expected {collection}[{index}][{key}] to be a point")
    return int(point[0]), int(point[1])


def _ellipse_mask(
    width: int,
    height: int,
    cx_frac: float,
    cy_frac: float,
    rx_frac: float,
    ry_frac: float,
) -> np.ndarray:
    yy, xx = np.indices((height, width))
    cx = cx_frac * (width - 1)
    cy = cy_frac * (height - 1)
    rx = max(1.0, rx_frac * width)
    ry = max(1.0, ry_frac * height)
    return (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2) <= 1.0


def _line_mask(
    width: int,
    height: int,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    radius: int,
) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    x0 = int(round(start[0] * (width - 1)))
    y0 = int(round(start[1] * (height - 1)))
    x1 = int(round(end[0] * (width - 1)))
    y1 = int(round(end[1] * (height - 1)))
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for i in range(steps + 1):
        t = i / steps
        x = int(round(x0 + (x1 - x0) * t))
        y = int(round(y0 + (y1 - y0) * t))
        y_min = max(0, y - radius)
        y_max = min(height, y + radius + 1)
        x_min = max(0, x - radius)
        x_max = min(width, x + radius + 1)
        mask[y_min:y_max, x_min:x_max] = True
    return mask


def _rect_mask(
    width: int,
    height: int,
    *,
    center: tuple[float, float],
    rx: int,
    ry: int,
) -> np.ndarray:
    x, y = _point(width, height, center[0], center[1])
    mask = np.zeros((height, width), dtype=bool)
    y_min = max(0, y - ry)
    y_max = min(height, y + ry + 1)
    x_min = max(0, x - rx)
    x_max = min(width, x + rx + 1)
    mask[y_min:y_max, x_min:x_max] = True
    return mask


def _point(
    width: int,
    height: int,
    x_frac: float,
    y_frac: float,
) -> tuple[int, int]:
    return (
        int(round(x_frac * (width - 1))),
        int(round(y_frac * (height - 1))),
    )


def _derive_gameplay_layers(
    material: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    walkable = np.zeros(material.shape, dtype=bool)
    blocks_sight = np.zeros(material.shape, dtype=bool)
    movement_cost = np.zeros(material.shape, dtype=np.float32)
    traversal_class = np.zeros(material.shape, dtype=np.int16)
    for y in range(material.shape[0]):
        for x in range(material.shape[1]):
            mat = Material(int(material[y, x]))
            wet = Wetness(int(wetness[y, x]))
            flag_mask = int(flags[y, x])
            walkable[y, x] = derive_walkable(mat, wet, flag_mask)
            blocks_sight[y, x] = derive_blocks_sight(mat, flag_mask)
            movement_cost[y, x] = derive_movement_cost(mat, wet, flag_mask)
            traversal_class[y, x] = int(derive_traversal_class(mat, wet, flag_mask))
    return walkable, blocks_sight, movement_cost, traversal_class


def _tiles_df(
    *,
    material: np.ndarray,
    biome: np.ndarray,
    elevation: np.ndarray,
    hydro: np.ndarray,
    wetness: np.ndarray,
    substrate: np.ndarray,
    walkable: np.ndarray,
    blocks_sight: np.ndarray,
    movement_cost: np.ndarray,
    traversal_class: np.ndarray,
    flags: np.ndarray,
) -> pl.DataFrame:
    yy, xx = np.indices(material.shape)
    return pl.DataFrame(
        {
            "x": xx.reshape(-1).astype(np.int32),
            "y": yy.reshape(-1).astype(np.int32),
            "material": material.reshape(-1).astype(np.int16),
            "biome": biome.reshape(-1).astype(np.int16),
            "elevation_band": elevation.reshape(-1).astype(np.int16),
            "hydro_role": hydro.reshape(-1).astype(np.int16),
            "wetness": wetness.reshape(-1).astype(np.int16),
            "substrate": substrate.reshape(-1).astype(np.int16),
            "walkable": walkable.reshape(-1),
            "blocks_sight": blocks_sight.reshape(-1),
            "movement_cost": movement_cost.reshape(-1).astype(np.float32),
            "traversal_class": traversal_class.reshape(-1).astype(np.int16),
            "surface_flags": flags.reshape(-1).astype(np.uint32),
        }
    )


def _hydrology_df(
    *,
    hydro: np.ndarray,
    flow_group: np.ndarray,
    seasonal: np.ndarray,
    underground: np.ndarray,
) -> pl.DataFrame:
    yy, xx = np.indices(hydro.shape)
    hydro_flat = hydro.reshape(-1)
    mask = hydro_flat != int(HydroRole.NONE)
    return pl.DataFrame(
        {
            "x": xx.reshape(-1).astype(np.int32)[mask],
            "y": yy.reshape(-1).astype(np.int32)[mask],
            "hydro_role": hydro_flat.astype(np.int16)[mask],
            "flow_group": flow_group.reshape(-1).astype(np.int32)[mask],
            "seasonal_state": seasonal.reshape(-1)[mask],
            "connected_to_underground": underground.reshape(-1)[mask],
        }
    )


def _features_df(
    *,
    width: int,
    height: int,
    starting_region: dict[str, object],
) -> pl.DataFrame:
    def point(x_frac: float, y_frac: float) -> tuple[int, int]:
        return _point(width, height, x_frac, y_frac)

    feature_specs = [
        {
            "point": point(0.20, 0.37),
            "feature_type": FeatureType.PONOR,
            "target_id": 1,
            "tags": "karst;seasonal;descent",
            "evidence_tags": [],
        },
        {
            "point": point(0.40, 0.43),
            "feature_type": FeatureType.ESTAVELLE,
            "target_id": 2,
            "tags": "karst;reversible",
            "evidence_tags": [],
        },
        {
            "point": point(0.55, 0.34),
            "feature_type": FeatureType.SPRING,
            "target_id": 3,
            "tags": "spring;refuge",
            "evidence_tags": [],
        },
        {
            "point": point(0.62, 0.55),
            "feature_type": FeatureType.CAVE_MOUTH,
            "target_id": 4,
            "tags": "cave;limestone",
            "evidence_tags": [],
        },
        {
            "point": point(0.58, 0.50),
            "feature_type": FeatureType.KARST_WINDOW,
            "target_id": 5,
            "tags": "karst;window",
            "evidence_tags": [],
        },
        {
            "point": point(0.55, 0.82),
            "feature_type": FeatureType.LAVA_TUBE_SKYLIGHT,
            "target_id": 6,
            "tags": "lava_tube;vertical",
            "evidence_tags": [],
        },
        {
            "point": point(0.72, 0.86),
            "feature_type": FeatureType.COLLAPSED_LAVA_TUBE,
            "target_id": 7,
            "tags": "lava_tube;collapse",
            "evidence_tags": [
                int(EvidenceTag.STRUCTURAL_COLLAPSE),
                int(EvidenceTag.VOLCANIC_BURIAL),
            ],
        },
        {
            "point": point(0.47, 0.45),
            "feature_type": FeatureType.FISH_TRAIL,
            "target_id": 8,
            "tags": "fish;seasonal",
            "evidence_tags": [],
        },
        {
            "point": _metadata_point(starting_region["harbor"], "point"),
            "feature_type": FeatureType.RUINED_HARBOR,
            "target_id": 100,
            "tags": "starting_region;harbor;ruined;dead_port",
            "evidence_tags": [
                int(EvidenceTag.LATE_COLONIAL_OCCUPATION),
                int(EvidenceTag.RUINED),
                int(EvidenceTag.OVERGROWN),
            ],
        },
        {
            "point": _metadata_point(
                _first_metadata_item(starting_region, "resource_sites", "fresh_water"),
                "point",
            ),
            "feature_type": FeatureType.FRESH_WATER_SITE,
            "target_id": 101,
            "tags": "starting_region;resource;fresh_water",
            "evidence_tags": [],
        },
        {
            "point": _metadata_point(
                _first_metadata_item(
                    starting_region, "resource_sites", "reeds_and_mud"
                ),
                "point",
            ),
            "feature_type": FeatureType.RESOURCE_SITE,
            "target_id": 102,
            "tags": "starting_region;resource;reeds_and_mud",
            "evidence_tags": [],
        },
        {
            "point": _metadata_point(
                _first_metadata_item(starting_region, "resource_sites", "timber"),
                "point",
            ),
            "feature_type": FeatureType.RESOURCE_SITE,
            "target_id": 103,
            "tags": "starting_region;resource;timber",
            "evidence_tags": [],
        },
        {
            "point": _metadata_point(
                _first_metadata_item(starting_region, "resource_sites", "stone"),
                "point",
            ),
            "feature_type": FeatureType.RESOURCE_SITE,
            "target_id": 104,
            "tags": "starting_region;resource;stone",
            "evidence_tags": [int(EvidenceTag.QUARRIED_STONE)],
        },
        {
            "point": _metadata_point(starting_region["route_segments"][0], "from_point"),
            "feature_type": FeatureType.ANCIENT_ROAD,
            "target_id": 105,
            "tags": "starting_region;route;ancient_road;endpoint",
            "evidence_tags": [
                int(EvidenceTag.EARLY_COLONIAL_OCCUPATION),
                int(EvidenceTag.ROAD_ENGINEERING),
                int(EvidenceTag.ABANDONED),
                int(EvidenceTag.OVERGROWN),
            ],
        },
        {
            "point": _metadata_point(
                _first_metadata_list_item(starting_region, "blockages"), "point"
            ),
            "feature_type": FeatureType.CLEARABLE_BLOCKAGE,
            "target_id": 106,
            "tags": "starting_region;route;blockage;clearable",
            "evidence_tags": [int(EvidenceTag.RECENT_COLLAPSE)],
        },
        {
            "point": _metadata_point(
                _first_metadata_list_item(starting_region, "waystation_candidates"),
                "point",
            ),
            "feature_type": FeatureType.WAYSTATION_CANDIDATE,
            "target_id": 107,
            "tags": "starting_region;waystation_candidate",
            "evidence_tags": [
                int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
                int(EvidenceTag.WAYSTATION_REMAINS),
                int(EvidenceTag.PARTIAL_REPAIR),
            ],
        },
        {
            "point": _metadata_point(
                _first_metadata_list_item(starting_region, "inland_sites"), "point"
            ),
            "feature_type": FeatureType.INLAND_SITE,
            "target_id": 108,
            "tags": "starting_region;inland_site;ruin_or_settlement_candidate",
            "evidence_tags": [
                int(EvidenceTag.PRECURSOR_OCCUPATION),
                int(EvidenceTag.MAUSOLEUM_COMPLEX),
                int(EvidenceTag.RUINED),
                int(EvidenceTag.OVERGROWN),
            ],
        },
        {
            "point": _metadata_point(
                _first_metadata_list_item(starting_region, "cave_refs"), "point"
            ),
            "feature_type": FeatureType.ORDINARY_CAVE,
            "target_id": 109,
            "tags": "starting_region;cave;ordinary",
            "evidence_tags": [
                int(EvidenceTag.PRECURSOR_OCCUPATION),
                int(EvidenceTag.PRIOR_EXPEDITION),
            ],
        },
    ]
    return pl.DataFrame(
        {
            "x": [int(spec["point"][0]) for spec in feature_specs],
            "y": [int(spec["point"][1]) for spec in feature_specs],
            "feature_type": [int(spec["feature_type"]) for spec in feature_specs],
            "target_id": [int(spec["target_id"]) for spec in feature_specs],
            "tags": [str(spec["tags"]) for spec in feature_specs],
            "evidence_tags": [
                list(spec["evidence_tags"]) for spec in feature_specs
            ],
        }
    )


def _first_metadata_item(
    metadata: dict[str, object],
    collection: str,
    kind: str,
) -> dict[str, object]:
    items = metadata[collection]
    if not isinstance(items, list):
        raise TypeError(f"Expected {collection} to be a list")
    for item in items:
        if isinstance(item, dict) and item.get("kind") == kind:
            return item
    raise ValueError(f"No {collection} item with kind {kind}")


def _first_metadata_list_item(
    metadata: dict[str, object],
    collection: str,
) -> dict[str, object]:
    items = metadata[collection]
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        raise TypeError(f"Expected {collection} to contain dict items")
    return items[0]


def _metadata_point(
    metadata: object,
    key: str,
    *,
    fallback: tuple[int, int] | None = None,
) -> tuple[int, int]:
    if not isinstance(metadata, dict):
        raise TypeError("Expected metadata item to be a dict")
    point = metadata.get(key)
    if point is None and fallback is not None:
        return fallback
    if not isinstance(point, list | tuple) or len(point) != 2:
        raise TypeError(f"Expected metadata point at {key}")
    return int(point[0]), int(point[1])
