# game/world/fov.py
"""
Field of View (FOV) and Line of Sight (LOS) calculations.
Uses Numba-accelerated Iterative Shadowcasting for FOV and Bresenham for LOS.
Includes height/ceiling checks and explored tile tracking.
"""

import time
from collections import deque
from collections.abc import Callable, Iterator
from typing import TypeAlias

import numba
import numpy as np
import structlog
from numba.typed import List as NumbaList

from .los import line_of_sight as _los_line_of_sight


def line_of_sight(
    x0: int, y0: int, x1: int, y1: int, transparency_map: np.ndarray
) -> bool:
    """Return True if tiles (x0, y0) and (x1, y1) have clear line of sight."""
    return _los_line_of_sight(x0, y0, x1, y1, transparency_map)


# --- Type Aliases ---
Point: TypeAlias = tuple[int, int]
Slope: TypeAlias = tuple[int, int]  # (y, x) representation
OpacityFn: TypeAlias = Callable[[int, int], bool]
VisitFn: TypeAlias = Callable[[int, int], None]
DistanceFn: TypeAlias = Callable[[int, int, int, int], float]

# Numba type definitions
sector_type = numba.types.Tuple(
    (
        numba.int64,  # octant
        numba.int64,  # x
        numba.types.Tuple((numba.int64, numba.int64)),  # top slope (y, x)
        numba.types.Tuple((numba.int64, numba.int64)),  # bottom slope (y, x)
    )
)

# --- Logging Setup ---
log = structlog.get_logger(__name__)

# --- Configuration Constants ---
BASE_THRESHOLD: int = 1
CLOSE_RANGE_SQ_THRESHOLD: int = 16
CLOSE_RANGE_DIVISOR: int = 8
FAR_RANGE_DIVISOR: int = 16
_THRESHOLD_AT_CUTOFF: int = CLOSE_RANGE_SQ_THRESHOLD // CLOSE_RANGE_DIVISOR
MAX_SECTORS: int = 10000  # Safety limit for sector processing


# --- Generic callback shadowcasting ---


def _euclidean_distance(
    origin_y: int, origin_x: int, target_y: int, target_x: int
) -> float:
    """Return Euclidean distance between two ``(y, x)`` cells."""
    dy = target_y - origin_y
    dx = target_x - origin_x
    return float(np.hypot(dy, dx))


def compute_shadowcast_callbacks(
    height: int,
    width: int,
    *,
    origin_y: int,
    origin_x: int,
    radius: int,
    is_opaque: OpacityFn,
    mark_visible: VisitFn,
    distance: DistanceFn | None = None,
) -> None:
    """Run callback-based symmetrical shadowcasting.

    Coordinates use the production map convention: arrays are indexed as
    ``[y, x]`` and callbacks receive ``(y, x)``. The origin is always marked
    visible when it is in bounds, including when ``radius`` is zero. Radius
    checks use the supplied ``distance`` callback or Euclidean distance by
    default. Out-of-bounds cells are treated as opaque and are never passed to
    ``mark_visible`` or ``is_opaque``.
    """
    if height < 0 or width < 0:
        raise ValueError("height and width must be non-negative")
    if radius < 0:
        raise ValueError("radius must be non-negative")
    if not (0 <= origin_y < height and 0 <= origin_x < width):
        raise ValueError("origin coordinates out of bounds")

    distance_fn = distance if distance is not None else _euclidean_distance

    def blocks_light(cell_y: int, cell_x: int) -> bool:
        if not (0 <= cell_y < height and 0 <= cell_x < width):
            return True
        return is_opaque(cell_y, cell_x)

    def set_visible(cell_y: int, cell_x: int) -> None:
        if 0 <= cell_y < height and 0 <= cell_x < width:
            mark_visible(cell_y, cell_x)

    def cast_light(
        row: int,
        start_slope: float,
        end_slope: float,
        xx: int,
        xy: int,
        yx: int,
        yy: int,
    ) -> None:
        if start_slope < end_slope:
            return

        next_start_slope = start_slope
        for distance_row in range(row, radius + 1):
            dx = -distance_row
            dy = -distance_row
            blocked = False
            while dx <= 0:
                dx += 1
                cell_x = origin_x + dx * xx + dy * xy
                cell_y = origin_y + dx * yx + dy * yy

                left_slope = (dx - 0.5) / (dy + 0.5)
                right_slope = (dx + 0.5) / (dy - 0.5)
                if start_slope < right_slope:
                    continue
                if end_slope > left_slope:
                    break

                if distance_fn(origin_y, origin_x, cell_y, cell_x) <= radius:
                    set_visible(cell_y, cell_x)

                cell_blocks = blocks_light(cell_y, cell_x)
                if blocked:
                    if cell_blocks:
                        next_start_slope = right_slope
                        continue
                    blocked = False
                    start_slope = next_start_slope
                elif cell_blocks and distance_row < radius:
                    blocked = True
                    cast_light(
                        distance_row + 1,
                        start_slope,
                        left_slope,
                        xx,
                        xy,
                        yx,
                        yy,
                    )
                    next_start_slope = right_slope
            if blocked:
                break

    mark_visible(origin_y, origin_x)
    multipliers = (
        (1, 0, 0, 1),
        (0, 1, 1, 0),
        (0, -1, 1, 0),
        (-1, 0, 0, 1),
        (-1, 0, 0, -1),
        (0, -1, -1, 0),
        (0, 1, -1, 0),
        (1, 0, 0, -1),
    )
    for xx, xy, yx, yy in multipliers:
        cast_light(1, 1.0, 0.0, xx, xy, yx, yy)


