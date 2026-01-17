import polars as pl

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL
from utils.shaped_map import shaped_dataframe_to_game_map


def test_shaped_dataframe_to_game_map_walkable_override():
    df = pl.DataFrame(
        {
            "x": [0.0, 1.0, 0.0],
            "y": [0.0, 0.0, 1.0],
            "material_id": [1, 3, 1],
            "walkable": [True, False, True],
            "floor_depth": [2.0, 6.0, 4.0],
            "height": [1.0, 2.0, 3.0],
            "ceiling_depth": [1.0, 4.0, 1.0],
        }
    )

    game_map, origin = shaped_dataframe_to_game_map(df)

    assert origin == (0, 0)
    assert game_map.width == 2
    assert game_map.height == 2
    assert game_map.tiles[0, 0] == TILE_ID_FLOOR
    assert game_map.tiles[0, 1] == TILE_ID_WALL
    assert game_map.tiles[1, 0] == TILE_ID_FLOOR
    assert game_map.tiles[1, 1] == TILE_ID_WALL
    assert game_map.height_map[0, 0] == 2
    assert game_map.height_map[0, 1] == 6
    assert game_map.height_map[1, 0] == 4
    assert game_map.height_map[1, 1] == 0
    assert game_map.ceiling_map[0, 0] == 3
    assert game_map.ceiling_map[0, 1] == 8
    assert game_map.ceiling_map[1, 0] == 7
    assert game_map.ceiling_map[1, 1] == 0


def test_shaped_dataframe_to_game_map_material_mapping():
    df = pl.DataFrame(
        {
            "x": [5.0, 6.0],
            "y": [10.0, 10.0],
            "material_id": [1, 0],
        }
    )

    game_map, origin = shaped_dataframe_to_game_map(df)

    assert origin == (5, 10)
    assert game_map.tiles[0, 0] == TILE_ID_FLOOR
    assert game_map.tiles[0, 1] == TILE_ID_WALL
