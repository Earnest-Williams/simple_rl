#!/usr/bin/env python3
# tools/play_game.py
"""
Play simple_rl.

Usage:
    # CLI starting on the generated overland starting port
    python tools/play_game.py --mode cli

    # GUI starting on the generated overland starting port
    python tools/play_game.py --mode gui

    # CLI from an Arrow/IPC shaped map
    python tools/play_game.py --arrow generated_dungeon.arrow --mode cli

    # GUI from an Arrow/IPC shaped map
    python tools/play_game.py --arrow generated_dungeon.arrow --mode gui
"""

from __future__ import annotations

import argparse
import inspect
import sys
import tomllib
from collections import deque
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Literal, Protocol

import numpy as np
import polars as pl
import yaml
from polars.exceptions import ColumnNotFoundError, PolarsError

SCRIPT_PATH = Path(__file__)
if SCRIPT_PATH.exists():
    repo_root = SCRIPT_PATH.resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from common.constants import Material  # noqa: E402
from engine.main_loop import MainLoop  # noqa: E402
from game.game_state import GameState  # noqa: E402
from game.world.game_map import (  # noqa: E402
    TILE_ID_FLOOR,
    TILE_ID_WALL,
    TILE_TYPES,
    GameMap,
)
from utils.shaped_map import shaped_dataframe_to_game_map  # noqa: E402

SPAWN_MIN_ROOM_SIZE = 20
SPAWN_SEARCH_RADIUS = 100
SPAWN_REQUIRE_DIAGONALS = True


class WindowManagerProtocol(Protocol):
    def show(self) -> None: ...

    def set_main_loop(self, main_loop: MainLoop) -> None: ...


class ApplicationProtocol(Protocol):
    def exec_(self) -> int: ...


def pick_player_spawn_from_df(
    df: pl.DataFrame, origin: tuple[int, int]
) -> tuple[int, int]:
    """
    Pick a spawn position (x,y) in map grid coords.
    Strategy:
      - If the DF has 'chamber_id', pick the largest chamber (most tiles),
        take its centroid.
      - Otherwise pick the first walkable / cave floor tile.
    """
    map_width: int
    map_height: int
    min_x: int
    min_y: int
    min_x, min_y = origin
    map_width = 1
    map_height = 1
    if df.height > 0 and "x" in df.columns and "y" in df.columns:
        x_coords: pl.Series = df.get_column("x")
        y_coords: pl.Series = df.get_column("y")
        x_min: float = float(x_coords.min())
        x_max: float = float(x_coords.max())
        y_min: float = float(y_coords.min())
        y_max: float = float(y_coords.max())
        map_width = max(1, int(round(x_max - x_min + 1)))
        map_height = max(1, int(round(y_max - y_min + 1)))

    def _clamp(value: int, *, upper: int) -> int:
        return max(0, min(value, upper))

    max_x: int = max(0, map_width - 1)
    max_y: int = max(0, map_height - 1)
    if "chamber_id" in df.columns:
        chamber_series: pl.Series
        chamber_ids: np.ndarray
        try:
            chamber_series = df.filter(pl.col("chamber_id") >= 0).get_column(
                "chamber_id"
            )
            chamber_ids = chamber_series.to_numpy().astype(int)
        except (ColumnNotFoundError, PolarsError, TypeError, ValueError):
            chamber_ids = np.array([], dtype=int)

        if chamber_ids.size == 0 and "chamber_id" in df.columns:
            try:
                chamber_ids = np.asarray(df["chamber_id"].to_list(), dtype=int)
                chamber_ids = chamber_ids[chamber_ids >= 0]
            except (TypeError, ValueError):
                chamber_ids = np.array([], dtype=int)

        if chamber_ids.size > 0:
            uniq: np.ndarray
            counts: np.ndarray
            uniq, counts = np.unique(chamber_ids, return_counts=True)
            top_id: int = int(uniq[np.argmax(counts)])
            chamber_rows: pl.DataFrame = df.filter(pl.col("chamber_id") == top_id)
            mean_x: float = chamber_rows.select(pl.col("x").mean()).item()
            mean_y: float = chamber_rows.select(pl.col("y").mean()).item()
            cx: int = int(round(mean_x - min_x))
            cy: int = int(round(mean_y - min_y))
            cx = _clamp(cx, upper=max_x)
            cy = _clamp(cy, upper=max_y)
            return cx, cy

    if "material_id" in df.columns:
        floors: pl.DataFrame = df.filter(
            pl.col("material_id") == int(Material.CAVE_FLOOR)
        )
        if floors.height > 0:
            tx: int = int(round(floors[0, "x"] - min_x))
            ty: int = int(round(floors[0, "y"] - min_y))
            tx = _clamp(tx, upper=max_x)
            ty = _clamp(ty, upper=max_y)
            return tx, ty

    return 1, 1


