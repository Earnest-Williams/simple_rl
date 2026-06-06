#!/usr/bin/env python3
"""Headless console debugger for the Lighting/FOV test scene.

This script intentionally avoids PySide6, PIL, structlog, and the renderer UI.
It mirrors the GUI's visibility-gated light activation rule while staying easy
for console iteration and profiling.

Run from the project root or from this directory:

    python tools/lighting_fov_tool/headless_lighting_debug.py --player 13,22
    python tools/lighting_fov_tool/headless_lighting_debug.py --interactive

Legend:
    # wall or pillar
    . unseen walkable tile
    v visible to player, unlit
    l reached by an active light, not visible to the player
    * reached by an active light and visible to the player
    @ player
    M sighted monster
    uppercase first letter of a light name = emitter tile
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, Sequence

import numpy as np

from scene import ElementType, LightSourceDef, SceneLayout, create_fixed_scene

PLAYER_SIGHT_RADIUS: Final[int] = 12
DEFAULT_VIEW_MARGIN: Final[int] = 2
CHANNELS_ALL: Final[int] = 0xFFFFFFFF
FovBackend = Literal["auto", "production", "bresenham"]


@dataclass(frozen=True)
class Observer:
    """An entity whose visible cells can make light worth computing."""

    name: str
    x: int
    y: int
    sight_radius: int


@dataclass(frozen=True)
class FovResult:
    """Computed FOV/reach outputs for one origin."""

    reach_mask: np.ndarray
    visible_out: np.ndarray
    dist_out: np.ndarray
    side_bits_out: np.ndarray
    visibility_out: np.ndarray
    backend_used: str


@dataclass(frozen=True)
class LightRuntimeResult:
    """Light source plus its precomputed reach result."""

    source: LightSourceDef
    fov: FovResult


@dataclass(frozen=True)
class ActiveLightReport:
    """Headless diagnostic details for one light."""

    name: str
    active: bool
    emitter_visible_to_player: bool
    reached_visible_cells: int
    reached_observer_cells: int
    radius_overlap_cells: int
    backend_used: str


def _ensure_project_in_path() -> None:
    """Add the project root to sys.path when this script is run directly."""
    current = Path(__file__).resolve().parent
    for _ in range(8):
        if (current / "CLAUDE.md").exists() or (current / "pyproject.toml").exists():
            current_str = str(current)
            if current_str not in sys.path:
                sys.path.insert(0, current_str)
            return
        parent = current.parent
        if parent == current:
            return
        current = parent


def build_opaque_grid(scene: SceneLayout) -> np.ndarray:
    """Return a cached-style boolean blocker grid for walls and pillars."""
    return (scene.tiles == ElementType.WALL) | (scene.tiles == ElementType.PILLAR)


def build_transparency_grid(opaque_grid: np.ndarray) -> np.ndarray:
    """Return a float transparency grid matching the GUI helper."""
    return (1.0 - opaque_grid).astype(np.float32)


def is_blocking(opaque_grid: np.ndarray, x: int, y: int) -> bool:
    """Return whether a cell blocks line of sight and light."""
    return bool(opaque_grid[y, x])


def has_los(
    opaque_grid: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> bool:
    """Return whether a Bresenham line reaches the target without blockers."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    x = x0
    y = y0
    while True:
        if x == x1 and y == y1:
            return True

        if (x, y) != (x0, y0) and opaque_grid[y, x]:
            return False

        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy


def compute_fov_bresenham(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    ox: int,
    oy: int,
    radius: int,
) -> FovResult:
    """Compute a circular FOV with optimized blocker-grid Bresenham LOS."""
    visible: np.ndarray = np.zeros((scene.height, scene.width), dtype=bool)
    dist_out: np.ndarray = -np.ones((scene.height, scene.width), dtype=np.int32)

    if radius <= 0 or not (0 <= ox < scene.width and 0 <= oy < scene.height):
        return _empty_fov_result(scene, "bresenham")

    radius_sq = radius * radius
    min_x = max(0, ox - radius)
    max_x = min(scene.width - 1, ox + radius)
    min_y = max(0, oy - radius)
    max_y = min(scene.height - 1, oy + radius)

    for y in range(min_y, max_y + 1):
        for x in range(min_x, max_x + 1):
            dx = x - ox
            dy = y - oy
            dist_sq = dx * dx + dy * dy
            if dist_sq <= radius_sq and has_los(opaque_grid, ox, oy, x, y):
                visible[y, x] = True
                dist_out[y, x] = dist_sq

    visible_out = visible.astype(np.uint8)
    return FovResult(
        reach_mask=visible,
        visible_out=visible_out,
        dist_out=dist_out,
        side_bits_out=np.zeros((scene.height, scene.width), dtype=np.uint8),
        visibility_out=visible.astype(np.float32),
        backend_used="bresenham",
    )


def _empty_fov_result(scene: SceneLayout, backend_used: str) -> FovResult:
    """Return an empty FOV result with the correct shapes and dtypes."""
    reach_mask = np.zeros((scene.height, scene.width), dtype=bool)
    return FovResult(
        reach_mask=reach_mask,
        visible_out=np.zeros((scene.height, scene.width), dtype=np.uint8),
        dist_out=-np.ones((scene.height, scene.width), dtype=np.int32),
        side_bits_out=np.zeros((scene.height, scene.width), dtype=np.uint8),
        visibility_out=np.zeros((scene.height, scene.width), dtype=np.float32),
        backend_used=backend_used,
    )


def compute_fov_production(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    transparency_grid: np.ndarray,
    ox: int,
    oy: int,
    radius: int,
) -> FovResult:
    """Compute FOV through the production octant FOV function."""
    if radius <= 0 or not (0 <= ox < scene.width and 0 <= oy < scene.height):
        return _empty_fov_result(scene, "production")

    _ensure_project_in_path()

    from engine.render_lighting import _precompute_geometry_blockers
    from game.world.light_fov import compute_fov_all_octants

    visible_out = np.zeros((scene.height, scene.width), dtype=np.uint8)
    dist_out = -np.ones((scene.height, scene.width), dtype=np.int32)
    side_bits_out = np.zeros((scene.height, scene.width), dtype=np.uint8)
    visibility_out = np.zeros((scene.height, scene.width), dtype=np.float32)

    cell_mask = np.full((scene.height, scene.width), CHANNELS_ALL, dtype=np.uint32)
    origin_height = int(scene.height_map[oy, ox])
    opaque_u8, transparency_f32 = _precompute_geometry_blockers(
        opaque_grid,
        scene.height_map,
        scene.ceiling_map,
        ox,
        oy,
        origin_height,
    )

    compute_fov_all_octants(
        opaque_u8,
        transparency_f32,
        cell_mask,
        CHANNELS_ALL,
        visible_out,
        dist_out,
        side_bits_out,
        visibility_out,
        ox,
        oy,
        radius,
    )

    return FovResult(
        reach_mask=visible_out != 0,
        visible_out=visible_out,
        dist_out=dist_out,
        side_bits_out=side_bits_out,
        visibility_out=visibility_out,
        backend_used="production",
    )


def compute_point_fov(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    transparency_grid: np.ndarray,
    ox: int,
    oy: int,
    radius: int,
    backend: FovBackend,
) -> FovResult:
    """Compute FOV from a point, matching the GUI's point-FOV abstraction."""
    if backend == "bresenham":
        return compute_fov_bresenham(scene, opaque_grid, ox, oy, radius)

    if backend == "production":
        return compute_fov_production(
            scene,
            opaque_grid,
            transparency_grid,
            ox,
            oy,
            radius,
        )

    try:
        return compute_fov_production(
            scene,
            opaque_grid,
            transparency_grid,
            ox,
            oy,
            radius,
        )
    except Exception:
        return compute_fov_bresenham(scene, opaque_grid, ox, oy, radius)


def light_radius_mask(scene: SceneLayout, light: LightSourceDef) -> np.ndarray:
    """Return all cells inside the light radius, ignoring blockers."""
    y_coords, x_coords = np.ogrid[0 : scene.height, 0 : scene.width]
    dx = x_coords - light.x
    dy = y_coords - light.y
    return (dx * dx + dy * dy) <= light.radius * light.radius