def compute_visibility_into(
    height: int,
    width: int,
    *,
    origin_y: int,
    origin_x: int,
    radius: int,
    is_opaque: OpacityFn,
    mark_visible: VisitFn,
    distance: DistanceFn | None = None,
) -> None:
    """Fill caller-owned visibility state using callback shadowcasting."""
    compute_shadowcast_callbacks(
        height,
        width,
        origin_y=origin_y,
        origin_x=origin_x,
        radius=radius,
        is_opaque=is_opaque,
        mark_visible=mark_visible,
        distance=distance,
    )


def compute_visibility(
    height: int,
    width: int,
    *,
    origin_y: int,
    origin_x: int,
    radius: int,
    is_opaque: OpacityFn,
    distance: DistanceFn | None = None,
) -> set[tuple[int, int]]:
    """Return visible ``(y, x)`` cells using callback shadowcasting."""
    visible: set[tuple[int, int]] = set()

    def mark_visible(cell_y: int, cell_x: int) -> None:
        visible.add((cell_y, cell_x))

    compute_visibility_into(
        height,
        width,
        origin_y=origin_y,
        origin_x=origin_x,
        radius=radius,
        is_opaque=is_opaque,
        mark_visible=mark_visible,
        distance=distance,
    )
    return visible


def iter_visible_cells(visible_grid: np.ndarray) -> Iterator[tuple[int, int]]:
    """Yield ``(y, x)`` coordinates for true cells in a visibility grid."""
    ys, xs = np.nonzero(visible_grid)
    for y, x in zip(ys, xs, strict=True):
        yield int(y), int(x)


def is_visible(visible_grid: np.ndarray, y: int, x: int) -> bool:
    """Return whether ``(y, x)`` is in bounds and marked visible."""
    height, width = visible_grid.shape
    if not (0 <= y < height and 0 <= x < width):
        return False
    return bool(visible_grid[y, x])


# --- Numba Helper Functions ---


@numba.njit(cache=True, inline="always")
def slope_greater(slope1_yx: Slope, y: int, x: int) -> bool:
    """Check if slope1 is greater than the slope to point (y,x)."""
    slope_y, slope_x = slope1_yx
    if slope_x == 0 and x == 0:
        return slope_y > y
    if slope_x == 0:
        return x > 0
    if x == 0:
        return slope_x <= 0
    return slope_y * x > slope_x * y


@numba.njit(cache=True, inline="always")
def slope_greater_or_equal(slope1_yx: Slope, y: int, x: int) -> bool:
    """Check if slope1 is greater than or equal to the slope to point (y,x)."""
    slope_y, slope_x = slope1_yx
    if slope_x == 0 and x == 0:
        return slope_y >= y
    if slope_x == 0:
        return x >= 0
    if x == 0:
        return slope_x < 0
    return slope_y * x >= slope_x * y


