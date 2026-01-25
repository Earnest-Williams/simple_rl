from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from worldgen import _build_wind_to
from worldgen.kernels.geometry import compute_cell_area
from worldgen.topology_cube_sphere import build_nbr_tables, build_pos_xyz


def test_polar_wind_degeneracy() -> None:
    n: int = 8
    pos: NDArray[np.float32] = build_pos_xyz(n)
    nbr4: NDArray[np.int32]
    nbr4, _ = build_nbr_tables(n)
    n_cells: int = 6 * n * n
    wind_to: NDArray[np.int32] = _build_wind_to(
        pos,
        nbr4,
        n_cells=n_cells,
        lat_polar_cap=0.9,
        seed=42,
    )
    z: NDArray[np.float32] = pos[:, 2]
    caps: NDArray[np.bool_] = np.abs(z) >= 0.9
    assert np.all(wind_to[caps] == -1)


def test_degenerate_cell_area() -> None:
    a: NDArray[np.float32] = np.array([1.0, 0.0, 1e-6], dtype=np.float32)
    b: NDArray[np.float32] = np.array([1.0, 1e-6, 0.0], dtype=np.float32)
    c: NDArray[np.float32] = np.array([1.0, -1e-6, 0.0], dtype=np.float32)
    corners: NDArray[np.float32] = np.empty((4, 3), dtype=np.float32)
    corners[0] = a / np.linalg.norm(a)
    corners[1] = b / np.linalg.norm(b)
    corners[2] = c / np.linalg.norm(c)
    corners[3] = corners[0]
    area: float = float(compute_cell_area(corners, radius_m=6371000.0))
    assert np.isfinite(area)
    assert area >= 0.0
