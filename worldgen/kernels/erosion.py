from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray

from worldgen.constants import ELEV_Q_M


@njit(cache=True)
def hydraulic_erosion_step(
    elev_q_i32: NDArray[np.int32],  # int32[n_cells]
    flow_to_i32: NDArray[np.int32],  # int32[n_cells]
    accum_f32: NDArray[np.float32],  # float32[n_cells]
    *,
    n_cells: int,
    hydraulic_k: float,
    base_elev_q_i32: NDArray[np.int32],  # int32[n_cells]
) -> NDArray[np.int32]:
    delta_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)

    u: int
    for u in range(n_cells):
        v: int = int(flow_to_i32[u])
        if v == -1:
            continue

        slope_q: int = int(elev_q_i32[u]) - int(elev_q_i32[v])
        if slope_q <= 0:
            continue

        capacity: float = float(accum_f32[u]) * (slope_q * ELEV_Q_M)
        max_erosion_q: int = max(0, int(elev_q_i32[u]) - int(base_elev_q_i32[u]))

        erosion_f: float = capacity * hydraulic_k / ELEV_Q_M
        erosion_q: int = int(min(erosion_f, float(max_erosion_q)))

        if erosion_q > 0:
            delta_q[u] -= erosion_q
            delta_q[v] += erosion_q // 2

    return elev_q_i32 + delta_q


@njit(cache=True)
def thermal_erosion_step(
    elev_q_i32: NDArray[np.int32],  # int32[n_cells]
    nbr8: NDArray[np.int32],  # int32[n_cells, 8]
    *,
    n_cells: int,
    talus_slope_q: int,
) -> NDArray[np.int32]:
    delta_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)

    u: int
    for u in range(n_cells):
        k: int
        for k in range(8):
            v: int = int(nbr8[u, k])
            if v < 0 or v >= n_cells:
                continue

            dh: int = int(elev_q_i32[u]) - int(elev_q_i32[v])
            if dh > talus_slope_q:
                transfer_q: int = (dh - talus_slope_q) // 2
                if transfer_q > 0:
                    delta_q[u] -= transfer_q
                    delta_q[v] += transfer_q

    return elev_q_i32 + delta_q