@numba.njit(cache=True, inline="always")
def slope_less(slope1_yx: Slope, y: int, x: int) -> bool:
    """Check if slope1 is less than the slope to point (y,x)."""
    slope_y, slope_x = slope1_yx
    if slope_x == 0 and x == 0:
        return slope_y < y
    if slope_x == 0:
        return x <= 0
    if x == 0:
        return slope_x > 0
    return slope_y * x < slope_x * y


@numba.njit(cache=True, inline="always")
def slope_less_or_equal(slope1_yx: Slope, y: int, x: int) -> bool:
    """Check if slope1 is less than or equal to the slope to point (y,x)."""
    slope_y, slope_x = slope1_yx
    if slope_x == 0 and x == 0:
        return slope_y <= y
    if slope_x == 0:
        return x <= 0
    if x == 0:
        return slope_x > 0
    return slope_y * x <= slope_x * y


@numba.njit(cache=True)
def _transform_coords(
    octant_x: int, octant_y: int, octant: int, origin_xy: Point
) -> Point:
    """Transform coordinates based on octant."""
    ox, oy = origin_xy
    nx, ny = ox, oy
    if octant == 0:
        nx += octant_x
        ny -= octant_y
    elif octant == 1:
        nx += octant_y
        ny -= octant_x
    elif octant == 2:
        nx -= octant_y
        ny -= octant_x
    elif octant == 3:
        nx -= octant_x
        ny -= octant_y
    elif octant == 4:
        nx -= octant_x
        ny += octant_y
    elif octant == 5:
        nx -= octant_y
        ny += octant_x
    elif octant == 6:
        nx += octant_y
        ny += octant_x
    elif octant == 7:
        nx += octant_x
        ny += octant_y
    return nx, ny


@numba.njit(cache=True)
def blocks_light_at(
    octant_x: int,
    octant_y: int,
    octant: int,
    origin_xy: Point,
    grid_shape: tuple[int, int],
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
) -> bool:
    """Check if a tile blocks light, considering bounds, opacity, and height."""
    nx, ny = _transform_coords(octant_x, octant_y, octant, origin_xy)
    height, width = grid_shape

    if not (0 <= nx < width and 0 <= ny < height):
        return True

    if opaque_grid[ny, nx]:
        return True

    # Height and ceiling checks
    target_h = height_map[ny, nx]
    target_ceiling = ceiling_map[ny, nx]

    if target_ceiling <= origin_height:
        return True  # Ceiling too low

    # Calculate height difference threshold based on distance
    dist_sq = octant_x * octant_x + octant_y * octant_y
    threshold = BASE_THRESHOLD

    if dist_sq <= CLOSE_RANGE_SQ_THRESHOLD:
        threshold = dist_sq // CLOSE_RANGE_DIVISOR
    else:
        threshold = (
            _THRESHOLD_AT_CUTOFF
            + (dist_sq - CLOSE_RANGE_SQ_THRESHOLD) // FAR_RANGE_DIVISOR
        )

    return abs(target_h - origin_height) > threshold


@numba.njit(cache=True)
def set_visible_at(
    octant_x: int,
    octant_y: int,
    octant: int,
    origin_xy: Point,
    grid_shape: tuple[int, int],
    visible_grid: np.ndarray,
    explored_grid: np.ndarray,
) -> None:
    """Mark a tile as visible and explored."""
    nx, ny = _transform_coords(octant_x, octant_y, octant, origin_xy)
    height, width = grid_shape
    if 0 <= nx < width and 0 <= ny < height:
        visible_grid[ny, nx] = True
        explored_grid[ny, nx] = True


@numba.njit(cache=True)
def is_in_range(octant_x: int, octant_y: int, range_limit_sq: int | float) -> bool:
    """Check if coordinates are within the range limit."""
    return (octant_x * octant_x + octant_y * octant_y) <= range_limit_sq


