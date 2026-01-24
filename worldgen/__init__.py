from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from numba import njit
from numpy.typing import NDArray

from worldgen.config import (
    ClimateConfig,
    ElevationConfig,
    HydrologyConfig,
    WorldConfig,
    compute_tunables_hash,
    config_as_dict,
    default_world_config,
)
from worldgen.constants import (
    CLIMATE_CAP_HI,
    CLIMATE_CAP_LO,
    CLIMATE_CAP_MIN,
    CLIMATE_CAP_SLOPE,
    CLIMATE_LAND_INIT_MOISTURE,
    CLIMATE_OCEAN_INIT_MOISTURE,
    CLIMATE_OCEAN_SOURCE_MOISTURE,
    ELEV_Q_M,
    ELEVATION_BASE_NOISE_LACUNARITY,
    ELEVATION_BASE_NOISE_OCTAVES,
    ELEVATION_BASE_NOISE_PERSISTENCE,
    ELEVATION_BASE_NOISE_SCALE,
    ELEVATION_HYDRAULIC_K_DEFAULT,
    ELEVATION_PLATE_AMPLITUDE_M,
    ELEVATION_PLATE_EXPONENT,
    ELEVATION_PLATE_NOISE_LACUNARITY,
    ELEVATION_PLATE_NOISE_OCTAVES,
    ELEVATION_PLATE_NOISE_PERSISTENCE,
    ELEVATION_PLATE_NOISE_SCALE,
    ELEVATION_ROUGHNESS_AMPLITUDE_M,
    ELEVATION_ROUGHNESS_BASELINE,
    ELEVATION_ROUGHNESS_EXPONENT,
    ELEVATION_ROUGH_NOISE_LACUNARITY,
    ELEVATION_ROUGH_NOISE_OCTAVES,
    ELEVATION_ROUGH_NOISE_PERSISTENCE,
    ELEVATION_ROUGH_NOISE_SCALE,
    ELEVATION_TECTONIC_AMPLITUDE_M,
    ELEVATION_TECTONIC_EXPONENT,
    NORMALIZE_EPS,
    NOISE_DOMAIN,
    PLATE_SEED_DOMAIN,
    WIND_DOMAIN,
    WIND_JITTER_MASK,
    WIND_JITTER_SCALE,
    WIND_POLE_REF_THRESHOLD,
    WIND_SCORE_FLOOR,
    WIND_SIGN_LAT_FREQ,
)
from worldgen.kernels.advection import advect_moisture_step
from worldgen.kernels.erosion import hydraulic_erosion_step, thermal_erosion_step
from worldgen.kernels.noise import eval_noise_sphere
from worldgen.kernels.smoothing import smooth_i32_nbr4
from worldgen.hydrology import (
    build_flow_accumulation,
    build_flow_direction,
    build_rivers_derived_fields,
)
from worldgen.io import ensure_dir, read_layer, write_layer
from worldgen.metadata import WorldMeta, build_world_meta, read_world_meta
from worldgen.report import WorldGenReport, generate_report
from worldgen.topology_cube_sphere import (
    build_cell_area,
    build_nbr_tables,
    build_pos_xyz,
)
from worldgen.topology_cube_sphere import lin_index
from worldgen.utils_coord import coord_hash_domain
from worldgen.validation import validate_array, validate_no_nan

__all__: List[str] = [
    "ClimateConfig",
    "ElevationConfig",
    "HydrologyConfig",
    "WorldConfig",
    "build_full_world",
    "build_world",
    "build_elevation",
    "build_climate",
    "build_hydrology",
    "default_world_config",
    "get_chunk",
]

# Default sea level quantized elevation for report generation
# Cells with elev_q > SEA_LEVEL_Q_DEFAULT are considered land
_SEA_LEVEL_Q_DEFAULT: int = 0


def _write_report(out_dir: Path, payload: Dict[str, object]) -> None:
    path: Path = out_dir / "report.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def _normalize01(values: NDArray[np.float32]) -> NDArray[np.float32]:
    min_v: float = float(np.min(values))
    max_v: float = float(np.max(values))
    span: float = max(max_v - min_v, NORMALIZE_EPS)
    return ((values - min_v) / span).astype(np.float32)


def _curve_pow(values: NDArray[np.float32], *, exponent: float) -> NDArray[np.float32]:
    clipped: NDArray[np.float32] = np.clip(values, 0.0, 1.0)
    return np.power(clipped, exponent).astype(np.float32)


