from __future__ import annotations

from typing import Any, Mapping

import numpy as np
import polars as pl

from common.constants import Material
from game.world.game_map import GameMap, TILE_ID_FLOOR, TILE_ID_WALL


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


def shaped_dataframe_to_game_map(
    df: pl.DataFrame,
    *,
    material_to_tile: Mapping[int, int] | None = None,
    default_tile_id: int = TILE_ID_WALL,
    default_height: int = 0,
    default_ceiling: int = 0,
    default_floor_depth: float = 0.0,
) -> tuple[GameMap, tuple[int, int]]:
    """Convert a shaped Polars DataFrame into a GameMap and origin offset."""
    if df.is_empty():
        raise ValueError("Shaped map DataFrame is empty.")

    required = {"x", "y"}
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
        default_tile_id,
        dtype=np.uint8,
        order="C",
    )

    tile_overrides = (
        dict(material_to_tile)
        if material_to_tile is not None
        else {
            int(Material.SOLID_ROCK): TILE_ID_WALL,
            int(Material.CAVE_FLOOR): TILE_ID_FLOOR,
            int(Material.SHAFT_OPENING): TILE_ID_FLOOR,
            int(Material.CLIFF_EDGE): TILE_ID_WALL,
            int(Material.DOOR_CLOSED): TILE_ID_WALL,
            int(Material.DOOR_OPEN): TILE_ID_FLOOR,
        }
    )

    if "walkable" in df.columns:
        walkable = df.get_column("walkable").to_numpy().astype(bool)
        tile_id_grid[gy, gx] = np.where(walkable, TILE_ID_FLOOR, TILE_ID_WALL)
    elif "material_id" in df.columns:
        material_ids = df.get_column("material_id").to_numpy().astype(np.int32)
        mapped_tiles = np.full(material_ids.shape, default_tile_id, dtype=np.uint8)
        for material_id, tile_id in tile_overrides.items():
            mapped_tiles[material_ids == material_id] = tile_id
        tile_id_grid[gy, gx] = mapped_tiles
    else:
        tile_id_grid[gy, gx] = TILE_ID_FLOOR

    game_map = GameMap(width=width, height=height)
    game_map.tiles[:, :] = tile_id_grid

    if "height" in df.columns:
        height_vals = df.get_column("height").to_numpy()
        height_vals = np.nan_to_num(height_vals, nan=default_height)
        height_grid = np.full(
            (height, width), default_height, dtype=np.int16, order="C"
        )
        height_grid[gy, gx] = np.rint(height_vals).astype(np.int16)
        game_map.height_map = height_grid

    ceiling_grid = np.full((height, width), default_ceiling, dtype=np.int16, order="C")
    if "ceiling_depth" in df.columns:
        ceiling_vals = df.get_column("ceiling_depth").to_numpy()
        ceiling_vals = np.nan_to_num(ceiling_vals, nan=default_ceiling)
        ceiling_grid[gy, gx] = np.rint(ceiling_vals).astype(np.int16)
    elif "floor_depth" in df.columns and "height" in df.columns:
        floor_vals = df.get_column("floor_depth").to_numpy()
        height_vals = df.get_column("height").to_numpy()
        ceiling_vals = floor_vals - height_vals
        ceiling_vals = np.nan_to_num(ceiling_vals, nan=default_ceiling)
        ceiling_grid[gy, gx] = np.rint(ceiling_vals).astype(np.int16)
    game_map.ceiling_map = ceiling_grid

    if "height" not in df.columns and "floor_depth" in df.columns:
        depth_vals = df.get_column("floor_depth").to_numpy()
        depth_vals = np.nan_to_num(depth_vals, nan=default_floor_depth)
        depth_grid = np.full(
            (height, width), default_height, dtype=np.int16, order="C"
        )
        depth_grid[gy, gx] = np.rint(depth_vals).astype(np.int16)
        game_map.height_map = depth_grid

    game_map.update_tile_transparency()
    return game_map, (min_x, min_y)


def load_shaped_map_as_gamemap(
    arrow_path: str,
    *,
    material_to_tile: Mapping[int, int] | None = None,
    default_tile_id: int = TILE_ID_WALL,
    default_height: int = 0,
    default_ceiling: int = 0,
    default_floor_depth: float = 0.0,
) -> tuple[GameMap, tuple[int, int]]:
    """Load a shaped map IPC file into a GameMap and origin offset."""
    df = pl.read_ipc(arrow_path)
    return shaped_dataframe_to_game_map(
        df,
        material_to_tile=material_to_tile,
        default_tile_id=default_tile_id,
        default_height=default_height,
        default_ceiling=default_ceiling,
        default_floor_depth=default_floor_depth,
    )
