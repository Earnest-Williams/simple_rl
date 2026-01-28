from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Iterator, TypedDict

import numpy as np
from numpy.typing import NDArray

from lights_dev import constants
from lights_dev.dungeon_data import Dungeon
from lights_dev.entities import Entity, LightSource, Player
from lights_dev.game_state import GameState
from lights_dev.runner import GameRunner


class LeakInfo(TypedDict):
    source: Tuple[int, int]
    target: Tuple[int, int]
    first_block: Tuple[int, int]
    rgb: Tuple[float, float, float]


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> Iterator[Tuple[int, int]]:
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    x, y = x0, y0
    if dy <= dx:
        err = dx // 2
        while True:
            x += sx
            err -= dy
            if err < 0:
                y += sy
                err += dx
            if x == x1 and y == y1:
                break
            yield x, y
    else:
        err = dy // 2
        while True:
            y += sy
            err -= dx
            if err < 0:
                x += sx
                err += dy
            if x == x1 and y == y1:
                break
            yield x, y


def find_leaks(
    dungeon: Dungeon,
    sources: List[Entity],
    rgb_sum: NDArray[np.float32],
) -> List[LeakInfo]:
    leaks: List[LeakInfo] = []
    for source in sources:
        lx, ly = source.position
        for y in range(dungeon.height):
            for x in range(dungeon.width):
                if np.any(rgb_sum[y, x] > 0.0):
                    blocked_mid = None
                    for bx, by in bresenham_line(lx, ly, x, y):
                        if dungeon.blocks_light(bx, by):
                            blocked_mid = (bx, by)
                            break
                    if blocked_mid is not None:
                        leak_rgb = tuple(float(v) for v in rgb_sum[y, x])
                        leaks.append(
                            {
                                "source": (lx, ly),
                                "target": (x, y),
                                "first_block": blocked_mid,
                                "rgb": leak_rgb,
                            }
                        )
    return leaks


def pretty_map(dungeon: Dungeon, rgb_sum: NDArray[np.float32]) -> str:
    chars = [[" " for _ in range(dungeon.width)] for _ in range(dungeon.height)]
    for y in range(dungeon.height):
        for x in range(dungeon.width):
            if dungeon.blocks_light(x, y):
                chars[y][x] = "#"
            elif np.any(rgb_sum[y, x] > 0.0):
                chars[y][x] = "*"
            else:
                chars[y][x] = "."
    return "\n".join("".join(row) for row in chars)