def _quantile_value(values: NDArray[np.float32], *, frac: float) -> float:
    if not 0.0 <= frac <= 1.0:
        raise ValueError("frac must be in [0, 1]")
    n: int = int(values.size)
    if n == 0:
        raise ValueError("values must be non-empty")
    k: int = int(np.floor(frac * (n - 1)))
    partitioned: NDArray[np.float32] = np.partition(values, k)
    return float(partitioned[k])


@njit(cache=True)
def _build_wind_to(
    pos_xyz: NDArray[np.float32],
    nbr4: NDArray[np.int32],
    *,
    n_cells: int,
    lat_polar_cap: float,
    seed: int,
) -> NDArray[np.int32]:
    wind_to: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)

    u: int
    for u in range(n_cells):
        z: float = float(pos_xyz[u, 2])
        if abs(z) >= lat_polar_cap:
            continue

        if abs(z) > WIND_POLE_REF_THRESHOLD:
            ref_x: float = 1.0
            ref_y: float = 0.0
            ref_z: float = 0.0
        else:
            ref_x = 0.0
            ref_y = 0.0
            ref_z = 1.0

        px: float = float(pos_xyz[u, 0])
        py: float = float(pos_xyz[u, 1])
        pz: float = float(pos_xyz[u, 2])

        east_x: float = ref_y * pz - ref_z * py
        east_y: float = ref_z * px - ref_x * pz
        east_z: float = ref_x * py - ref_y * px
        norm: float = np.sqrt(east_x * east_x + east_y * east_y + east_z * east_z)
        if norm <= 0.0:
            continue

        inv_norm: float = 1.0 / norm
        east_x *= inv_norm
        east_y *= inv_norm
        east_z *= inv_norm

        lat: float = np.arcsin(max(-1.0, min(z, 1.0)))
        wind_sign: float = 1.0 if np.sin(WIND_SIGN_LAT_FREQ * lat) >= 0.0 else -1.0
        wind_x: float = east_x * wind_sign
        wind_y: float = east_y * wind_sign
        wind_z: float = east_z * wind_sign

        best_v: int = -1
        best_score: float = WIND_SCORE_FLOOR
        k: int
        for k in range(4):
            v: int = int(nbr4[u, k])
            if v < 0 or v >= n_cells:
                continue
            dx: float = float(pos_xyz[v, 0]) - px
            dy: float = float(pos_xyz[v, 1]) - py
            dz: float = float(pos_xyz[v, 2]) - pz
            score: float = dx * wind_x + dy * wind_y + dz * wind_z
            jitter_raw: int = coord_hash_domain(seed, WIND_DOMAIN, v) & WIND_JITTER_MASK
            score += float(jitter_raw) * WIND_JITTER_SCALE
            if score > best_score:
                best_score = score
                best_v = v
        wind_to[u] = best_v

    return wind_to


def build_world(
    out_dir: Path,
    *,
    seed: int,
    N: int,
    cfg: WorldConfig,
    overwrite: bool = False,
) -> None:
    if out_dir.exists() and not overwrite:
        raise FileExistsError("out_dir already exists; set overwrite=True")
    if out_dir.exists() and overwrite:
        shutil.rmtree(out_dir)
    ensure_dir(out_dir)

    global_hash: str = compute_tunables_hash(cfg, scope="global")
    chunk_hash: str = compute_tunables_hash(cfg, scope="chunk")

    meta: WorldMeta = build_world_meta(
        world_seed=seed,
        N=N,
        planet_radius_m=cfg.planet_radius_m,
        elev_quantum_m=ELEV_Q_M,
        global_tunables_hash=global_hash,
        chunk_tunables_hash=chunk_hash,
    )

    pos_xyz: NDArray[np.float32] = build_pos_xyz(N)
    nbr4_i32: NDArray[np.int32]
    nbr8_i32: NDArray[np.int32]
    nbr4_i32, nbr8_i32 = build_nbr_tables(N)
    cell_area_f32: NDArray[np.float32] = build_cell_area(N, cfg.planet_radius_m)

    n_cells: int = 6 * N * N
    validate_array(pos_xyz, "pos_xyz", np.dtype("float32"), (n_cells, 3))
    validate_array(nbr4_i32, "nbr4", np.dtype("int32"), (n_cells, 4))
    validate_array(nbr8_i32, "nbr8", np.dtype("int32"), (n_cells, 8))
    validate_array(cell_area_f32, "cell_area", np.dtype("float32"), (n_cells,))

    write_layer(out_dir=out_dir, key="pos_xyz", arr=pos_xyz, meta=meta, units="unit")
    write_layer(out_dir=out_dir, key="nbr4", arr=nbr4_i32, meta=meta)
    write_layer(out_dir=out_dir, key="nbr8", arr=nbr8_i32, meta=meta)
    write_layer(
        out_dir=out_dir, key="cell_area", arr=cell_area_f32, meta=meta, units="m2"
    )

    meta.write(out_dir)
    _write_report(
        out_dir,
        {
            "world_seed": seed,
            "N": N,
            "n_cells": n_cells,
            "status": "topology_complete",
        },
    )
    (out_dir / "tunables.json").write_text(
        json.dumps(config_as_dict(cfg), indent=2, sort_keys=True)
    )


