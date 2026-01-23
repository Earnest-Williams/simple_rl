from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import numpy as np
import orjson
from numpy.typing import NDArray

from simple_rl.worldgen.config import ELEV_Q_M


def compute_quantiles(
    arr: NDArray[np.floating[np.generic]],  # float32[n_cells]
    percentiles: List[int],
) -> Dict[str, float]:
    if arr.size == 0:
        raise ValueError("arr must be non-empty")
    p: int
    for p in percentiles:
        if p < 0 or p > 100:
            raise ValueError("percentiles must be between 0 and 100")
    sorted_arr: NDArray[np.floating[np.generic]] = np.sort(arr)
    n: int = int(sorted_arr.shape[0])
    result: Dict[str, float] = {}
    p = 0
    for p in percentiles:
        idx: int = int(p * n / 100)
        if idx >= n:
            idx = n - 1
        result[f"p{p}"] = float(sorted_arr[idx])
    return result


def compute_seam_continuity(
    layer: NDArray[np.floating[np.generic]],  # float32[n_cells]
    nbr4: NDArray[np.int32],  # int32[n_cells, 4]
    seam_pairs: List[Tuple[int, int]],
    sample_size: int,
) -> float:
    if sample_size <= 0:
        raise ValueError("sample_size must be > 0")
    n_cells: int = int(layer.shape[0])
    if n_cells == 0:
        return 1.0
    if nbr4.shape[0] != n_cells:
        raise ValueError("nbr4 must have the same length as layer")

    seam_set: Set[Tuple[int, int]] = set(seam_pairs)
    u: int
    v: int
    for u, v in seam_pairs:
        seam_set.add((v, u))

    non_seam_total: float = 0.0
    non_seam_count: int = 0
    u = 0
    for u in range(n_cells):
        if non_seam_count >= sample_size:
            break
        k: int
        for k in range(4):
            v: int = int(nbr4[u, k])
            if v < 0 or v >= n_cells:
                continue
            if (u, v) in seam_set:
                continue
            non_seam_total += abs(float(layer[u] - layer[v]))
            non_seam_count += 1
            break

    seam_total: float = 0.0
    seam_count: int = 0
    u = 0
    v = 0
    for u, v in seam_pairs[:sample_size]:
        if u < 0 or v < 0:
            continue
        if u >= n_cells or v >= n_cells:
            continue
        seam_total += abs(float(layer[u] - layer[v]))
        seam_count += 1

    if seam_count == 0 or non_seam_count == 0:
        return 1.0

    return (seam_total / seam_count) / (non_seam_total / non_seam_count)


def generate_report(
    out_dir: Path,
    *,
    elev_q_i32: NDArray[np.int32],  # int32[n_cells]
    temp_f32: NDArray[np.float32],  # float32[n_cells]
    precip_f32: NDArray[np.float32],  # float32[n_cells]
    is_river_u8: NDArray[np.uint8],  # uint8[n_cells]
    stream_order_u8: NDArray[np.uint8],  # uint8[n_cells]
    nbr4: NDArray[np.int32],  # int32[n_cells, 4]
    sea_level_q: int,
    seam_pairs: List[Tuple[int, int]],
    sample_size: int = 10000,
) -> Dict[str, Any]:
    if not out_dir.exists():
        raise FileNotFoundError("out_dir must exist before writing report.json")
    if elev_q_i32.shape[0] == 0:
        raise ValueError("elev_q_i32 must be non-empty")

    land_mask: NDArray[np.bool_] = elev_q_i32 >= sea_level_q
    land_fraction: float = float(np.mean(land_mask))

    temp_quantiles: Dict[str, float] = compute_quantiles(
        temp_f32, [5, 25, 50, 75, 95]
    )
    precip_quantiles: Dict[str, float] = compute_quantiles(
        precip_f32, [5, 25, 50, 75, 95]
    )

    total_river_cells: int = int(np.sum(is_river_u8))
    max_order: int = int(np.max(stream_order_u8)) if stream_order_u8.size else 0
    order_hist: List[int] = []
    o: int
    for o in range(1, max_order + 1):
        order_hist.append(int(np.sum(stream_order_u8 == o)))

    elev_seam_ratio: float = compute_seam_continuity(
        elev_q_i32.astype(np.float32) * ELEV_Q_M,
        nbr4,
        seam_pairs,
        sample_size,
    )
    temp_seam_ratio: float = compute_seam_continuity(
        temp_f32,
        nbr4,
        seam_pairs,
        sample_size,
    )
    precip_seam_ratio: float = compute_seam_continuity(
        precip_f32,
        nbr4,
        seam_pairs,
        sample_size,
    )

    report: Dict[str, Any] = {
        "land_fraction": land_fraction,
        "temp_quantiles": temp_quantiles,
        "precip_quantiles": precip_quantiles,
        "river_stats": {
            "total_river_cells": total_river_cells,
            "order_histogram": order_hist,
        },
        "seam_continuity": {
            "elev_seam_vs_nonseam_ratio": elev_seam_ratio,
            "temp_seam_vs_nonseam_ratio": temp_seam_ratio,
            "precip_seam_vs_nonseam_ratio": precip_seam_ratio,
        },
    }

    tmp: Path = out_dir / "report.json.tmp"
    with tmp.open("wb") as handle:
        handle.write(orjson.dumps(report, option=orjson.OPT_INDENT_2))
    os.replace(tmp, out_dir / "report.json")

    return report