def _has_open_neighbors(
    game_map: GameMap, x: int, y: int, *, require_diagonals: bool = True
) -> bool:
    """Return True if every adjacent tile is walkable and transparent."""
    neighbors: list[tuple[int, int]] = [(0, -1), (1, 0), (0, 1), (-1, 0)]
    if require_diagonals:
        neighbors += [(1, -1), (1, 1), (-1, 1), (-1, -1)]

    for dx, dy in neighbors:
        nx: int = x + dx
        ny: int = y + dy
        if not game_map.in_bounds(nx, ny):
            return False
        if not game_map.is_walkable(nx, ny):
            return False
        if not game_map.is_transparent(nx, ny):
            return False
    return True


def _compute_component_sizes(game_map: GameMap) -> np.ndarray:
    """Label walkable components and return size per tile."""
    height: int = game_map.height
    width: int = game_map.width
    sizes: np.ndarray = np.zeros((height, width), dtype=np.int32)
    visited: np.ndarray = np.zeros((height, width), dtype=bool)
    walkable: np.ndarray = np.zeros((height, width), dtype=bool)
    for tile_id, tile_type in TILE_TYPES.items():
        if tile_type.walkable:
            walkable[game_map.tiles == tile_id] = True

    for y in range(height):
        for x in range(width):
            if visited[y, x]:
                continue
            if not walkable[y, x]:
                continue
            q: deque[tuple[int, int]] = deque()
            q.append((x, y))
            visited[y, x] = True
            component: list[tuple[int, int]] = []
            while q:
                cx, cy = q.popleft()
                component.append((cx, cy))
                for dx, dy in (
                    (0, -1),
                    (1, 0),
                    (0, 1),
                    (-1, 0),
                    (1, -1),
                    (1, 1),
                    (-1, 1),
                    (-1, -1),
                ):
                    nx: int = cx + dx
                    ny: int = cy + dy
                    if not game_map.in_bounds(nx, ny):
                        continue
                    if visited[ny, nx]:
                        continue
                    if not walkable[ny, nx]:
                        continue
                    visited[ny, nx] = True
                    q.append((nx, ny))
            size: int = len(component)
            for cx, cy in component:
                sizes[cy, cx] = size
    return sizes


