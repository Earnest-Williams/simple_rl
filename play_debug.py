from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import numpy as np
import pygame  # type: ignore[import-untyped]

from common.constants import Material
from orchestrator import DEFAULT_CA_ITERATIONS, DEFAULT_MAX_DEPTH, DEFAULT_MAX_NODES
from orchestrator import run_pipeline
from utils.shaped_map import load_shaped_map_as_arrays


TILE_SIZE: Final[int] = 12
VIEW_COLS: Final[int] = 96
VIEW_ROWS: Final[int] = 54
SCREEN_WIDTH: Final[int] = VIEW_COLS * TILE_SIZE
SCREEN_HEIGHT: Final[int] = VIEW_ROWS * TILE_SIZE
FPS: Final[int] = 30


@dataclass(slots=True)
class Player:
    row: int
    col: int


def is_walkable(tile_id: int) -> bool:
    return tile_id in {
        int(Material.CAVE_FLOOR),
        int(Material.SHAFT_OPENING),
        int(Material.DOOR_OPEN),
    }


def find_spawn(tile_grid: np.ndarray) -> tuple[int, int]:
    walkable_mask: np.ndarray = (
        (tile_grid == int(Material.CAVE_FLOOR))
        | (tile_grid == int(Material.SHAFT_OPENING))
        | (tile_grid == int(Material.DOOR_OPEN))
    )

    rows: np.ndarray
    cols: np.ndarray
    rows, cols = np.where(walkable_mask)

    if len(rows) == 0:
        raise RuntimeError("No walkable tiles found in generated dungeon.")

    middle_index: int = len(rows) // 2
    return int(rows[middle_index]), int(cols[middle_index])


def try_move(player: Player, tile_grid: np.ndarray, d_row: int, d_col: int) -> None:
    next_row: int = player.row + d_row
    next_col: int = player.col + d_col

    height: int = int(tile_grid.shape[0])
    width: int = int(tile_grid.shape[1])

    if next_row < 0 or next_col < 0 or next_row >= height or next_col >= width:
        return

    tile_id: int = int(tile_grid[next_row, next_col])
    if is_walkable(tile_id):
        player.row = next_row
        player.col = next_col


def draw(
    screen: pygame.Surface,
    font: pygame.font.Font,
    tile_grid: np.ndarray,
    player: Player,
    origin: tuple[int, int],
) -> None:
    screen.fill((0, 0, 0))

    grid_height: int = int(tile_grid.shape[0])
    grid_width: int = int(tile_grid.shape[1])

    camera_row: int = player.row - VIEW_ROWS // 2
    camera_col: int = player.col - VIEW_COLS // 2

    for screen_row in range(VIEW_ROWS):
        grid_row: int = camera_row + screen_row
        if grid_row < 0 or grid_row >= grid_height:
            continue

        for screen_col in range(VIEW_COLS):
            grid_col: int = camera_col + screen_col
            if grid_col < 0 or grid_col >= grid_width:
                continue

            tile_id: int = int(tile_grid[grid_row, grid_col])

            if tile_id == int(Material.SOLID_ROCK):
                color: tuple[int, int, int] = (18, 18, 22)
            elif tile_id == int(Material.CAVE_FLOOR):
                color = (95, 88, 78)
            elif tile_id == int(Material.SHAFT_OPENING):
                color = (60, 45, 90)
            elif tile_id == int(Material.CLIFF_EDGE):
                color = (120, 65, 45)
            elif tile_id == int(Material.DOOR_OPEN):
                color = (130, 95, 45)
            elif tile_id == int(Material.DOOR_CLOSED):
                color = (75, 45, 20)
            else:
                color = (200, 0, 200)

            rect: pygame.Rect = pygame.Rect(
                screen_col * TILE_SIZE,
                screen_row * TILE_SIZE,
                TILE_SIZE,
                TILE_SIZE,
            )
            pygame.draw.rect(screen, color, rect)

    player_screen_col: int = player.col - camera_col
    player_screen_row: int = player.row - camera_row

    player_rect: pygame.Rect = pygame.Rect(
        player_screen_col * TILE_SIZE,
        player_screen_row * TILE_SIZE,
        TILE_SIZE,
        TILE_SIZE,
    )
    pygame.draw.rect(screen, (230, 220, 120), player_rect)

    origin_x: int
    origin_y: int
    origin_x, origin_y = origin

    world_x: int = player.col + origin_x
    world_y: int = player.row + origin_y

    hud: pygame.Surface = font.render(
        f"grid=({player.col},{player.row}) "
        f"world=({world_x},{world_y}) "
        f"tile={int(tile_grid[player.row, player.col])}",
        True,
        (230, 230, 230),
    )
    screen.blit(hud, (8, 8))

    pygame.display.flip()


def generate_or_load_tile_grid(
    arrow_path: Path | None,
    seed: int,
    max_nodes: int,
    max_depth: int,
    ca_iterations: int,
) -> tuple[np.ndarray, tuple[int, int]]:
    output_path: Path = (
        arrow_path if arrow_path is not None else Path("generated_dungeon.arrow")
    )

    if output_path.exists():
        arrays: dict[str, object] = load_shaped_map_as_arrays(str(output_path))
        tile_grid: np.ndarray = np.asarray(arrays["tile_id_grid"])
        origin: tuple[int, int] = cast(tuple[int, int], arrays["origin"])
        return tile_grid, origin

    results: dict[str, object] = run_pipeline(
        seed=seed,
        max_nodes=max_nodes,
        max_depth=max_depth,
        ca_iterations=ca_iterations,
        output_file=str(output_path),
        run_sim=False,
    )

    arrays = load_shaped_map_as_arrays(str(output_path))
    tile_grid = np.asarray(results["tile_grid"])
    origin = cast(tuple[int, int], arrays["origin"])

    return tile_grid, origin


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--arrow", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--ca-iterations", type=int, default=DEFAULT_CA_ITERATIONS)
    args: argparse.Namespace = parser.parse_args()

    tile_grid: np.ndarray
    origin: tuple[int, int]
    tile_grid, origin = generate_or_load_tile_grid(
        arrow_path=args.arrow,
        seed=args.seed,
        max_nodes=args.max_nodes,
        max_depth=args.max_depth,
        ca_iterations=args.ca_iterations,
    )

    spawn_row: int
    spawn_col: int
    spawn_row, spawn_col = find_spawn(tile_grid)

    player: Player = Player(row=spawn_row, col=spawn_col)

    pygame.init()
    pygame.display.set_caption("simple_rl dungeon debug walker")

    screen: pygame.Surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font: pygame.font.Font = pygame.font.Font(None, 24)
    frame_timer: pygame.time.Clock = pygame.time.Clock()

    running: bool = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in {pygame.K_w, pygame.K_UP}:
                    try_move(player, tile_grid, -1, 0)
                elif event.key in {pygame.K_s, pygame.K_DOWN}:
                    try_move(player, tile_grid, 1, 0)
                elif event.key in {pygame.K_a, pygame.K_LEFT}:
                    try_move(player, tile_grid, 0, -1)
                elif event.key in {pygame.K_d, pygame.K_RIGHT}:
                    try_move(player, tile_grid, 0, 1)

        draw(screen, font, tile_grid, player, origin)
        frame_timer.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
