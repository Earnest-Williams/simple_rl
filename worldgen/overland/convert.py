from __future__ import annotations

from typing import Any

import numpy as np
import polars as pl

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from worldgen.overland.schema import OverlandBundle, OverlandMapMetadata
from worldgen.overland.transitions import (
    generate_transition_requests,
    transition_requests_to_df,
)


def overland_to_game_map(
    bundle: OverlandBundle | pl.DataFrame, *, with_metadata: bool = False
) -> GameMap | tuple[GameMap, OverlandMapMetadata]:
    """Convert overland tiles (or full bundle) to runtime GameMap.

    Backward-compatible with existing tile-only calls. When with_metadata=True
    and a bundle is passed, returns (GameMap, OverlandMapMetadata) sidecar
    carrying richer route states, evidence, repair costs, etc. for runtime
    simulation (repair, survey, etc.).
    """
    if isinstance(bundle, pl.DataFrame):
        tiles_df = bundle
        overland_bundle: OverlandBundle | None = None
        metadata: dict[str, Any] | None = None
    else:
        overland_bundle = bundle
        tiles_df = bundle.tiles_df
        metadata = bundle.metadata

    width = int(tiles_df.get_column("x").max()) + 1
    height = int(tiles_df.get_column("y").max()) + 1
    game_map = GameMap(width=width, height=height)
    for row in tiles_df.iter_rows(named=True):
        x = int(row["x"])
        y = int(row["y"])
        game_map.tiles[y, x] = TILE_ID_FLOOR if bool(row["walkable"]) else TILE_ID_WALL
    game_map.update_tile_transparency()

    if not with_metadata or metadata is None:
        return game_map

    route_segments = metadata.get("starting_region_contract", {}).get(
        "route_segments", []
    )
    sidecar = OverlandMapMetadata(
        material_grid=_grid_from_column(tiles_df, "material", width, height, np.int16),
        biome_grid=_grid_from_column(tiles_df, "biome", width, height, np.int16),
        hydro_grid=_grid_from_column(tiles_df, "hydro_role", width, height, np.int16),
        wetness_grid=_grid_from_column(tiles_df, "wetness", width, height, np.int16),
        movement_cost_grid=_grid_from_column(
            tiles_df,
            "movement_cost",
            width,
            height,
            np.float32,
            default=np.inf,
        ),
        traversal_class_grid=_grid_from_column(
            tiles_df,
            "traversal_class",
            width,
            height,
            np.int16,
        ),
        route_segments=route_segments,
        evidence_tags=metadata.get("evidence_tags", {}),
        transitions=_transition_lookup(overland_bundle),
        affordances=_affordance_lookup(overland_bundle.affordances_df),
        starting_contract=metadata.get("starting_region_contract", {}),
    )
    game_map.overland_metadata = sidecar
    return game_map, sidecar


def _grid_from_column(
    tiles_df: pl.DataFrame,
    column: str,
    width: int,
    height: int,
    dtype: Any,
    *,
    default: int | float = 0,
) -> np.ndarray:
    grid = np.full((height, width), default, dtype=dtype)
    for row in tiles_df.select("x", "y", column).iter_rows(named=True):
        grid[int(row["y"]), int(row["x"])] = row[column]
    return grid


def _transition_lookup(
    bundle: OverlandBundle | None,
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    if bundle is None:
        return {}
    transitions_df = transition_requests_to_df(generate_transition_requests(bundle))
    return _rows_by_coord(transitions_df, x_column="source_x", y_column="source_y")


def _affordance_lookup(
    affordances_df: pl.DataFrame,
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    return _rows_by_coord(affordances_df, x_column="x", y_column="y")


def _rows_by_coord(
    df: pl.DataFrame,
    *,
    x_column: str,
    y_column: str,
) -> dict[tuple[int, int], list[dict[str, Any]]]:
    lookup: dict[tuple[int, int], list[dict[str, Any]]] = {}
    if df.is_empty():
        return lookup
    for row in df.iter_rows(named=True):
        payload = dict(row)
        x = int(payload.pop(x_column))
        y = int(payload.pop(y_column))
        lookup.setdefault((x, y), []).append(payload)
    return lookup
