from __future__ import annotations

import logging
from collections import deque

import numba
import numpy as np

from lights_dev import constants
from lights_dev import demo_dungeon_generator as dungeon_generator
from lights_dev.dungeon_data import Dungeon
from lights_dev.entities import Entity, LightSource, Player
from lights_dev.fov import FOVSystem
from lights_dev.lighting import LightingSystem, _get_brightness_from_rgb_sum
from lights_dev.memory import update_memory_fade
from utils.game_rng import GameRNG


@numba.jit(nopython=True)
def _update_dungeon_time(dungeon_instance: Dungeon, dt: np.float32) -> None:
    dungeon_instance.current_time += dt


def find_path(
    start: tuple[int, int],
    end: tuple[int, int],
    tiles: np.ndarray,
    width: int,
    height: int,
) -> list[tuple[int, int]] | None:
    if not (
        0 <= start[0] < width
        and 0 <= start[1] < height
        and 0 <= end[0] < width
        and 0 <= end[1] < height
    ):
        return None
    if (
        tiles[start[1], start[0]] != constants.FLOOR_ID
        or tiles[end[1], end[0]] != constants.FLOOR_ID
    ):
        return None
    if start == end:
        return [start]
    q = deque([(start, [start])])
    visited: set[tuple[int, int]] = {start}
    while q:
        (vx, vy), path = q.popleft()
        for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
            nx, ny = vx + dx, vy + dy
            if (
                0 <= nx < width
                and 0 <= ny < height
                and tiles[ny, nx] == constants.FLOOR_ID
                and (nx, ny) not in visited
            ):
                new_path = list(path)
                new_path.append((nx, ny))
                if (nx, ny) == end:
                    return new_path
                visited.add((nx, ny))
                q.append(((nx, ny), new_path))
    return None


def get_object_size_category(
    dungeon: Dungeon, x: int, y: int, entities: list[Entity]
) -> str:
    for entity in entities:
        if entity.x == x and entity.y == y:
            return entity.size_category
    if 0 <= x < dungeon.width and 0 <= y < dungeon.height:
        return constants.TILE_ID_TO_CATEGORY.get(
            dungeon.tiles[y, x], constants.DEFAULT_ENTITY_CATEGORY
        )
    return "wall"


def distance_sq(x1: int, y1: int, x2: int, y2: int) -> int:
    return (x1 - x2) ** 2 + (y1 - y2) ** 2


