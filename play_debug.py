from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import numpy as np
import polars as pl
import pygame  # type: ignore[import-untyped]

from common.constants import Material
from orchestrator import DEFAULT_CA_ITERATIONS, DEFAULT_MAX_DEPTH, DEFAULT_MAX_NODES
from orchestrator import run_pipeline
from utils.shaped_map import load_shaped_map_as_arrays


TILE_SIZE_OPTIONS: Final[tuple[int, ...]] = (2, 3, 4, 6, 8, 12, 16, 24)
DEFAULT_TILE_SIZE_INDEX: Final[int] = 5

SCREEN_WIDTH: Final[int] = 1152
SCREEN_HEIGHT: Final[int] = 648

@dataclass(slots=True)
class ViewState:
    tile_size_index: int = DEFAULT_TILE_SIZE_INDEX

    @property
    def tile_size(self) -> int:
        return TILE_SIZE_OPTIONS[self.tile_size_index]

    @property
    def view_cols(self) -> int:
        return SCREEN_WIDTH // self.tile_size

    @property
    def view_rows(self) -> int:
        return SCREEN_HEIGHT // self.tile_size

    def zoom_in(self) -> None:
        self.tile_size_index = min(
            len(TILE_SIZE_OPTIONS) - 1,
            self.tile_size_index + 1,
        )

    def zoom_out(self) -> None:
        self.tile_size_index = max(0, self.tile_size_index - 1)


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


def _walkable_mask(tile_grid: np.ndarray) -> np.ndarray:
    return (
        (tile_grid == int(Material.CAVE_FLOOR))
        | (tile_grid == int(Material.SHAFT_OPENING))
        | (tile_grid == int(Material.DOOR_OPEN))
    )


def _nearest_walkable(
    tile_grid: np.ndarray,
    preferred_row: int,
    preferred_col: int,
) -> tuple[int, int]:
    walkable_mask: np.ndarray = _walkable_mask(tile_grid)

    rows: np.ndarray
    cols: np.ndarray
    rows, cols = np.where(walkable_mask)

    if len(rows) == 0:
        raise RuntimeError("No walkable tiles found in generated dungeon.")

    d_row: np.ndarray = rows - preferred_row
    d_col: np.ndarray = cols - preferred_col
    dist_sq: np.ndarray = (d_row * d_row) + (d_col * d_col)

    best_index: int = int(np.argmin(dist_sq))
    return int(rows[best_index]), int(cols[best_index])


def _spawn_from_arrow(
    arrow_path: Path,
    origin: tuple[int, int],
    spawn_node_id: int,
) -> tuple[int, int] | None:
    if not arrow_path.exists():
        return None

    df: pl.DataFrame = pl.read_ipc(str(arrow_path))
    if "node_id" not in df.columns:
        return None

    node_df: pl.DataFrame = df.filter(pl.col("node_id") == spawn_node_id)
    if node_df.is_empty():
        return None

    row: dict[str, object] = node_df.select(["x", "y"]).row(0, named=True)

    world_x: int = int(round(float(row["x"])))
    world_y: int = int(round(float(row["y"])))

    origin_x: int
    origin_y: int
    origin_x, origin_y = origin

    grid_col: int = world_x - origin_x
    grid_row: int = world_y - origin_y

    return grid_row, grid_col


def find_spawn(
    tile_grid: np.ndarray,
    origin: tuple[int, int],
    arrow_path: Path,
    *,
    spawn_node_id: int = 0,
) -> tuple[int, int]:
    preferred_spawn: tuple[int, int] | None = _spawn_from_arrow(
        arrow_path=arrow_path,
        origin=origin,
        spawn_node_id=spawn_node_id,
    )

    if preferred_spawn is None:
        grid_height: int = int(tile_grid.shape[0])
        grid_width: int = int(tile_grid.shape[1])
        return _nearest_walkable(
            tile_grid=tile_grid,
            preferred_row=grid_height // 2,
            preferred_col=grid_width // 2,
        )

    preferred_row: int
    preferred_col: int
    preferred_row, preferred_col = preferred_spawn

    in_bounds: bool = (
        0 <= preferred_row < int(tile_grid.shape[0])
        and 0 <= preferred_col < int(tile_grid.shape[1])
    )

    if in_bounds and is_walkable(int(tile_grid[preferred_row, preferred_col])):
        return preferred_row, preferred_col

    return _nearest_walkable(
        tile_grid=tile_grid,
        preferred_row=preferred_row,
        preferred_col=preferred_col,
    )


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


def _get_tile_color(tile_id: int) -> tuple[int, int, int]:
    """Get the color for a given tile ID."""
    if tile_id == int(Material.SOLID_ROCK):
        return (18, 18, 22)
    elif tile_id == int(Material.CAVE_FLOOR):
        return (95, 88, 78)
    elif tile_id == int(Material.SHAFT_OPENING):
        return (60, 45, 90)
    elif tile_id == int(Material.CLIFF_EDGE):
        return (120, 65, 45)
    elif tile_id == int(Material.DOOR_OPEN):
        return (130, 95, 45)
    elif tile_id == int(Material.DOOR_CLOSED):
        return (75, 45, 20)
    else:
        return (200, 0, 200)


