#!/usr/bin/env python3
# tools/play_from_arrow.py
"""
Play a generated shaped map.

Usage:
    # CLI (no GUI required)
    python tools/play_from_arrow.py --arrow generated_dungeon.arrow --mode cli

    # GUI (requires PySide6 and engine assets)
    python tools/play_from_arrow.py --arrow generated_dungeon.arrow --mode gui
"""
from __future__ import annotations

import argparse
from importlib import import_module
from importlib.util import find_spec
from pathlib import Path
from typing import Literal, Protocol, Tuple

import numpy as np
import polars as pl
from polars.exceptions import ColumnNotFoundError, PolarsError

from common.constants import Material
from engine.main_loop import MainLoop
from game.game_state import GameState
from game.world.game_map import GameMap, TILE_ID_FLOOR, TILE_ID_WALL
from utils.shaped_map import shaped_dataframe_to_game_map


class WindowManagerProtocol(Protocol):
    def show(self) -> None:
        ...

    def set_main_loop(self, main_loop: MainLoop) -> None:
        ...


class ApplicationProtocol(Protocol):
    def exec_(self) -> int:
        ...


def pick_player_spawn_from_df(
    df: pl.DataFrame, origin: Tuple[int, int]
) -> Tuple[int, int]:
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


def print_viewport(gs: GameState, radius_x: int = 12, radius_y: int = 8) -> None:
    """Print an ASCII viewport centered on the player showing local tiles."""
    gm: GameMap = gs.game_map
    player_pos: Tuple[int, int] | None = gs.player_position
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
        for msg, color in gs.message_log[-5:]:
            print(msg)
    print(f"Player: ({px},{py})  Map size: {gm.width}x{gm.height}")


def create_gamestate_from_arrow(
    arrow_path: Path, rng_seed: int | None = None
) -> Tuple[GameState, pl.DataFrame, Tuple[int, int]]:
    """
    Create GameMap and GameState from an arrow/ipc file.
    Returns (GameState, dataframe, origin)
    """
    df: pl.DataFrame = pl.read_ipc(arrow_path)
    game_map: GameMap
    origin: Tuple[int, int]
    game_map, origin = shaped_dataframe_to_game_map(df)
    spawn_x: int
    spawn_y: int
    spawn_x, spawn_y = pick_player_spawn_from_df(df, origin)

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
    return gs, df, origin


class DummyWindow:
    def update_frame(self) -> None:
        return None


def run_cli_mode(arrow_path: Path) -> None:
    gs: GameState
    _df: pl.DataFrame
    _origin: Tuple[int, int]
    gs, _df, _origin = create_gamestate_from_arrow(arrow_path)

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
        mapping: dict[str, Tuple[int, int]] = {
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


def _load_gui_dependencies(
) -> tuple[type[WindowManagerProtocol], type[ApplicationProtocol]] | None:
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
    window_manager = getattr(window_manager_module, "WindowManager")
    application = getattr(qt_widgets_module, "QApplication")
    return window_manager, application


def run_gui_mode(arrow_path: Path) -> None:
    deps: (
        tuple[type[WindowManagerProtocol], type[ApplicationProtocol]] | None
    ) = _load_gui_dependencies()
    if deps is None:
        print(
            "GUI mode requires PySide6 and engine.window_manager. Falling back to CLI."
        )
        run_cli_mode(arrow_path)
        return

    window_manager_cls: type[WindowManagerProtocol]
    application_cls: type[ApplicationProtocol]
    window_manager_cls, application_cls = deps

    gs: GameState
    _df: pl.DataFrame
    _origin: Tuple[int, int]
    gs, _df, _origin = create_gamestate_from_arrow(arrow_path)

    app: ApplicationProtocol = application_cls([])
    wm: WindowManagerProtocol = window_manager_cls()
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
        required=True,
        help="Arrow/IPCs generated by shaper",
    )
    parser.add_argument("--mode", "-m", type=str, choices=("cli", "gui"), default="cli")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    arrow_path: Path = args.arrow
    if not arrow_path.exists():
        print(f"Arrow file not found: {arrow_path}")
        raise SystemExit(1)

    mode_value: str = args.mode
    if mode_value not in ("cli", "gui"):
        raise ValueError(f"Unsupported mode: {mode_value}")
    mode: Literal["cli", "gui"] = mode_value

    if mode == "cli":
        run_cli_mode(arrow_path)
    else:
        run_gui_mode(arrow_path)


if __name__ == "__main__":
    main()
