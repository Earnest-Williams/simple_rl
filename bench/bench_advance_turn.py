from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.game_state import GameState


def build_state(
    *,
    width: int,
    height: int,
    entities: int,
    fov_radius: int,
    seed: int,
) -> "GameState":
    from game.game_state import GameState
    from game.world.game_map import TILE_ID_FLOOR, GameMap

    game_map = GameMap(width, height)
    game_map.tiles.fill(TILE_ID_FLOOR)
    game_map.update_tile_transparency()

    player_pos = (width // 2, height // 2)
    state = GameState(
        existing_map=game_map,
        player_start_pos=player_pos,
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=fov_radius,
        item_templates={},
        rng_seed=seed,
        enable_sound=False,
        enable_ai=True,
    )
    state.entity_registry.set_entity_component(state.player_id, "faction", "heroes")

    created = 0
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if (x, y) == player_pos:
                continue
            state.entity_registry.create_entity(
                x=x,
                y=y,
                glyph=101,
                color_fg=(255, 0, 0),
                name=f"Enemy {created}",
                ai_type="goap",
                species="enemy",
                faction="monsters",
            )
            created += 1
            if created >= entities:
                return state

    raise ValueError(f"map {width}x{height} does not fit {entities} AI entities")


def run_turns(state: "GameState", turns: int) -> None:
    for _ in range(turns):
        state.advance_turn()


@contextmanager
def suppress_runtime_output(enabled: bool):
    if not enabled:
        yield
        return

    sink = io.StringIO()
    with redirect_stdout(sink), redirect_stderr(sink):
        yield


def bench(
    *,
    width: int,
    height: int,
    entities: int,
    turns: int,
    warmup_turns: int,
    fov_radius: int,
    seed: int,
    top: int,
    quiet_runtime: bool,
) -> None:
    with suppress_runtime_output(quiet_runtime):
        state = build_state(
            width=width,
            height=height,
            entities=entities,
            fov_radius=fov_radius,
            seed=seed,
        )
        run_turns(state, warmup_turns)

    profiler = cProfile.Profile()
    with suppress_runtime_output(quiet_runtime):
        start = time.perf_counter()
        profiler.enable()
        run_turns(state, turns)
        profiler.disable()
        elapsed = time.perf_counter() - start

    print(
        "advance_turn benchmark:",
        f"entities={entities}",
        f"map={width}x{height}",
        f"warmup_turns={warmup_turns}",
        f"measured_turns={turns}",
        f"total={elapsed:.3f}s",
        f"avg={elapsed * 1000 / turns:.2f}ms/turn",
        f"turns_per_second={turns / elapsed:.2f}",
    )

    stats_output = io.StringIO()
    stats = pstats.Stats(profiler, stream=stats_output).strip_dirs().sort_stats(
        "cumulative"
    )
    stats.print_stats(top)
    print(stats_output.getvalue())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile GameState.advance_turn().")
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--height", type=int, default=80)
    parser.add_argument("--entities", type=int, default=200)
    parser.add_argument("--turns", type=int, default=10)
    parser.add_argument("--warmup-turns", type=int, default=3)
    parser.add_argument("--fov-radius", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument(
        "--verbose-runtime",
        action="store_true",
        help="Show engine logs during setup and turns.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    bench(
        width=args.width,
        height=args.height,
        entities=args.entities,
        turns=args.turns,
        warmup_turns=args.warmup_turns,
        fov_radius=args.fov_radius,
        seed=args.seed,
        top=args.top,
        quiet_runtime=not args.verbose_runtime,
    )
