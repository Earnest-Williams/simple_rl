from __future__ import annotations

import logging
import os
import time

import numpy as np

from lights_dev import constants
from lights_dev.fov import FOVSystem
from lights_dev.game_state import GameState, find_path
from lights_dev.lighting import LightingSystem
from lights_dev.memory import precompile as precompile_memory
from lights_dev.renderer import Renderer
from utils.game_rng import GameRNG

try:
    import readchar

    READCHAR_AVAILABLE = True
except ImportError:
    READCHAR_AVAILABLE = False


def run_simulation() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    is_profiling = os.environ.get("MY_PROFILER_RUNNING", "0") == "1"
    is_interactive = READCHAR_AVAILABLE and not is_profiling
    if not is_interactive and not is_profiling:
        print("ERROR: Need 'readchar' or profiler mode.")
        return

    print(f"--- Running in {'PROFILER' if is_profiling else 'INTERACTIVE'} mode ---")
    print(f"--- Debug Render Mode: {constants.DEBUG_RENDER_MODE} ---")

    main_seed = 12345 if is_profiling else int(time.time() * 1000)
    rng_instance = GameRNG(seed=main_seed)
    print(f"--- Using RNG Seed: {main_seed} ---")

    game_state = GameState(80, 30, rng_instance)
    try:
        game_state.initialize_map_and_entities()
    except Exception as exc:
        logging.exception("Map init failed!")
        print(f"\nERROR: {exc}")
        print("\033[?25h")
        return

    print("Pre-compiling Numba functions...")
    if game_state.dungeon and game_state.player:
        try:
            FOVSystem.precompile(game_state.dungeon, game_state.player.position)
            LightingSystem.precompile(game_state.dungeon, game_state.player.position)
            precompile_memory(game_state.dungeon.height, game_state.dungeon.width)
        except Exception as exc:
            logging.exception("Numba pre-compile error!")
            print(f"\nWARNING: {exc}")
    elif not game_state.player:
        print("WARNING: Player missing, skipping pre-compile.")
    print("Pre-compilation finished.")

    frame_count = 0
    start_time = time.time()
    last_frame_time = start_time
    target_duration = 60 if is_profiling else 300
    total_update_vis_time = 0.0
    last_key_pressed = ""
    profiler_path: list[tuple[int, int]] | None = None
    profiler_path_index = 0
    profiler_target_x = (
        game_state.dungeon.width - 6
        if game_state.player and game_state.player.x < game_state.dungeon.width // 2
        else 5
    )
    last_profiler_move_time = start_time
    profiler_move_delay = 0.01

    renderer = Renderer(constants.DEBUG_RENDER_MODE)

    try:
        while time.time() - start_time < target_duration:
            current_frame_time = time.time()
            dt = min(current_frame_time - last_frame_time, 0.1)
            last_frame_time = current_frame_time
            player_moved = False
            quit_flag = False

            if is_profiling:
                if current_frame_time - last_profiler_move_time >= profiler_move_delay:
                    if profiler_path and profiler_path_index < len(profiler_path):
                        next_pos = profiler_path[profiler_path_index]
                        if game_state.player:
                            game_state.player.x, game_state.player.y = next_pos
                        profiler_path_index += 1
                        player_moved = True
                        last_profiler_move_time = current_frame_time
                    elif game_state.player:
                        start_pos = game_state.player.position
                        target_pos = (profiler_target_x, start_pos[1])
                        if start_pos != target_pos:
                            profiler_path = find_path(
                                start_pos,
                                target_pos,
                                game_state.dungeon.tiles,
                                game_state.dungeon.width,
                                game_state.dungeon.height,
                            )
                            if profiler_path and len(profiler_path) > 1:
                                profiler_path_index = 1
                                next_pos = profiler_path[profiler_path_index]
                                game_state.player.x, game_state.player.y = next_pos
                                profiler_path_index += 1
                                player_moved = True
                                last_profiler_move_time = current_frame_time
                                profiler_target_x = (
                                    5
                                    if profiler_target_x
                                    > game_state.dungeon.width // 2
                                    else game_state.dungeon.width - 6
                                )
                            else:
                                profiler_path = None
                                profiler_target_x = (
                                    5
                                    if profiler_target_x
                                    > game_state.dungeon.width // 2
                                    else game_state.dungeon.width - 6
                                )
                        else:
                            profiler_target_x = (
                                5
                                if profiler_target_x > game_state.dungeon.width // 2
                                else game_state.dungeon.width - 6
                            )
                            profiler_path = None
            elif is_interactive and READCHAR_AVAILABLE:
                print("Move (WASD/Arrows/Numpad 1-9), Q to quit: ", end="", flush=True)
                key = readchar.readkey()
                last_key_pressed = key
                print(" " * 50, end="\r")
                dx, dy = 0, 0
                if key.lower() == "q":
                    quit_flag = True
                elif key == readchar.key.UP or key == "w" or key == "8":
                    dy = -1
                elif key == readchar.key.DOWN or key == "s" or key == "2":
                    dy = 1
                elif key == readchar.key.LEFT or key == "a" or key == "4":
                    dx = -1
                elif key == readchar.key.RIGHT or key == "d" or key == "6":
                    dx = 1
                elif key == "7" or key == readchar.key.HOME:
                    dx, dy = -1, -1
                elif key == "9" or key == readchar.key.PAGE_UP:
                    dx, dy = 1, -1
                elif key == "1" or key == readchar.key.END:
                    dx, dy = -1, 1
                elif key == "3" or key == readchar.key.PAGE_DOWN:
                    dx, dy = 1, 1
                elif key == "5" or key == readchar.key.CLEAR or key == ".":
                    dx, dy = 0, 0
                if quit_flag:
                    break
                if (dx != 0 or dy != 0) and game_state.player:
                    target_x = game_state.player.x + dx
                    target_y = game_state.player.y + dy
                    if (
                        0 <= target_x < game_state.dungeon.width
                        and 0 <= target_y < game_state.dungeon.height
                        and game_state.dungeon.tiles[target_y, target_x]
                        == constants.FLOOR_ID
                    ):
                        game_state.player.x = target_x
                        game_state.player.y = target_y
                        player_moved = True
                elif not quit_flag:
                    player_moved = True
            if quit_flag:
                break

            update_start_time = time.perf_counter()
            game_state.update(dt)
            update_time = time.perf_counter() - update_start_time
            if is_profiling or player_moved:
                vis_start_time = time.perf_counter()
                game_state.update_visibility()
                vis_end_time = time.perf_counter()
                frame_vis_time = vis_end_time - vis_start_time
                total_update_vis_time += frame_vis_time
            else:
                frame_vis_time = 0
            render_start_time = time.perf_counter()
            rendered_map = renderer.render(game_state)
            render_end_time = time.perf_counter()
            render_time = render_end_time - render_start_time
            print("\033[H\033[J", end="")
            print(rendered_map)

            update_count = frame_count + 1
            avg_vis_time_ms = (
                (total_update_vis_time / update_count) * 1000 if update_count > 0 else 0
            )
            mode_str = "PROFILER" if is_profiling else "INTERACTIVE"
            debug_str = (
                f" (Debug: {constants.DEBUG_RENDER_MODE})"
                if constants.DEBUG_RENDER_MODE != "normal"
                else ""
            )
            print(
                f"\nMode: {mode_str}{debug_str} | Sim Time: {game_state.dungeon.current_time:.1f}s / {target_duration:.0f}s | Frame: {frame_count + 1}"
            )
            print(
                f"Frame Times (ms): Render={render_time * 1000:.1f}, VisUpdate={frame_vis_time * 1000:.2f}, StateUpdate={update_time * 1000:.2f} | Avg Vis: {avg_vis_time_ms:.3f}ms | DeltaT: {dt * 1000:.1f}ms"
            )
            if game_state.player:
                p_mem = 0.0
                try:
                    p_mem = game_state.dungeon.memory_intensity[
                        game_state.player.y, game_state.player.x
                    ]
                except IndexError:
                    logging.warning("Player index error mem check.")
                    p_mem = -1.0
                status_line = (
                    f"Player @ {game_state.player.position} (Lvl:{game_state.player.light_level}, "
                    f"R:{game_state.player.light_radius}) | Mem@P: {p_mem:.2f}"
                )
                if is_interactive:
                    status_line += f" | Last key: '{last_key_pressed}'"
                print(status_line)
            if is_profiling:
                print("Profiler running... Press Ctrl+C to exit.")
            frame_count += 1
    except KeyboardInterrupt:
        print("\nSimulation stopped by user (Ctrl+C).")
    except Exception:
        print("\033[?25h")
        print("\n--- ERROR ---")
        logging.exception("Error during loop:")
        print("-------------")
    finally:
        print("\033[?25h")
        print("Simulation finished.")
