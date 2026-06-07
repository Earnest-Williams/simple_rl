#!/usr/bin/env python3
"""Headless settlement generation route for inspection and regression tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def generate_starting_port(
    *,
    seed: int,
    out_dir: Path,
    width: int,
    height: int,
    population: int,
    overwrite: bool,
) -> dict[str, object]:
    from utils.game_rng import GameRNG
    from worldgen.settlements import (
        RegionConstraints,
        generate_settlement,
        starting_port_config,
        write_settlement_bundle,
    )

    bundle = generate_settlement(
        starting_port_config(
            width=width,
            height=height,
            population_target=population,
        ),
        rng=GameRNG(seed=seed),
        region=RegionConstraints(
            coastline="south",
            river_mouth=(width // 2, height - 1),
            road_endpoints=((width // 2, 0),),
            cave_entrances=((width // 3, height // 2),),
            faction="port_authority",
            trade_route_importance=1.0,
        ),
    )
    paths = write_settlement_bundle(bundle, out_dir, overwrite=overwrite)
    return {
        "seed": seed,
        "out_dir": str(out_dir),
        "name": bundle.metadata["name"],
        "population": bundle.metadata["population"],
        "map_rows": bundle.map_df.height,
        "building_rows": bundle.buildings_df.height,
        "district_rows": bundle.districts_df.height,
        "road_rows": bundle.roads_df.height,
        "entrance_rows": bundle.entrances_df.height,
        "artifacts": {key: str(path) for key, path in paths.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a settlement bundle without starting the UI."
    )
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--out-dir", type=Path, default=Path("tmp/settlements/starting_port")
    )
    parser.add_argument("--width", type=int, default=160)
    parser.add_argument("--height", type=int, default=112)
    parser.add_argument("--population", type=int, default=2200)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    summary = generate_starting_port(
        seed=args.seed,
        out_dir=args.out_dir,
        width=args.width,
        height=args.height,
        population=args.population,
        overwrite=args.overwrite,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
