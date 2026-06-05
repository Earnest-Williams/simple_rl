from __future__ import annotations

from collections.abc import Iterable, Sequence
from heapq import heappop, heappush
from typing import TypeVar

T = TypeVar("T")
from math import atan2, cos, pi, sin, sqrt

import numpy as np

from .acceleration import stamp_disk
from .model import Rect, TerrainCode

WATER_CODES = {
    TerrainCode.WATER,
    TerrainCode.DEEP_WATER,
    TerrainCode.MARSH,
    TerrainCode.SWAMP,
    TerrainCode.MOAT,
}
BUILD_BLOCKING = {
    TerrainCode.WATER,
    TerrainCode.DEEP_WATER,
    TerrainCode.MOUNTAIN,
    TerrainCode.WALL,
    TerrainCode.PALISADE,
    TerrainCode.BUILDING,
    TerrainCode.RUIN,
    TerrainCode.CEMETERY,
}


def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, int(value)))


def bresenham(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Integer line points."""
    points: list[tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy
    return points


def polyline(points: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for a, b in zip(points, points[1:], strict=False):
        segment = bresenham(a[0], a[1], b[0], b[1])
        if out:
            segment = segment[1:]
        out.extend(segment)
    return out


def draw_points(
    grid: np.ndarray,
    points: Iterable[tuple[int, int]],
    code: TerrainCode | int,
    radius: int = 0,
) -> None:
    h, w = grid.shape
    c = int(code)
    for x, y in points:
        if radius <= 0:
            if 0 <= x < w and 0 <= y < h:
                grid[y, x] = c
        else:
            stamp_disk(grid, int(x), int(y), int(radius), c)


def ellipse_ring(
    cx: int,
    cy: int,
    rx: int,
    ry: int,
    samples: int = 256,
    jitter: float = 0.0,
    rng: np.random.Generator | None = None,
) -> list[tuple[int, int]]:
    pts: list[tuple[int, int]] = []
    for i in range(samples):
        a = 2.0 * pi * i / samples
        scale = 1.0
        if rng is not None and jitter > 0:
            scale += float(rng.uniform(-jitter, jitter))
        x = int(round(cx + cos(a) * rx * scale))
        y = int(round(cy + sin(a) * ry * scale))
        pts.append((x, y))
    return polyline(pts + [pts[0]])


def rect_ring(rect: Rect) -> list[tuple[int, int]]:
    x0, y0, x1, y1 = rect.x, rect.y, rect.x2 - 1, rect.y2 - 1
    return polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def weighted_choice(
    rng: np.random.Generator, items: Sequence[T], weights: Sequence[float]
) -> T:
    total = float(sum(max(0.0, w) for w in weights))
    if total <= 0:
        return items[int(rng.integers(0, len(items)))]
    r = float(rng.random()) * total
    c = 0.0
    for item, weight in zip(items, weights, strict=False):
        c += max(0.0, float(weight))
        if r <= c:
            return item
    return items[-1]


def nearest_cell(cells: np.ndarray, target: tuple[int, int]) -> tuple[int, int]:
    if cells.size == 0:
        return target
    tx, ty = target
    dx = cells[:, 1] - tx
    dy = cells[:, 0] - ty
    idx = int(np.argmin(dx * dx + dy * dy))
    return (int(cells[idx, 1]), int(cells[idx, 0]))


def cells_within_radius(
    width: int, height: int, center: tuple[int, int], radius: int
) -> np.ndarray:
    cx, cy = center
    y0, y1 = max(0, cy - radius), min(height, cy + radius + 1)
    x0, x1 = max(0, cx - radius), min(width, cx + radius + 1)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius * radius
    return np.stack([yy[mask], xx[mask]], axis=1)


def passable_mask(terrain: np.ndarray, *, allow_water: bool = False) -> np.ndarray:
    mask = terrain != int(TerrainCode.MOUNTAIN)
    if not allow_water:
        mask &= terrain != int(TerrainCode.WATER)
        mask &= terrain != int(TerrainCode.DEEP_WATER)
        mask &= terrain != int(TerrainCode.MOAT)
    return mask  # type: ignore[no-any-return]


def water_mask(terrain: np.ndarray) -> np.ndarray:
    return (  # type: ignore[no-any-return]
        (terrain == int(TerrainCode.WATER))
        | (terrain == int(TerrainCode.DEEP_WATER))
        | (terrain == int(TerrainCode.MARSH))
        | (terrain == int(TerrainCode.SWAMP))
    )


def shore_mask(terrain: np.ndarray) -> np.ndarray:
    h, w = terrain.shape
    water = water_mask(terrain)
    shore = np.zeros_like(water)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx == 0 and dy == 0:
                continue
            shifted = np.zeros_like(water)
            ys = slice(max(0, dy), h + min(0, dy))
            xs = slice(max(0, dx), w + min(0, dx))
            ys2 = slice(max(0, -dy), h - max(0, dy))
            xs2 = slice(max(0, -dx), w - max(0, dx))
            shifted[ys, xs] = water[ys2, xs2]
            shore |= shifted
    return shore & ~water  # type: ignore[no-any-return]


def find_shore_cells(terrain: np.ndarray) -> np.ndarray:
    return np.argwhere(shore_mask(terrain))


def rect_is_clear(
    rect: Rect,
    terrain: np.ndarray,
    overlay: np.ndarray,
    *,
    allow_on: set[int] | None = None,
) -> bool:
    h, w = terrain.shape
    if rect.x < 1 or rect.y < 1 or rect.x2 >= w - 1 or rect.y2 >= h - 1:
        return False
    allow_on = allow_on or set()
    terr = terrain[rect.y : rect.y2, rect.x : rect.x2]
    over = overlay[rect.y : rect.y2, rect.x : rect.x2]
    if np.any(over != int(TerrainCode.VOID)):
        return False
    blocked = np.isin(terr, [int(c) for c in BUILD_BLOCKING if int(c) not in allow_on])
    return not bool(np.any(blocked))


def stamp_rect(grid: np.ndarray, rect: Rect, code: TerrainCode | int) -> None:
    grid[rect.y : rect.y2, rect.x : rect.x2] = int(code)


def border_points(
    width: int, height: int, side: str, margin: int = 4
) -> list[tuple[int, int]]:
    side = side.lower()
    if side == "north":
        return [(x, margin) for x in range(margin, width - margin)]
    if side == "south":
        return [(x, height - margin - 1) for x in range(margin, width - margin)]
    if side == "west":
        return [(margin, y) for y in range(margin, height - margin)]
    if side == "east":
        return [(width - margin - 1, y) for y in range(margin, height - margin)]
    raise ValueError(f"unknown side: {side}")


def path_cost(code: int, allow_bridges: bool) -> float:
    c = (
        TerrainCode(int(code))
        if int(code) in [t.value for t in TerrainCode]
        else TerrainCode.GRASS
    )
    if c == TerrainCode.DEEP_WATER:
        return 40.0 if allow_bridges else 9999.0
    if c == TerrainCode.WATER:
        return 14.0 if allow_bridges else 9999.0
    if c in (TerrainCode.MARSH, TerrainCode.SWAMP):
        return 8.0
    if c == TerrainCode.MOUNTAIN:
        return 40.0
    if c == TerrainCode.HILL:
        return 3.0
    if c in (TerrainCode.FOREST, TerrainCode.DENSE_FOREST):
        return 3.5
    if c in (
        TerrainCode.FARMLAND,
        TerrainCode.FIELD,
        TerrainCode.PASTURE,
        TerrainCode.ORCHARD,
    ):
        return 1.3
    if c == TerrainCode.ROAD:
        return 0.4
    return 1.0


def astar_path(
    terrain: np.ndarray,
    start: tuple[int, int],
    goal: tuple[int, int],
    *,
    allow_bridges: bool = True,
    max_expansions: int = 100000,
) -> list[tuple[int, int]]:
    """A* over the terrain layer. Coordinates are (x, y)."""
    h, w = terrain.shape
    sx, sy = start
    gx, gy = goal
    sx, sy = clamp(sx, 0, w - 1), clamp(sy, 0, h - 1)
    gx, gy = clamp(gx, 0, w - 1), clamp(gy, 0, h - 1)

    def heuristic(x: int, y: int) -> float:
        return abs(x - gx) + abs(y - gy)

    open_heap: list[tuple[float, float, int, int]] = []
    heappush(open_heap, (heuristic(sx, sy), 0.0, sx, sy))
    came: dict[tuple[int, int], tuple[int, int]] = {}
    cost_so_far = {(sx, sy): 0.0}
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    expansions = 0
    while open_heap and expansions < max_expansions:
        _, cost, x, y = heappop(open_heap)
        expansions += 1
        if (x, y) == (gx, gy):
            break
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                continue
            step = path_cost(int(terrain[ny, nx]), allow_bridges)
            if step >= 9999.0:
                continue
            if dx != 0 and dy != 0:
                step *= 1.414
            new_cost = cost + step
            old = cost_so_far.get((nx, ny))
            if old is None or new_cost < old:
                cost_so_far[(nx, ny)] = new_cost
                priority = new_cost + heuristic(nx, ny)
                heappush(open_heap, (priority, new_cost, nx, ny))
                came[(nx, ny)] = (x, y)
    if (gx, gy) not in came:
        return bresenham(sx, sy, gx, gy)
    cur = (gx, gy)
    path = [cur]
    while cur != (sx, sy):
        cur = came[cur]
        path.append(cur)
    path.reverse()
    return path


def random_point_in_annulus(
    rng: np.random.Generator,
    center: tuple[int, int],
    r_min: float,
    r_max: float,
    width: int,
    height: int,
) -> tuple[int, int]:
    angle = float(rng.random()) * 2.0 * pi
    radius = float(rng.uniform(r_min, r_max))
    x = clamp(round(center[0] + cos(angle) * radius), 2, width - 3)
    y = clamp(round(center[1] + sin(angle) * radius), 2, height - 3)
    return x, y


def angle_between(a: tuple[int, int], b: tuple[int, int]) -> float:
    return atan2(b[1] - a[1], b[0] - a[0])


def distance(a: tuple[int, int], b: tuple[int, int]) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)