def build_elevation(
    out_dir: Path,
    *,
    seed: int,
    N: int,
    cfg: ElevationConfig,
    plate_seed_xyz: NDArray[np.float32] | None = None,
) -> None:
    meta: WorldMeta = read_world_meta(out_dir)
    if meta.N != N:
        raise ValueError("N must match meta.json")
    if meta.world_seed != seed:
        raise ValueError("seed must match meta.json")

    required_layers: Tuple[str, ...] = ("pos_xyz", "nbr4", "nbr8", "cell_area")
    for key in required_layers:
        if key not in meta.layers:
            raise ValueError(f"{key} layer is required for elevation")

    n_cells: int = meta.n_cells
    pos_xyz: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["pos_xyz"]),
        dtype=np.float32,
    )
    nbr4_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["nbr4"]),
        dtype=np.int32,
    )
    nbr8_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["nbr8"]),
        dtype=np.int32,
    )
    cell_area_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["cell_area"]),
        dtype=np.float32,
    )

    validate_array(pos_xyz, "pos_xyz", np.dtype("float32"), (n_cells, 3))
    validate_array(nbr4_i32, "nbr4", np.dtype("int32"), (n_cells, 4))
    validate_array(nbr8_i32, "nbr8", np.dtype("int32"), (n_cells, 8))
    validate_array(cell_area_f32, "cell_area", np.dtype("float32"), (n_cells,))

    noise_seed: int = coord_hash_domain(seed, NOISE_DOMAIN, 0)
    rough_seed: int = coord_hash_domain(seed, NOISE_DOMAIN, 1)
    plate_seed: int = coord_hash_domain(seed, PLATE_SEED_DOMAIN, 0)

    base_noise: NDArray[np.float32] = eval_noise_sphere(
        pos_xyz,
        noise_seed,
        octaves=ELEVATION_BASE_NOISE_OCTAVES,
        lacunarity=ELEVATION_BASE_NOISE_LACUNARITY,
        persistence=ELEVATION_BASE_NOISE_PERSISTENCE,
        scale=ELEVATION_BASE_NOISE_SCALE,
    ).astype(np.float32)
    rough_noise: NDArray[np.float32] = eval_noise_sphere(
        pos_xyz,
        rough_seed,
        octaves=ELEVATION_ROUGH_NOISE_OCTAVES,
        lacunarity=ELEVATION_ROUGH_NOISE_LACUNARITY,
        persistence=ELEVATION_ROUGH_NOISE_PERSISTENCE,
        scale=ELEVATION_ROUGH_NOISE_SCALE,
    ).astype(np.float32)
    plate_noise: NDArray[np.float32] = eval_noise_sphere(
        pos_xyz,
        plate_seed,
        octaves=ELEVATION_PLATE_NOISE_OCTAVES,
        lacunarity=ELEVATION_PLATE_NOISE_LACUNARITY,
        persistence=ELEVATION_PLATE_NOISE_PERSISTENCE,
        scale=ELEVATION_PLATE_NOISE_SCALE,
    ).astype(np.float32)

    plate_influence: NDArray[np.float32]
    if plate_seed_xyz is not None:
        plate_seed_arr: NDArray[np.float32] = np.ascontiguousarray(
            plate_seed_xyz,
            dtype=np.float32,
        )
        if plate_seed_arr.ndim != 2 or plate_seed_arr.shape[1] != 3:
            raise ValueError("plate_seed_xyz must have shape (n, 3)")
        plate_norm: NDArray[np.float32] = np.linalg.norm(plate_seed_arr, axis=1)
        if np.any(plate_norm <= 0.0):
            raise ValueError("plate_seed_xyz rows must be non-zero vectors")
        plate_seed_arr = (plate_seed_arr / plate_norm[:, None]).astype(np.float32)
        plate_influence = np.max(pos_xyz @ plate_seed_arr.T, axis=1).astype(np.float32)
    else:
        plate_influence = plate_noise

    tectonic_mask: NDArray[np.float32] = _curve_pow(
        _normalize01(base_noise),
        exponent=ELEVATION_TECTONIC_EXPONENT,
    )
    plate_mask: NDArray[np.float32] = _curve_pow(
        _normalize01(plate_influence),
        exponent=ELEVATION_PLATE_EXPONENT,
    )
    rough_mask: NDArray[np.float32] = _curve_pow(
        _normalize01(rough_noise),
        exponent=ELEVATION_ROUGHNESS_EXPONENT,
    )

    elev_m: NDArray[np.float32] = (
        (tectonic_mask * 2.0 - 1.0) * ELEVATION_TECTONIC_AMPLITUDE_M
        + (plate_mask * 2.0 - 1.0) * ELEVATION_PLATE_AMPLITUDE_M
        + (rough_mask - ELEVATION_ROUGHNESS_BASELINE) * ELEVATION_ROUGHNESS_AMPLITUDE_M
    ).astype(np.float32)
    validate_no_nan(elev_m, "elev_m")

    sea_level_m: float = _quantile_value(elev_m, frac=cfg.target_ocean_frac)
    elev_m = elev_m - sea_level_m

    base_elev_q: NDArray[np.int32] = np.round(elev_m / ELEV_Q_M).astype(np.int32)
    elev_q: NDArray[np.int32] = base_elev_q.copy()

    cap_q: int = int(round(cfg.smooth_cap_m / ELEV_Q_M))
    smooth_steps: int = max(0, cfg.N_smooth)
    for _ in range(smooth_steps):
        elev_q = smooth_i32_nbr4(
            elev_q,
            nbr4_i32,
            n_cells=n_cells,
            strength=float(cfg.smooth_strength),
            cap_q=cap_q,
        )

    base_elev_q = elev_q.copy()
    erosion_steps: int = max(0, cfg.erosion_iterations)
    hydraulic_k: float = ELEVATION_HYDRAULIC_K_DEFAULT
    talus_slope_m: float = float(
        np.tan(np.deg2rad(cfg.talus_angle_deg)),
    )
    talus_slope_q: int = max(0, int(round(talus_slope_m / ELEV_Q_M)))

    for _ in range(erosion_steps):
        flow_to_i32: NDArray[np.int32] = build_flow_direction(
            elev_q,
            nbr8_i32,
            cell_area_f32,
            seed=seed,
        )
        accum_f32: NDArray[np.float32] = build_flow_accumulation(
            flow_to_i32,
            cell_area_f32,
        )
        elev_q = hydraulic_erosion_step(
            elev_q,
            flow_to_i32,
            accum_f32,
            n_cells=n_cells,
            hydraulic_k=hydraulic_k,
            base_elev_q_i32=base_elev_q,
        )
        elev_q = thermal_erosion_step(
            elev_q,
            nbr8_i32,
            n_cells=n_cells,
            talus_slope_q=talus_slope_q,
        )

    elev_q = np.ascontiguousarray(elev_q, dtype=np.int32)
    validate_array(elev_q, "elev_q", np.dtype("int32"), (n_cells,))

    write_layer(out_dir=out_dir, key="elev_q", arr=elev_q, meta=meta, units="m")
    meta.write(out_dir)


