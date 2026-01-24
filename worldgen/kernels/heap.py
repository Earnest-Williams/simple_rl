from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def heap_init(
    heap_nodes: NDArray[np.int32],  # int32[capacity]
    heap_pos: NDArray[np.int32],  # int32[n_cells]
    heap_keys: NDArray[np.float64],  # float64[n_cells]
) -> int:
    heap_pos[:] = -1
    return 0


@njit(cache=True)
def heap_push(
    heap_nodes: NDArray[np.int32],  # int32[capacity]
    heap_pos: NDArray[np.int32],  # int32[n_cells]
    heap_keys: NDArray[np.float64],  # float64[n_cells]
    *,
    size: int,
    node: int,
    key: float,
) -> int:
    heap_nodes[size] = node
    heap_pos[node] = size
    heap_keys[node] = key

    i: int = size
    while i > 0:
        parent: int = (i - 1) // 2
        p_node: int = heap_nodes[parent]
        if heap_keys[p_node] <= key:
            break
        heap_nodes[i] = p_node
        heap_pos[p_node] = i
        heap_nodes[parent] = node
        heap_pos[node] = parent
        i = parent

    return size + 1


@njit(cache=True)
def heap_pop_min(
    heap_nodes: NDArray[np.int32],  # int32[capacity]
    heap_pos: NDArray[np.int32],  # int32[n_cells]
    heap_keys: NDArray[np.float64],  # float64[n_cells]
    size: int,
) -> tuple[int, int]:
    if size == 0:
        return -1, 0

    result: int = heap_nodes[0]
    heap_pos[result] = -1
    size -= 1

    if size == 0:
        return result, 0

    last: int = heap_nodes[size]
    heap_nodes[0] = last
    heap_pos[last] = 0
    last_key: float = heap_keys[last]

    i: int = 0
    while True:
        left: int = 2 * i + 1
        right: int = 2 * i + 2
        smallest: int = i
        smallest_key: float = last_key

        if left < size:
            left_node: int = heap_nodes[left]
            left_key: float = heap_keys[left_node]
            if left_key < smallest_key:
                smallest = left
                smallest_key = left_key

        if right < size:
            right_node: int = heap_nodes[right]
            right_key: float = heap_keys[right_node]
            if right_key < smallest_key:
                smallest = right

        if smallest == i:
            break

        swap_node: int = heap_nodes[smallest]
        heap_nodes[i] = swap_node
        heap_pos[swap_node] = i
        heap_nodes[smallest] = last
        heap_pos[last] = smallest
        i = smallest

    return result, size


@njit(cache=True)
def heap_decrease_key(
    heap_nodes: NDArray[np.int32],  # int32[capacity]
    heap_pos: NDArray[np.int32],  # int32[n_cells]
    heap_keys: NDArray[np.float64],  # float64[n_cells]
    *,
    node: int,
    new_key: float,
) -> None:
    if heap_pos[node] < 0:
        return

    heap_keys[node] = new_key
    i: int = heap_pos[node]

    while i > 0:
        parent: int = (i - 1) // 2
        p_node: int = heap_nodes[parent]
        if heap_keys[p_node] <= new_key:
            break
        heap_nodes[i] = p_node
        heap_pos[p_node] = i
        heap_nodes[parent] = node
        heap_pos[node] = parent
        i = parent
