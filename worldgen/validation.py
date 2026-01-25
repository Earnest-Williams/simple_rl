from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def validate_array(
    arr: NDArray[np.generic],
    name: str,
    expected_dtype: np.dtype[np.generic],
    expected_shape: tuple[int, ...],
) -> None:
    if arr.dtype != expected_dtype:
        msg: str = f"{name}: expected dtype {expected_dtype}, got {arr.dtype}"
        raise ValueError(msg)
    if arr.shape != expected_shape:
        msg = f"{name}: expected shape {expected_shape}, got {arr.shape}"
        raise ValueError(msg)
    if not arr.flags["C_CONTIGUOUS"]:
        msg = f"{name}: array must be C-contiguous"
        raise ValueError(msg)


def validate_no_nan(arr: NDArray[np.floating[np.generic]], name: str) -> None:
    if np.any(~np.isfinite(arr)):
        msg: str = f"{name}: contains NaN or infinity values"
        raise ValueError(msg)
