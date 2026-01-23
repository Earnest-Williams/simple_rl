from __future__ import annotations

from typing import Tuple

import numpy as np
from numba import njit
from numpy.typing import NDArray

from simple_rl.worldgen.kernels.heap import (
    heap_decrease_key,
    heap_pop_min,
    heap_push,
)
from simple_rl.worldgen.kernels.union_find import uf_find, uf_init, uf_union
from simple_rl.worldgen.utils_coord import FLOW_DOMAIN, coord_hash_domain
from simple_rl.worldgen.validation import validate_array

UNRESOLVED: int = -2
SINK: int = -1
_INF_I32: int = np.iinfo(np.int32).max


@njit(cache=True)
def _heap_key(phi: int, seed: int, node: int) -> float:
    jitter_raw: int = coord_hash_domain(seed, FLOW_DOMAIN, node) & 0xFFFF
    jitter: float = float(jitter_raw) * 1e-6
    return float(phi) + jitter


@njit(cache=True)
def _break_flow_cycles_numba(flow_to: NDArray[np.int32], seed: int) -> None:
    n_cells: int = int(flow_to.shape[0])
    state: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    visit_id: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    step_index: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    path: NDArray[np.int32] = np.empty(n_cells, dtype=np.int32)
    run_id: int = 1

    start: int
    for start in range(n_cells):
        if state[start] != 0:
            continue
        length: int = 0
        node: int = start
        while True:
            if node == SINK:
                i: int
                for i in range(length):
                    state[path[i]] = 2
                break
            if node < 0 or node >= n_cells:
                for i in range(length):
                    state[path[i]] = 2
                break
            if state[node] == 2:
                for i in range(length):
                    state[path[i]] = 2
                break
            if state[node] == 1 and visit_id[node] == run_id:
                cycle_start: int = step_index[node]
                break_node: int = path[cycle_start]
                min_hash: int = coord_hash_domain(seed, FLOW_DOMAIN, break_node)
                i = cycle_start + 1
                while i < length:
                    candidate: int = path[i]
                    cand_hash: int = coord_hash_domain(seed, FLOW_DOMAIN, candidate)
                    if cand_hash < min_hash:
                        min_hash = cand_hash
                        break_node = candidate
                    i += 1
                flow_to[break_node] = SINK
                for i in range(length):
                    state[path[i]] = 2
                break
            state[node] = 1
            visit_id[node] = run_id
            step_index[node] = length
            path[length] = node
            length += 1
            node = int(flow_to[node])
        run_id += 1


