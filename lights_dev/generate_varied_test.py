from __future__ import annotations

import math
from typing import Iterator, TypedDict

import numpy as np
from numpy.typing import NDArray

from lights_dev import constants
from lights_dev.dungeon_data import Dungeon
from lights_dev.entities import Entity, LightSource, Player
from lights_dev.game_state import GameState
from lights_dev.runner import GameRunner


class LeakInfo(TypedDict):
    source: tuple[int, int]
    target: tuple[int, int]
    first_block: tuple[int, int]
    rgb: tuple[float, float, float]


# Bresenham helper (same idea as debug_illum)
def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> Iterator[tuple[int, int]]:
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
    sources: list[Entity],
    rgb_sum: NDArray[np.float32],
) -> list[LeakInfo]:
    leaks: list[LeakInfo] = []
    for source in sources:
        lx, ly = source.x, source.y
        for y in range(dungeon.height):
            for x in range(dungeon.width):
                if np.any(rgb_sum[y, x] > 0.0):
                    blocked_mid: tuple[int, int] | None = None
                    for bx, by in bresenham_line(lx, ly, x, y):
                        if dungeon.blocks_light(bx, by):
                            blocked_mid = (bx, by)
                            break
                    if blocked_mid is not None:
                        rgb_values = tuple(float(v) for v in rgb_sum[y, x])
                        leaks.append(
                            {
                                "source": (lx, ly),
                                "target": (x, y),
                                "first_block": blocked_mid,
                                "rgb": rgb_values,
                            }
                        )
    return leaks


def pretty_map(dungeon: Dungeon, rgb_sum: NDArray[np.float32]) -> str:
    ch = [[" " for _ in range(dungeon.width)] for _ in range(dungeon.height)]
    for y in range(dungeon.height):
        for x in range(dungeon.width):
            if dungeon.blocks_light(x, y):
                ch[y][x] = "#"
            elif np.any(rgb_sum[y, x] > 0.0):
                ch[y][x] = "*"
            else:
                ch[y][x] = "."
    return "\n".join("".join(row) for row in ch)


