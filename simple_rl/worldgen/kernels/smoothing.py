from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def smooth_f32_nbr4(
    data: NDArray[np.float32],  # float32[n_cells]
    nbr4: NDArray[np.int32],  # int32[n_cells, 4]
    *,
    n_cells: int,
    strength: float,
    cap: float,
) -> NDArray[np.float32]:
    result: NDArray[np.float32] = data.copy()

    u: int
    for u in range(n_cells):
        total: float = 0.0
        count: int = 0
        k: int
        for k in range(4):
            v: int = int(nbr4[u, k])
            if v < 0 or v >= n_cells:
                continue
            total += float(data[v])
            count += 1

        if count == 0:
            continue

        mean_nbr: float = total / count
        diff: float = mean_nbr - float(data[u])

        diff = max(-cap, min(diff, cap))

        result[u] = np.float32(float(data[u]) + diff * strength)

    return result


@njit(cache=True)
def smooth_i32_nbr4(
    data_q: NDArray[np.int32],  # int32[n_cells]
    nbr4: NDArray[np.int32],  # int32[n_cells, 4]
    *,
    n_cells: int,
    strength: float,
    cap_q: int,
) -> NDArray[np.int32]:
    result: NDArray[np.int32] = data_q.copy()

    u: int
    for u in range(n_cells):
        total: int = 0
        count: int = 0
        k: int
        for k in range(4):
            v: int = int(nbr4[u, k])
            if v < 0 or v >= n_cells:
                continue
            total += int(data_q[v])
            count += 1

        if count == 0:
            continue

        mean_nbr: float = total / count
        diff_f: float = mean_nbr - float(data_q[u])

        diff_f = max(float(-cap_q), min(diff_f, float(cap_q)))

        adjustment: int = int(np.round(diff_f * strength))
        result[u] = int(data_q[u]) + adjustment

    return result