@njit(cache=True)
def _build_flow_direction_numba(
    elev_q_i32: NDArray[np.int32],
    nbr8_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
    seed: int,
) -> NDArray[np.int32]:
    n_cells: int = int(elev_q_i32.shape[0])
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
                    if (
                        coord_hash_domain(seed, FLOW_DOMAIN, v)
                        < coord_hash_domain(seed, FLOW_DOMAIN, best_v)
                    ):
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

    counts: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    for u in range(n_cells):
        comp_id: int = int(component_ids[u])
        if comp_id >= 0:
            counts[comp_id] += 1

    offsets: NDArray[np.int32] = np.zeros(n_cells + 1, dtype=np.int32)
    i: int
    for i in range(n_cells):
        offsets[i + 1] = offsets[i] + counts[i]
    total: int = int(offsets[n_cells])
    comp_members: NDArray[np.int32] = np.empty(total, dtype=np.int32)
    cursor: NDArray[np.int32] = offsets[:-1].copy()

    for u in range(n_cells):
        comp_id = int(component_ids[u])
        if comp_id >= 0:
            idx: int = int(cursor[comp_id])
            comp_members[idx] = u
            cursor[comp_id] += 1

    phi: NDArray[np.int32] = np.full(n_cells, _INF_I32, dtype=np.int32)
    heap_keys: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    heap_pos: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)

    comp_id = 0
    for comp_id in range(n_cells):
        comp_size: int = int(counts[comp_id])
        if comp_size == 0:
            continue
        start: int = int(offsets[comp_id])
        end: int = int(offsets[comp_id + 1])

        outlets: NDArray[np.int32] = np.empty(comp_size, dtype=np.int32)
        out_count: int = 0
        idx = start
        while idx < end:
            u = int(comp_members[idx])
            k = 0
            for k in range(8):
                v = int(nbr8_i32[u, k])
                if v < 0 or v >= n_cells:
                    continue
                if elev_q_i32[v] < elev_q_i32[u]:
                    outlets[out_count] = u
                    out_count += 1
                    break
            idx += 1

        if out_count == 0:
            sink: int = int(comp_members[start])
            min_hash: int = coord_hash_domain(seed, FLOW_DOMAIN, sink)
            idx = start + 1
            while idx < end:
                u = int(comp_members[idx])
                cand_hash: int = coord_hash_domain(seed, FLOW_DOMAIN, u)
                if cand_hash < min_hash:
                    min_hash = cand_hash
                    sink = u
                idx += 1
            flow_to[sink] = SINK
            outlets[0] = sink
            out_count = 1

        idx = start
        while idx < end:
            u = int(comp_members[idx])
            heap_pos[u] = -1
            phi[u] = _INF_I32
            idx += 1

        heap_nodes: NDArray[np.int32] = np.empty(comp_size, dtype=np.int32)
        size: int = 0
        i = 0
        while i < out_count:
            u = int(outlets[i])
            phi[u] = 0
            key: float = _heap_key(0, seed, u)
            size = heap_push(
                heap_nodes,
                heap_pos,
                heap_keys,
                size=size,
                node=u,
                key=key,
            )
            i += 1

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
                    key = _heap_key(candidate, seed, v)
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

        idx = start
        while idx < end:
            u = int(comp_members[idx])
            if flow_to[u] != UNRESOLVED:
                idx += 1
                continue
            best_v: int = -1
            best_phi: int = int(phi[u])
            k = 0
            for k in range(8):
                v = int(nbr8_i32[u, k])
                if v < 0 or v >= n_cells:
                    continue
                if component_ids[v] != comp_id:
                    continue
                if phi[v] < best_phi:
                    best_phi = int(phi[v])
                    best_v = v
                elif phi[v] == best_phi and best_v != -1:
                    if (
                        coord_hash_domain(seed, FLOW_DOMAIN, v)
                        < coord_hash_domain(seed, FLOW_DOMAIN, best_v)
                    ):
                        best_v = v
            if best_v != -1:
                flow_to[u] = best_v
            else:
                flow_to[u] = SINK
            idx += 1

    _break_flow_cycles_numba(flow_to, seed)
    return flow_to


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
    flow_to: NDArray[np.int32] = _build_flow_direction_numba(
        elev_q_i32,
        nbr8_i32,
        cell_area_f32,
        seed,
    )
    return flow_to


@njit(cache=True)
def _build_flow_accumulation_numba(
    flow_to_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
) -> Tuple[NDArray[np.float32], int]:
    n_cells: int = int(flow_to_i32.shape[0])
    in_deg: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    u: int
    for u in range(n_cells):
        v: int = int(flow_to_i32[u])
        if v == SINK:
            continue
        in_deg[v] += 1

    accum_f32: NDArray[np.float32] = cell_area_f32.astype(np.float32).copy()
    heap_nodes: NDArray[np.int32] = np.empty(n_cells, dtype=np.int32)
    heap_pos: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    heap_keys: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    size: int = 0

    for u in range(n_cells):
        if in_deg[u] == 0:
            key: float = float(u)
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
        v = int(flow_to_i32[u])
        if v != SINK:
            accum_f32[v] += accum_f32[u]
            in_deg[v] -= 1
            if in_deg[v] == 0:
                key = float(v)
                size = heap_push(
                    heap_nodes,
                    heap_pos,
                    heap_keys,
                    size=size,
                    node=v,
                    key=key,
                )

    remaining: int = int(np.sum(in_deg))
    return accum_f32, remaining


