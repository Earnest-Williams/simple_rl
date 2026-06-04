from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from worldgen.overland.schema import OverlandBundle

OVERLAND_FILES: dict[str, str] = {
    "tiles_df": "overland_tiles.arrow",
    "hydrology_df": "overland_hydrology.arrow",
    "features_df": "overland_features.arrow",
    "affordances_df": "overland_affordances.arrow",
}


def write_overland_bundle(
    bundle: OverlandBundle,
    out_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for attr, filename in OVERLAND_FILES.items():
        path = out_dir / filename
        _check_writable(path, overwrite=overwrite)
        getattr(bundle, attr).write_ipc(path)
        paths[attr] = path
    metadata_path = out_dir / "overland_metadata.json"
    _check_writable(metadata_path, overwrite=overwrite)
    metadata_path.write_text(
        json.dumps(
            {
                **bundle.metadata,
                "artifacts": {key: path.name for key, path in paths.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )
    paths["metadata"] = metadata_path
    return paths


def load_worldgen_bundle(out_dir: Path) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": out_dir}
    for key, filename in {
        **OVERLAND_FILES,
        "settlement_map_df": "settlement_map.arrow",
        "settlement_entrances_df": "settlement_entrances.arrow",
    }.items():
        path = out_dir / filename
        if path.exists():
            payload[key] = pl.read_ipc(path)
    for metadata_name in ("overland_metadata.json", "settlement_metadata.json"):
        path = out_dir / metadata_name
        if path.exists():
            payload[metadata_name.removesuffix(".json")] = json.loads(path.read_text())
    return payload


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
