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
) -> dict[str, object]:
    from worldgen.overland import generate_overland_region, write_overland_bundle

    bundle = generate_overland_region(
        seed=seed,
        width=width,
        height=height,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    paths = write_overland_bundle(bundle, out_dir, overwrite=overwrite)
    return {
        "seed": seed,
        "width": width,
        "height": height,
        "profile": bundle.metadata["profile"],
        "tile_rows": bundle.tiles_df.height,
        "hydrology_rows": bundle.hydrology_df.height,
        "feature_rows": bundle.features_df.height,
        "affordance_rows": bundle.affordances_df.height,
        "artifacts": {key: str(path) for key, path in paths.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a karst-to-volcanic overland bundle."
    )
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--height", type=int, default=72)
    parser.add_argument("--out-dir", type=Path, default=Path("tmp/overland/karst_volcanic"))
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
            ),
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