def build_flow_accumulation(
    flow_to_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
) -> NDArray[np.float32]:
    n_cells: int = int(flow_to_i32.shape[0])
    validate_array(flow_to_i32, "flow_to_i32", np.dtype("int32"), (n_cells,))
    validate_array(cell_area_f32, "cell_area_f32", np.dtype("float32"), (n_cells,))

    u: int
    for u in range(n_cells):
        v: int = int(flow_to_i32[u])
        if v == SINK:
            continue
        if v < 0 or v >= n_cells:
            msg: str = f"flow_to_i32[{u}] is out of range: {v}"
            raise ValueError(msg)

    accum_f32: NDArray[np.float32]
    remaining: int
    accum_f32, remaining = _build_flow_accumulation_numba(flow_to_i32, cell_area_f32)
    if remaining != 0:
        raise ValueError("flow_to_i32 contains a directed cycle after correction")
    return accum_f32


@njit(cache=True)
def _build_rivers_derived_fields_numba(
    accum_f32: NDArray[np.float32],
    flow_to_i32: NDArray[np.int32],
    cell_area_f32: NDArray[np.float32],
    min_catchment_cells: int,
    intensity_log_base: float,
) -> Tuple[NDArray[np.uint8], NDArray[np.float32], NDArray[np.uint8]]:
    n_cells: int = int(accum_f32.shape[0])
    cell_area_ref: float = float(np.median(cell_area_f32))
    threshold: float = cell_area_ref * float(min_catchment_cells)

    is_river_u8: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    river_intensity_f32: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    u: int
    for u in range(n_cells):
        if accum_f32[u] >= threshold:
            is_river_u8[u] = 1
            river_intensity_f32[u] = np.float32(
                np.log1p(accum_f32[u] / (cell_area_ref * intensity_log_base))
            )

    in_deg: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    for u in range(n_cells):
        if is_river_u8[u] == 0:
            continue
        v: int = int(flow_to_i32[u])
        if v != SINK and is_river_u8[v] == 1:
            in_deg[v] += 1

    max_up: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    cnt_max: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)
    order: NDArray[np.uint8] = np.zeros(n_cells, dtype=np.uint8)

    heap_nodes: NDArray[np.int32] = np.empty(n_cells, dtype=np.int32)
    heap_pos: NDArray[np.int32] = np.full(n_cells, -1, dtype=np.int32)
    heap_keys: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    size: int = 0

    for u in range(n_cells):
        if is_river_u8[u] == 1 and in_deg[u] == 0 and flow_to_i32[u] != SINK:
            key: float = float(u)
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
        if max_up[u] == 0:
            order[u] = 1
        elif cnt_max[u] >= 2:
            order[u] = np.uint8(int(max_up[u]) + 1)
        else:
            order[u] = max_up[u]

        v = int(flow_to_i32[u])
        if v != SINK and is_river_u8[v] == 1:
            if order[u] > max_up[v]:
                max_up[v] = order[u]
                cnt_max[v] = np.uint8(1)
            elif order[u] == max_up[v]:
                cnt_max[v] = np.uint8(int(cnt_max[v]) + 1)

            in_deg[v] -= 1
            if in_deg[v] == 0:
                key = float(v)
                size = heap_push(
                    heap_nodes,
                    heap_pos,
                    heap_keys,
                    size=size,
                    node=v,
                    key=key,
                )

    return is_river_u8, river_intensity_f32, order


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

    u: int
    for u in range(n_cells):
        v: int = int(flow_to_i32[u])
        if v == SINK:
            continue
        if v < 0 or v >= n_cells:
            msg: str = f"flow_to_i32[{u}] is out of range: {v}"
            raise ValueError(msg)

    return _build_rivers_derived_fields_numba(
        accum_f32,
        flow_to_i32,
        cell_area_f32,
        min_catchment_cells,
        intensity_log_base,
    )