def _draw_tiles(
    screen: pygame.Surface,
    tile_grid: np.ndarray,
    camera_row: int,
    camera_col: int,
    view_cols: int,
    view_rows: int,
    tile_size: int,
) -> None:
    """Draw the tile grid within the viewport."""
    grid_height: int = int(tile_grid.shape[0])
    grid_width: int = int(tile_grid.shape[1])

    for screen_row in range(view_rows):
        grid_row: int = camera_row + screen_row
        if grid_row < 0 or grid_row >= grid_height:
            continue

        for screen_col in range(view_cols):
            grid_col: int = camera_col + screen_col
            if grid_col < 0 or grid_col >= grid_width:
                continue

            tile_id: int = int(tile_grid[grid_row, grid_col])
            color: tuple[int, int, int] = _get_tile_color(tile_id)

            rect: pygame.Rect = pygame.Rect(
                screen_col * tile_size,
                screen_row * tile_size,
                tile_size,
                tile_size,
            )
            pygame.draw.rect(screen, color, rect)


def _draw_player(
    screen: pygame.Surface,
    player: Player,
    camera_col: int,
    camera_row: int,
    tile_size: int,
) -> None:
    """Draw the player marker on the screen."""
    player_screen_col: int = player.col - camera_col
    player_screen_row: int = player.row - camera_row

    player_rect: pygame.Rect = pygame.Rect(
        player_screen_col * tile_size,
        player_screen_row * tile_size,
        max(1, tile_size),
        max(1, tile_size),
    )
    pygame.draw.rect(screen, (230, 220, 120), player_rect)

    if tile_size <= 4:
        marker_radius: int = 5
        marker_center: tuple[int, int] = (
            player_screen_col * tile_size + tile_size // 2,
            player_screen_row * tile_size + tile_size // 2,
        )
        pygame.draw.circle(screen, (230, 220, 120), marker_center, marker_radius, 1)


def _draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    player: Player,
    tile_grid: np.ndarray,
    origin: tuple[int, int],
    tile_size: int,
    view_cols: int,
    view_rows: int,
) -> None:
    """Draw the HUD with player information."""
    origin_x: int
    origin_y: int
    origin_x, origin_y = origin

    world_x: int = player.col + origin_x
    world_y: int = player.row + origin_y

    hud: pygame.Surface = font.render(
        f"grid=({player.col},{player.row}) "
        f"world=({world_x},{world_y}) "
        f"tile={int(tile_grid[player.row, player.col])} "
        f"zoom_tile={tile_size}px "
        f"view={view_cols}x{view_rows} "
        f"[ +/- zoom, arrows/WASD move ]",
        True,
        (230, 230, 230),
    )
    screen.blit(hud, (8, 8))


def draw(
    screen: pygame.Surface,
    font: pygame.font.Font,
    tile_grid: np.ndarray,
    player: Player,
    origin: tuple[int, int],
    view_state: ViewState,
) -> None:
    """Main draw function that coordinates all rendering."""
    screen.fill((0, 0, 0))

    tile_size: int = view_state.tile_size
    view_cols: int = view_state.view_cols
    view_rows: int = view_state.view_rows

    camera_row: int = player.row - view_rows // 2
    camera_col: int = player.col - view_cols // 2

    _draw_tiles(screen, tile_grid, camera_row, camera_col, view_cols, view_rows, tile_size)
    _draw_player(screen, player, camera_col, camera_row, tile_size)
    _draw_hud(screen, font, player, tile_grid, origin, tile_size, view_cols, view_rows)

    pygame.display.flip()


def generate_or_load_tile_grid(
    arrow_path: Path | None,
    seed: int,
    max_nodes: int,
    max_depth: int,
    ca_iterations: int,
) -> tuple[np.ndarray, tuple[int, int], Path]:
    output_path: Path = (
        arrow_path if arrow_path is not None else Path("generated_dungeon.arrow")
    )

    if output_path.exists():
        arrays: dict[str, object] = load_shaped_map_as_arrays(str(output_path))
        tile_grid: np.ndarray = np.asarray(arrays["tile_id_grid"])
        origin: tuple[int, int] = cast(tuple[int, int], arrays["origin"])
        return tile_grid, origin, output_path

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

    return tile_grid, origin, output_path


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--arrow", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--ca-iterations", type=int, default=DEFAULT_CA_ITERATIONS)
    parser.add_argument("--spawn-node-id", type=int, default=0)
    args: argparse.Namespace = parser.parse_args()

    tile_grid: np.ndarray
    origin: tuple[int, int]
    resolved_arrow_path: Path
    tile_grid, origin, resolved_arrow_path = generate_or_load_tile_grid(
        arrow_path=args.arrow,
        seed=args.seed,
        max_nodes=args.max_nodes,
        max_depth=args.max_depth,
        ca_iterations=args.ca_iterations,
    )

    spawn_row: int
    spawn_col: int
    spawn_row, spawn_col = find_spawn(
        tile_grid=tile_grid,
        origin=origin,
        arrow_path=resolved_arrow_path,
        spawn_node_id=args.spawn_node_id,
    )

    player: Player = Player(row=spawn_row, col=spawn_col)
    view_state: ViewState = ViewState()

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
                elif event.key in {pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS}:
                    view_state.zoom_in()
                elif event.key in {pygame.K_MINUS, pygame.K_KP_MINUS}:
                    view_state.zoom_out()

        draw(screen, font, tile_grid, player, origin, view_state)
        frame_timer.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