@numba.njit(cache=True)
def _compute_fov_numba_core(
    origin_xy: Point,
    range_limit: int,
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
    visible_grid: np.ndarray,
    explored_grid: np.ndarray,
) -> None:
    """Numba-optimized FOV core computation."""
    range_limit_sq = range_limit * range_limit
    grid_shape = opaque_grid.shape

    # Initialize with Numba-compatible list
    sectors = NumbaList()
    for octant in range(8):
        sectors.append((octant, 1, (1, 1), (0, 1)))

    sector_count = 0
    while len(sectors) > 0 and sector_count < MAX_SECTORS:
        sector_count += 1

        # Pop first element (FIFO behavior)
        current = sectors.pop(0)
        octant, current_x = current[0], current[1]
        top_slope, bottom_slope = current[2], current[3]

        blocked = False
        for current_y in range(current_x, range_limit + 1):
            if not is_in_range(current_x, current_y, range_limit_sq):
                break

            cell_top_y = 2 * current_y + 1
            cell_bottom_y = 2 * current_y - 1
            cell_x = 2 * current_x
            center_y, center_x = current_y, current_x

            if slope_less(top_slope, center_y, center_x) or slope_less_or_equal(
                bottom_slope, center_y, center_x
            ):
                continue

            set_visible_at(
                current_x,
                current_y,
                octant,
                origin_xy,
                grid_shape,
                visible_grid,
                explored_grid,
            )

            cell_blocks = blocks_light_at(
                current_x,
                current_y,
                octant,
                origin_xy,
                grid_shape,
                opaque_grid,
                height_map,
                ceiling_map,
                origin_height,
            )

            if blocked:
                if cell_blocks:
                    continue
                else:
                    blocked = False
                    bottom_slope = (cell_top_y, cell_x)
            else:
                if cell_blocks:
                    blocked = True
                    if slope_greater(top_slope, cell_bottom_y, cell_x):
                        sectors.append(
                            (octant, current_x + 1, top_slope, (cell_bottom_y, cell_x))
                        )
                    top_slope = (cell_top_y, cell_x)

        if not blocked:
            sectors.append((octant, current_x + 1, top_slope, bottom_slope))


def _compute_fov_python_fallback(
    origin_xy: Point,
    range_limit: int,
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
    visible_grid: np.ndarray,
    explored_grid: np.ndarray,
) -> None:
    """Python fallback implementation for debugging and fallback."""
    range_limit_sq = range_limit * range_limit
    grid_shape = opaque_grid.shape

    sectors: deque = deque()
    for octant in range(8):
        sectors.append((octant, 1, (1, 1), (0, 1)))

    sector_count = 0
    while sectors and sector_count < MAX_SECTORS:
        sector_count += 1

        octant, current_x, top_slope, bottom_slope = sectors.popleft()

        blocked = False
        for current_y in range(current_x, range_limit + 1):
            if not is_in_range(current_x, current_y, range_limit_sq):
                break

            cell_top_y = 2 * current_y + 1
            cell_bottom_y = 2 * current_y - 1
            cell_x = 2 * current_x
            center_y, center_x = current_y, current_x

            if slope_less(top_slope, center_y, center_x) or slope_less_or_equal(
                bottom_slope, center_y, center_x
            ):
                continue

            set_visible_at(
                current_x,
                current_y,
                octant,
                origin_xy,
                grid_shape,
                visible_grid,
                explored_grid,
            )

            cell_blocks = blocks_light_at(
                current_x,
                current_y,
                octant,
                origin_xy,
                grid_shape,
                opaque_grid,
                height_map,
                ceiling_map,
                origin_height,
            )

            if blocked:
                if cell_blocks:
                    continue
                else:
                    blocked = False
                    bottom_slope = (cell_top_y, cell_x)
            else:
                if cell_blocks:
                    blocked = True
                    if slope_greater(top_slope, cell_bottom_y, cell_x):
                        sectors.append(
                            (octant, current_x + 1, top_slope, (cell_bottom_y, cell_x))
                        )
                    top_slope = (cell_top_y, cell_x)

        if not blocked:
            sectors.append((octant, current_x + 1, top_slope, bottom_slope))


