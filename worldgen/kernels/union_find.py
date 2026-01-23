from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def uf_init(n: int) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
    parent: NDArray[np.int32] = np.arange(n, dtype=np.int32)
    rank: NDArray[np.int32] = np.zeros(n, dtype=np.int32)
    return parent, rank


@njit(cache=True)
def uf_find(parent: NDArray[np.int32], x: int) -> int:
    root: int = x
    while parent[root] != root:
        root = parent[root]

    while parent[x] != root:
        next_x: int = parent[x]
        parent[x] = root
        x = next_x

    return root


@njit(cache=True)
def uf_union(
    parent: NDArray[np.int32],
    rank: NDArray[np.int32],
    x: int,
    y: int,
) -> bool:
    rx: int = uf_find(parent, x)
    ry: int = uf_find(parent, y)

    if rx == ry:
        return False

    if rank[rx] < rank[ry]:
        parent[rx] = ry
    elif rank[rx] > rank[ry]:
        parent[ry] = rx
    else:
        if rx < ry:
            parent[ry] = rx
            rank[rx] += 1
        else:
            parent[rx] = ry
            rank[ry] += 1

    return True


@njit(cache=True)
def uf_build_components(
    parent: NDArray[np.int32],
    n: int,
) -> NDArray[np.int32]:
    component: NDArray[np.int32] = np.empty(n, dtype=np.int32)
    i: int
    for i in range(n):
        component[i] = uf_find(parent, i)
    return component
