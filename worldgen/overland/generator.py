from __future__ import annotations

from typing import Literal

import numpy as np
import polars as pl

from common.constants import Material
from utils.game_rng import GameRNG
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.rules import (
    derive_blocks_sight,
    derive_walkable,
    surface_flag_mask,
)
from worldgen.overland.schema import (
    SCHEMA_VERSION,
    Biome,
    ElevationBand,
    FeatureType,
    HydroRole,
    OverlandBundle,
    Substrate,
    SurfaceFlag,
    Wetness,
)

OverlandProfile = Literal["KARST_TO_VOLCANIC_MOUNTAIN"]


def generate_overland_region(
    *,
    seed: int,
    width: int,
    height: int,
    profile: OverlandProfile = "KARST_TO_VOLCANIC_MOUNTAIN",
) -> OverlandBundle:
    if profile != "KARST_TO_VOLCANIC_MOUNTAIN":
        raise ValueError(f"Unsupported overland profile: {profile}")
    if width < 48 or height < 40:
        raise ValueError("width must be >= 48 and height must be >= 40")

    rng = GameRNG(seed=seed)
    y, x = np.indices((height, width))
    yn = y / max(1, height - 1)
    noise = np.array(rng.get_floats(0.0, 1.0, width * height), dtype=np.float32).reshape(
        height, width
    )

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

    walkable, blocks_sight = _derive_gameplay_layers(material, wetness, flags)
    tiles_df = _tiles_df(
        material=material,
        biome=biome,
        elevation=elevation,
        hydro=hydro,
        wetness=wetness,
        substrate=substrate,
        walkable=walkable,
        blocks_sight=blocks_sight,
        flags=flags,
    )
    hydrology_df = _hydrology_df(
        hydro=hydro,
        flow_group=flow_group,
        seasonal=seasonal,
        underground=underground,
    )
    features_df = _features_df(width=width, height=height)
    metadata = {
        "seed": seed,
        "width": width,
        "height": height,
        "profile": profile,
        "schema_version": SCHEMA_VERSION,
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
    flow_group[basin] = 1
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
    flow_group[spring] = 2
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
    flow_group[marsh] = 3
    flags[marsh] = surface_flag_mask(SurfaceFlag.SEASONAL, SurfaceFlag.VEGETATION_DENSE)

    estavelle = _ellipse_mask(width, height, 0.40, 0.43, 0.035, 0.025)
    material[estavelle] = int(Material.ESTAVELLE_WATER)
    hydro[estavelle] = int(HydroRole.ESTAVELLE)
    wetness[estavelle] = int(Wetness.SHALLOW_FLOODED)
    underground[estavelle] = True

    ponor = _ellipse_mask(width, height, 0.20, 0.37, 0.035, 0.025)
    material[ponor] = int(Material.PONOR)
    hydro[ponor] = int(HydroRole.PONOR)
    wetness[ponor] = int(Wetness.SHALLOW_FLOODED)
    substrate[ponor] = int(Substrate.LIMESTONE)
    underground[ponor] = True
    flags[ponor] = surface_flag_mask(
        SurfaceFlag.HAZARD, SurfaceFlag.TRANSITION, SurfaceFlag.SEASONAL
    )

    fish_trail = _line_mask(width, height, (0.28, 0.38), (0.47, 0.45), radius=1)
    material[fish_trail] = int(Material.FISH_TRAIL)
    hydro[fish_trail] = int(HydroRole.TEMPORARY_POOL)
    wetness[fish_trail] = int(Wetness.WET)
    substrate[fish_trail] = int(Substrate.MUD)
    flags[fish_trail] = surface_flag_mask(SurfaceFlag.SEASONAL, SurfaceFlag.SLOWS_MOVEMENT)

    gorge = _line_mask(width, height, (0.66, 0.32), (0.62, 0.57), radius=2)
    biome[gorge] = int(Biome.LIMESTONE_GORGE)
    material[gorge] = int(Material.LIMESTONE_PAVEMENT)
    elevation[gorge] = int(ElevationBand.FOOTHILL)
    substrate[gorge] = int(Substrate.LIMESTONE)
    wetness[gorge] = int(Wetness.DAMP)
    hydro[gorge] = int(HydroRole.SURFACE_CHANNEL)
    flow_group[gorge] = 4

    gorge_wall = _line_mask(width, height, (0.69, 0.32), (0.65, 0.57), radius=1)
    biome[gorge_wall] = int(Biome.LIMESTONE_GORGE)
    material[gorge_wall] = int(Material.LIMESTONE_CLIFF)
    hydro[gorge_wall] = int(HydroRole.NONE)

    cave = _ellipse_mask(width, height, 0.62, 0.55, 0.025, 0.018)
    material[cave] = int(Material.CAVE_MOUTH)
    hydro[cave] = int(HydroRole.KARST_WINDOW)
    underground[cave] = True
    flags[cave] = surface_flag_mask(SurfaceFlag.TRANSITION)


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


def _derive_gameplay_layers(
    material: np.ndarray,
    wetness: np.ndarray,
    flags: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    walkable = np.zeros(material.shape, dtype=bool)
    blocks_sight = np.zeros(material.shape, dtype=bool)
    for y in range(material.shape[0]):
        for x in range(material.shape[1]):
            mat = Material(int(material[y, x]))
            wet = Wetness(int(wetness[y, x]))
            flag_mask = int(flags[y, x])
            walkable[y, x] = derive_walkable(mat, wet, flag_mask)
            blocks_sight[y, x] = derive_blocks_sight(mat, flag_mask)
    return walkable, blocks_sight


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


def _features_df(*, width: int, height: int) -> pl.DataFrame:
    def point(x_frac: float, y_frac: float) -> tuple[int, int]:
        return (
            int(round(x_frac * (width - 1))),
            int(round(y_frac * (height - 1))),
        )

    feature_specs = [
        (*point(0.20, 0.37), FeatureType.PONOR, 1, "karst;seasonal;descent"),
        (*point(0.40, 0.43), FeatureType.ESTAVELLE, 2, "karst;reversible"),
        (*point(0.55, 0.34), FeatureType.SPRING, 3, "spring;refuge"),
        (*point(0.62, 0.55), FeatureType.CAVE_MOUTH, 4, "cave;limestone"),
        (*point(0.58, 0.50), FeatureType.KARST_WINDOW, 5, "karst;window"),
        (*point(0.55, 0.82), FeatureType.LAVA_TUBE_SKYLIGHT, 6, "lava_tube;vertical"),
        (*point(0.72, 0.86), FeatureType.COLLAPSED_LAVA_TUBE, 7, "lava_tube;collapse"),
        (*point(0.47, 0.45), FeatureType.FISH_TRAIL, 8, "fish;seasonal"),
    ]
    return pl.DataFrame(
        {
            "x": [spec[0] for spec in feature_specs],
            "y": [spec[1] for spec in feature_specs],
            "feature_type": [int(spec[2]) for spec in feature_specs],
            "target_id": [int(spec[3]) for spec in feature_specs],
            "tags": [str(spec[4]) for spec in feature_specs],
        }
    )
