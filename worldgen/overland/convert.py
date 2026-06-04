from __future__ import annotations

import polars as pl

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap


def overland_to_game_map(tiles_df: pl.DataFrame) -> GameMap:
    width = int(tiles_df.get_column("x").max()) + 1
    height = int(tiles_df.get_column("y").max()) + 1
    game_map = GameMap(width=width, height=height)
    for row in tiles_df.iter_rows(named=True):
        x = int(row["x"])
        y = int(row["y"])
        game_map.tiles[y, x] = TILE_ID_FLOOR if bool(row["walkable"]) else TILE_ID_WALL
    game_map.update_tile_transparency()
    return game_map
