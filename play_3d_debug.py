from __future__ import annotations

import argparse
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

import numpy as np
import polars as pl
import pygame  # type: ignore

from common.constants import Material
from orchestrator import DEFAULT_CA_ITERATIONS, DEFAULT_MAX_DEPTH, DEFAULT_MAX_NODES
from orchestrator import run_pipeline
from utils.shaped_map import load_shaped_map_as_arrays


SCREEN_WIDTH: Final[int] = 960
SCREEN_HEIGHT: Final[int] = 540
FPS: Final[int] = 30
PROJECTION_SCALE: Final[float] = 400.0


@dataclass(slots=True)
class Camera:
    row: float
    col: float
    yaw_rad: float
    eye_height: float


@dataclass(slots=True)
class Hit:
    row: int
    col: int
    tile_id: int
    distance: float
    adj_row: int
    adj_col: int


def is_walkable(tile_id: int) -> bool:
    return tile_id in {
        int(Material.CAVE_FLOOR),
        int(Material.SHAFT_OPENING),
        int(Material.DOOR_OPEN),
    }


def is_blocking(tile_id: int) -> bool:
    return not is_walkable(tile_id)


def _walkable_mask(tile_grid: np.ndarray) -> np.ndarray:
    return cast(
        np.ndarray,
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

    world_x: int = int(round(float(str(row["x"]))))
    world_y: int = int(round(float(str(row["y"]))))

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


def cast_ray(
    camera: Camera,
    ray_angle: float,
    tile_grid: np.ndarray,
    max_steps: int = 1000,
    step_size: float = 0.05,
) -> Hit | None:
    ray_row: float = camera.row
    ray_col: float = camera.col

    grid_height: int = int(tile_grid.shape[0])
    grid_width: int = int(tile_grid.shape[1])

    sin_a: float = math.sin(ray_angle)
    cos_a: float = math.cos(ray_angle)

    prev_ir: int = int(ray_row)
    prev_ic: int = int(ray_col)

    for _ in range(max_steps):
        ray_row += sin_a * step_size
        ray_col += cos_a * step_size

        ir: int = int(ray_row)
        ic: int = int(ray_col)

        if ir < 0 or ic < 0 or ir >= grid_height or ic >= grid_width:
            break

        tile_id: int = int(tile_grid[ir, ic])
        if is_blocking(tile_id):
            dx: float = ray_col - camera.col
            dy: float = ray_row - camera.row
            dist: float = math.hypot(dx, dy)
            return Hit(
                row=ir, col=ic, tile_id=tile_id, distance=dist,
                adj_row=prev_ir, adj_col=prev_ic
            )

        if ir != prev_ir or ic != prev_ic:
            prev_ir = ir
            prev_ic = ic

    return None


def get_wall_color(tile_id: int) -> tuple[int, int, int]:
    if tile_id == int(Material.SOLID_ROCK):
        return (60, 60, 70)
    elif tile_id == int(Material.CLIFF_EDGE):
        return (120, 65, 45)
    elif tile_id == int(Material.DOOR_CLOSED):
        return (75, 45, 20)
    return (200, 0, 200)


def draw_3d(
    screen: pygame.Surface,
    camera: Camera,
    tile_grid: np.ndarray,
    floor_depth_grid: np.ndarray,
    height_grid: np.ndarray,
) -> None:
    # Basic ceiling and floor background
    pygame.draw.rect(
        screen,
        (20, 20, 25),  # Ceiling color
        (0, 0, SCREEN_WIDTH, SCREEN_HEIGHT // 2),
    )
    pygame.draw.rect(
        screen,
        (35, 30, 25),  # Floor color
        (0, SCREEN_HEIGHT // 2, SCREEN_WIDTH, SCREEN_HEIGHT // 2),
    )

    fov: float = math.radians(60)
    half_fov: float = fov / 2.0
    start_angle: float = camera.yaw_rad - half_fov
    angle_step: float = fov / SCREEN_WIDTH

    cam_r: int = int(camera.row)
    cam_c: int = int(camera.col)
    
    # We need the true camera Z based on its current tile floor
    camera_z: float = 0.0
    if 0 <= cam_r < tile_grid.shape[0] and 0 <= cam_c < tile_grid.shape[1]:
        current_floor_z = float(floor_depth_grid[cam_r, cam_c])
        camera_z = current_floor_z - camera.eye_height

    horizon_y: int = SCREEN_HEIGHT // 2

    for col in range(SCREEN_WIDTH):
        ray_angle: float = start_angle + (col * angle_step)
        hit: Hit | None = cast_ray(camera, ray_angle, tile_grid)

        if hit is None:
            continue

        # Correct fisheye
        corrected_distance: float = hit.distance * math.cos(ray_angle - camera.yaw_rad)
        if corrected_distance < 0.001:
            corrected_distance = 0.001

        # Project floor and ceiling endpoints
        hit_floor_z: float = float(floor_depth_grid[hit.row, hit.col])
        hit_height: float = float(height_grid[hit.row, hit.col])

        if hit_height <= 0.0:
            hit_floor_z = float(floor_depth_grid[hit.adj_row, hit.adj_col])
            hit_height = float(height_grid[hit.adj_row, hit.adj_col])
            if hit_height <= 0.0:
                hit_height = 4.0

        hit_ceiling_z: float = hit_floor_z - hit_height
        
        # Pygame Y axis goes down. Depth convention: larger depth is down.
        relative_floor: float = hit_floor_z - camera_z
        relative_ceiling: float = hit_ceiling_z - camera_z

        wall_top: int = horizon_y + int((relative_ceiling * PROJECTION_SCALE) / corrected_distance)
        wall_bottom: int = horizon_y + int((relative_floor * PROJECTION_SCALE) / corrected_distance)

        color: tuple[int, int, int] = get_wall_color(hit.tile_id)
        
        # Simple distance shading
        shade: float = max(0.1, 1.0 - (hit.distance / 30.0))
        r: int = int(color[0] * shade)
        g: int = int(color[1] * shade)
        b: int = int(color[2] * shade)

        pygame.draw.line(
            screen,
            (r, g, b),
            (col, wall_top),
            (col, wall_bottom),
        )


def draw_hud(
    screen: pygame.Surface,
    font: pygame.font.Font,
    camera: Camera,
    tile_grid: np.ndarray,
    floor_depth_grid: np.ndarray,
    height_grid: np.ndarray,
    origin: tuple[int, int],
) -> None:
    r: int = int(camera.row)
    c: int = int(camera.col)

    tile_id: int = -1
    floor_z: float = 0.0
    height: float = 0.0
    ceiling_z: float = 0.0

    in_bounds: bool = (
        0 <= r < int(tile_grid.shape[0]) and 0 <= c < int(tile_grid.shape[1])
    )

    if in_bounds:
        tile_id = int(tile_grid[r, c])
        floor_z = float(floor_depth_grid[r, c])
        height = float(height_grid[r, c])
        ceiling_z = floor_z - height

    world_x: int = c + origin[0]
    world_y: int = r + origin[1]

    lines: list[str] = [
        f"grid=({camera.col:.2f}, {camera.row:.2f})",
        f"world=({world_x}, {world_y})",
        f"tile={tile_id}",
        f"floor_z={floor_z:.2f}",
        f"height={height:.2f}",
        f"ceiling_z={ceiling_z:.2f}",
        f"clearance={height:.2f}",
        f"yaw={math.degrees(camera.yaw_rad):.1f}",
        "W/A/S/D: move, Q/E: rotate",
    ]

    y_offset: int = 8
    for line in lines:
        text_surface: pygame.Surface = font.render(line, True, (230, 230, 230))
        screen.blit(text_surface, (8, y_offset))
        y_offset += 24


def try_move(camera: Camera, tile_grid: np.ndarray, d_row: float, d_col: float) -> None:
    next_row: float = camera.row + d_row
    next_col: float = camera.col + d_col

    grid_height: int = int(tile_grid.shape[0])
    grid_width: int = int(tile_grid.shape[1])

    ir: int = int(next_row)
    ic: int = int(next_col)

    if ir < 0 or ic < 0 or ir >= grid_height or ic >= grid_width:
        return

    tile_id: int = int(tile_grid[ir, ic])
    if is_walkable(tile_id):
        camera.row = next_row
        camera.col = next_col


def generate_or_load_grids(
    arrow_path: Path | None,
    seed: int,
    max_nodes: int,
    max_depth: int,
    ca_iterations: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, int], Path]:
    output_path: Path = (
        arrow_path if arrow_path is not None else Path("generated_dungeon.arrow")
    )

    if not output_path.exists():
        results: dict[str, object] = run_pipeline(
            seed=seed,
            max_nodes=max_nodes,
            max_depth=max_depth,
            ca_iterations=ca_iterations,
            output_file=str(output_path),
            run_sim=False,
        )

    arrays: dict[str, object] = load_shaped_map_as_arrays(str(output_path))
    tile_grid: np.ndarray = np.asarray(arrays["tile_id_grid"])
    floor_depth_grid: np.ndarray = np.asarray(arrays["floor_depth_grid"])
    height_grid: np.ndarray = np.asarray(arrays["height_grid"])
    origin: tuple[int, int] = cast(tuple[int, int], arrays["origin"])

    return tile_grid, floor_depth_grid, height_grid, origin, output_path


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
    floor_depth_grid: np.ndarray
    height_grid: np.ndarray
    origin: tuple[int, int]
    resolved_arrow_path: Path

    (
        tile_grid,
        floor_depth_grid,
        height_grid,
        origin,
        resolved_arrow_path,
    ) = generate_or_load_grids(
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

    # Initial eye height convention from requirements: camera_z = floor_z - 1.6
    camera: Camera = Camera(
        row=spawn_row + 0.5,
        col=spawn_col + 0.5,
        yaw_rad=0.0,
        eye_height=1.6,
    )

    pygame.init()
    pygame.display.set_caption("simple_rl 3D debug viewer")

    screen: pygame.Surface = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    font: pygame.font.Font = pygame.font.Font(None, 24)
    frame_timer: pygame.time.Clock = pygame.time.Clock()

    running: bool = True
    move_speed: float = 0.1
    rot_speed: float = 0.05

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

        keys = pygame.key.get_pressed()
        
        if keys[pygame.K_q] or keys[pygame.K_LEFT]:
            camera.yaw_rad -= rot_speed
        if keys[pygame.K_e] or keys[pygame.K_RIGHT]:
            camera.yaw_rad += rot_speed
            
        sin_yaw = math.sin(camera.yaw_rad)
        cos_yaw = math.cos(camera.yaw_rad)
        
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            try_move(camera, tile_grid, sin_yaw * move_speed, cos_yaw * move_speed)
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            try_move(camera, tile_grid, -sin_yaw * move_speed, -cos_yaw * move_speed)
        if keys[pygame.K_a]:
            try_move(camera, tile_grid, -cos_yaw * move_speed, sin_yaw * move_speed)
        if keys[pygame.K_d]:
            try_move(camera, tile_grid, cos_yaw * move_speed, -sin_yaw * move_speed)

        draw_3d(screen, camera, tile_grid, floor_depth_grid, height_grid)
        draw_hud(
            screen,
            font,
            camera,
            tile_grid,
            floor_depth_grid,
            height_grid,
            origin,
        )

        pygame.display.flip()
        frame_timer.tick(FPS)

    pygame.quit()


if __name__ == "__main__":
    main()