def compute_fov(
    origin_xy: Point,
    range_limit: int,
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
    visible_grid: np.ndarray,
    explored_grid: np.ndarray,
) -> None:
    """
    Public interface for FOV computation.
    Attempts Numba-optimized version first, falls back to Python implementation.
    """
    func_log = log.bind(
        origin=origin_xy, range_limit=range_limit, grid_shape=opaque_grid.shape
    )
    func_log.info("Starting FOV computation")
    start_time = time.perf_counter()

    # Input validation
    if not isinstance(opaque_grid, np.ndarray) or opaque_grid.ndim != 2:
        raise TypeError("opaque_grid must be a 2D NumPy array")
    if opaque_grid.shape != height_map.shape or opaque_grid.shape != ceiling_map.shape:
        raise ValueError("Grid shapes must match")
    if not np.issubdtype(opaque_grid.dtype, np.bool_):
        opaque_grid = opaque_grid.astype(np.bool_)
    if not np.issubdtype(visible_grid.dtype, np.bool_) or not np.issubdtype(
        explored_grid.dtype, np.bool_
    ):
        raise TypeError("visible_grid and explored_grid must be boolean arrays")

    height, width = opaque_grid.shape
    ox, oy = origin_xy
    if not (0 <= ox < width and 0 <= oy < height):
        raise ValueError("Origin coordinates out of bounds")

    # Initialize visibility
    visible_grid.fill(False)
    visible_grid[oy, ox] = True
    explored_grid[oy, ox] = True

    try:
        # Try Numba-optimized version first
        _compute_fov_numba_core(
            origin_xy,
            range_limit,
            opaque_grid,
            height_map,
            ceiling_map,
            origin_height,
            visible_grid,
            explored_grid,
        )
    except Exception as e:
        func_log.warning("Numba FOV failed, falling back to Python", error=str(e))
        try:
            # Fall back to Python version
            _compute_fov_python_fallback(
                origin_xy,
                range_limit,
                opaque_grid,
                height_map,
                ceiling_map,
                origin_height,
                visible_grid,
                explored_grid,
            )
        except Exception as e:
            func_log.error("FOV calculation failed", error=str(e), exc_info=True)
            visible_grid.fill(False)
            visible_grid[oy, ox] = True

    end_time = time.perf_counter()
    duration_ms = (end_time - start_time) * 1000
    func_log.info(
        "FOV computation finished",
        duration_ms=f"{duration_ms:.2f}",
        visible_count=np.sum(visible_grid),
    )


def compute_fov_into(
    origin_xy: Point,
    range_limit: int,
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
    visible_grid: np.ndarray,
    explored_grid: np.ndarray,
) -> None:
    """Fill caller-owned visibility grids using the production FOV path."""
    compute_fov(
        origin_xy,
        range_limit,
        opaque_grid,
        height_map,
        ceiling_map,
        origin_height,
        visible_grid,
        explored_grid,
    )


def compute_light_color_array(
    *,
    origin_xy: Point,
    range_limit: int,
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_height: int,
    target_rgb_array: np.ndarray,
    base_color_rgb: tuple[int, int, int],
) -> None:
    """Legacy height-aware colored-light accumulator.

    Production rendering now uses ``engine.render_lighting``'s cached
    callback-visibility contribution path.  This helper remains for tools that
    explicitly want the height-aware FOV experiment.
    """
    h, w = opaque_grid.shape
    temp_visible = np.zeros((h, w), dtype=np.bool_)
    temp_explored = np.zeros((h, w), dtype=np.bool_)
    _compute_fov_numba_core(
        origin_xy,
        range_limit,
        opaque_grid,
        height_map,
        ceiling_map,
        origin_height,
        temp_visible,
        temp_explored,
    )

    if range_limit <= 0:
        return

    ox, oy = origin_xy
    radius_sq = float(range_limit * range_limit)
    min_x = max(0, ox - range_limit)
    max_x = min(w, ox + range_limit + 1)
    min_y = max(0, oy - range_limit)
    max_y = min(h, oy + range_limit + 1)

    y_coords, x_coords = np.ogrid[min_y:max_y, min_x:max_x]
    dx = x_coords - ox
    dy = y_coords - oy
    dist_sq = dx * dx + dy * dy
    visible_slice = temp_visible[min_y:max_y, min_x:max_x]
    valid = (dist_sq <= radius_sq) & visible_slice
    intensity = np.where(valid, 1.0 - (dist_sq / radius_sq), 0.0)
    color_rgb = np.array(base_color_rgb, dtype=np.float32)
    target_rgb_array[min_y:max_y, min_x:max_x, :] += intensity[..., None] * color_rgb