class GameState:
    def __init__(self, width: int, height: int, rng: GameRNG):
        self.rng = rng
        self.dungeon = Dungeon(width, height)
        self.player: Player | None = None
        self.light_sources: list[LightSource] = []
        self.all_entities: list[Entity] = []
        self.current_illumination_rgb_sum: np.ndarray = np.zeros(
            (height, width, 3), dtype=np.float32
        )
        self.current_player_los: np.ndarray = np.zeros((height, width), dtype=np.bool_)

    def initialize_map_and_entities(self) -> None:
        dungeon_generator.dungeon_generate_map_u_shape(self.dungeon, self.rng)
        player_x = self.dungeon.width // 2
        player_y = 5
        search_attempts = 0
        while self.dungeon.tiles[player_y, player_x] != constants.FLOOR_ID:
            player_y += 1
            search_attempts += 1
            if (
                player_y >= self.dungeon.height - 1
                or search_attempts > self.dungeon.height
            ):
                player_x = 5
                player_y = 5
                search_attempts = 0
                while self.dungeon.tiles[player_y, player_x] != constants.FLOOR_ID:
                    player_x += 1
                    search_attempts += 1
                    if (
                        player_x >= self.dungeon.width - 1
                        or search_attempts > self.dungeon.width * 2
                    ):
                        logging.error("Player start failed!")
                        player_x = self.dungeon.width // 2
                        player_y = 5
                        break
                break
        self.player = Player(player_x, player_y, light_radius=10, light_level=3)

        light_radius = 16
        light_level = 5
        light1_x, light1_y = 10, self.dungeon.height // 2
        light2_x, light2_y = self.dungeon.width - 11, self.dungeon.height // 2
        if self.dungeon.tiles[light1_y, light1_x] != constants.FLOOR_ID:
            light1_x += 1
        if self.dungeon.tiles[light2_y, light2_x] != constants.FLOOR_ID:
            light2_x -= 1
        if self.dungeon.tiles[light1_y, light1_x] != constants.FLOOR_ID:
            light1_x, light1_y = 11, self.dungeon.height // 2 + 1
        if self.dungeon.tiles[light2_y, light2_x] != constants.FLOOR_ID:
            light2_x, light2_y = self.dungeon.width - 12, self.dungeon.height // 2 + 1

        self.light_sources = [
            LightSource(
                light1_x,
                light1_y,
                self.rng,
                light_radius,
                light_level,
                flicker=False,
                base_color_rgb=constants.ORB_COLOR_RGB,
            ),
            LightSource(
                light2_x,
                light2_y,
                self.rng,
                light_radius,
                light_level,
                flicker=True,
                base_color_rgb=(255, 100, 100),
            ),
        ]

        self.all_entities = ([self.player] if self.player else []) + self.light_sources
        self.generate_player_path()

    def generate_player_path(self) -> None:
        if not self.player:
            return
        self.player.set_path([(self.player.x, self.player.y)])

    def update(self, dt: float) -> None:
        if not self.dungeon:
            return
        _update_dungeon_time(self.dungeon, np.float32(dt))
        update_memory_fade(
            self.dungeon.current_time,
            self.dungeon.last_seen_time,
            self.dungeon.memory_intensity,
            self.dungeon.visible,
        )
        for light in self.light_sources:
            light.update()
        self.all_entities = ([self.player] if self.player else []) + self.light_sources

    def update_visibility(self) -> None:
        if not self.player or not self.dungeon:
            if self.dungeon:
                self.dungeon.visible.fill(False)
            self.current_illumination_rgb_sum.fill(0.0)
            self.current_player_los.fill(False)
            return
        d = self.dungeon
        px, py = self.player.position
        self.current_player_los = FOVSystem.compute_fov(
            d, self.player.position, constants.MAX_LOS_DISTANCE
        )
        LightingSystem.compute_illumination(
            d,
            ([self.player] if self.player else []) + self.light_sources,
            self.current_illumination_rgb_sum,
        )
        final_visible = np.zeros_like(self.current_player_los)
        max_vis_check_level = constants.MAX_LIGHT_LEVEL_FOR_VIS_CHECK
        min_brightness_for_vis = 1.0 / (max_vis_check_level * 2.5)
        for y in range(d.height):
            for x in range(d.width):
                if self.current_player_los[y, x]:
                    rgb_sum = self.current_illumination_rgb_sum[y, x]
                    brightness = _get_brightness_from_rgb_sum(rgb_sum)
                    if brightness >= min_brightness_for_vis:
                        approx_level = min(
                            max_vis_check_level,
                            max(1, int(brightness * max_vis_check_level + 0.5)),
                        )
                        obj_category = get_object_size_category(
                            d, x, y, self.all_entities
                        )
                        level_str = str(approx_level)
                        required_range = 0
                        try:
                            level_info = constants.LIGHT_LEVEL_DATA.get(level_str)
                            if level_info:
                                category_info = level_info.get(obj_category)
                            if category_info:
                                required_range = category_info.get(
                                    "noticeable_range", 0
                                )
                        except Exception as exc:
                            logging.error(f"Light lookup error: {exc}")
                            required_range = 0
                        dist_sq_to_player = distance_sq(px, py, x, y)
                        if dist_sq_to_player <= required_range * required_range:
                            final_visible[y, x] = True
        d.visible = final_visible
        current_sim_time = d.current_time
        d.last_seen_time[final_visible] = current_sim_time
        d.memory_intensity[final_visible] = 1.0
