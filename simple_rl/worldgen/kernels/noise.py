from __future__ import annotations

from typing import Tuple

import numpy as np
from numba import njit
from numpy.typing import NDArray

NOISE_DOMAIN: int = 0x4E4F4953
NOISE_OCTAVE_CONST: int = 0x9E3779B9
MASK64: int = (1 << 64) - 1
MASK32: int = (1 << 32) - 1


@njit(cache=True)
def splitmix64(x: int) -> int:
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & MASK64
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & MASK64
    return (x ^ (x >> 31)) & MASK64


@njit(cache=True)
def hash_gradient(seed: int, ix: int, iy: int, iz: int) -> tuple[float, float, float]:
    key: int = ((seed & MASK32) << 32) ^ (
        ((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791)) & MASK32
    )
    h: int = splitmix64(key)

    gx: float = ((h & 0xFFFF) / 32768.0) - 1.0
    gy: float = (((h >> 16) & 0xFFFF) / 32768.0) - 1.0
    gz: float = (((h >> 32) & 0xFFFF) / 32768.0) - 1.0

    length: float = np.sqrt(gx * gx + gy * gy + gz * gz)
    if length > 1e-10:
        inv_len: float = 1.0 / length
        gx *= inv_len
        gy *= inv_len
        gz *= inv_len

    return gx, gy, gz


@njit(cache=True)
def smoothstep(t: float) -> float:
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@njit(cache=True)
def noise_3d_single(seed: int, x: float, y: float, z: float) -> float:
    ix: int = int(np.floor(x))
    iy: int = int(np.floor(y))
    iz: int = int(np.floor(z))

    fx: float = x - ix
    fy: float = y - iy
    fz: float = z - iz

    wx: float = smoothstep(fx)
    wy: float = smoothstep(fy)
    wz: float = smoothstep(fz)

    result: float = 0.0
    dz: int
    dy: int
    dx: int
    for dz in range(2):
        for dy in range(2):
            for dx in range(2):
                gx: float
                gy: float
                gz: float
                gx, gy, gz = hash_gradient(seed, ix + dx, iy + dy, iz + dz)
                dot: float = gx * (fx - dx) + gy * (fy - dy) + gz * (fz - dz)

                weight: float = 1.0
                weight *= (1.0 - wx) if dx == 0 else wx
                weight *= (1.0 - wy) if dy == 0 else wy
                weight *= (1.0 - wz) if dz == 0 else wz

                result += weight * dot

    return result


@njit(cache=True)
def octave_seed(world_seed: int, octave: int) -> int:
    return world_seed ^ NOISE_DOMAIN ^ (octave * NOISE_OCTAVE_CONST)


@njit(cache=True)
def noise_3d_multi_octave(
    seed: int,
    *,
    x: float,
    y: float,
    z: float,
    octaves: int,
    lacunarity: float,
    persistence: float,
) -> float:
    if octaves <= 0:
        raise ValueError(f"octaves must be positive, got {octaves}")

    total: float = 0.0
    freq: float = 1.0
    amp: float = 1.0
    max_amp: float = 0.0

    k: int
    for k in range(octaves):
        seed_k: int = octave_seed(seed, k)
        total += amp * noise_3d_single(seed_k, x * freq, y * freq, z * freq)
        max_amp += amp
        freq *= lacunarity
        amp *= persistence

    return total / max_amp


@njit(cache=True)
def eval_noise_sphere(
    pos_xyz: NDArray[np.float32],  # float32[n_cells, 3]
    seed: int,
    *,
    octaves: int = 4,
    lacunarity: float = 2.0,
    persistence: float = 0.5,
    scale: float = 1.0,
) -> NDArray[np.float32]:
    n: int = pos_xyz.shape[0]
    result: NDArray[np.float32] = np.empty(n, dtype=np.float32)

    i: int
    for i in range(n):
        x: float = pos_xyz[i, 0] * scale
        y: float = pos_xyz[i, 1] * scale
        z: float = pos_xyz[i, 2] * scale
        result[i] = noise_3d_multi_octave(
            seed,
            x=x,
            y=y,
            z=z,
            octaves=octaves,
            lacunarity=lacunarity,
            persistence=persistence,
        )

    return result
