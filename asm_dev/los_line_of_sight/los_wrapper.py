import os
import ctypes
import warnings
import numpy as np
from numpy.typing import NDArray

# -----------------------------------------------------------------------------
# Legacy Pure-Python Fallback
# -----------------------------------------------------------------------------
def _py_los_many(
    starts_x: NDArray[np.int32],
    starts_y: NDArray[np.int32],
    ends_x: NDArray[np.int32],
    ends_y: NDArray[np.int32],
    transparency_map: NDArray[np.uint8],
) -> NDArray[np.uint8]:
    """Legacy unoptimized implementation for non-x86-64/Linux platforms."""
    # Insert your original simple_rl Python LOS logic here
    pass

# -----------------------------------------------------------------------------
# Hardware-Optimized x86-64 loader
# -----------------------------------------------------------------------------
_HAS_ASM = False

try:
    _lib_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "liblos.so")
    _lib = ctypes.CDLL(_lib_path)
    
    _lib.los_many.argtypes = [
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_int32),
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int32, ctypes.c_int32,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int64,
    ]
    _lib.los_many.restype = None
    _HAS_ASM = True
    
except OSError:
    warnings.warn("Optimized x86-64 LOS library not loaded. Falling back to pure Python.", RuntimeWarning)


def los_many(
    starts_x: NDArray[np.int32],
    starts_y: NDArray[np.int32],
    ends_x: NDArray[np.int32],
    ends_y: NDArray[np.int32],
    transparency_map: NDArray[np.uint8],
) -> NDArray[np.uint8]:
    
    n = len(starts_x)
    if not (len(starts_y) == len(ends_x) == len(ends_y) == n):
        raise ValueError("All coordinate arrays must have identical length")

    t = np.ascontiguousarray(transparency_map, dtype=np.uint8)
    if t.ndim != 2:
        raise ValueError("transparency_map must be 2D")

    if not _HAS_ASM:
        return _py_los_many(starts_x, starts_y, ends_x, ends_y, t)

    h, w = t.shape

    sx = np.ascontiguousarray(starts_x, dtype=np.int32)
    sy = np.ascontiguousarray(starts_y, dtype=np.int32)
    ex = np.ascontiguousarray(ends_x,   dtype=np.int32)
    ey = np.ascontiguousarray(ends_y,   dtype=np.int32)

    out = np.empty(n, dtype=np.uint8)

    _lib.los_many(
        sx.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        sy.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ex.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        ey.ctypes.data_as(ctypes.POINTER(ctypes.c_int32)),
        t.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
        h, w,
        out.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
        n
    )
    return out