def build_varied_layout(d: Dungeon) -> None:
    """
    Produce a larger more interesting test map in-place on a Dungeon `d`.
    - perimeter walls
    - central big room
    - left and right side rooms
    - partial walls (gaps/windows)
    - pillars
    """
    h = d.height
    w = d.width

    # floor everything first
    d.tiles[:, :] = constants.FLOOR_ID

    # outer perimeter
    d.tiles[0, :] = constants.WALL_ID
    d.tiles[-1, :] = constants.WALL_ID
    d.tiles[:, 0] = constants.WALL_ID
    d.tiles[:, -1] = constants.WALL_ID

    # big central room (leave door openings)
    cx0, cy0 = w // 4, h // 4
    cx1, cy1 = 3 * w // 4, 3 * h // 4
    d.tiles[cy0, cx0 : cx1 + 1] = constants.WALL_ID
    d.tiles[cy1, cx0 : cx1 + 1] = constants.WALL_ID
    d.tiles[cy0 : cy1 + 1, cx0] = constants.WALL_ID
    d.tiles[cy0 : cy1 + 1, cx1] = constants.WALL_ID

    # create door gaps
    d.tiles[cy0, (cx0 + cx1) // 2] = constants.FLOOR_ID
    d.tiles[cy1, (cx0 + cx1) // 2] = constants.FLOOR_ID
    d.tiles[(cy0 + cy1) // 2, cx0] = constants.FLOOR_ID
    d.tiles[(cy0 + cy1) // 2, cx1] = constants.FLOOR_ID

    # left and right side rooms, with internal partial walls
    left_room_x = 2
    left_room_w = w // 6
    top = 2
    bottom = h - 3
    # vertical walls with gaps for partial wall tests
    for y in range(top, bottom):
        if (y % 6) == 0:
            continue  # gap/windows every 6 tiles
        d.tiles[y, left_room_x + left_room_w] = constants.WALL_ID

    right_room_x = w - (left_room_x + left_room_w) - 1
    for y in range(top, bottom):
        if (y % 7) == 1:
            continue
        d.tiles[y, right_room_x] = constants.WALL_ID

    # add pillars in a grid inside central room and side rooms
    for ry in range(cy0 + 2, cy1 - 1, 4):
        for rx in range(cx0 + 3, cx1 - 2, 6):
            d.tiles[ry, rx] = constants.PILLAR_ID

    # an internal zig-zag partial wall
    base_y = cy0 + 3
    base_x = cx0 + 2
    for i in range(14):
        sx = base_x + i
        sy = base_y + (i % 3)
        if i % 5 == 0:
            # leave occasional hole
            continue
        d.tiles[sy, sx] = constants.WALL_ID

    # a 'thin' partial wall: floor on top half, wall on bottom (simulate half-height)
    # We'll just use wall ids on some rows to make occlusion interesting.
    thin_wall_y = cy1 - 4
    for x in range(cx0 + 1, cx1):
        if (x % 4) in (1, 2):
            d.tiles[thin_wall_y, x] = constants.WALL_ID


def place_varied_lights(gs: GameState) -> None:
    """Place multiple lights that exercise the code paths."""
    rng = gs.rng

    lights: list[LightSource] = []

    # Player at center: torch, low height
    px = gs.dungeon.width // 2
    py = gs.dungeon.height // 2
    player = Player(px, py, light_radius=3, light_level=3, height=1.0)
    gs.player = player

    # Tall bluish orb (high up)
    orb1 = LightSource(
        10,
        8,
        rng,
        light_radius=20,
        light_level=5,
        flicker=False,
        base_color_rgb=constants.ORB_COLOR_RGB,
        height=3.0,
    )
    # Low warm lantern
    lantern1 = LightSource(
        20,
        12,
        rng,
        light_radius=6,
        light_level=4,
        flicker=True,
        base_color_rgb=(255, 140, 40),
        height=0.7,
    )
    # Overlapping warm orb
    orb2 = LightSource(
        px + 6,
        py - 3,
        rng,
        light_radius=14,
        light_level=5,
        flicker=False,
        base_color_rgb=(255, 200, 120),
        height=2.0,
    )
    # Low red lantern overlapping a pillar
    lantern2 = LightSource(
        px - 4,
        py + 4,
        rng,
        light_radius=8,
        light_level=4,
        flicker=True,
        base_color_rgb=(255, 100, 100),
        height=0.6,
    )

    # Directional spotlight: point from top towards central room
    spot_x = gs.dungeon.width // 2
    spot_y = 3
    dir_spot = LightSource(
        spot_x,
        spot_y,
        rng,
        light_radius=18,
        light_level=6,
        flicker=False,
        base_color_rgb=(255, 255, 220),
        height=4.0,
    )
    # aim downward (towards center)
    dir_dx = px - dir_spot.x
    dir_dy = py - dir_spot.y
    dir_spot.direction = math.atan2(dir_dy, dir_dx)  # radians
    dir_spot.cone_angle = math.pi / 6  # ~30 degrees

    # Partial-block light: right-side behind a partial wall
    partial_light = LightSource(
        gs.dungeon.width - 12,
        gs.dungeon.height // 2 + 2,
        rng,
        light_radius=12,
        light_level=5,
        base_color_rgb=(180, 220, 255),
        height=2.5,
        flicker=False,
    )

    # Add overlapping cluster of small lights
    cluster: list[LightSource] = []
    for dx in (-2, 0, 2):
        for dy in (-1, 1):
            cluster.append(
                LightSource(
                    px + dx + 12,
                    py + dy + 2,
                    rng,
                    light_radius=6,
                    light_level=3,
                    flicker=False,
                    base_color_rgb=(180, 255, 180),
                    height=1.2,
                )
            )

    lights.extend([orb1, lantern1, orb2, lantern2, dir_spot, partial_light] + cluster)

    # Assign to game state
    gs.light_sources = lights
    gs.all_entities = [gs.player] + lights


def run_test() -> None:
    # create runner and game_state
    runner = GameRunner(80, 40, seed=12345)
    # This creates a default demo map and player; we'll overwrite it.
    runner.initialize()
    gs = runner.game_state
    d = gs.dungeon

    # build our varied layout
    build_varied_layout(d)

    # place lights (replaces whatever runner.initialize placed)
    place_varied_lights(gs)

    # force precompile so numba warms up (safe)
    runner.precompile()

    # compute visibility and illumination
    gs.update(0.01)  # updates time and memory fade
    gs.update_visibility()  # computes FOV + lighting

    # Print the text renderings
    renderer = runner.renderer
    renderer.set_renderer_mode("level")  # brightness numbers
    print(renderer.render(gs))

    renderer.set_renderer_mode("level_color")  # blended true color (clamped)
    print(renderer.render(gs))

    # show ASCII wall/lighting map from debug perspective
    print("--- ASCII (walls=#, lit=*) ---")
    print(pretty_map(d, gs.current_illumination_rgb_sum))

    # Run leak detection
    sources = ([gs.player] if gs.player else []) + gs.light_sources
    leaks = find_leaks(d, sources, gs.current_illumination_rgb_sum)
    if not leaks:
        print("\nNo direct LOS leaks detected by Bresenham test.")
    else:
        leak_count = len(leaks)
        print(f"\nDetected {leak_count} leak(s):")
        for leak in leaks[:40]:
            source = leak["source"]
            target = leak["target"]
            first_block = leak["first_block"]
            rgb = leak["rgb"]
            print(
                " Source {source} -> Target {target} "
                "(first blocker {first_block}) rgb={rgb}".format(
                    source=source,
                    target=target,
                    first_block=first_block,
                    rgb=rgb,
                )
            )


if __name__ == "__main__":
    run_test()
