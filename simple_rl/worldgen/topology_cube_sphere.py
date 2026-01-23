from __future__ import annotations

from typing import Any, Dict, Tuple

import numpy as np
from numba import njit, prange
from numpy.typing import NDArray

from simple_rl.worldgen.kernels.geometry import compute_cell_area
from simple_rl.worldgen.utils_coord import (
    _cube_xyz,
    _face_uv,
    cube_face_from_xyz,
    pos_xyz,
    pos_xyz_from_uv,
)

EDGE_NORTH: int = 0
EDGE_EAST: int = 1
EDGE_SOUTH: int = 2
EDGE_WEST: int = 3


def lin_index(face: int, i: int, j: int, N: int) -> int:
    return ((face * N) + j) * N + i


@njit(cache=True)
def _neighbor_from_face(
    face: int,
    i: int,
    j: int,
    di: int,
    dj: int,
    N: int,
) -> Tuple[int, int, int]:
    step: float = 2.0 / N
    u: float
    v: float
    u, v = _face_uv(face, i, j, N)
    u2: float = u + (di * step)
    v2: float = v + (dj * step)
    if -1.0 <= u2 <= 1.0 and -1.0 <= v2 <= 1.0:
        i2: int = i + di
        j2: int = j + dj
        return face, i2, j2
    x: float
    y: float
    z: float
    x, y, z = _cube_xyz(face, u2, v2)
    face2: int
    u_face: float
    v_face: float
    face2, u_face, v_face = cube_face_from_xyz(x, y, z)
    i2f: float = (u_face + 1.0) * 0.5 * N
    j2f: float = (v_face + 1.0) * 0.5 * N
    i2 = int(min(max(int(i2f), 0), N - 1))
    j2 = int(min(max(int(j2f), 0), N - 1))
    return face2, i2, j2


def build_default_edge_map() -> Dict[int, Dict[int, Dict[str, Any]]]:
    edge_map: Dict[int, Dict[int, Dict[str, Any]]] = {}
    sample_i: int = 0
    sample_j: int = 0
    N: int = 4
    for face in range(6):
        edge_map[face] = {}
        for edge, di, dj in [
            (EDGE_NORTH, 0, -1),
            (EDGE_EAST, 1, 0),
            (EDGE_SOUTH, 0, 1),
            (EDGE_WEST, -1, 0),
        ]:
            face2: int
            i2: int
            j2: int
            face2, i2, j2 = _neighbor_from_face(
                face,
                sample_i,
                sample_j,
                di,
                dj,
                N,
            )
            edge_map[face][edge] = {
                "face": face2,
                "edge": edge,
                "xform": 0,
            }
    return edge_map


@njit(cache=True, parallel=True)
def _build_pos_xyz(N: int) -> NDArray[np.float32]:
    n_cells: int = 6 * N * N
    pos: NDArray[np.float32] = np.empty((n_cells, 3), dtype=np.float32)
    face_size: int = N * N
    for lin in prange(n_cells):
        face: int = lin // face_size
        rem: int = lin - (face * face_size)
        j: int = rem // N
        i: int = rem - (j * N)
        pos[lin] = pos_xyz(face, i, j, N)
    return pos


def build_pos_xyz(N: int) -> NDArray[np.float32]:
    if N <= 0:
        raise ValueError("N must be > 0")
    return _build_pos_xyz(N)


@njit(cache=True, parallel=True)
def _build_cell_area(N: int, planet_radius_m: float) -> NDArray[np.float32]:
    n_cells: int = 6 * N * N
    cell_area_f32: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    face_size: int = N * N
    for lin in prange(n_cells):
        face: int = lin // face_size
        rem: int = lin - (face * face_size)
        j: int = rem // N
        i: int = rem - (j * N)
        u0: float = (2.0 * i / N) - 1.0
        u1: float = (2.0 * (i + 1) / N) - 1.0
        v0: float = (2.0 * j / N) - 1.0
        v1: float = (2.0 * (j + 1) / N) - 1.0
        corners: NDArray[np.float32] = np.empty((4, 3), dtype=np.float32)
        corners[0] = pos_xyz_from_uv(face, u0, v0)
        corners[1] = pos_xyz_from_uv(face, u1, v0)
        corners[2] = pos_xyz_from_uv(face, u1, v1)
        corners[3] = pos_xyz_from_uv(face, u0, v1)
        cell_area_f32[lin] = float(compute_cell_area(corners, planet_radius_m))
    return cell_area_f32


def build_cell_area(N: int, planet_radius_m: float) -> NDArray[np.float32]:
    if N <= 0:
        raise ValueError("N must be > 0")
    if planet_radius_m <= 0.0:
        raise ValueError("planet_radius_m must be > 0")
    return _build_cell_area(N, planet_radius_m)


@njit(cache=True, parallel=True)
def _build_nbr_tables(N: int) -> Tuple[NDArray[np.int32], NDArray[np.int32]]:
    n_cells: int = 6 * N * N
    nbr4_i32: NDArray[np.int32] = np.empty((n_cells, 4), dtype=np.int32)
    nbr8_i32: NDArray[np.int32] = np.empty((n_cells, 8), dtype=np.int32)
    face_size: int = N * N
    for lin in prange(n_cells):
        face: int = lin // face_size
        rem: int = lin - (face * face_size)
        j: int = rem // N
        i: int = rem - (j * N)
        n_face: int
        n_i: int
        n_j: int
        n_face, n_i, n_j = _neighbor_from_face(face, i, j, 0, -1, N)
        nbr4_i32[lin, 0] = lin_index(n_face, n_i, n_j, N)
        n_face, n_i, n_j = _neighbor_from_face(face, i, j, 1, 0, N)
        nbr4_i32[lin, 1] = lin_index(n_face, n_i, n_j, N)
        n_face, n_i, n_j = _neighbor_from_face(face, i, j, 0, 1, N)
        nbr4_i32[lin, 2] = lin_index(n_face, n_i, n_j, N)
        n_face, n_i, n_j = _neighbor_from_face(face, i, j, -1, 0, N)
        nbr4_i32[lin, 3] = lin_index(n_face, n_i, n_j, N)

        neighbors8: Tuple[Tuple[int, int], ...] = (
            (0, -1),
            (1, -1),
            (1, 0),
            (1, 1),
            (0, 1),
            (-1, 1),
            (-1, 0),
            (-1, -1),
        )
        for idx in range(8):
            di: int = neighbors8[idx][0]
            dj: int = neighbors8[idx][1]
            n_face, n_i, n_j = _neighbor_from_face(face, i, j, di, dj, N)
            nbr8_i32[lin, idx] = lin_index(n_face, n_i, n_j, N)

    return nbr4_i32, nbr8_i32


def build_nbr_tables(
    N: int,
    edge_map: Dict[int, Dict[int, Dict[str, Any]]],
) -> Tuple[NDArray[np.int32], NDArray[np.int32]]:
    if N <= 0:
        raise ValueError("N must be > 0")
    del edge_map
    return _build_nbr_tables(N)
