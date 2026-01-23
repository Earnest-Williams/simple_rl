from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

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


def read_world_meta(out_dir: Path) -> WorldMeta:
    if not out_dir.exists():
        raise FileNotFoundError("out_dir must exist before reading meta.json")
    path: Path = out_dir / "meta.json"
    if not path.exists():
        raise FileNotFoundError("meta.json is missing in out_dir")
    payload: object = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError("meta.json payload must be a JSON object")
    payload_dict: Dict[str, object] = {}
    for key, value in payload.items():
        if not isinstance(key, str):
            raise ValueError("meta.json keys must be strings")
        payload_dict[key] = value

    def _req_str(data: Dict[str, object], key: str) -> str:
        value: object = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"meta.json[{key}] must be a string")
        return value

    def _req_int(data: Dict[str, object], key: str) -> int:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"meta.json[{key}] must be an integer")
        return value

    def _req_float(data: Dict[str, object], key: str) -> float:
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"meta.json[{key}] must be a number")
        return float(value)

    def _req_dict(data: Dict[str, object], key: str) -> Dict[str, object]:
        value = data.get(key)
        if not isinstance(value, dict):
            raise ValueError(f"meta.json[{key}] must be an object")
        clean: Dict[str, object] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("meta.json layer keys must be strings")
            clean[k] = v
        return clean

    layers_payload: Dict[str, object] = _req_dict(payload_dict, "layers")
    layers: Dict[str, LayerMeta] = {}
    for key, raw in layers_payload.items():
        if not isinstance(raw, dict):
            raise ValueError(f"meta.json layers[{key}] must be an object")
        layer_dict: Dict[str, object] = {}
        for k, v in raw.items():
            if not isinstance(k, str):
                raise ValueError("meta.json layer field names must be strings")
            layer_dict[k] = v

        path_str: str = _req_str(layer_dict, "path")
        dtype: str = _req_str(layer_dict, "dtype")
        shape_obj: object = layer_dict.get("shape")
        if not isinstance(shape_obj, list):
            raise ValueError(f"meta.json layers[{key}].shape must be a list")
        shape_list: List[int] = []
        for item in shape_obj:
            if isinstance(item, bool) or not isinstance(item, int):
                raise ValueError(f"meta.json layers[{key}].shape entries must be int")
            shape_list.append(item)
        shape: Tuple[int, ...] = tuple(shape_list)
        units_obj: object = layer_dict.get("units")
        units: str | None
        if units_obj is None:
            units = None
        elif isinstance(units_obj, str):
            units = units_obj
        else:
            raise ValueError(f"meta.json layers[{key}].units must be string or null")
        sentinel_obj: object = layer_dict.get("sentinel")
        sentinel: int | float | None
        if sentinel_obj is None:
            sentinel = None
        elif isinstance(sentinel_obj, bool) or not isinstance(
            sentinel_obj, (int, float)
        ):
            raise ValueError(f"meta.json layers[{key}].sentinel must be number or null")
        else:
            if isinstance(sentinel_obj, float):
                sentinel = float(sentinel_obj)
            else:
                sentinel = sentinel_obj

        layers[key] = LayerMeta(
            path=path_str,
            dtype=dtype,
            shape=shape,
            units=units,
            sentinel=sentinel,
        )

    return WorldMeta(
        format_version=_req_str(payload_dict, "format_version"),
        world_seed=_req_int(payload_dict, "world_seed"),
        N=_req_int(payload_dict, "N"),
        n_cells=_req_int(payload_dict, "n_cells"),
        planet_radius_m=_req_float(payload_dict, "planet_radius_m"),
        elev_quantum_m=_req_float(payload_dict, "elev_quantum_m"),
        layers=layers,
    )
