from __future__ import annotations

from typing import Any

import polars as pl

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from worldgen.overland.schema import OverlandBundle, OverlandMapMetadata


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
        metadata: dict[str, Any] | None = None
    else:
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

    # Build minimal sidecar from metadata (grids derived from bundle DFs in future)
    # For now, route_segments from starting contract; full grids stubbed.
    route_segments = metadata.get("starting_region_contract", {}).get(
        "route_segments", []
    )
    sidecar = OverlandMapMetadata(
        material_grid=None,
        biome_grid=None,
        hydro_grid=None,
        wetness_grid=None,
        route_segments=route_segments,
        evidence_tags=metadata.get("evidence_tags", {}),
        transitions={},
        affordances={},
        starting_contract=metadata.get("starting_region_contract", {}),
    )
    return game_map, sidecar
