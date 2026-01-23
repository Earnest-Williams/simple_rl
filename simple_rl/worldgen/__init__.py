from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import numpy as np
from numpy.typing import NDArray

from simple_rl.worldgen.config import (
    ELEV_Q_M,
    ClimateConfig,
    ElevationConfig,
    HydrologyConfig,
    WorldConfig,
    compute_tunables_hash,
    config_as_dict,
    default_world_config,
)
from simple_rl.worldgen.hydrology import (
    build_flow_accumulation,
    build_flow_direction,
    build_rivers_derived_fields,
)
from simple_rl.worldgen.io import ensure_dir, read_layer, write_layer
from simple_rl.worldgen.metadata import WorldMeta, build_world_meta, read_world_meta
from simple_rl.worldgen.topology_cube_sphere import (
    build_cell_area,
    build_nbr_tables,
    build_pos_xyz,
)
from simple_rl.worldgen.validation import validate_array

__all__: List[str] = [
    "ClimateConfig",
    "ElevationConfig",
    "HydrologyConfig",
    "WorldConfig",
    "build_world",
    "build_elevation",
    "build_climate",
    "build_hydrology",
    "default_world_config",
    "get_chunk",
]


def _write_report(out_dir: Path, payload: Dict[str, object]) -> None:
    path: Path = out_dir / "report.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


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
        import shutil

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
    del out_dir
    del seed
    del N
    del cfg
    del plate_seed_xyz
    raise NotImplementedError("Elevation pipeline is not implemented yet")


def build_climate(
    out_dir: Path,
    *,
    seed: int,
    N: int,
    cfg: ClimateConfig,
) -> None:
    del out_dir
    del seed
    del N
    del cfg
    raise NotImplementedError("Climate pipeline is not implemented yet")


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
    del out_dir
    del face
    del i0
    del j0
    del width
    del height
    del margin_cells
    del detail_cells_per_sim
    raise NotImplementedError("Chunk generation is not implemented yet")
