from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl


def load_shaped_map_as_arrays(
    arrow_path: str,
    *,
    default_material_id: int = 0,
    default_height: float = 0.0,
    default_floor_depth: float = 0.0,
    default_chamber_id: int = -1,
) -> dict[str, Any]:
    """Load a shaped map IPC file into numpy grids."""
    df = pl.read_ipc(arrow_path)

    required = {"x", "y", "material_id"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in shaped map: {sorted(missing)}")

    x = np.rint(df.get_column("x").to_numpy()).astype(np.int32)
    y = np.rint(df.get_column("y").to_numpy()).astype(np.int32)

    min_x, max_x = int(x.min()), int(x.max())
    min_y, max_y = int(y.min()), int(y.max())
    width = max_x - min_x + 1
    height = max_y - min_y + 1

    gx = x - min_x
    gy = y - min_y

    tile_id_grid = np.full(
        (height, width),
        default_material_id,
        dtype=np.uint16,
        order="C",
    )
    tile_id_grid[gy, gx] = df.get_column("material_id").to_numpy().astype(np.uint16)

    out: dict[str, Any] = {
        "tile_id_grid": tile_id_grid,
        "origin": (min_x, min_y),
        "shape": (height, width),
    }

    if "height" in df.columns:
        height_grid = np.full(
            (height, width),
            default_height,
            dtype=np.float32,
            order="C",
        )
        height_grid[gy, gx] = df.get_column("height").to_numpy().astype(np.float32)
        out["height_grid"] = height_grid

    if "floor_depth" in df.columns:
        floor_depth_grid = np.full(
            (height, width),
            default_floor_depth,
            dtype=np.float32,
            order="C",
        )
        floor_depth_grid[gy, gx] = (
            df.get_column("floor_depth").to_numpy().astype(np.float32)
        )
        out["floor_depth_grid"] = floor_depth_grid

    if "chamber_id" in df.columns:
        chamber_id_grid = np.full(
            (height, width),
            default_chamber_id,
            dtype=np.int32,
            order="C",
        )
        chamber_id_grid[gy, gx] = df.get_column("chamber_id").to_numpy().astype(np.int32)
        out["chamber_id_grid"] = chamber_id_grid

    return out
