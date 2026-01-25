from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Literal

import orjson

from worldgen.constants import (
    CLIMATE_ADVECT_STEPS_DEFAULT,
    CLIMATE_LAPSE_C_PER_KM_DEFAULT,
    CLIMATE_LAT_GAMMA_DEFAULT,
    CLIMATE_LAT_POLAR_CAP_DEFAULT,
    CLIMATE_OROG_SCALE_M_DEFAULT,
    CLIMATE_T_EQUATOR_DEFAULT,
    CLIMATE_T_POLE_DEFAULT,
    CLIMATE_TRANSPORT_FRAC_DEFAULT,
    ELEVATION_EROSION_ITERATIONS_DEFAULT,
    ELEVATION_SMOOTH_CAP_M_DEFAULT,
    ELEVATION_SMOOTH_PASSES_DEFAULT,
    ELEVATION_SMOOTH_STRENGTH_DEFAULT,
    ELEVATION_TALUS_ANGLE_DEG_DEFAULT,
    ELEVATION_TARGET_OCEAN_FRAC_DEFAULT,
    HYDROLOGY_INTENSITY_LOG_BASE_DEFAULT,
    HYDROLOGY_MIN_CATCHMENT_CELLS_DEFAULT,
    PLANET_RADIUS_M_DEFAULT,
)


@dataclass(frozen=True)
class ElevationConfig:
    N_smooth: int = ELEVATION_SMOOTH_PASSES_DEFAULT
    target_ocean_frac: float = ELEVATION_TARGET_OCEAN_FRAC_DEFAULT
    smooth_strength: float = ELEVATION_SMOOTH_STRENGTH_DEFAULT
    smooth_cap_m: float = ELEVATION_SMOOTH_CAP_M_DEFAULT
    erosion_iterations: int = ELEVATION_EROSION_ITERATIONS_DEFAULT
    talus_angle_deg: float = ELEVATION_TALUS_ANGLE_DEG_DEFAULT

    def __post_init__(self) -> None:
        if self.N_smooth < 0:
            raise ValueError("N_smooth must be >= 0")
        if not 0.0 < self.target_ocean_frac < 1.0:
            raise ValueError("target_ocean_frac must be between 0 and 1")
        if self.smooth_strength < 0.0:
            raise ValueError("smooth_strength must be >= 0")
        if self.smooth_cap_m <= 0.0:
            raise ValueError("smooth_cap_m must be > 0")
        if self.erosion_iterations < 0:
            raise ValueError("erosion_iterations must be >= 0")
        if self.talus_angle_deg <= 0.0:
            raise ValueError("talus_angle_deg must be > 0")


@dataclass(frozen=True)
class ClimateConfig:
    T_equator: float = CLIMATE_T_EQUATOR_DEFAULT
    T_pole: float = CLIMATE_T_POLE_DEFAULT
    lapse_c_per_km: float = CLIMATE_LAPSE_C_PER_KM_DEFAULT
    lat_gamma: float = CLIMATE_LAT_GAMMA_DEFAULT
    lat_polar_cap: float = CLIMATE_LAT_POLAR_CAP_DEFAULT
    S_adv: int = CLIMATE_ADVECT_STEPS_DEFAULT
    transport_frac: float = CLIMATE_TRANSPORT_FRAC_DEFAULT
    orog_scale_m: float = CLIMATE_OROG_SCALE_M_DEFAULT

    def __post_init__(self) -> None:
        if self.S_adv <= 0:
            raise ValueError("S_adv must be > 0")
        if not 0.0 < self.transport_frac <= 1.0:
            raise ValueError("transport_frac must be in (0, 1]")
        if self.orog_scale_m <= 0.0:
            raise ValueError("orog_scale_m must be > 0")
        if not 0.0 < self.lat_polar_cap < 1.0:
            raise ValueError("lat_polar_cap must be between 0 and 1")


@dataclass(frozen=True)
class HydrologyConfig:
    min_catchment_cells: int = HYDROLOGY_MIN_CATCHMENT_CELLS_DEFAULT
    intensity_log_base: float = HYDROLOGY_INTENSITY_LOG_BASE_DEFAULT

    def __post_init__(self) -> None:
        if self.min_catchment_cells <= 0:
            raise ValueError("min_catchment_cells must be > 0")
        if self.intensity_log_base <= 1.0:
            raise ValueError("intensity_log_base must be > 1")


@dataclass(frozen=True)
class WorldConfig:
    elevation: ElevationConfig
    climate: ClimateConfig
    hydrology: HydrologyConfig
    planet_radius_m: float = PLANET_RADIUS_M_DEFAULT

    def __post_init__(self) -> None:
        if self.planet_radius_m <= 0.0:
            raise ValueError("planet_radius_m must be > 0")


def default_world_config() -> WorldConfig:
    elevation: ElevationConfig = ElevationConfig()
    climate: ClimateConfig = ClimateConfig()
    hydrology: HydrologyConfig = HydrologyConfig()
    return WorldConfig(
        elevation=elevation,
        climate=climate,
        hydrology=hydrology,
        planet_radius_m=PLANET_RADIUS_M_DEFAULT,
    )


def config_as_dict(cfg: WorldConfig) -> dict[str, object]:
    return asdict(cfg)


def extract_global_fields(cfg: WorldConfig) -> dict[str, object]:
    """Extract fields affecting global simulation layers (elevation, climate, hydrology).

    All current WorldConfig fields affect the global simulation:
    - elevation: tectonic plates, uplift, erosion
    - climate: temperature, wind, moisture
    - hydrology: flow direction, accumulation, rivers
    - planet_radius_m: topology, cell areas
    """
    return config_as_dict(cfg)


def extract_chunk_fields(cfg: WorldConfig) -> dict[str, object]:
    """Extract fields affecting only chunk-level detail generation.

    Currently returns empty dict because there are no chunk-specific tunables
    in WorldConfig yet. Chunk generation parameters like detail_cells_per_sim
    are passed as arguments to get_chunk() rather than stored in the config.

    When chunk-specific tunables are added to WorldConfig in the future
    (e.g., detail resolution, noise parameters, interpolation settings),
    this function should be updated to return only those fields.
    """
    return {}


def compute_tunables_hash(
    cfg: WorldConfig, *, scope: Literal["global", "chunk"]
) -> str:
    if scope == "global":
        fields: dict[str, object] = extract_global_fields(cfg)
    else:
        fields = extract_chunk_fields(cfg)
    blob: bytes = orjson.dumps(fields, option=orjson.OPT_SORT_KEYS)
    digest: str = hashlib.sha256(blob).hexdigest()
    return f"sha256:{digest}"
