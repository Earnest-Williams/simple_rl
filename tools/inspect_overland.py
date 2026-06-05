#!/usr/bin/env python3
"""Render generated overland Arrow artifacts as CI-friendly ASCII."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect overland_tiles.arrow.")
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--view",
        choices=("material", "biome", "hydro", "wetness", "traversal", "actor"),
        default="material",
    )
    parser.add_argument("--profile", default="HUMAN_ON_FOOT")
    args = parser.parse_args()

    from worldgen.overland import ActorTraversalProfile, render_overland_ascii

    tiles_path = args.path
    if args.path.is_dir():
        tiles_path = args.path / "overland_tiles.arrow"
    profile = ActorTraversalProfile[args.profile.upper()]
    print(
        render_overland_ascii(pl.read_ipc(tiles_path), view=args.view, profile=profile)
    )


if __name__ == "__main__":
    main()
