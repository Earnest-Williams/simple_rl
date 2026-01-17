"""Run the GOAP auto headless harness and emit a JSON summary."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter

from utils.game_rng import GameRNG

from auto import main as auto_main
from auto import simulation as auto_simulation


def _apply_max_turns_override(max_turns: int | None) -> None:
    if max_turns is None:
        return
    auto_simulation.MAX_TURNS = max_turns
    auto_main.MAX_TURNS = max_turns


def run_regression(
    *,
    seed: int,
    num_runs: int = 3,
    max_turns: int | None = None,
) -> dict[str, object]:
    _apply_max_turns_override(max_turns)
    start_time = time.time()

    master_rng = GameRNG(seed=seed)
    run_seeds = [master_rng.get_int(0, 2**32 - 1) for _ in range(num_runs)]

    results: list[tuple[int, dict[str, float], str]] = []
    for run_id, run_seed in enumerate(run_seeds, start=1):
        results.append(auto_main.run_single_headless((run_id, None, run_seed)))

    turns_survived = [entry[0] for entry in results]
    outcomes = [entry[2] for entry in results]
    outcome_counts = Counter(outcomes)
    elapsed_s = time.time() - start_time

    summary = {
        "seed": seed,
        "num_runs": num_runs,
        "completed_runs": len(results),
        "max_turns": auto_main.MAX_TURNS,
        "average_turns": (sum(turns_survived) / len(turns_survived)) if turns_survived else 0.0,
        "min_turns": min(turns_survived) if turns_survived else 0,
        "max_turns_survived": max(turns_survived) if turns_survived else 0,
        "outcomes": dict(outcome_counts),
        "runs": [
            {"run": run_id, "seed": run_seed, "turns_survived": turns, "outcome": outcome}
            for run_id, run_seed, (turns, _weights, outcome) in zip(
                range(1, num_runs + 1), run_seeds, results
            )
        ],
        "elapsed_seconds": elapsed_s,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the GOAP auto headless harness and emit JSON."
    )
    parser.add_argument("--seed", type=int, default=1337, help="Seed for reproducibility.")
    parser.add_argument(
        "-n",
        "--num-runs",
        type=int,
        default=3,
        help="Number of headless runs to execute.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=None,
        help="Override MAX_TURNS for a shorter run.",
    )
    args = parser.parse_args()

    summary = run_regression(seed=args.seed, num_runs=args.num_runs, max_turns=args.max_turns)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