def build_climate(
    out_dir: Path,
    *,
    seed: int,
    N: int,
    cfg: ClimateConfig,
) -> None:
    meta: WorldMeta = read_world_meta(out_dir)
    if meta.N != N:
        raise ValueError("N must match meta.json")
    if meta.world_seed != seed:
        raise ValueError("seed must match meta.json")

    required_layers: Tuple[str, ...] = ("pos_xyz", "nbr4", "cell_area", "elev_q")
    for key in required_layers:
        if key not in meta.layers:
            raise ValueError(f"{key} layer is required for climate")

    n_cells: int = meta.n_cells
    pos_xyz: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["pos_xyz"]),
        dtype=np.float32,
    )
    nbr4_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["nbr4"]),
        dtype=np.int32,
    )
    cell_area_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["cell_area"]),
        dtype=np.float32,
    )
    elev_q_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["elev_q"]),
        dtype=np.int32,
    )

    validate_array(pos_xyz, "pos_xyz", np.dtype("float32"), (n_cells, 3))
    validate_array(nbr4_i32, "nbr4", np.dtype("int32"), (n_cells, 4))
    validate_array(cell_area_f32, "cell_area", np.dtype("float32"), (n_cells,))
    validate_array(elev_q_i32, "elev_q", np.dtype("int32"), (n_cells,))

    z: NDArray[np.float32] = pos_xyz[:, 2]
    lat: NDArray[np.float32] = np.arcsin(np.clip(z, -1.0, 1.0))
    lat_norm: NDArray[np.float32] = np.abs(lat) / (np.pi / 2.0)
    lat_curve: NDArray[np.float32] = np.power(lat_norm, cfg.lat_gamma).astype(
        np.float32
    )
    temp_base: NDArray[np.float32] = (
        cfg.T_equator * (1.0 - lat_curve) + cfg.T_pole * lat_curve
    ).astype(np.float32)

    elev_m: NDArray[np.float32] = elev_q_i32.astype(np.float32) * ELEV_Q_M
    lapse: NDArray[np.float32] = ((cfg.lapse_C_per_km / 1000.0) * elev_m).astype(
        np.float32
    )
    temp_f32: NDArray[np.float32] = (temp_base - lapse).astype(np.float32)
    validate_no_nan(temp_f32, "temp_f32")

    wind_to_i32: NDArray[np.int32] = _build_wind_to(
        pos_xyz,
        nbr4_i32,
        n_cells=n_cells,
        lat_polar_cap=cfg.lat_polar_cap,
        seed=seed,
    )
    validate_array(wind_to_i32, "wind_to", np.dtype("int32"), (n_cells,))

    sea_mask: NDArray[np.uint8] = (elev_q_i32 <= 0).astype(np.uint8)
    moist_f32: NDArray[np.float32] = np.where(
        sea_mask == 1,
        CLIMATE_OCEAN_INIT_MOISTURE,
        CLIMATE_LAND_INIT_MOISTURE,
    ).astype(np.float32)
    precip_accum: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)

    adv_steps: int = max(1, cfg.S_adv)
    for _ in range(adv_steps):
        moist_f32 = advect_moisture_step(
            moist_f32,
            precip_accum,
            elev_q_i32,
            wind_to_i32,
            sea_mask,
            temp_f32,
            n_cells=n_cells,
            transport_frac=float(cfg.transport_frac),
            orog_scale_m=float(cfg.orog_scale_m),
            ocean_source=CLIMATE_OCEAN_SOURCE_MOISTURE,
            cap_min=CLIMATE_CAP_MIN,
            cap_slope=CLIMATE_CAP_SLOPE,
            cap_lo=CLIMATE_CAP_LO,
            cap_hi=CLIMATE_CAP_HI,
        )

    validate_no_nan(precip_accum, "precip_accum")
    temp_f32 = np.ascontiguousarray(temp_f32, dtype=np.float32)
    wind_to_i32 = np.ascontiguousarray(wind_to_i32, dtype=np.int32)
    moist_f32 = np.ascontiguousarray(moist_f32, dtype=np.float32)
    precip_accum = np.ascontiguousarray(precip_accum, dtype=np.float32)

    write_layer(out_dir=out_dir, key="temp", arr=temp_f32, meta=meta, units="degC")
    write_layer(
        out_dir=out_dir,
        key="wind_to",
        arr=wind_to_i32,
        meta=meta,
        sentinel=-1,
    )
    write_layer(out_dir=out_dir, key="moist", arr=moist_f32, meta=meta)
    write_layer(
        out_dir=out_dir,
        key="precip",
        arr=precip_accum,
        meta=meta,
        units="mm_per_step",
    )
    meta.write(out_dir)