def build_varied_layout(dungeon: Dungeon) -> None:
    height = dungeon.height
    width = dungeon.width
    dungeon.tiles[:, :] = constants.FLOOR_ID
    dungeon.tiles[0, :] = constants.WALL_ID
    dungeon.tiles[-1, :] = constants.WALL_ID
    dungeon.tiles[:, 0] = constants.WALL_ID
    dungeon.tiles[:, -1] = constants.WALL_ID

    cx0, cy0 = width // 4, height // 4
    cx1, cy1 = 3 * width // 4, 3 * height // 4
    dungeon.tiles[cy0, cx0 : cx1 + 1] = constants.WALL_ID
    dungeon.tiles[cy1, cx0 : cx1 + 1] = constants.WALL_ID
    dungeon.tiles[cy0 : cy1 + 1, cx0] = constants.WALL_ID
    dungeon.tiles[cy0 : cy1 + 1, cx1] = constants.WALL_ID

    dungeon.tiles[cy0, (cx0 + cx1) // 2] = constants.FLOOR_ID
    dungeon.tiles[cy1, (cx0 + cx1) // 2] = constants.FLOOR_ID
    dungeon.tiles[(cy0 + cy1) // 2, cx0] = constants.FLOOR_ID
    dungeon.tiles[(cy0 + cy1) // 2, cx1] = constants.FLOOR_ID

    left_room_x = 2
    left_room_width = width // 6
    top = 2
    bottom = height - 3
    for y in range(top, bottom):
        if (y % 6) == 0:
            continue
        dungeon.tiles[y, left_room_x + left_room_width] = constants.WALL_ID

    right_room_x = width - (left_room_x + left_room_width) - 1
    for y in range(top, bottom):
        if (y % 7) == 1:
            continue
        dungeon.tiles[y, right_room_x] = constants.WALL_ID

    for ry in range(cy0 + 2, cy1 - 1, 4):
        for rx in range(cx0 + 3, cx1 - 2, 6):
            dungeon.tiles[ry, rx] = constants.PILLAR_ID

    base_y = cy0 + 3
    base_x = cx0 + 2
    for i in range(14):
        sx = base_x + i
        sy = base_y + (i % 3)
        if i % 5 == 0:
            continue
        dungeon.tiles[sy, sx] = constants.WALL_ID

    thin_wall_y = cy1 - 4
    for x in range(cx0 + 1, cx1):
        if (x % 4) in (1, 2):
            dungeon.tiles[thin_wall_y, x] = constants.WALL_ID


def place_varied_lights(game_state: GameState) -> None:
    rng = game_state.rng
    lights: List[LightSource] = []

    px = game_state.dungeon.width // 2
    py = game_state.dungeon.height // 2
    player = Player(px, y=py, light_radius=3, light_level=3, height=1.0)
    game_state.player = player

    orb1 = LightSource(
        10,
        y=8,
        rng=rng,
        light_radius=20,
        light_level=5,
        flicker=False,
        base_color_rgb=constants.ORB_COLOR_RGB,
        height=3.0,
    )
    lantern1 = LightSource(
        20,
        y=12,
        rng=rng,
        light_radius=6,
        light_level=4,
        flicker=True,
        base_color_rgb=(255, 140, 40),
        height=0.7,
    )
    orb2 = LightSource(
        px + 6,
        y=py - 3,
        rng=rng,
        light_radius=14,
        light_level=5,
        flicker=False,
        base_color_rgb=(255, 200, 120),
        height=2.0,
    )
    lantern2 = LightSource(
        px - 4,
        y=py + 4,
        rng=rng,
        light_radius=8,
        light_level=4,
        flicker=True,
        base_color_rgb=(255, 100, 100),
        height=0.6,
    )

    dir_spot = LightSource(
        px,
        y=3,
        rng=rng,
        light_radius=18,
        light_level=6,
        flicker=False,
        base_color_rgb=(255, 255, 220),
        height=4.0,
    )
    dir_dx = px - dir_spot.x
    dir_dy = py - dir_spot.y
    dir_spot.direction = math.atan2(dir_dy, dir_dx)
    dir_spot.cone_angle = math.pi / 6

    partial_light = LightSource(
        game_state.dungeon.width - 12,
        y=game_state.dungeon.height // 2 + 2,
        rng=rng,
        light_radius=12,
        light_level=5,
        base_color_rgb=(180, 220, 255),
        height=2.5,
        flicker=False,
    )

    cluster: List[LightSource] = []
    for dx in (-2, 0, 2):
        for dy in (-1, 1):
            cluster.append(
                LightSource(
                    px + dx + 12,
                    y=py + dy + 2,
                    rng=rng,
                    light_radius=6,
                    light_level=3,
                    flicker=False,
                    base_color_rgb=(180, 255, 180),
                    height=1.2,
                )
            )

    lights.extend([orb1, lantern1, orb2, lantern2, dir_spot, partial_light] + cluster)
    game_state.light_sources = lights
    game_state.all_entities = ([game_state.player] if game_state.player else []) + lights


def dump_state_to_file(game_state: GameState, outpath: Path) -> None:
    dungeon = game_state.dungeon
    lines: List[str] = []
    lines.append(f"VARIED TEST DUMP {time.asctime()}")
    lines.append(f"Map size: {dungeon.width}x{dungeon.height}")
    rng_seed = getattr(game_state.rng, "seed", "unknown")
    lines.append(f"Seed: {rng_seed}")
    lines.append("----- Dungeon ASCII -----")
    lines.append(pretty_map(dungeon, game_state.current_illumination_rgb_sum))
    lines.append("----- Tiles (counts) -----")
    unique, counts = np.unique(dungeon.tiles, return_counts=True)
    tile_counts = dict(zip(unique.tolist(), counts.tolist()))
    lines.append(str(tile_counts))
    lines.append("----- Lights -----")
    for li, light in enumerate(game_state.light_sources):
        light_height = getattr(light, "height", 1.0)
        light_direction = getattr(light, "direction", None)
        light_cone = getattr(light, "cone_angle", None)
        lines.append(
            f"{li}: pos=({light.x},{light.y}), radius={light.light_radius}, "
            f"level={light.light_level}, height={light_height}, dir={light_direction}, "
            f"cone={light_cone}, color={light.base_color_rgb}"
        )
    rgb = game_state.current_illumination_rgb_sum
    lines.append("----- Numeric Brightness dump -----")
    for y in range(dungeon.height):
        row: List[str] = []
        for x in range(dungeon.width):
            if np.any(rgb[y, x] > 0.0):
                row.append(f"{sum(rgb[y, x]):.2f}")
            else:
                row.append(" .  ")
        lines.append(" ".join(row))
    sources: List[Entity] = (
        ([game_state.player] if game_state.player else []) + game_state.light_sources
    )
    leaks = find_leaks(dungeon, sources, rgb)
    if not leaks:
        lines.append("\nNo direct LOS leaks detected.")
    else:
        lines.append(f"\nDetected {len(leaks)} leaks. Showing up to 100:")
        for leak in leaks[:100]:
            leak_source = leak["source"]
            leak_target = leak["target"]
            leak_blocker = leak["first_block"]
            leak_rgb = leak["rgb"]
            lines.append(
                f" Source {leak_source} -> Target {leak_target} "
                f"(first blocker {leak_blocker}) rgb={leak_rgb}"
            )
            tx, ty = leak_target
            minx = max(0, tx - 4)
            maxx = min(dungeon.width - 1, tx + 4)
            miny = max(0, ty - 4)
            maxy = min(dungeon.height - 1, ty + 4)
            lines.append("Context 9x9:")
            for yy in range(miny, maxy + 1):
                row: List[str] = []
                for xx in range(minx, maxx + 1):
                    if dungeon.blocks_light(xx, yy):
                        ch = "# "
                    elif np.any(rgb[yy, xx] > 0.0):
                        ch = "* "
                    else:
                        ch = ". "
                    if (xx, yy) == leak_source:
                        ch = "S "
                    if (xx, yy) == leak_blocker:
                        ch = "B "
                    if (xx, yy) == leak_target:
                        ch = "T "
                    row.append(ch)
                lines.append("".join(row))
    outpath.write_text("\n".join(lines), encoding="utf-8")


def run_test_and_write() -> None:
    runner = GameRunner(80, 40, seed=12345)
    runner.initialize()
    game_state = runner.game_state
    build_varied_layout(game_state.dungeon)
    place_varied_lights(game_state)
    runner.precompile()
    game_state.update(0.01)
    game_state.update_visibility()
    ts = time.strftime("%Y%m%d_%H%M%S")
    outpath = Path.cwd() / f"varied_test_output_{ts}.log"
    dump_state_to_file(game_state, outpath)
    print(f"Wrote debug output to {outpath}")


if __name__ == "__main__":
    run_test_and_write()
