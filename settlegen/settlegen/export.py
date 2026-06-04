from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from .model import Settlement, TERRAIN_NAMES

try:  # optional Rust-backed analytics/export dependency
    import polars as pl

    POLARS_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    pl = None  # type: ignore
    POLARS_AVAILABLE = False


def settlement_to_polars(settlement: Settlement):
    """Return Polars DataFrames for buildings, districts, and summary.

    This function imports Polars lazily. Games that do not use analytics can
    avoid the optional dependency entirely.
    """
    if not POLARS_AVAILABLE:
        raise RuntimeError("Polars is not installed. Install with: pip install settlegen[analytics]")
    buildings = pl.DataFrame(list(settlement.iter_building_records()))
    districts = pl.DataFrame(
        [
            {
                "id": d.id,
                "kind": d.kind,
                "center_x": d.center[0],
                "center_y": d.center[1],
                "radius": d.radius,
                "wealth": d.wealth,
                "tags": ";".join(d.tags),
            }
            for d in settlement.districts
        ]
    )
    summary = pl.DataFrame(
        [
            {"metric": "population", "value": settlement.population},
            {"metric": "buildings", "value": len(settlement.buildings)},
            {"metric": "districts", "value": len(settlement.districts)},
            {"metric": "roads", "value": len(settlement.roads)},
            {"metric": "magic_sites", "value": len(settlement.magic_sites)},
        ]
    )
    return {"buildings": buildings, "districts": districts, "summary": summary}


def write_json(settlement: Settlement, path: str | Path, *, include_grids: bool = False) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settlement.to_dict(include_grids=include_grids), indent=2), encoding="utf-8")
    return path


def write_grids_npz(settlement: Settlement, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        path,
        terrain=settlement.terrain,
        overlay=settlement.overlay,
        combined=settlement.combined_grid(),
    )
    return path


def write_buildings_csv(settlement: Settlement, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(settlement.iter_building_records())
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    if POLARS_AVAILABLE:
        pl.DataFrame(rows).write_csv(path)
        return path
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_tile_legend(path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{"code": code, "name": name} for code, name in sorted(TERRAIN_NAMES.items())]
    if POLARS_AVAILABLE:
        pl.DataFrame(rows).write_csv(path)
    else:
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["code", "name"])
            writer.writeheader()
            writer.writerows(rows)
    return path


def write_bundle(settlement: Settlement, directory: str | Path, *, include_json_grids: bool = False) -> dict[str, Path]:
    """Write a game-friendly bundle: metadata JSON, compressed grids, CSV tables."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    return {
        "json": write_json(settlement, directory / "settlement.json", include_grids=include_json_grids),
        "grids": write_grids_npz(settlement, directory / "grids.npz"),
        "buildings": write_buildings_csv(settlement, directory / "buildings.csv"),
        "legend": write_tile_legend(directory / "tile_legend.csv"),
    }
