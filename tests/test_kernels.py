from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldgen.kernels.advection import advect_moisture_step
from worldgen.kernels.erosion import hydraulic_erosion_step, thermal_erosion_step
from worldgen.kernels.noise import eval_noise_sphere
from worldgen.kernels.smoothing import smooth_i32_nbr4
from worldgen.topology_cube_sphere import build_nbr_tables, build_pos_xyz


def test_noise_deterministic() -> None:
    N: int = 4
    pos: NDArray[np.float32] = build_pos_xyz(N)
    out1: NDArray[np.float32] = eval_noise_sphere(
        pos, 42, octaves=2, lacunarity=2.0, persistence=0.5, scale=1.0
    )
    out2: NDArray[np.float32] = eval_noise_sphere(
        pos, 42, octaves=2, lacunarity=2.0, persistence=0.5, scale=1.0
    )
    assert np.allclose(out1, out2)


def test_smoothing_and_erosion_basic() -> None:
    N: int = 4
    n_cells: int = 6 * N * N
    nbr4: NDArray[np.int32]
    nbr8: NDArray[np.int32]
    nbr4, nbr8 = build_nbr_tables(N)

    arr_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    arr_q[0] = 100
    smoothed: NDArray[np.int32] = smooth_i32_nbr4(
        arr_q, nbr4, n_cells=n_cells, strength=0.5, cap_q=10
    )
    assert smoothed.dtype == np.int32
    assert not np.any(np.isnan(smoothed.astype(np.float32)))

    base: NDArray[np.int32] = arr_q.copy()
    flow_to: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    accum: NDArray[np.float32] = np.ones(n_cells, dtype=np.float32)
    out1: NDArray[np.int32] = hydraulic_erosion_step(
        base, flow_to, accum, n_cells=n_cells, hydraulic_k=0.01, base_elev_q_i32=base
    )
    out2: NDArray[np.int32] = hydraulic_erosion_step(
        base, flow_to, accum, n_cells=n_cells, hydraulic_k=0.01, base_elev_q_i32=base
    )
    assert np.array_equal(out1, out2)

    out3: NDArray[np.int32] = thermal_erosion_step(
        base, nbr8, n_cells=n_cells, talus_slope_q=5
    )
    out4: NDArray[np.int32] = thermal_erosion_step(
        base, nbr8, n_cells=n_cells, talus_slope_q=5
    )
    assert np.array_equal(out3, out4)


def test_advection_stability() -> None:
    N: int = 4
    n_cells: int = 6 * N * N
    moist: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    precip_accum: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    elev_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    wind_to: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    sea_mask: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    temp: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    out: NDArray[np.float32] = advect_moisture_step(
        moist,
        precip_accum,
        elev_q,
        wind_to,
        sea_mask,
        temp,
        n_cells=n_cells,
        transport_frac=0.5,
        orog_scale_m=100.0,
        ocean_source=0.6,
        cap_min=0.05,
        cap_slope=0.015,
        cap_lo=0.1,
        cap_hi=1.0,
    )
    assert out.dtype == np.float32
    assert np.all(out >= 0.0)
