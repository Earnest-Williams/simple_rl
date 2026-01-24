from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def cross_3d(a: NDArray[np.float32], b: NDArray[np.float32]) -> NDArray[np.float32]:
    result: NDArray[np.float32] = np.empty(3, dtype=np.float32)
    result[0] = a[1] * b[2] - a[2] * b[1]
    result[1] = a[2] * b[0] - a[0] * b[2]
    result[2] = a[0] * b[1] - a[1] * b[0]
    return result


@njit(cache=True)
def dot_3d(a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
    return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])


@njit(cache=True)
def normalize_3d(v: NDArray[np.float32]) -> NDArray[np.float32]:
    length: float = float(np.sqrt(dot_3d(v, v)))
    if length <= 1e-10:
        return v
    inv_len: float = 1.0 / length
    result: NDArray[np.float32] = np.empty(3, dtype=np.float32)
    result[0] = v[0] * inv_len
    result[1] = v[1] * inv_len
    result[2] = v[2] * inv_len
    return result


@njit(cache=True)
def spherical_triangle_area(
    a: NDArray[np.float32],
    b: NDArray[np.float32],
    c: NDArray[np.float32],
) -> float:
    a = normalize_3d(a)
    b = normalize_3d(b)
    c = normalize_3d(c)

    ab: NDArray[np.float32] = cross_3d(a, b)
    bc: NDArray[np.float32] = cross_3d(b, c)
    ca: NDArray[np.float32] = cross_3d(c, a)

    lab: float = float(np.sqrt(dot_3d(ab, ab)))
    lbc: float = float(np.sqrt(dot_3d(bc, bc)))
    lca: float = float(np.sqrt(dot_3d(ca, ca)))

    if lab < 1e-10 or lbc < 1e-10 or lca < 1e-10:
        edge1: NDArray[np.float32] = b - a
        edge2: NDArray[np.float32] = c - a
        cross_prod: NDArray[np.float32] = cross_3d(edge1, edge2)
        return 0.5 * float(np.sqrt(dot_3d(cross_prod, cross_prod)))

    ab = ab * (1.0 / lab)
    bc = bc * (1.0 / lbc)
    ca = ca * (1.0 / lca)

    cos_alpha: float = -dot_3d(ab, ca)
    cos_beta: float = -dot_3d(bc, ab)
    cos_gamma: float = -dot_3d(ca, bc)

    cos_alpha = max(-1.0, min(1.0, cos_alpha))
    cos_beta = max(-1.0, min(1.0, cos_beta))
    cos_gamma = max(-1.0, min(1.0, cos_gamma))

    alpha: float = float(np.arccos(cos_alpha))
    beta: float = float(np.arccos(cos_beta))
    gamma: float = float(np.arccos(cos_gamma))

    excess: float = alpha + beta + gamma - float(np.pi)
    return abs(excess)


@njit(cache=True)
def compute_cell_area(corners: NDArray[np.float32], radius_m: float) -> float:
    area1: float = spherical_triangle_area(corners[0], corners[1], corners[2])
    area2: float = spherical_triangle_area(corners[0], corners[2], corners[3])
    return (area1 + area2) * radius_m * radius_m
