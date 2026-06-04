from __future__ import annotations

import numpy as np

try:  # optional dependency; the generator works without it
    from numba import njit

    NUMBA_AVAILABLE = True
except Exception:  # pragma: no cover - depends on environment
    NUMBA_AVAILABLE = False

    def njit(*args, **kwargs):  # type: ignore
        def wrap(fn):
            return fn

        if args and callable(args[0]):
            return args[0]
        return wrap


@njit(cache=True)
def _smooth2d_numba(values: np.ndarray, passes: int) -> np.ndarray:
    h, w = values.shape
    cur = values.copy()
    nxt = values.copy()
    for _ in range(passes):
        for y in range(h):
            for x in range(w):
                total = 0.0
                count = 0.0
                for dy in range(-1, 2):
                    yy = y + dy
                    if yy < 0 or yy >= h:
                        continue
                    for dx in range(-1, 2):
                        xx = x + dx
                        if xx < 0 or xx >= w:
                            continue
                        total += cur[yy, xx]
                        count += 1.0
                nxt[y, x] = total / count
        tmp = cur
        cur = nxt
        nxt = tmp
    return cur


def _smooth2d_numpy(values: np.ndarray, passes: int) -> np.ndarray:
    cur = values.astype(np.float32, copy=True)
    for _ in range(passes):
        padded = np.pad(cur, 1, mode="edge")
        cur = (
            padded[:-2, :-2]
            + padded[:-2, 1:-1]
            + padded[:-2, 2:]
            + padded[1:-1, :-2]
            + padded[1:-1, 1:-1]
            + padded[1:-1, 2:]
            + padded[2:, :-2]
            + padded[2:, 1:-1]
            + padded[2:, 2:]
        ) / 9.0
    return cur.astype(np.float32)


def smooth2d(values: np.ndarray, passes: int = 4) -> np.ndarray:
    """Smooth a 2-D float array using Numba when available, NumPy otherwise."""
    if passes <= 0:
        return values.astype(np.float32, copy=True)
    values = values.astype(np.float32, copy=False)
    if NUMBA_AVAILABLE:
        return _smooth2d_numba(values, int(passes)).astype(np.float32)
    return _smooth2d_numpy(values, int(passes))


@njit(cache=True)
def _stamp_disk_numba(grid: np.ndarray, cx: int, cy: int, radius: int, code: int) -> None:
    h, w = grid.shape
    r2 = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        if y < 0 or y >= h:
            continue
        for x in range(cx - radius, cx + radius + 1):
            if x < 0 or x >= w:
                continue
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy <= r2:
                grid[y, x] = code


def stamp_disk(grid: np.ndarray, cx: int, cy: int, radius: int, code: int) -> None:
    if radius <= 0:
        if 0 <= cy < grid.shape[0] and 0 <= cx < grid.shape[1]:
            grid[cy, cx] = code
        return
    _stamp_disk_numba(grid, int(cx), int(cy), int(radius), int(code))
