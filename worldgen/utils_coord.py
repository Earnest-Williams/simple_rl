from __future__ import annotations

from typing import Tuple

import numpy as np
from numba import njit
from numpy.typing import NDArray

from worldgen.constants import (
    BIOME_JITTER_DOMAIN,
    FLOW_DOMAIN,
    FLAT_DOMAIN,
    HASH_MASK_64,
    HASH_SPLITMIX_INCREMENT,
    HASH_SPLITMIX_MUL1,
    HASH_SPLITMIX_MUL2,
    NOISE_DOMAIN,
    PLATE_SEED_DOMAIN,
    WIND_DOMAIN,
)

__all__: list[str] = [
    "BIOME_JITTER_DOMAIN",
    "FLOW_DOMAIN",
    "FLAT_DOMAIN",
    "NOISE_DOMAIN",
    "PLATE_SEED_DOMAIN",
    "WIND_DOMAIN",
    "coord_hash",
    "coord_hash_domain",
    "hash01",
    "hash01_domain",
    "pos_xyz",
    "pos_xyz_from_uv",
    "cube_face_from_xyz",
]


@njit(cache=True)
def _splitmix64(value: int) -> int:
    x: int = value & HASH_MASK_64
    x = (x + HASH_SPLITMIX_INCREMENT) & HASH_MASK_64
    x = (x ^ (x >> 30)) * HASH_SPLITMIX_MUL1 & HASH_MASK_64
    x = (x ^ (x >> 27)) * HASH_SPLITMIX_MUL2 & HASH_MASK_64
    x = x ^ (x >> 31)
    return x & HASH_MASK_64


@njit(cache=True)
def coord_hash(world_seed: int, lin: int) -> int:
    combined: int = (world_seed ^ lin) & HASH_MASK_64
    return _splitmix64(combined)


@njit(cache=True)
def coord_hash_domain(world_seed: int, domain: int, lin: int) -> int:
    combined: int = world_seed ^ domain
    return coord_hash(combined, lin)


@njit(cache=True)
def hash01(world_seed: int, lin: int) -> float:
    hashed: int = coord_hash(world_seed, lin)
    mantissa: int = hashed >> 11
    return mantissa * (1.0 / (1 << 53))


@njit(cache=True)
def hash01_domain(world_seed: int, domain: int, lin: int) -> float:
    combined: int = world_seed ^ domain
    return hash01(combined, lin)


@njit(cache=True)
def _face_uv(face: int, i: int, j: int, N: int) -> Tuple[float, float]:
    if N <= 0:
        raise ValueError("N must be > 0")
    if i < 0 or i >= N or j < 0 or j >= N:
        raise ValueError("i and j must be within [0, N)")
    u: float = (2.0 * (i + 0.5) / N) - 1.0
    v: float = (2.0 * (j + 0.5) / N) - 1.0
    return u, v


@njit(cache=True)
def _cube_xyz(face: int, u: float, v: float) -> Tuple[float, float, float]:
    if face == 0:
        return 1.0, v, -u
    if face == 1:
        return -1.0, v, u
    if face == 2:
        return u, 1.0, -v
    if face == 3:
        return u, -1.0, v
    if face == 4:
        return u, v, 1.0
    if face == 5:
        return -u, v, -1.0
    raise ValueError("face must be in [0, 5]")


@njit(cache=True)
def pos_xyz_from_uv(face: int, u: float, v: float) -> NDArray[np.float32]:
    x: float
    y: float
    z: float
    x, y, z = _cube_xyz(face, u, v)
    vec: NDArray[np.float32] = np.array([x, y, z], dtype=np.float32)
    norm: float = float(np.linalg.norm(vec))
    if norm <= 0.0:
        raise ValueError("Cannot normalize zero-length vector")
    vec /= norm
    return vec


@njit(cache=True)
def pos_xyz(face: int, i: int, j: int, N: int) -> NDArray[np.float32]:
    u: float
    v: float
    u, v = _face_uv(face, i, j, N)
    return pos_xyz_from_uv(face, u, v)


@njit(cache=True)
def cube_face_from_xyz(x: float, y: float, z: float) -> Tuple[int, float, float]:
    ax: float = abs(x)
    ay: float = abs(y)
    az: float = abs(z)
    if ax >= ay and ax >= az:
        face: int = 0 if x >= 0.0 else 1
        denom: float = ax
        u: float = -z / denom if face == 0 else z / denom
        v: float = y / denom
        return face, u, v
    if ay >= ax and ay >= az:
        face = 2 if y >= 0.0 else 3
        denom = ay
        u = x / denom
        v = -z / denom if face == 2 else z / denom
        return face, u, v
    face = 4 if z >= 0.0 else 5
    denom = az
    u = x / denom if face == 4 else -x / denom
    v = y / denom
    return face, u, v
