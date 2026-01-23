from __future__ import annotations

from bisect import insort
from typing import Dict, List, Tuple

import numpy as np
from numpy.typing import NDArray

from simple_rl.worldgen.kernels.heap import (
    heap_decrease_key,
    heap_pop_min,
    heap_push,
)
from simple_rl.worldgen.kernels.union_find import uf_find, uf_init, uf_union
from simple_rl.worldgen.utils_coord import coord_hash
from simple_rl.worldgen.validation import validate_array

UNRESOLVED: int = -2
SINK: int = -1
_INF_I32: int = np.iinfo(np.int32).max


def _heap_key(phi: int, *, seed: int, node: int) -> float:
    jitter_raw: int = coord_hash(seed, node) & 0xFFFF
    jitter: float = float(jitter_raw) * 1e-6
    return float(phi) + jitter


def build_flow_direction(
    elev_q_i32: NDArray[np.int32],
    nbr8_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
    *,
    seed: int,
) -> NDArray[np.int32]:
    n_cells: int = int(elev_q_i32.shape[0])
    validate_array(elev_q_i32, "elev_q_i32", np.dtype("int32"), (n_cells,))
    validate_array(nbr8_i32, "nbr8_i32", np.dtype("int32"), (n_cells, 8))
    validate_array(cell_area_f32, "cell_area_f32", np.dtype("float32"), (n_cells,))

    flow_to: NDArray[np.int32] = np.full(n_cells, UNRESOLVED, dtype=np.int32)
    flat_mask: NDArray[np.bool_] = np.zeros(n_cells, dtype=np.bool_)

    u: int
    for u in range(n_cells):
        elev_u: int = int(elev_q_i32[u])
        min_elev: int = _INF_I32
        best_v: int = -1
        has_equal: bool = False
        k: int
        for k in range(8):
            v: int = int(nbr8_i32[u, k])
            if v < 0 or v >= n_cells:
                continue
            elev_v: int = int(elev_q_i32[v])
            if elev_v == elev_u:
                has_equal = True
            if elev_v < min_elev:
                min_elev = elev_v
                best_v = v
            elif elev_v == min_elev and best_v != -1:
                if cell_area_f32[v] > cell_area_f32[best_v]:
                    best_v = v
                elif cell_area_f32[v] == cell_area_f32[best_v]:
                    if coord_hash(seed, v) < coord_hash(seed, best_v):
                        best_v = v
        flat_mask[u] = has_equal
        if min_elev < elev_u:
            flow_to[u] = best_v

    u = 0
    for u in range(n_cells):
        if flow_to[u] == UNRESOLVED and not flat_mask[u]:
            flow_to[u] = SINK

    parent, rank = uf_init(n_cells)
    for u in range(n_cells):
        if not flat_mask[u]:
            continue
        k = 0
        for k in range(8):
            v = int(nbr8_i32[u, k])
            if v <= u:
                continue
            if not flat_mask[v]:
                continue
            if elev_q_i32[v] != elev_q_i32[u]:
                continue
            uf_union(parent, rank, u, v)

    component_ids: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    for u in range(n_cells):
        if flat_mask[u]:
            component_ids[u] = uf_find(parent, u)

    components: Dict[int, List[int]] = {}
    for u in range(n_cells):
        comp_id: int = int(component_ids[u])
        if comp_id < 0:
            continue
        if comp_id not in components:
            components[comp_id] = []
        components[comp_id].append(u)

    phi: NDArray[np.int32] = np.full(n_cells, _INF_I32, dtype=np.int32)
    heap_keys: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    heap_pos: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)

    comp_id = 0
    for comp_id, comp_cells in components.items():
        outlets: List[int] = []
        for u in comp_cells:
            k = 0
            for k in range(8):
                v = int(nbr8_i32[u, k])
                if v < 0 or v >= n_cells:
                    continue
                if elev_q_i32[v] < elev_q_i32[u]:
                    outlets.append(u)
                    break

        if len(outlets) == 0:
            sink: int = min(comp_cells, key=lambda idx: coord_hash(seed, idx))
            flow_to[sink] = SINK
            outlets.append(sink)

        for u in comp_cells:
            heap_pos[u] = -1
            phi[u] = _INF_I32

        heap_nodes: NDArray[np.int32] = np.empty(len(comp_cells), dtype=np.int32)
        size: int = 0
        for u in outlets:
            phi[u] = 0
            key: float = _heap_key(0, seed=seed, node=u)
            size = heap_push(
                heap_nodes,
                heap_pos,
                heap_keys,
                size=size,
                node=u,
                key=key,
            )

        while size > 0:
            u, size = heap_pop_min(heap_nodes, heap_pos, heap_keys, size)
            if u < 0:
                break
            k = 0
            for k in range(8):
                v = int(nbr8_i32[u, k])
                if v < 0 or v >= n_cells:
                    continue
                if component_ids[v] != comp_id:
                    continue
                candidate: int = int(phi[u]) + 1
                if candidate < phi[v]:
                    phi[v] = candidate
                    key = _heap_key(candidate, seed=seed, node=v)
                    if heap_pos[v] < 0:
                        size = heap_push(
                            heap_nodes,
                            heap_pos,
                            heap_keys,
                            size=size,
                            node=v,
                            key=key,
                        )
                    else:
                        heap_decrease_key(
                            heap_nodes,
                            heap_pos,
                            heap_keys,
                            node=v,
                            new_key=key,
                        )

        for u in comp_cells:
            if flow_to[u] != UNRESOLVED:
                continue
            best_v = -1
            best_phi = phi[u]
            k = 0
            for k in range(8):
                v = int(nbr8_i32[u, k])
                if v < 0 or v >= n_cells:
                    continue
                if component_ids[v] != comp_id:
                    continue
                if phi[v] < best_phi:
                    best_phi = phi[v]
                    best_v = v
                elif phi[v] == best_phi and best_v != -1:
                    if coord_hash(seed, v) < coord_hash(seed, best_v):
                        best_v = v
            if best_v != -1:
                flow_to[u] = best_v
            else:
                flow_to[u] = SINK

    _break_flow_cycles(flow_to, seed=seed)
    return flow_to


