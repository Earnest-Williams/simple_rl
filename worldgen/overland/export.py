from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from worldgen.overland.routes import generate_debug_routes, overland_routes_to_df
from worldgen.overland.schema import OverlandBundle
from worldgen.overland.transitions import (
    generate_transition_requests,
    transition_requests_to_df,
)

OVERLAND_FILES: dict[str, str] = {
    "tiles_df": "overland_tiles.arrow",
    "hydrology_df": "overland_hydrology.arrow",
    "features_df": "overland_features.arrow",
    "affordances_df": "overland_affordances.arrow",
}

COMPUTED_OVERLAND_FILES: dict[str, str] = {
    "transitions_df": "overland_transitions.arrow",
    "routes_df": "overland_routes.arrow",
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
    transitions_path = out_dir / COMPUTED_OVERLAND_FILES["transitions_df"]
    _check_writable(transitions_path, overwrite=overwrite)
    transition_requests_to_df(generate_transition_requests(bundle)).write_ipc(
        transitions_path
    )
    paths["transitions_df"] = transitions_path
    routes_path = out_dir / COMPUTED_OVERLAND_FILES["routes_df"]
    _check_writable(routes_path, overwrite=overwrite)
    overland_routes_to_df(generate_debug_routes(bundle)).write_ipc(routes_path)
    paths["routes_df"] = routes_path
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
        **COMPUTED_OVERLAND_FILES,
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
