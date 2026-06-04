#!/usr/bin/env python3
"""Headless overland region generation route."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def generate_region(
    *,
    seed: int,
    width: int,
    height: int,
    out_dir: Path,
    overwrite: bool,
    with_starting_port: bool = False,
) -> dict[str, object]:
    from utils.game_rng import GameRNG
    from worldgen.overland import (
        generate_overland_region,
        generate_transition_requests,
        merge_settlement_into_overland,
        write_overland_bundle,
    )
    from worldgen.settlements import generate_settlement, starting_port_from_overland

    bundle = generate_overland_region(
        seed=seed,
        width=width,
        height=height,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    starting_port: dict[str, object] | None = None
    if with_starting_port:
        port_width = min(80, max(56, width - 16))
        port_height = min(56, max(40, height - 16))
        config, region, origin = starting_port_from_overland(
            bundle,
            width=port_width,
            height=port_height,
            population_target=1400,
        )
        settlement = generate_settlement(
            config,
            rng=GameRNG(seed=seed),
            region=region,
        )
        bundle = merge_settlement_into_overland(bundle, settlement, origin=origin)
        starting_port = {
            "name": settlement.metadata["name"],
            "kind": settlement.metadata["kind"],
            "origin": list(origin),
            "width": settlement.metadata["width"],
            "height": settlement.metadata["height"],
        }
    paths = write_overland_bundle(bundle, out_dir, overwrite=overwrite)
    transition_count = len(generate_transition_requests(bundle))
    summary: dict[str, object] = {
        "seed": seed,
        "width": width,
        "height": height,
        "profile": bundle.metadata["profile"],
        "tile_rows": bundle.tiles_df.height,
        "hydrology_rows": bundle.hydrology_df.height,
        "feature_rows": bundle.features_df.height,
        "affordance_rows": bundle.affordances_df.height,
        "transition_rows": transition_count,
        "artifacts": {key: str(path) for key, path in paths.items()},
    }
    if starting_port is not None:
        summary["starting_port"] = starting_port
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a karst-to-volcanic overland bundle."
    )
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--height", type=int, default=72)
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/overland/karst_volcanic"))
    parser.add_argument("--with-starting-port", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    print(
        json.dumps(
            generate_region(
                seed=args.seed,
                width=args.width,
                height=args.height,
                out_dir=args.out_dir,
                overwrite=args.overwrite,
                with_starting_port=args.with_starting_port,
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
