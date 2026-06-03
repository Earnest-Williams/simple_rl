#!/usr/bin/env python
"""Production light-leak diagnostic for FOV and side-aware lighting.

Usage:
    python complete_light_diagnostic.py
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from typing import Final

import numpy as np
from numpy.typing import NDArray

from engine.render_lighting import LightContributionCache
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap, LightSource
from game.world.light_fov import compute_fov_all_octants

SCENE_WIDTH: Final[int] = 9
SCENE_HEIGHT: Final[int] = 9
TARGET_X: Final[int] = 8
TARGET_Y: Final[int] = 4
LIGHT_X: Final[int] = 0
LIGHT_Y: Final[int] = 4
LIGHT_RADIUS: Final[int] = 10


@dataclass(frozen=True, slots=True)
class DiagnosticScene:
    """Production map plus a single light and leak target."""

    game_map: GameMap
    light: LightSource
    target_x: int
    target_y: int


def create_simple_test_scene() -> DiagnosticScene:
    """Create the wall-room leak scenario on production map structures."""
    game_map = GameMap(SCENE_WIDTH, SCENE_HEIGHT)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.ceiling_map[:, :] = 10

    wall_positions: tuple[tuple[int, int], ...] = (
        (3, 3),
        (4, 3),
        (5, 3),
        (3, 4),
        (5, 4),
        (3, 5),
        (4, 5),
        (5, 5),
    )
    for x, y in wall_positions:
        game_map.tiles[y, x] = TILE_ID_WALL
    game_map.update_tile_transparency()

    light = LightSource(
        x=LIGHT_X,
        y=LIGHT_Y,
        radius=LIGHT_RADIUS,
        color=(255, 220, 180),
        intensity=1.0,
        height=0.0,
    )
    return DiagnosticScene(game_map, light, TARGET_X, TARGET_Y)


def print_dungeon_layout(scene: DiagnosticScene) -> None:
    """Print the diagnostic layout."""
    print("Layout:")
    for y in range(scene.game_map.height):
        row: list[str] = []
        for x in range(scene.game_map.width):
            if x == scene.light.x and y == scene.light.y:
                row.append("L")
            elif x == scene.target_x and y == scene.target_y:
                row.append("T")
            elif scene.game_map.tiles[y, x] == TILE_ID_WALL:
                row.append("#")
            else:
                row.append(".")
        print(" ".join(row))
    print(f"\nL = Light source at ({scene.light.x}, {scene.light.y})")
    print(f"T = Target behind wall at ({scene.target_x}, {scene.target_y})\n")


def check_blocks_light_implementation(game_map: GameMap) -> None:
    """Report wall and floor transparency from production GameMap state."""
    print("=" * 60)
    print("DIAGNOSTIC 1: Production GameMap transparency")
    print("=" * 60)
    wall_blocks = not game_map.is_transparent(3, 4)
    door_transparent = game_map.is_transparent(4, 4)
    print(f"Wall at (3,4) blocks light: {wall_blocks}")
    print(f"Opening at (4,4) is transparent: {door_transparent}")
    print()


def check_transparency_array(
    opaque: NDArray[np.uint8], transparency: NDArray[np.float32]
) -> None:
    """Print production arrays used by FOV and lighting."""
    print("=" * 60)
    print("DIAGNOSTIC 2: Opaque and transparency arrays")
    print("=" * 60)
    print(f"Opaque cells: {int(np.sum(opaque))}")
    print(f"Transparent cells: {int(np.sum(transparency > 0.0))}")
    print("Opaque grid (1=blocks, 0=open):")
    for y in range(opaque.shape[0]):
        values = [str(int(opaque[y, x])) for x in range(opaque.shape[1])]
        print(" ".join(values))
    print()


def check_fov_visibility(
    visible: NDArray[np.uint8],
    visibility: NDArray[np.float32],
    opaque: NDArray[np.uint8],
    src_x: int,
    src_y: int,
) -> None:
    """Print FOV visibility and side-effect diagnostic summary."""
    print("=" * 60)
    print("DIAGNOSTIC 3: Production light_fov visibility")
    print("=" * 60)
    print(f"Source at ({src_x},{src_y}) visible={visible[src_y, src_x]}")
    print(f"Visible cells: {int(np.sum(visible))}")
    print(f"Opaque visible cells: {int(np.sum(visible[opaque != 0]))}")
    print(f"Target visibility: {float(visibility[TARGET_Y, TARGET_X]):.4f}")
    print()


def bresenham_line(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Return points on the line between endpoints, excluding endpoints."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    x = x0
    y = y0

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
            points.append((x, y))
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
            points.append((x, y))

    return points


def check_line_of_sight_leaks(
    contribution: NDArray[np.float32],
    opaque: NDArray[np.uint8],
    visibility: NDArray[np.float32],
    src_x: int,
    src_y: int,
    target_x: int,
    target_y: int,
) -> None:
    """Check whether the target behind the wall receives production light."""
    print("=" * 60)
    print("DIAGNOSTIC 4: Line-of-sight leak check")
    print("=" * 60)

    total_alpha = np.sum(contribution[:, :, :, 3], axis=2)
    target_alpha = float(total_alpha[target_y, target_x])
    target_vis = float(visibility[target_y, target_x])
    target_opaque = int(opaque[target_y, target_x])

    print(f"Target cell ({target_x}, {target_y}):")
    print(f"  Opaque: {target_opaque}")
    print(f"  Visibility: {target_vis:.4f}")
    print(f"  Alpha (light): {target_alpha:.4f}")

    print(f"\nLine-of-sight from ({src_x},{src_y}) to ({target_x},{target_y}):")
    line = bresenham_line(src_x, src_y, target_x, target_y)

    blocker_found: tuple[int, int] | None = None
    for index, (bx, by) in enumerate(line, start=1):
        blocks = bool(opaque[by, bx])
        vis = float(visibility[by, bx])
        print(f"  Step {index}: ({bx},{by}) - opaque={blocks}, visibility={vis:.4f}")
        if blocks and blocker_found is None:
            blocker_found = (bx, by)
            print("         ^^^ FIRST BLOCKER")

    print("\n" + "=" * 60)
    if target_alpha > 0.01 and blocker_found is not None:
        print("❌ LIGHT LEAK DETECTED!")
        print(
            f"   Light reaches ({target_x},{target_y}) despite blocker at {blocker_found}"
        )
    elif target_alpha <= 0.01 and blocker_found is not None:
        print("✓ CORRECT: Target is blocked and not lit")
    elif target_alpha > 0.01:
        print("✓ Target is lit and has clear line of sight")
    else:
        print("⚠ Target has clear line of sight but is not lit; it may be out of range")
    print("=" * 60)
    print()


def run_complete_diagnostic() -> None:
    """Run the complete production diagnostic suite."""
    print("\n" + "=" * 70)
    print(" " * 15 + "PRODUCTION LIGHT LEAKAGE DIAGNOSTIC SUITE")
    print("=" * 70 + "\n")

    scene = create_simple_test_scene()
    print_dungeon_layout(scene)
    check_blocks_light_implementation(scene.game_map)

    h = scene.game_map.height
    w = scene.game_map.width
    opaque = (~scene.game_map.transparent).astype(np.uint8)
    transparency = scene.game_map.transparent.astype(np.float32)
    check_transparency_array(opaque, transparency)

    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side_bits = np.zeros((h, w), dtype=np.uint8)
    visibility = np.zeros((h, w), dtype=np.float32)

    compute_fov_all_octants(
        opaque,
        transparency,
        visible,
        dist,
        side_bits,
        visibility,
        scene.light.x,
        scene.light.y,
        scene.light.radius,
    )
    check_fov_visibility(visible, visibility, opaque, scene.light.x, scene.light.y)

    cache = LightContributionCache(h, w)
    rgb = cache.update(
        [scene.light],
        opaque.astype(np.bool_),
        scene_seq=scene.game_map.scene_geometry_version,
        height_map=scene.game_map.height_map,
        ceiling_map=scene.game_map.ceiling_map,
    )
    contribution = cache.side_rgba_view()
    target_rgb = rgb[scene.target_y, scene.target_x]
    nearby_rgb = rgb[scene.light.y, scene.light.x + 1]
    print(f"Target RGB: {target_rgb.tolist()}\n")
    if float(np.max(nearby_rgb)) <= 0.0:
        raise RuntimeError("Diagnostic scene failed: adjacent open tile was not lit.")
    if float(np.max(target_rgb)) > 0.01:
        raise RuntimeError("Diagnostic scene failed: blocked target received light.")

    check_line_of_sight_leaks(
        contribution,
        opaque,
        visibility,
        scene.light.x,
        scene.light.y,
        scene.target_x,
        scene.target_y,
    )

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        run_complete_diagnostic()
    except Exception as exc:
        print(f"\n❌ Error during diagnostic: {exc}")
        traceback.print_exc()
