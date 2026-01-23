from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Tuple

import numpy as np


@dataclass
class LayerMeta:
    path: str
    dtype: str
    shape: Tuple[int, ...]
    units: str | None = None
    sentinel: int | float | None = None

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "path": self.path,
            "dtype": self.dtype,
            "shape": list(self.shape),
        }
        if self.units is not None:
            payload["units"] = self.units
        if self.sentinel is not None:
            payload["sentinel"] = self.sentinel
        return payload


@dataclass
class WorldMeta:
    format_version: str
    world_seed: int
    N: int
    n_cells: int
    planet_radius_m: float
    elev_quantum_m: float
    layers: Dict[str, LayerMeta] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        layers_payload: Dict[str, object] = {
            key: value.to_dict() for key, value in sorted(self.layers.items())
        }
        return {
            "format_version": self.format_version,
            "world_seed": self.world_seed,
            "N": self.N,
            "n_cells": self.n_cells,
            "planet_radius_m": self.planet_radius_m,
            "elev_quantum_m": self.elev_quantum_m,
            "layers": layers_payload,
        }

    def write(self, out_dir: Path) -> Path:
        if not out_dir.exists():
            raise FileNotFoundError("out_dir must exist before writing meta.json")
        payload: Dict[str, object] = self.to_dict()
        path: Path = out_dir / "meta.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path


def build_world_meta(
    *,
    world_seed: int,
    N: int,
    planet_radius_m: float,
    elev_quantum_m: float,
    format_version: str = "0.1.0",
) -> WorldMeta:
    if N <= 0:
        raise ValueError("N must be > 0")
    if planet_radius_m <= 0.0:
        raise ValueError("planet_radius_m must be > 0")
    if elev_quantum_m <= 0.0:
        raise ValueError("elev_quantum_m must be > 0")
    n_cells: int = 6 * N * N
    return WorldMeta(
        format_version=format_version,
        world_seed=world_seed,
        N=N,
        n_cells=n_cells,
        planet_radius_m=planet_radius_m,
        elev_quantum_m=elev_quantum_m,
        layers={},
    )


def dtype_to_str(dtype: np.dtype[np.generic]) -> str:
    return str(dtype)
