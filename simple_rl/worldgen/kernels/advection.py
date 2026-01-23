from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray

ELEV_Q_M: float = 0.1


@njit(cache=True)
def advect_moisture_step(
    moist_cur: NDArray[np.float32],  # float32[n_cells]
    precip_accum: NDArray[np.float32],  # float32[n_cells]
    elev_q_i32: NDArray[np.int32],  # int32[n_cells]
    wind_to_i32: NDArray[np.int32],  # int32[n_cells]
    sea_mask: NDArray[np.uint8],  # uint8[n_cells]
    temp_f32: NDArray[np.float32],  # float32[n_cells]
    *,
    n_cells: int,
    transport_frac: float,
    orog_scale_m: float,
    ocean_source: float,
    cap_min: float,
    cap_slope: float,
    cap_lo: float,
    cap_hi: float,
) -> NDArray[np.float32]:
    moist_delta: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    precip_delta: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)

    u: int
    for u in range(n_cells):
        v: int = int(wind_to_i32[u])
        if v == -1:
            continue

        m: float = float(moist_cur[u]) * transport_frac

        elev_u: float = float(elev_q_i32[u]) * ELEV_Q_M
        elev_v: float = float(elev_q_i32[v]) * ELEV_Q_M
        dh: float = max(0.0, elev_v - elev_u)

        p_orog: float = m * (1.0 - np.exp(-dh / orog_scale_m))

        moist_delta[u] -= m
        moist_delta[v] += m - p_orog
        precip_delta[v] += p_orog

    moist_next: NDArray[np.float32] = moist_cur + moist_delta
    precip_accum += precip_delta

    for u in range(n_cells):
        if sea_mask[u] == 1 and moist_next[u] < ocean_source:
            moist_next[u] = ocean_source

        cap: float = cap_min + cap_slope * float(temp_f32[u])
        cap = max(cap_lo, min(cap, cap_hi))

        cond: float = float(moist_next[u]) - cap
        if cond > 0.0:
            precip_accum[u] += cond
            moist_next[u] = cap

        clamped: float = max(0.0, min(float(moist_next[u]), 1.0))
        moist_next[u] = clamped

    return moist_next
