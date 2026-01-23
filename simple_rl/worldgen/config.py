from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict

ELEV_Q_M: float = 0.1


@dataclass(frozen=True)
class ElevationConfig:
    N_smooth: int = 4
    target_ocean_frac: float = 0.68
    smooth_strength: float = 0.35
    smooth_cap_m: float = 90.0
    erosion_iterations: int = 2
    talus_angle_deg: float = 35.0

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
    T_equator: float = 30.0
    T_pole: float = -20.0
    lapse_C_per_km: float = 6.0
    lat_gamma: float = 1.15
    lat_polar_cap: float = 0.985
    S_adv: int = 96
    transport_frac: float = 0.85
    orog_scale_m: float = 500.0

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
    min_catchment_cells: int = 256
    intensity_log_base: float = 10.0

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
    planet_radius_m: float = 6_371_000.0

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
        planet_radius_m=6_371_000.0,
    )


def config_as_dict(cfg: WorldConfig) -> Dict[str, object]:
    return asdict(cfg)