def _break_flow_cycles(flow_to: NDArray[np.int32], *, seed: int) -> None:
    n_cells: int = int(flow_to.shape[0])
    state: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)

    start: int
    for start in range(n_cells):
        if state[start] != 0:
            continue
        path: List[int] = []
        index_map: Dict[int, int] = {}
        node: int = start
        while True:
            if node == SINK:
                for v in path:
                    state[v] = 2
                break
            if node < 0 or node >= n_cells:
                for v in path:
                    state[v] = 2
                break
            if state[node] == 2:
                for v in path:
                    state[v] = 2
                break
            if state[node] == 1:
                cycle_start: int = index_map[node]
                cycle_nodes: List[int] = path[cycle_start:]
                break_node: int = min(
                    cycle_nodes, key=lambda idx: coord_hash(seed, idx)
                )
                flow_to[break_node] = SINK
                for v in path:
                    state[v] = 2
                break
            state[node] = 1
            index_map[node] = len(path)
            path.append(node)
            node = int(flow_to[node])


def build_flow_accumulation(
    flow_to_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
) -> NDArray[np.float32]:
    n_cells: int = int(flow_to_i32.shape[0])
    validate_array(flow_to_i32, "flow_to_i32", np.dtype("int32"), (n_cells,))
    validate_array(cell_area_f32, "cell_area_f32", np.dtype("float32"), (n_cells,))

    in_deg: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    u: int
    for u in range(n_cells):
        v: int = int(flow_to_i32[u])
        if v == SINK:
            continue
        if v < 0 or v >= n_cells:
            raise ValueError(f"flow_to_i32[{u}] is out of range: {v}")
        in_deg[v] += 1

    accum_f32: NDArray[np.float32] = cell_area_f32.astype(np.float32).copy()
    queue: List[int] = []
    for u in range(n_cells):
        if in_deg[u] == 0:
            queue.append(u)
    queue.sort()

    while len(queue) > 0:
        u = queue.pop(0)
        v = int(flow_to_i32[u])
        if v != SINK:
            accum_f32[v] += accum_f32[u]
            in_deg[v] -= 1
            if in_deg[v] == 0:
                insort(queue, v)

    if int(np.sum(in_deg)) != 0:
        raise ValueError("flow_to_i32 contains a directed cycle after correction")

    return accum_f32


def build_rivers_derived_fields(
    accum_f32: NDArray[np.float32],
    flow_to_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
    *,
    min_catchment_cells: int,
    intensity_log_base: float,
) -> Tuple[NDArray[np.uint8], NDArray[np.float32], NDArray[np.uint8]]:
    n_cells: int = int(accum_f32.shape[0])
    validate_array(accum_f32, "accum_f32", np.dtype("float32"), (n_cells,))
    validate_array(flow_to_i32, "flow_to_i32", np.dtype("int32"), (n_cells,))
    validate_array(cell_area_f32, "cell_area_f32", np.dtype("float32"), (n_cells,))
    if min_catchment_cells <= 0:
        raise ValueError("min_catchment_cells must be > 0")
    if intensity_log_base <= 1.0:
        raise ValueError("intensity_log_base must be > 1")

    cell_area_ref: float = float(np.median(cell_area_f32))
    threshold: float = cell_area_ref * float(min_catchment_cells)
    is_river: NDArray[np.bool_] = accum_f32 >= threshold
    is_river_u8: NDArray[np.uint8] = is_river.astype(np.uint8)
    river_intensity_f32: NDArray[np.float32] = np.where(
        is_river,
        np.log1p(accum_f32 / (cell_area_ref * float(intensity_log_base))),
        0.0,
    ).astype(np.float32)

    in_deg: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    u: int
    for u in range(n_cells):
        if not is_river[u]:
            continue
        v: int = int(flow_to_i32[u])
        if v != SINK and is_river[v]:
            in_deg[v] += 1

    max_up: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    cnt_max: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    order: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)

    headwaters: List[int] = []
    for u in range(n_cells):
        if is_river[u] and in_deg[u] == 0 and flow_to_i32[u] != SINK:
            headwaters.append(u)
    headwaters.sort()

    queue = list(headwaters)
    while len(queue) > 0:
        u = queue.pop(0)
        if max_up[u] == 0:
            order[u] = 1
        elif cnt_max[u] >= 2:
            order[u] = np.uint8(int(max_up[u]) + 1)
        else:
            order[u] = max_up[u]

        v = int(flow_to_i32[u])
        if v != SINK and is_river[v]:
            if order[u] > max_up[v]:
                max_up[v] = order[u]
                cnt_max[v] = np.uint8(1)
            elif order[u] == max_up[v]:
                cnt_max[v] = np.uint8(int(cnt_max[v]) + 1)

            in_deg[v] -= 1
            if in_deg[v] == 0:
                insort(queue, v)

    return is_river_u8, river_intensity_f32, order