def build_hydrology(
    out_dir: Path,
    *,
    N: int,
    cfg: HydrologyConfig,
) -> None:
    meta: WorldMeta = read_world_meta(out_dir)
    if meta.N != N:
        raise ValueError("N must match meta.json")
    if "elev_q" not in meta.layers:
        raise ValueError("elev_q layer is required for hydrology")
    if "nbr8" not in meta.layers:
        raise ValueError("nbr8 layer is required for hydrology")
    if "cell_area" not in meta.layers:
        raise ValueError("cell_area layer is required for hydrology")

    elev_q_i32: NDArray[np.int32] = read_layer(
        out_dir=out_dir,
        layer=meta.layers["elev_q"],
    ).astype(np.int32)
    nbr8_i32: NDArray[np.int32] = read_layer(
        out_dir=out_dir,
        layer=meta.layers["nbr8"],
    ).astype(np.int32)
    cell_area_f32: NDArray[np.float32] = read_layer(
        out_dir=out_dir,
        layer=meta.layers["cell_area"],
    ).astype(np.float32)

    n_cells: int = 6 * N * N
    validate_array(elev_q_i32, "elev_q_i32", np.dtype("int32"), (n_cells,))
    validate_array(nbr8_i32, "nbr8_i32", np.dtype("int32"), (n_cells, 8))
    validate_array(cell_area_f32, "cell_area_f32", np.dtype("float32"), (n_cells,))

    flow_to_i32: NDArray[np.int32] = build_flow_direction(
        elev_q_i32,
        nbr8_i32,
        cell_area_f32,
        seed=meta.world_seed,
    )
    accum_f32: NDArray[np.float32] = build_flow_accumulation(
        flow_to_i32,
        cell_area_f32,
    )
    is_river_u8: NDArray[np.uint8]
    river_intensity_f32: NDArray[np.float32]
    stream_order_u8: NDArray[np.uint8]
    is_river_u8, river_intensity_f32, stream_order_u8 = build_rivers_derived_fields(
        accum_f32,
        flow_to_i32,
        cell_area_f32,
        min_catchment_cells=cfg.min_catchment_cells,
        intensity_log_base=cfg.intensity_log_base,
    )

    validate_array(flow_to_i32, "flow_to", np.dtype("int32"), (n_cells,))
    validate_array(accum_f32, "accum", np.dtype("float32"), (n_cells,))
    validate_array(is_river_u8, "is_river", np.dtype("uint8"), (n_cells,))
    validate_array(
        river_intensity_f32, "river_intensity", np.dtype("float32"), (n_cells,)
    )
    validate_array(stream_order_u8, "stream_order", np.dtype("uint8"), (n_cells,))

    write_layer(
        out_dir=out_dir,
        key="flow_to",
        arr=flow_to_i32,
        meta=meta,
        sentinel=-1,
    )
    write_layer(
        out_dir=out_dir,
        key="accum",
        arr=accum_f32,
        meta=meta,
        units="m2",
    )
    write_layer(
        out_dir=out_dir,
        key="is_river",
        arr=is_river_u8,
        meta=meta,
        sentinel=0,
    )
    write_layer(
        out_dir=out_dir,
        key="river_intensity",
        arr=river_intensity_f32,
        meta=meta,
    )
    write_layer(
        out_dir=out_dir,
        key="stream_order",
        arr=stream_order_u8,
        meta=meta,
    )
    meta.write(out_dir)


