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
        choices=("material", "biome", "hydro", "wetness", "traversal", "actor", "evidence"),
        default="material",
    )
    parser.add_argument("--profile", default="HUMAN_ON_FOOT")
    args = parser.parse_args()

    if args.view == "evidence":
        _inspect_evidence(args.path)
        return

    from worldgen.overland import ActorTraversalProfile, render_overland_ascii

    tiles_path = args.path
    if args.path.is_dir():
        tiles_path = args.path / "overland_tiles.arrow"
    profile = ActorTraversalProfile[args.profile.upper()]
    print(
        render_overland_ascii(pl.read_ipc(tiles_path), view=args.view, profile=profile)
    )


def _inspect_evidence(path: Path) -> None:
    from worldgen.overland.schema import (
        EvidenceTag,
        FeatureType,
        RouteSegmentState,
        TransitionType,
    )

    dir_path = path if path.is_dir() else path.parent

    features_path = dir_path / "overland_features.arrow"
    if features_path.exists():
        df = pl.read_ipc(features_path)
        df_with_evidence = df.filter(pl.col("evidence_tags").list.len() > 0)
        if not df_with_evidence.is_empty():
            print("=== FEATURES WITH EVIDENCE TAGS ===")
            for row in df_with_evidence.iter_rows(named=True):
                try:
                    f_type = FeatureType(row["feature_type"]).name
                except ValueError:
                    f_type = str(row["feature_type"])
                tags_str = ", ".join(EvidenceTag(tag).name for tag in row["evidence_tags"])
                print(f"({row['x']}, {row['y']}) {f_type}: {tags_str}")
            print()

    transitions_path = dir_path / "overland_transitions.arrow"
    if transitions_path.exists():
        df = pl.read_ipc(transitions_path)
        df_with_evidence = df.filter(pl.col("evidence_tags").list.len() > 0)
        if not df_with_evidence.is_empty():
            print("=== TRANSITIONS WITH EVIDENCE TAGS ===")
            for row in df_with_evidence.iter_rows(named=True):
                try:
                    t_type = TransitionType(row["transition_type"]).name
                except ValueError:
                    t_type = str(row["transition_type"])
                tags_str = ", ".join(EvidenceTag(tag).name for tag in row["evidence_tags"])
                print(
                    f"({row['source_x']}, {row['source_y']}) {t_type} -> {row['target_kind']}: {tags_str}"
                )
            print()

    metadata_path = dir_path / "overland_metadata.json"
    if metadata_path.exists():
        import json

        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            route_segments = metadata.get("route_segments") or metadata.get(
                "starting_region_contract", {}
            ).get("route_segments", [])
            if route_segments:
                print("=== ROUTE SEGMENTS WITH EVIDENCE TAGS ===")
                for seg in route_segments:
                    evidence = seg.get("evidence_tags", [])
                    if evidence:
                        try:
                            state_name = RouteSegmentState(seg["state"]).name
                        except ValueError:
                            state_name = str(seg["state"])
                        tags_str = ", ".join(EvidenceTag(tag).name for tag in evidence)
                        from_pt = seg.get("from_point") or seg.get("from")
                        to_pt = seg.get("to_point") or seg.get("to")
                        print(
                            f"Route '{seg['route_id']}' from {from_pt} to {to_pt} [{state_name}]: {tags_str}"
                        )
                print()
        except Exception as e:
            print(f"Error parsing metadata.json: {e}")

    routes_path = dir_path / "overland_routes.arrow"
    if routes_path.exists():
        df = pl.read_ipc(routes_path)
        df_with_evidence = df.filter(pl.col("evidence_tags").list.len() > 0).unique(
            subset=["route_id"]
        )
        if not df_with_evidence.is_empty():
            print("=== DEBUG ROUTES WITH EVIDENCE TAGS ===")
            for row in df_with_evidence.iter_rows(named=True):
                tags_str = ", ".join(EvidenceTag(tag).name for tag in row["evidence_tags"])
                print(
                    f"Route '{row['route_id']}' ({row['source_x']}, {row['source_y']}) to ({row['target_x']}, {row['target_y']}): {tags_str}"
                )
            print()


if __name__ == "__main__":
    main()
