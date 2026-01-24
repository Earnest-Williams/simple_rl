from game.world.game_map import GameMap, TILE_ID_FLOOR, TILE_ID_WALL
from tools.play_from_arrow import _compute_component_sizes, _select_spawn_position


def _make_map(width: int, height: int, floor_tiles: list[tuple[int, int]]) -> GameMap:
    game_map = GameMap(width, height)
    game_map.tiles[:, :] = TILE_ID_WALL
    for x, y in floor_tiles:
        game_map.tiles[y, x] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    return game_map


def test_spawn_suitable_tile_selected() -> None:
    floor_tiles = [(x, y) for y in range(3) for x in range(3)]
    game_map = _make_map(3, 3, floor_tiles)
    component_sizes = _compute_component_sizes(game_map)

    spawn_x, spawn_y = _select_spawn_position(
        game_map,
        component_sizes,
        1,
        1,
        min_room_size=5,
        search_radius=5,
        require_diagonals=True,
    )

    assert (spawn_x, spawn_y) == (1, 1)


def test_spawn_nearby_suitable_tile_found() -> None:
    floor_tiles = [(x, y) for y in range(2, 5) for x in range(2, 5)]
    game_map = _make_map(7, 7, floor_tiles)
    component_sizes = _compute_component_sizes(game_map)

    spawn_x, spawn_y = _select_spawn_position(
        game_map,
        component_sizes,
        0,
        0,
        min_room_size=5,
        search_radius=10,
        require_diagonals=True,
    )

    assert (spawn_x, spawn_y) == (3, 3)


def test_spawn_relaxed_diagonals() -> None:
    floor_tiles = [(2, 1), (2, 2), (2, 3), (1, 2), (3, 2)]
    game_map = _make_map(5, 5, floor_tiles)
    component_sizes = _compute_component_sizes(game_map)

    spawn_x, spawn_y = _select_spawn_position(
        game_map,
        component_sizes,
        2,
        2,
        min_room_size=5,
        search_radius=5,
        require_diagonals=True,
    )

    assert (spawn_x, spawn_y) == (2, 2)


def test_spawn_falls_back_to_any_floor() -> None:
    game_map = _make_map(5, 5, [(2, 2)])
    component_sizes = _compute_component_sizes(game_map)

    spawn_x, spawn_y = _select_spawn_position(
        game_map,
        component_sizes,
        0,
        0,
        min_room_size=5,
        search_radius=5,
        require_diagonals=True,
    )

    assert (spawn_x, spawn_y) == (2, 2)


def test_spawn_falls_back_to_default_when_no_floor() -> None:
    game_map = _make_map(3, 3, [])
    component_sizes = _compute_component_sizes(game_map)

    spawn_x, spawn_y = _select_spawn_position(
        game_map,
        component_sizes,
        0,
        0,
        min_room_size=5,
        search_radius=5,
        require_diagonals=True,
    )

    assert (spawn_x, spawn_y) == (1, 1)
