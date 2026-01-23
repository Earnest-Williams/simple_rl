from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from simple_rl.worldgen.kernels.advection import advect_moisture_step
from simple_rl.worldgen.kernels.erosion import (
    hydraulic_erosion_step,
    thermal_erosion_step,
)
from simple_rl.worldgen.kernels.smoothing import smooth_f32_nbr4, smooth_i32_nbr4


def _nbr4_line(n_cells: int) -> NDArray[np.int32]:
    nbr4: NDArray[np.int32] = np.full((n_cells, 4), -1, dtype=np.int32)
    for u in range(n_cells):
        if u > 0:
            nbr4[u, 3] = u - 1
        if u + 1 < n_cells:
            nbr4[u, 1] = u + 1
    return nbr4


def _nbr8_pair() -> NDArray[np.int32]:
    nbr8: NDArray[np.int32] = np.full((2, 8), -1, dtype=np.int32)
    nbr8[0, 0] = 1
    nbr8[1, 0] = 0
    return nbr8


def test_smooth_f32_nbr4_basic() -> None:
    data: NDArray[np.float32] = np.array([0.0, 10.0, 0.0], dtype=np.float32)
    nbr4: NDArray[np.int32] = _nbr4_line(3)
    result: NDArray[np.float32] = smooth_f32_nbr4(
        data,
        nbr4,
        n_cells=3,
        strength=0.5,
        cap=5.0,
    )
    expected: NDArray[np.float32] = np.array([2.5, 7.5, 2.5], dtype=np.float32)
    np.testing.assert_allclose(result, expected)


def test_smooth_i32_nbr4_basic() -> None:
    data_q: NDArray[np.int32] = np.array([0, 10, 0], dtype=np.int32)
    nbr4: NDArray[np.int32] = _nbr4_line(3)
    result: NDArray[np.int32] = smooth_i32_nbr4(
        data_q,
        nbr4,
        n_cells=3,
        strength=0.5,
        cap_q=5,
    )
    expected: NDArray[np.int32] = np.array([2, 8, 2], dtype=np.int32)
    np.testing.assert_array_equal(result, expected)


def test_advect_moisture_step_basic() -> None:
    moist_cur: NDArray[np.float32] = np.array([0.5, 0.0, 0.0], dtype=np.float32)
    precip_accum: NDArray[np.float32] = np.zeros(3, dtype=np.float32)
    elev_q_i32: NDArray[np.int32] = np.array([0, 0, 0], dtype=np.int32)
    wind_to_i32: NDArray[np.int32] = np.array([1, 2, -1], dtype=np.int32)
    sea_mask: NDArray[np.uint8] = np.array([1, 0, 0], dtype=np.uint8)
    temp_f32: NDArray[np.float32] = np.array([0.0, 0.0, 0.0], dtype=np.float32)

    result: NDArray[np.float32] = advect_moisture_step(
        moist_cur,
        precip_accum,
        elev_q_i32,
        wind_to_i32,
        sea_mask,
        temp_f32,
        n_cells=3,
        transport_frac=1.0,
        orog_scale_m=1_000.0,
        ocean_source=0.4,
        cap_min=1.0,
        cap_slope=0.0,
        cap_lo=0.0,
        cap_hi=1.0,
    )

    expected_moist: NDArray[np.float32] = np.array([0.4, 0.5, 0.0], dtype=np.float32)
    expected_precip: NDArray[np.float32] = np.zeros(3, dtype=np.float32)
    np.testing.assert_allclose(result, expected_moist)
    np.testing.assert_allclose(precip_accum, expected_precip)


def test_hydraulic_erosion_step_basic() -> None:
    elev_q_i32: NDArray[np.int32] = np.array([10, 5, 0], dtype=np.int32)
    flow_to_i32: NDArray[np.int32] = np.array([1, 2, -1], dtype=np.int32)
    accum_f32: NDArray[np.float32] = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    base_elev_q_i32: NDArray[np.int32] = np.array([0, 0, 0], dtype=np.int32)

    result: NDArray[np.int32] = hydraulic_erosion_step(
        elev_q_i32,
        flow_to_i32,
        accum_f32,
        n_cells=3,
        hydraulic_k=1.0,
        base_elev_q_i32=base_elev_q_i32,
    )
    expected: NDArray[np.int32] = np.array([5, 2, 2], dtype=np.int32)
    np.testing.assert_array_equal(result, expected)


def test_thermal_erosion_step_basic() -> None:
    elev_q_i32: NDArray[np.int32] = np.array([10, 0], dtype=np.int32)
    nbr8: NDArray[np.int32] = _nbr8_pair()

    result: NDArray[np.int32] = thermal_erosion_step(
        elev_q_i32,
        nbr8,
        n_cells=2,
        talus_slope_q=5,
    )
    expected: NDArray[np.int32] = np.array([8, 2], dtype=np.int32)
    np.testing.assert_array_equal(result, expected)