def get_chunk(
    out_dir: Path,
    *,
    face: int,
    i0: int,
    j0: int,
    width: int,
    height: int,
    margin_cells: int,
    detail_cells_per_sim: int,
) -> Dict[str, object]:
    meta: WorldMeta = read_world_meta(out_dir)
    if face < 0 or face >= 6:
        raise ValueError("face must be in [0, 5]")
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be > 0")
    if margin_cells < 0:
        raise ValueError("margin_cells must be >= 0")
    if detail_cells_per_sim <= 0:
        raise ValueError("detail_cells_per_sim must be > 0")
    if i0 < 0 or j0 < 0:
        raise ValueError("i0 and j0 must be >= 0")
    if i0 + width > meta.N or j0 + height > meta.N:
        raise ValueError("chunk bounds exceed face dimensions")

    required_layers: Tuple[str, ...] = (
        "pos_xyz",
        "elev_q",
        "temp",
        "precip",
        "flow_to",
        "river_intensity",
        "stream_order",
    )
    for key in required_layers:
        if key not in meta.layers:
            raise ValueError(f"{key} layer is required for chunk generation")

    n_cells: int = meta.n_cells
    pos_xyz: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["pos_xyz"]),
        dtype=np.float32,
    )
    elev_q_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["elev_q"]),
        dtype=np.int32,
    )
    temp_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["temp"]),
        dtype=np.float32,
    )
    precip_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["precip"]),
        dtype=np.float32,
    )
    flow_to_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["flow_to"]),
        dtype=np.int32,
    )
    river_intensity_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["river_intensity"]),
        dtype=np.float32,
    )
    stream_order_u8: NDArray[np.uint8] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["stream_order"]),
        dtype=np.uint8,
    )

    validate_array(pos_xyz, "pos_xyz", np.dtype("float32"), (n_cells, 3))
    validate_array(elev_q_i32, "elev_q", np.dtype("int32"), (n_cells,))
    validate_array(temp_f32, "temp", np.dtype("float32"), (n_cells,))
    validate_array(precip_f32, "precip", np.dtype("float32"), (n_cells,))
    validate_array(flow_to_i32, "flow_to", np.dtype("int32"), (n_cells,))
    validate_array(
        river_intensity_f32, "river_intensity", np.dtype("float32"), (n_cells,)
    )
    validate_array(stream_order_u8, "stream_order", np.dtype("uint8"), (n_cells,))

    i_start: int = i0 - margin_cells
    j_start: int = j0 - margin_cells
    i_end: int = i0 + width + margin_cells
    j_end: int = j0 + height + margin_cells
    if i_start < 0 or j_start < 0 or i_end > meta.N or j_end > meta.N:
        raise ValueError("margin_cells expands chunk beyond face bounds")

    i_vals: NDArray[np.int32] = np.arange(i_start, i_end, dtype=np.int32)
    j_vals: NDArray[np.int32] = np.arange(j_start, j_end, dtype=np.int32)
    i_grid: NDArray[np.int32]
    j_grid: NDArray[np.int32]
    i_grid, j_grid = np.meshgrid(i_vals, j_vals, indexing="xy")

    base_face: int = lin_index(face, 0, 0, meta.N)
    lin_grid: NDArray[np.int64] = (
        base_face + (j_grid.astype(np.int64) * meta.N) + i_grid.astype(np.int64)
    )

    elev_chunk_q: NDArray[np.int32] = elev_q_i32[lin_grid]
    temp_chunk_f32: NDArray[np.float32] = temp_f32[lin_grid]
    precip_chunk_f32: NDArray[np.float32] = precip_f32[lin_grid]
    river_chunk_f32: NDArray[np.float32] = river_intensity_f32[lin_grid]
    stream_chunk_u8: NDArray[np.uint8] = stream_order_u8[lin_grid]

    elev_chunk_m: NDArray[np.float32] = elev_chunk_q.astype(np.float32) * ELEV_Q_M
    height_detail: NDArray[np.float32] = np.repeat(
        np.repeat(elev_chunk_m, detail_cells_per_sim, axis=1),
        detail_cells_per_sim,
        axis=0,
    ).astype(np.float32)

    land_mask_u8: NDArray[np.uint8] = (elev_chunk_q > 0).astype(np.uint8)

    center_i: int = i0 + (width // 2)
    center_j: int = j0 + (height // 2)
    center_lin: int = lin_index(face, center_i, center_j, meta.N)
    center_xyz: NDArray[np.float32] = pos_xyz[center_lin].astype(np.float32)

    payload: Dict[str, object] = {
        "request": {
            "face": face,
            "i0": i0,
            "j0": j0,
            "width": width,
            "height": height,
            "margin_cells": margin_cells,
            "detail_cells_per_sim": detail_cells_per_sim,
        },
        "heightfield_m": height_detail,
        "elev_q": elev_chunk_q.astype(np.int32),
        "temp": temp_chunk_f32.astype(np.float32),
        "precip": precip_chunk_f32.astype(np.float32),
        "rivers": {
            "river_intensity": river_chunk_f32.astype(np.float32),
            "stream_order": stream_chunk_u8.astype(np.uint8),
        },
        "feature_masks": {
            "land_mask": land_mask_u8,
        },
        "seam_pairs": [],
        "diagnostics": {
            "global_lin": lin_grid.astype(np.int64),
            "face": face,
            "center_xyz": center_xyz,
        },
        "provenance": {
            "seed": meta.world_seed,
            "N": meta.N,
            "format_version": meta.format_version,
            "global_tunables_hash": meta.global_tunables_hash,
            "chunk_tunables_hash": meta.chunk_tunables_hash,
        },
    }
    return payload


def _extract_seam_pairs(
    nbr4: NDArray[np.int32],  # int32[n_cells, 4]
    N: int,
) -> List[Tuple[int, int]]:
    """
    Extract pairs of cell indices that cross cube-sphere face boundaries.
    Returns a list of (u, v) tuples where u and v are on different faces.
    """
    n_cells: int = int(nbr4.shape[0])
    n_face_cells: int = N * N
    seam_pairs: List[Tuple[int, int]] = []

    # Determine which face each cell belongs to
    face_idx: NDArray[np.int32] = np.arange(n_cells, dtype=np.int32) // n_face_cells

    # For each cell, check its neighbors
    u: int
    for u in range(n_cells):
        u_face: int = int(face_idx[u])
        k: int
        for k in range(4):
            v: int = int(nbr4[u, k])
            # Valid neighbor on a different face
            if 0 <= v < n_cells and u_face != face_idx[v]:
                # Only add each pair once (u < v to avoid duplicates)
                if u < v:
                    seam_pairs.append((u, v))

    return seam_pairs


def _compute_report(out_dir: Path) -> Dict[str, object]:
    """
    Compute the canonical report.json payload (land_fraction, quantiles, rivers).
    Delegates to worldgen.report.generate_report for consistency.
    """
    meta: WorldMeta = read_world_meta(out_dir)

    required_layers: Tuple[str, ...] = (
        "elev_q",
        "temp",
        "precip",
        "is_river",
        "stream_order",
        "nbr4",
    )
    for key in required_layers:
        if key not in meta.layers:
            raise ValueError(f"{key} diagnostic layer required for report generation")

    # Load required layers
    elev_q_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["elev_q"]),
        dtype=np.int32,
    )
    temp_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["temp"]),
        dtype=np.float32,
    )
    precip_f32: NDArray[np.float32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["precip"]),
        dtype=np.float32,
    )
    is_river_u8: NDArray[np.uint8] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["is_river"]),
        dtype=np.uint8,
    )
    stream_order_u8: NDArray[np.uint8] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["stream_order"]),
        dtype=np.uint8,
    )
    nbr4_i32: NDArray[np.int32] = np.ascontiguousarray(
        read_layer(out_dir=out_dir, layer=meta.layers["nbr4"]),
        dtype=np.int32,
    )

    # Extract seam pairs from nbr4
    seam_pairs: List[Tuple[int, int]] = _extract_seam_pairs(nbr4_i32, meta.N)

    # Delegate to generate_report from worldgen.report
    # Use _SEA_LEVEL_Q_DEFAULT to match the original threshold (elev_q > 0 for land)
    report: WorldGenReport = generate_report(
        out_dir=out_dir,
        elev_q_i32=elev_q_i32,
        temp_f32=temp_f32,
        precip_f32=precip_f32,
        is_river_u8=is_river_u8,
        stream_order_u8=stream_order_u8,
        nbr4=nbr4_i32,
        sea_level_q=_SEA_LEVEL_Q_DEFAULT,
        seam_pairs=seam_pairs,
    )

    # Return as Dict for backward compatibility with caller
    return dict(report)