def _find_nearest_suitable_spawn(
    game_map: GameMap,
    component_sizes: np.ndarray,
    start_x: int,
    start_y: int,
    *,
    max_radius: int = SPAWN_SEARCH_RADIUS,
    min_room_size: int = SPAWN_MIN_ROOM_SIZE,
    require_diagonals: bool = SPAWN_REQUIRE_DIAGONALS,
) -> tuple[int, int] | None:
    """BFS for the nearest tile that is walkable, open, and in a large area."""
    if (
        game_map.in_bounds(start_x, start_y)
        and game_map.is_walkable(start_x, start_y)
        and _has_open_neighbors(
            game_map, start_x, start_y, require_diagonals=require_diagonals
        )
        and component_sizes[start_y, start_x] >= min_room_size
    ):
        return start_x, start_y

    height: int = game_map.height
    width: int = game_map.width
    visited: np.ndarray = np.zeros((height, width), dtype=bool)
    q: deque[tuple[int, int, int]] = deque()
    q.append((start_x, start_y, 0))
    if game_map.in_bounds(start_x, start_y):
        visited[start_y, start_x] = True

    while q:
        x, y, dist = q.popleft()
        if dist > max_radius:
            continue
        for dx, dy in (
            (0, -1),
            (1, 0),
            (0, 1),
            (-1, 0),
            (1, -1),
            (1, 1),
            (-1, 1),
            (-1, -1),
        ):
            nx: int = x + dx
            ny: int = y + dy
            if not game_map.in_bounds(nx, ny):
                continue
            if visited[ny, nx]:
                continue
            visited[ny, nx] = True
            if not game_map.is_walkable(nx, ny):
                q.append((nx, ny, dist + 1))
                continue
            if not _has_open_neighbors(
                game_map, nx, ny, require_diagonals=require_diagonals
            ):
                q.append((nx, ny, dist + 1))
                continue
            if component_sizes[ny, nx] >= min_room_size:
                return nx, ny
            q.append((nx, ny, dist + 1))
    return None


def _select_spawn_position(
    game_map: GameMap,
    component_sizes: np.ndarray,
    spawn_x: int,
    spawn_y: int,
    *,
    min_room_size: int = SPAWN_MIN_ROOM_SIZE,
    search_radius: int = SPAWN_SEARCH_RADIUS,
    require_diagonals: bool = SPAWN_REQUIRE_DIAGONALS,
) -> tuple[int, int]:
    """Return a suitable spawn position, using fallback searches as needed."""
    alt: tuple[int, int] | None = _find_nearest_suitable_spawn(
        game_map,
        component_sizes,
        spawn_x,
        spawn_y,
        max_radius=search_radius,
        min_room_size=min_room_size,
        require_diagonals=require_diagonals,
    )
    if alt is not None:
        return alt

    alt2: tuple[int, int] | None = _find_nearest_suitable_spawn(
        game_map,
        component_sizes,
        spawn_x,
        spawn_y,
        max_radius=search_radius,
        min_room_size=min_room_size,
        require_diagonals=False,
    )
    if alt2 is not None:
        return alt2

    floor_rows: np.ndarray
    floor_cols: np.ndarray
    floor_rows, floor_cols = np.where(game_map.tiles == TILE_ID_FLOOR)
    if floor_rows.size > 0:
        return int(floor_cols[0]), int(floor_rows[0])
    return 1, 1


def _ascii_for_overland_material(material_id: int) -> str:
    from common.constants import Material

    mapping = {
        int(Material.ROAD): "=",
        int(Material.TRACK): ":",
        int(Material.TRAIL): ",",
        int(Material.DOCK): "D",
        int(Material.BRIDGE): "B",
        int(Material.BUILDING_FLOOR): "_",
        int(Material.WOOD_WALL): "W",
        int(Material.STONE_WALL): "#",
        int(Material.FIELD): "f",
        int(Material.ORCHARD): "o",
        int(Material.PASTURE): "p",
        int(Material.RUIN_FLOOR): "r",
        int(Material.RUIN_WALL): "R",
        int(Material.CAVE_MOUTH): "C",
        int(Material.SHALLOW_WATER): "~",
        int(Material.DEEP_WATER): "~",
        int(Material.FLOWING_WATER): "~",
        int(Material.FOREST_FLOOR): ".",
        int(Material.MUDFLAT): "m",
    }
    return mapping.get(material_id, ".")


