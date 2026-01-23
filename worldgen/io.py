from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from worldgen.metadata import LayerMeta, WorldMeta, dtype_to_str


def ensure_dir(path: Path) -> None:
    if not path.exists():
        path.mkdir(parents=True, exist_ok=False)
    if not path.is_dir():
        raise NotADirectoryError(f"{path} is not a directory")


def write_layer(
    *,
    out_dir: Path,
    key: str,
    arr: NDArray[np.generic],
    meta: WorldMeta,
    units: str | None = None,
    sentinel: int | float | None = None,
) -> Path:
    if not out_dir.exists():
        raise FileNotFoundError("out_dir must exist before writing layers")
    if key in meta.layers:
        raise ValueError(f"Layer already exists in meta: {key}")
    filename: str = f"{key}.npy"
    path: Path = out_dir / filename
    np.save(path, arr)
    layer_meta: LayerMeta = LayerMeta(
        path=filename,
        dtype=dtype_to_str(arr.dtype),
        shape=arr.shape,
        units=units,
        sentinel=sentinel,
    )
    meta.layers[key] = layer_meta
    return path


def read_layer(
    *,
    out_dir: Path,
    layer: LayerMeta,
) -> NDArray[np.generic]:
    path: Path = out_dir / layer.path
    if not path.exists():
        raise FileNotFoundError(f"Missing layer file: {path}")
    arr: NDArray[np.generic] = np.load(path)
    return arr