def get_observers(scene: SceneLayout) -> list[Observer]:
    """Return the player plus every monster with eyes."""
    px, py = scene.player_pos
    observers = [
        Observer(
            name="player",
            x=px,
            y=py,
            sight_radius=PLAYER_SIGHT_RADIUS,
        )
    ]

    for monster in scene.monsters:
        if not monster.has_eyes:
            continue
        observers.append(
            Observer(
                name=monster.name,
                x=monster.x,
                y=monster.y,
                sight_radius=monster.sight_radius,
            )
        )

    return observers


def compute_observer_visible_mask(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    transparency_grid: np.ndarray,
    backend: FovBackend,
) -> np.ndarray:
    """Return cells visible to at least one sighted observer."""
    observer_visible: np.ndarray = np.zeros((scene.height, scene.width), dtype=bool)
    for observer in get_observers(scene):
        observer_fov = compute_point_fov(
            scene,
            opaque_grid,
            transparency_grid,
            observer.x,
            observer.y,
            observer.sight_radius,
            backend,
        )
        observer_visible |= observer_fov.reach_mask
    return observer_visible


def compute_player_visible_mask(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    transparency_grid: np.ndarray,
    backend: FovBackend,
) -> np.ndarray:
    """Return cells visible to the player only."""
    px, py = scene.player_pos
    return compute_point_fov(
        scene,
        opaque_grid,
        transparency_grid,
        px,
        py,
        PLAYER_SIGHT_RADIUS,
        backend,
    ).reach_mask


def compute_light_runtime_results(
    scene: SceneLayout,
    opaque_grid: np.ndarray,
    transparency_grid: np.ndarray,
    backend: FovBackend,
) -> list[LightRuntimeResult]:
    """Compute each light reach mask exactly once."""
    results: list[LightRuntimeResult] = []
    for light in scene.light_sources:
        if light.radius <= 0 or light.intensity <= 0.0:
            fov = _empty_fov_result(scene, "disabled")
        else:
            fov = compute_point_fov(
                scene,
                opaque_grid,
                transparency_grid,
                light.x,
                light.y,
                light.radius,
                backend,
            )
        results.append(LightRuntimeResult(source=light, fov=fov))
    return results


def build_light_report(
    light_result: LightRuntimeResult,
    player_visible: np.ndarray,
    observer_visible: np.ndarray,
) -> ActiveLightReport:
    """Return activation diagnostics using a precomputed light reach result."""
    light = light_result.source
    reached = light_result.fov.reach_mask
    radius = light_radius_mask_from_shape(player_visible.shape, light)
    reached_observer_cells = int(np.count_nonzero(reached & observer_visible))
    reached_visible_cells = int(np.count_nonzero(reached & player_visible))
    radius_overlap_cells = int(np.count_nonzero(radius & observer_visible))
    emitter_visible_to_player = bool(player_visible[light.y, light.x])

    return ActiveLightReport(
        name=light.name,
        active=reached_observer_cells > 0,
        emitter_visible_to_player=emitter_visible_to_player,
        reached_visible_cells=reached_visible_cells,
        reached_observer_cells=reached_observer_cells,
        radius_overlap_cells=radius_overlap_cells,
        backend_used=light_result.fov.backend_used,
    )


def light_radius_mask_from_shape(
    shape: tuple[int, int],
    light: LightSourceDef,
) -> np.ndarray:
    """Return a radius mask for a light with only an array shape available."""
    height, width = shape
    y_coords, x_coords = np.ogrid[0:height, 0:width]
    dx = x_coords - light.x
    dy = y_coords - light.y
    return (dx * dx + dy * dy) <= light.radius * light.radius