def print_viewport(gs: GameState, radius_x: int = 12, radius_y: int = 8) -> None:
    """Print an ASCII viewport centered on the player showing local tiles."""
    gm: GameMap = gs.game_map
    player_pos: tuple[int, int] | None = gs.player_position
    if player_pos is None:
        print("Player position unknown.")
        return
    px: int
    py: int
    px, py = player_pos
    y0: int = max(0, py - radius_y)
    y1: int = min(gm.height, py + radius_y + 1)
    x0: int = max(0, px - radius_x)
    x1: int = min(gm.width, px + radius_x + 1)

    rows: list[str] = []
    for y in range(y0, y1):
        line: list[str] = []
        for x in range(x0, x1):
            if x == px and y == py:
                line.append("@")
                continue
            metadata = getattr(gm, "overland_metadata", None)
            if metadata is not None:
                mat = int(metadata.material_grid[y, x])
                line.append(_ascii_for_overland_material(mat))
                continue
            tid: int = int(gm.tiles[y, x])
            if tid == TILE_ID_FLOOR:
                line.append(".")
            elif tid == TILE_ID_WALL:
                line.append("#")
            else:
                line.append("?")
        rows.append("".join(line))
    print("\n".join(rows))
    if gs.message_log:
        print("--- Messages ---")
        for msg, _ in gs.message_log[-5:]:
            print(msg)
    print(f"Player: ({px},{py})  Map size: {gm.width}x{gm.height}")


def create_gamestate_from_arrow(
    arrow_path: Path, rng_seed: int | None = None
) -> GameState:
    """
    Create GameMap and GameState from an arrow/ipc file.
    """
    df: pl.DataFrame = pl.read_ipc(arrow_path)
    game_map: GameMap
    origin: tuple[int, int]
    game_map, origin = shaped_dataframe_to_game_map(df)

    spawn_x: int
    spawn_y: int
    spawn_x, spawn_y = pick_player_spawn_from_df(df, origin)

    component_sizes: np.ndarray = _compute_component_sizes(game_map)
    spawn_x, spawn_y = _select_spawn_position(
        game_map, component_sizes, spawn_x, spawn_y
    )

    gs = GameState(
        existing_map=game_map,
        player_start_pos=(spawn_x, spawn_y),
        player_glyph=64,
        player_start_hp=100,
        player_fov_radius=10,
        item_templates={},
        entity_templates={},
        effect_definitions={},
        rng_seed=rng_seed,
        ai_config={},
        memory_fade_config={},
        enable_sound=False,
        enable_ai=False,
    )
    return gs


def create_gamestate_from_overland(
    seed: int, width: int = 128, height: int = 96
) -> GameState:
    from game.world.start_overland import load_starting_overland_game_map

    game_map, (spawn_x, spawn_y) = load_starting_overland_game_map(
        seed=seed,
        width=width,
        height=height,
    )

    gs = GameState(
        existing_map=game_map,
        player_start_pos=(spawn_x, spawn_y),
        player_glyph=64,
        player_start_hp=100,
        player_fov_radius=10,
        item_templates={},
        entity_templates={},
        effect_definitions={},
        rng_seed=seed,
        ai_config={},
        memory_fade_config={},
        enable_sound=False,
        enable_ai=False,
    )
    return gs


class DummyWindow:
    def update_frame(self) -> None:
        return None


def run_cli_mode(arrow_path: Path | None, seed: int) -> None:
    if arrow_path:
        gs = create_gamestate_from_arrow(arrow_path, seed)
    else:
        gs = create_gamestate_from_overland(seed)

    ml: MainLoop = MainLoop(
        game_state=gs,
        window=DummyWindow(),
        vis_enabled_default=False,
        vis_max_diff=2,
        vis_color_high=[255, 255, 255],
        vis_color_mid=[160, 160, 160],
        vis_color_low=[60, 60, 60],
        vis_blend_factor=0.5,
        max_traversable_step=1,
        lighting_ambient=0.2,
        lighting_min_fov=0.0,
        lighting_falloff=1.0,
    )

    print("CLI walker started. Use WASD to move, q to quit.")
    print_viewport(gs)
    while True:
        try:
            cmd: str = input("> ").strip().lower()
        except EOFError:
            print("Input closed. Quitting.")
            break
        if not cmd:
            continue
        if cmd[0] == "q":
            print("Quitting.")
            break
        mapping: dict[str, tuple[int, int]] = {
            "w": (0, -1),
            "s": (0, 1),
            "a": (-1, 0),
            "d": (1, 0),
        }
        if cmd[0] in mapping:
            dx: int
            dy: int
            dx, dy = mapping[cmd[0]]
            action: dict[str, int | str] = {
                "type": "move",
                "dx": dx,
                "dy": dy,
            }
            try:
                ml.handle_action(action)
            except Exception as exc:
                print(f"Action error: {exc}")
            print_viewport(gs)
        else:
            print("Unknown command. Use w/a/s/d to move, q to quit.")


