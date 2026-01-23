from __future__ import annotations

from typing import Tuple

import numpy as np
from numpy.typing import NDArray

BIOME_JITTER_DOMAIN: int = 0x42494F4D
NOISE_DOMAIN: int = 0x4E4F4953
PLATE_SEED_DOMAIN: int = 0x504C4154
WIND_DOMAIN: int = 0x57494E44
FLOW_DOMAIN: int = 0x464C4F57
FLAT_DOMAIN: int = 0x464C4154

_HASH_MASK: int = 0xFFFFFFFFFFFFFFFF


def _splitmix64(value: int) -> int:
    x: int = value & _HASH_MASK
    x = (x + 0x9E3779B97F4A7C15) & _HASH_MASK
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & _HASH_MASK
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & _HASH_MASK
    x = x ^ (x >> 31)
    return x & _HASH_MASK


def coord_hash(world_seed: int, lin: int) -> int:
    combined: int = (world_seed ^ lin) & _HASH_MASK
    return _splitmix64(combined)


def hash01(world_seed: int, lin: int) -> float:
    hashed: int = coord_hash(world_seed, lin)
    mantissa: int = hashed >> 11
    return mantissa * (1.0 / (1 << 53))


def hash01_domain(world_seed: int, domain: int, lin: int) -> float:
    combined: int = world_seed ^ domain
    return hash01(combined, lin)


def _face_uv(face: int, i: int, j: int, N: int) -> Tuple[float, float]:
    if N <= 0:
        raise ValueError("N must be > 0")
    if i < 0 or i >= N or j < 0 or j >= N:
        raise ValueError("i and j must be within [0, N)")
    u: float = (2.0 * (i + 0.5) / N) - 1.0
    v: float = (2.0 * (j + 0.5) / N) - 1.0
    return u, v


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


def pos_xyz(face: int, i: int, j: int, N: int) -> NDArray[np.float32]:
    u: float
    v: float
    u, v = _face_uv(face, i, j, N)
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