def compute_light_reports(
    scene: SceneLayout,
    backend: FovBackend,
) -> list[ActiveLightReport]:
    """Return activation diagnostics for every light without duplicate reach work."""
    opaque_grid = build_opaque_grid(scene)
    transparency_grid = build_transparency_grid(opaque_grid)
    player_visible = compute_player_visible_mask(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    observer_visible = compute_observer_visible_mask(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    light_results = compute_light_runtime_results(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    return [
        build_light_report(light_result, player_visible, observer_visible)
        for light_result in light_results
    ]


def compute_active_light_mask(
    scene: SceneLayout,
    backend: FovBackend,
) -> tuple[np.ndarray, list[ActiveLightReport]]:
    """Return all cells reached by active lights plus per-light reports."""
    opaque_grid = build_opaque_grid(scene)
    transparency_grid = build_transparency_grid(opaque_grid)
    player_visible = compute_player_visible_mask(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    observer_visible = compute_observer_visible_mask(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    light_results = compute_light_runtime_results(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )

    active_mask: np.ndarray = np.zeros((scene.height, scene.width), dtype=bool)
    reports: list[ActiveLightReport] = []

    for light_result in light_results:
        report = build_light_report(light_result, player_visible, observer_visible)
        reports.append(report)
        if report.active:
            active_mask |= light_result.fov.reach_mask

    return active_mask, reports


def parse_xy(raw: str) -> tuple[int, int]:
    """Parse an x,y coordinate pair."""
    parts = raw.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected x,y")
    try:
        x = int(parts[0])
        y = int(parts[1])
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected integer x,y") from exc
    return x, y


def set_player(scene: SceneLayout, pos: tuple[int, int]) -> None:
    """Move the player if the target is in bounds and walkable."""
    x, y = pos
    if not (0 <= x < scene.width and 0 <= y < scene.height):
        raise ValueError(f"player position out of bounds: {pos}")
    opaque_grid = build_opaque_grid(scene)
    if is_blocking(opaque_grid, x, y):
        raise ValueError(f"player position is blocked: {pos}")
    scene.player_pos = pos


def bounds_for_view(
    scene: SceneLayout,
    focus: str | None,
    margin: int,
) -> tuple[int, int, int, int]:
    """Return inclusive-exclusive bounds for the requested console view."""
    if focus is None or focus == "all":
        return 0, scene.width, 0, scene.height

    points: list[tuple[int, int]] = [scene.player_pos]
    if focus == "left":
        points.extend([(1, 15), (12, 28), (11, 27), (2, 19)])
    elif focus == "se":
        points.extend([(44, 26), (55, 35), (52, 32), (54, 34)])
    else:
        for light in scene.light_sources:
            if light.name == focus:
                points.append((light.x, light.y))
                break

    min_x = max(0, min(x for x, _ in points) - margin)
    max_x = min(scene.width, max(x for x, _ in points) + margin + 1)
    min_y = max(0, min(y for _, y in points) - margin)
    max_y = min(scene.height, max(y for _, y in points) + margin + 1)
    return min_x, max_x, min_y, max_y


def light_glyph(name: str) -> str:
    """Return a compact marker for a light name."""
    return name[0].upper() if name else "L"


def render_ascii(
    scene: SceneLayout,
    focus: str | None = "left",
    backend: FovBackend = "auto",
) -> str:
    """Render the scene as ASCII with player visibility and active light reach."""
    opaque_grid = build_opaque_grid(scene)
    transparency_grid = build_transparency_grid(opaque_grid)
    player_visible = compute_player_visible_mask(
        scene,
        opaque_grid,
        transparency_grid,
        backend,
    )
    active_light, reports = compute_active_light_mask(scene, backend)
    light_positions = {
        (light.x, light.y): light_glyph(light.name) for light in scene.light_sources
    }
    monster_positions = {
        (monster.x, monster.y): "M" for monster in scene.monsters if monster.has_eyes
    }
    active_names = {report.name for report in reports if report.active}
    backends_used = sorted({report.backend_used for report in reports})

    min_x, max_x, min_y, max_y = bounds_for_view(scene, focus, DEFAULT_VIEW_MARGIN)
    lines: list[str] = []
    lines.append(
        f"player={scene.player_pos} active_lights={','.join(sorted(active_names)) or '<none>'}"
    )
    lines.append(f"fov_backend={backend} used={','.join(backends_used) or '<none>'}")
    lines.append("legend: # block . unseen v visible l active-light-only * visible-lit @ player M monster")
    lines.append(f"view: x={min_x}..{max_x - 1}, y={min_y}..{max_y - 1}")

    for y in range(min_y, max_y):
        row_chars: list[str] = []
        for x in range(min_x, max_x):
            pos = (x, y)
            if pos == scene.player_pos:
                row_chars.append("@")
            elif pos in monster_positions:
                row_chars.append(monster_positions[pos])
            elif pos in light_positions:
                row_chars.append(light_positions[pos])
            elif is_blocking(opaque_grid, x, y):
                row_chars.append("#")
            elif player_visible[y, x] and active_light[y, x]:
                row_chars.append("*")
            elif player_visible[y, x]:
                row_chars.append("v")
            elif active_light[y, x]:
                row_chars.append("l")
            else:
                row_chars.append(".")
        lines.append(f"{y:02d} {''.join(row_chars)}")

    return "\n".join(lines)


def format_reports(reports: Sequence[ActiveLightReport]) -> str:
    """Format per-light activation diagnostics."""
    lines = [
        "light activation report:",
        "name                 active emitter_seen reached_player reached_observers radius_overlap backend",
    ]
    for report in reports:
        lines.append(
            f"{report.name:<20} "
            f"{str(report.active):<6} "
            f"{str(report.emitter_visible_to_player):<12} "
            f"{report.reached_visible_cells:<14} "
            f"{report.reached_observer_cells:<17} "
            f"{report.radius_overlap_cells:<14} "
            f"{report.backend_used}"
        )
    return "\n".join(lines)


def try_move(scene: SceneLayout, dx: int, dy: int) -> bool:
    """Try to move the player by a delta."""
    px, py = scene.player_pos
    nx = px + dx
    ny = py + dy
    if not (0 <= nx < scene.width and 0 <= ny < scene.height):
        return False
    opaque_grid = build_opaque_grid(scene)
    if is_blocking(opaque_grid, nx, ny):
        return False
    scene.player_pos = (nx, ny)
    return True


def run_interactive(scene: SceneLayout, focus: str | None, backend: FovBackend) -> None:
    """Run a tiny keyboard-driven console loop."""
    print("Commands: w/a/s/d move, r report, q quit")
    while True:
        print(render_ascii(scene, focus, backend))
        command = input("> ").strip().lower()
        if command == "q":
            return
        if command == "r":
            print(format_reports(compute_light_reports(scene, backend)))
            continue
        moves = {
            "w": (0, -1),
            "a": (-1, 0),
            "s": (0, 1),
            "d": (1, 0),
        }
        if command in moves:
            dx, dy = moves[command]
            moved = try_move(scene, dx, dy)
            if not moved:
                print("blocked")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--player",
        type=parse_xy,
        default=None,
        help="override player start as x,y, for example 13,22",
    )
    parser.add_argument(
        "--focus",
        default="left",
        help="view focus: left, se, all, or an exact light name",
    )
    parser.add_argument(
        "--fov-backend",
        choices=["auto", "production", "bresenham"],
        default="auto",
        help="FOV backend. auto uses production when importable, else bresenham.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="print only the activation report",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="run a tiny WASD console loop",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the headless debugger."""
    parser = build_parser()
    args = parser.parse_args(argv)

    scene = create_fixed_scene()
    if args.player is not None:
        set_player(scene, args.player)

    backend = str(args.fov_backend)
    if backend not in ("auto", "production", "bresenham"):
        raise ValueError(f"unsupported backend: {backend}")

    focus = str(args.focus) if args.focus else None
    if args.interactive:
        run_interactive(scene, focus, backend)  # type: ignore[arg-type]
        return 0

    reports = compute_light_reports(scene, backend)  # type: ignore[arg-type]
    if not args.report_only:
        print(render_ascii(scene, focus, backend))  # type: ignore[arg-type]
        print()
    print(format_reports(reports))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