def _load_gui_dependencies() -> (
    tuple[type[WindowManagerProtocol], type[ApplicationProtocol]] | None
):
    if find_spec("engine.window_manager") is None:
        return None
    if find_spec("PySide6.QtWidgets") is None:
        return None
    window_manager_module = import_module("engine.window_manager")
    qt_widgets_module = import_module("PySide6.QtWidgets")
    if not hasattr(window_manager_module, "WindowManager"):
        raise AttributeError("engine.window_manager.WindowManager not found.")
    if not hasattr(qt_widgets_module, "QApplication"):
        raise AttributeError("PySide6.QtWidgets.QApplication not found.")
    window_manager = window_manager_module.WindowManager
    application = qt_widgets_module.QApplication
    return window_manager, application


def run_gui_mode(arrow_path: Path | None, seed: int) -> None:
    deps: tuple[type[WindowManagerProtocol], type[ApplicationProtocol]] | None = (
        _load_gui_dependencies()
    )
    if deps is None:
        print(
            "GUI mode requires PySide6 and engine.window_manager. Falling back to CLI."
        )
        run_cli_mode(arrow_path, seed)
        return

    window_manager_cls: type[WindowManagerProtocol]
    application_cls: type[ApplicationProtocol]
    window_manager_cls, application_cls = deps

    if arrow_path:
        gs = create_gamestate_from_arrow(arrow_path, seed)
    else:
        gs = create_gamestate_from_overland(seed)

    app: ApplicationProtocol = application_cls([])

    def _supports_no_arg_constructor(
        cls: type[WindowManagerProtocol],
    ) -> bool | None:
        try:
            signature = inspect.signature(cls)
        except (TypeError, ValueError) as exc:
            print(f"Unable to inspect WindowManager signature: {exc}")
            return None
        required_params = [
            param
            for param in signature.parameters.values()
            if param.default is inspect._empty
            and param.kind
            not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
        ]
        return len(required_params) <= 1

    def _load_app_config(cfg_path: Path) -> dict[str, object]:
        if not cfg_path.exists():
            return {}
        try:
            with cfg_path.open("r", encoding="utf-8") as fh:
                raw_config = yaml.safe_load(fh)
        except (OSError, yaml.YAMLError) as exc:
            print(f"Failed to load config YAML: {exc}")
            return {}
        if isinstance(raw_config, dict):
            return dict(raw_config)
        return {}

    def _load_keybindings_config(keybindings_path: Path) -> dict[str, object]:
        if not keybindings_path.exists():
            return {}
        try:
            with keybindings_path.open("rb") as fh:
                raw_keybindings = tomllib.load(fh)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            print(f"Failed to load keybindings TOML: {exc}")
            return {}
        if isinstance(raw_keybindings, dict):
            return dict(raw_keybindings)
        return {}

    def _safe_int(value: object, default: int, *, label: str) -> int:
        if isinstance(value, bool):
            print(f"Invalid {label} value (bool); using default {default}.")
            return default
        if isinstance(value, int | float):
            return int(value)
        if isinstance(value, str):
            text_value = value.strip()
            try:
                return int(text_value)
            except ValueError:
                print(f"Invalid {label} value '{value}'; using default {default}.")
                return default
        if value is None:
            return default
        print(
            f"Invalid {label} type '{type(value).__name__}'; using default {default}."
        )
        return default

    supports_no_arg: bool | None = _supports_no_arg_constructor(window_manager_cls)
    if supports_no_arg is True:
        wm: WindowManagerProtocol = window_manager_cls()
    else:
        base: Path = Path(__file__).parent.parent
        cfg_path: Path = base / "config" / "config.yaml"
        keybindings_path: Path = base / "config" / "keybindings.toml"

        app_config: dict[str, object] = _load_app_config(cfg_path)
        keybindings_config: dict[str, object] = _load_keybindings_config(
            keybindings_path
        )

        initial_tileset_path: str = str(
            app_config.get(
                "initial_tileset_folder", "fonts/classic_roguelike_sliced_svgs"
            )
        )
        initial_tile_width: int = _safe_int(
            app_config.get("initial_tile_width", 16),
            16,
            label="initial_tile_width",
        )
        initial_tile_height: int = _safe_int(
            app_config.get("initial_tile_height", 16),
            16,
            label="initial_tile_height",
        )

        map_width: int = _safe_int(
            app_config.get("map_width", 80),
            80,
            label="map_width",
        )
        map_height: int = _safe_int(
            app_config.get("map_height", 50),
            50,
            label="map_height",
        )
        if gs.game_map is not None:
            map_width = int(gs.game_map.width)
            map_height = int(gs.game_map.height)

        wm_args = (
            app_config,
            keybindings_config,
            initial_tileset_path,
            initial_tile_width,
            initial_tile_height,
            map_width,
            map_height,
        )
        if supports_no_arg is None:
            try:
                wm = window_manager_cls()
            except TypeError as exc:
                print(
                    "WindowManager constructor requires configuration; "
                    f"falling back to config-based init: {exc}"
                )
                wm = window_manager_cls(*wm_args)
        else:
            wm = window_manager_cls(*wm_args)
    ml: MainLoop = MainLoop(
        game_state=gs,
        window=wm,
        vis_enabled_default=True,
        vis_max_diff=2,
        vis_color_high=[255, 255, 255],
        vis_color_mid=[160, 160, 160],
        vis_color_low=[60, 60, 60],
        vis_blend_factor=0.5,
        max_traversable_step=1,
        lighting_ambient=0.2,
        lighting_min_fov=0.0,
        lighting_falloff=1.0,
    )

    wm.set_main_loop(ml)

    wm.show()
    app.exec_()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--arrow",
        "-a",
        type=Path,
        required=False,
        help="Arrow/IPCs generated by shaper",
    )
    parser.add_argument("--mode", "-m", type=str, choices=("cli", "gui"), default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--first-playable",
        action="store_true",
        help="Launch the first playable expedition loop",
    )
    args = parser.parse_args()

    arrow_path: Path | None = args.arrow

    if args.first_playable and arrow_path:
        print("Error: --first-playable cannot be used with --arrow.")
        raise SystemExit(1)

    if arrow_path and not arrow_path.exists():
        print(f"Arrow file not found: {arrow_path}")
        raise SystemExit(1)

    mode_value: str | None = args.mode
    seed: int
    if args.first_playable:
        print("First playable expedition mode: starting at ruined harbor.")
        seed = args.seed if args.seed is not None else 20260604
        mode_value = mode_value if mode_value is not None else "gui"
    else:
        seed = args.seed if args.seed is not None else 1
        mode_value = mode_value if mode_value is not None else "cli"

    if mode_value not in ("cli", "gui"):
        raise ValueError(f"Unsupported mode: {mode_value}")
    mode: Literal["cli", "gui"] = mode_value

    if mode == "cli":
        run_cli_mode(arrow_path, seed)
    else:
        run_gui_mode(arrow_path, seed)


if __name__ == "__main__":
    main()
