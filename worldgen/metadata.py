from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, field_validator


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
    global_tunables_hash: str | None = None
    chunk_tunables_hash: str | None = None

    def to_dict(self) -> Dict[str, object]:
        layers_payload: Dict[str, object] = {
            key: value.to_dict() for key, value in sorted(self.layers.items())
        }
        payload: Dict[str, object] = {
            "format_version": self.format_version,
            "world_seed": self.world_seed,
            "N": self.N,
            "n_cells": self.n_cells,
            "planet_radius_m": self.planet_radius_m,
            "elev_quantum_m": self.elev_quantum_m,
            "layers": layers_payload,
        }
        if self.global_tunables_hash is not None:
            payload["global_tunables_hash"] = self.global_tunables_hash
        if self.chunk_tunables_hash is not None:
            payload["chunk_tunables_hash"] = self.chunk_tunables_hash
        return payload

    def write(self, out_dir: Path) -> Path:
        if not out_dir.exists():
            raise FileNotFoundError("out_dir must exist before writing meta.json")
        payload: Dict[str, object] = self.to_dict()
        path: Path = out_dir / "meta.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path


class LayerMetaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    dtype: str
    shape: List[int]
    units: str | None = None
    sentinel: int | float | None = None

    @field_validator("shape")
    @classmethod
    def _shape_ints(cls, value: List[int]) -> List[int]:
        for item in value:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError("shape entries must be integers")
        return value

    @field_validator("sentinel")
    @classmethod
    def _sentinel_not_bool(
        cls, value: int | float | None
    ) -> int | float | None:
        if isinstance(value, bool):
            raise ValueError("sentinel must be a number or null")
        return value


class WorldMetaModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format_version: str
    world_seed: int
    N: int
    n_cells: int
    planet_radius_m: float
    elev_quantum_m: float
    layers: Dict[str, LayerMetaModel]
    global_tunables_hash: str | None = None
    chunk_tunables_hash: str | None = None

    @field_validator("world_seed", "N", "n_cells")
    @classmethod
    def _int_not_bool(cls, value: int) -> int:
        if isinstance(value, bool):
            raise ValueError("integer fields must not be boolean")
        return value

    @field_validator("planet_radius_m", "elev_quantum_m")
    @classmethod
    def _float_not_bool(cls, value: float) -> float:
        if isinstance(value, bool):
            raise ValueError("float fields must not be boolean")
        return float(value)


def build_world_meta(
    *,
    world_seed: int,
    N: int,
    planet_radius_m: float,
    elev_quantum_m: float,
    global_tunables_hash: str | None = None,
    chunk_tunables_hash: str | None = None,
    format_version: str = "2.0.0",
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
        global_tunables_hash=global_tunables_hash,
        chunk_tunables_hash=chunk_tunables_hash,
    )


def dtype_to_str(dtype: np.dtype[np.generic]) -> str:
    return str(dtype)


def read_world_meta(out_dir: Path) -> WorldMeta:
    if not out_dir.exists():
        raise FileNotFoundError("out_dir must exist before reading meta.json")
    path: Path = out_dir / "meta.json"
    if not path.exists():
        raise FileNotFoundError("meta.json is missing in out_dir")
    model: WorldMetaModel = WorldMetaModel.model_validate_json(path.read_text())
    layers: Dict[str, LayerMeta] = {}
    for key, layer in model.layers.items():
        layers[key] = LayerMeta(
            path=layer.path,
            dtype=layer.dtype,
            shape=tuple(layer.shape),
            units=layer.units,
            sentinel=layer.sentinel,
        )
    return WorldMeta(
        format_version=model.format_version,
        world_seed=model.world_seed,
        N=model.N,
        n_cells=model.n_cells,
        planet_radius_m=float(model.planet_radius_m),
        elev_quantum_m=float(model.elev_quantum_m),
        layers=layers,
        global_tunables_hash=model.global_tunables_hash,
        chunk_tunables_hash=model.chunk_tunables_hash,
    )