def build_full_world(
    out_dir: Path,
    *,
    seed: int,
    N: int,
    cfg: WorldConfig,
    overwrite: bool = False,
    precompile_kernels: bool = False,
) -> None:
    """
    Convenience wrapper: build_world -> build_elevation -> build_climate ->
    build_hydrology, then compute and write report.json.
    """
    if precompile_kernels:
        _precompile_kernels(N)

    build_world(out_dir, seed=seed, N=N, cfg=cfg, overwrite=overwrite)
    build_elevation(out_dir, seed=seed, N=N, cfg=cfg.elevation)
    build_climate(out_dir, seed=seed, N=N, cfg=cfg.climate)
    build_hydrology(out_dir, N=N, cfg=cfg.hydrology)

    # _compute_report delegates to generate_report which writes report.json
    _ = _compute_report(out_dir)


def _precompile_kernels(N: int) -> None:
    """Trigger a small compile of inner kernels so numba caches get created."""
    pos_xyz: NDArray[np.float32] = build_pos_xyz(N)
    nbr4_i32: NDArray[np.int32]
    nbr8_i32: NDArray[np.int32]
    nbr4_i32, nbr8_i32 = build_nbr_tables(N)
    _ = build_cell_area(N, 6371000.0)

    n_cells: int = int(6 * N * N)
    seed: int = 1

    _ = eval_noise_sphere(
        pos_xyz.astype(np.float32),
        seed,
        octaves=1,
        lacunarity=2.0,
        persistence=0.5,
        scale=1.0,
    )

    arr_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    _ = smooth_i32_nbr4(arr_q, nbr4_i32, n_cells=n_cells, strength=0.5, cap_q=10)

    moist: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    precip_accum: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    elev_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    wind_to: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    sea_mask: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    temp_f32: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    _ = advect_moisture_step(
        moist,
        precip_accum,
        elev_q,
        wind_to,
        sea_mask,
        temp_f32,
        n_cells=n_cells,
        transport_frac=0.5,
        orog_scale_m=100.0,
        ocean_source=0.5,
        cap_min=0.05,
        cap_slope=0.01,
        cap_lo=0.1,
        cap_hi=1.0,
    )

    cell_area_f32: NDArray[np.float32] = np.ones(n_cells, dtype=np.float32)
    flow_to: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    accum_f32: NDArray[np.float32] = np.ones(n_cells, dtype=np.float32)
    _ = hydraulic_erosion_step(
        arr_q,
        flow_to,
        accum_f32,
        n_cells=n_cells,
        hydraulic_k=0.01,
        base_elev_q_i32=arr_q,
    )
    _ = thermal_erosion_step(arr_q, nbr8_i32, n_cells=n_cells, talus_slope_q=10)
