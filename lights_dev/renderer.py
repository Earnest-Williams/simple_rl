from __future__ import annotations

import numpy as np

from lights_dev import constants
from lights_dev.entities import LightSource
from lights_dev.game_state import GameState
from lights_dev.lighting import LightingSystem, _get_brightness_from_rgb_sum
from lights_dev.memory import get_memory_character


def _format_true_color(rgb: tuple[int, int, int]) -> str:
    return f"\033[38;2;{rgb[0]};{rgb[1]};{rgb[2]}m"


def _get_base_rgb_for_tile(tile_id: int) -> tuple[int, int, int]:
    if tile_id == constants.WALL_ID:
        return constants.WALL_COLOR_RGB
    if tile_id == constants.PILLAR_ID:
        return constants.PILLAR_COLOR_RGB
    return constants.FLOOR_COLOR_RGB


def _compute_faded_memory_rgb(
    base_rgb: tuple[int, int, int], memory_intensity: float
) -> tuple[int, int, int]:
    factor = max(0.0, min(1.0, memory_intensity))
    amb = constants.AMBIENT_COLOR_RGB
    r_val = int(amb[0] + (base_rgb[0] - amb[0]) * factor)
    g_val = int(amb[1] + (base_rgb[1] - amb[1]) * factor)
    b_val = int(amb[2] + (base_rgb[2] - amb[2]) * factor)
    return (
        max(0, min(255, r_val)),
        max(0, min(255, g_val)),
        max(0, min(255, b_val)),
    )


class Renderer:
    def __init__(self, render_mode: str) -> None:
        self.render_mode = render_mode

    def set_renderer_mode(self, mode: str) -> None:
        self.render_mode = mode

    def render(self, game_state: GameState) -> str:
        if not game_state.dungeon:
            return "Error: Dungeon not initialized."
        d = game_state.dungeon
        rgb_sum_array = game_state.current_illumination_rgb_sum
        player_pos = game_state.player.position if game_state.player else (-1, -1)

        if self.render_mode == "level":
            result = ["--- Est. Brightness (0.0-1.0+, from RGB Sum) ---"]
            for y in range(d.height):
                row = [
                    (
                        f"{_get_brightness_from_rgb_sum(rgb_sum_array[y, x]):.2f}"
                        if np.any(rgb_sum_array[y, x] > 0.0)
                        else " .  "
                    )
                    for x in range(d.width)
                ]
                result.append(" ".join(row))
            return "\n".join(result) + "\n"

        if self.render_mode == "intensity":
            result = ["--- Memory Intensity (DEBUG) ---"]
            for y in range(d.height):
                row = [
                    (
                        f"{d.memory_intensity[y, x]:.1f}"
                        if d.memory_intensity[y, x] > 0.01
                        else " . "
                    )
                    for x in range(d.width)
                ]
                result.append(" ".join(row))
            return "\n".join(result) + "\n"

        if self.render_mode == "level_color":
            result = ["--- Blended RGB True Color (DEBUG, Clamped Sum) ---"]
            for y in range(d.height):
                row_chars: list[str] = []
                for x in range(d.width):
                    rgb_sum = rgb_sum_array[y, x]
                    brightness = _get_brightness_from_rgb_sum(rgb_sum)
                    if brightness > 0.001:
                        r_val = int(max(0, min(255, rgb_sum[0])))
                        g_val = int(max(0, min(255, rgb_sum[1])))
                        b_val = int(max(0, min(255, rgb_sum[2])))
                        final_rgb = (r_val, g_val, b_val)
                        color_code = _format_true_color(final_rgb)
                        tile_id = d.tiles[y, x]
                        char = (
                            constants.VISIBLE_WALL
                            if tile_id == constants.WALL_ID
                            else (
                                constants.VISIBLE_PILLAR
                                if tile_id == constants.PILLAR_ID
                                else constants.VISIBLE_FLOOR
                            )
                        )
                        row_chars.append(
                            f"{color_code}{char}{constants.COLOR['RESET']}"
                        )
                    else:
                        memory_intensity = d.memory_intensity[y, x]
                        if memory_intensity > 0.0:
                            tile_id = d.tiles[y, x]
                            base_rgb = _get_base_rgb_for_tile(tile_id)
                            final_rgb = _compute_faded_memory_rgb(
                                base_rgb, memory_intensity
                            )
                            color_code = _format_true_color(final_rgb)
                            char = get_memory_character(tile_id, memory_intensity)
                            row_chars.append(
                                f"{color_code}{char}{constants.COLOR['RESET']}"
                            )
                        else:
                            row_chars.append(constants.UNSEEN)
                result.append("".join(row_chars))
            return "\n".join(result) + "\n"

        result: list[str] = []
        for y in range(d.height):
            row_chars: list[str] = []
            for x in range(d.width):
                is_visible = d.visible[y, x]
                memory_intensity = d.memory_intensity[y, x]
                tile_id = d.tiles[y, x]
                char = constants.UNSEEN
                final_color_code = ""
                is_player_tile = x == player_pos[0] and y == player_pos[1]
                light_source_at_tile: LightSource | None = None
                if not is_player_tile:
                    for light in game_state.light_sources:
                        if light.x == x and light.y == y:
                            light_source_at_tile = light
                            break
                if is_visible:
                    rgb_sum = rgb_sum_array[y, x]
                    brightness = _get_brightness_from_rgb_sum(rgb_sum)
                    base_rgb = constants.FLOOR_COLOR_RGB
                    if is_player_tile:
                        char = constants.PLAYER_CHAR
                        base_rgb = constants.PLAYER_COLOR_RGB
                    elif light_source_at_tile is not None:
                        char = constants.LIGHT_CHAR
                        base_rgb = light_source_at_tile.base_color_rgb
                    else:
                        if tile_id == constants.WALL_ID:
                            char = constants.VISIBLE_WALL
                            base_rgb = constants.WALL_COLOR_RGB
                        elif tile_id == constants.PILLAR_ID:
                            char = constants.VISIBLE_PILLAR
                            base_rgb = constants.PILLAR_COLOR_RGB
                        else:
                            char = constants.VISIBLE_FLOOR
                            base_rgb = constants.FLOOR_COLOR_RGB
                    if brightness > 0.001:
                        final_rgb = LightingSystem.apply_lighting(
                            base_rgb, rgb_sum, brightness
                        )
                        final_color_code = _format_true_color(final_rgb)
                    else:
                        final_color_code = _format_true_color(constants.AMBIENT_COLOR_RGB)
                elif memory_intensity > 0.0:
                    if is_player_tile:
                        base_rgb = constants.PLAYER_COLOR_RGB
                    elif light_source_at_tile is not None:
                        base_rgb = light_source_at_tile.base_color_rgb
                    else:
                        base_rgb = _get_base_rgb_for_tile(tile_id)
                    final_rgb = _compute_faded_memory_rgb(base_rgb, memory_intensity)
                    final_color_code = _format_true_color(final_rgb)
                    if is_player_tile:
                        char = get_memory_character(constants.FLOOR_ID, memory_intensity)
                    elif light_source_at_tile is not None:
                        char = (
                            constants.MEMORY_LIGHT
                            if memory_intensity > 0.3
                            else get_memory_character(constants.FLOOR_ID, memory_intensity)
                        )
                    else:
                        char = get_memory_character(tile_id, memory_intensity)
                final_char = char if char != " " else constants.UNSEEN
                if final_color_code:
                    row_chars.append(
                        f"{final_color_code}{final_char}{constants.COLOR['RESET']}"
                    )
                else:
                    row_chars.append(final_char)
            result.append("".join(row_chars))
        return "\n".join(result)
