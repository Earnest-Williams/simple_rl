"""Correctness tests for FlowFieldPathfinder.compute_field (Dijkstra integration)."""

from __future__ import annotations

import heapq
import math
from typing import Final

import numpy as np
from numpy.typing import NDArray

from game.systems.pathfinding.flowfield import (
    DIAGONAL_EXTRA_COST,
    DIRECTIONS_8,
    MAX_PATHFIND_DISTANCE,
    FlowFieldPathfinder,
)

TOLERANCE: Final[float] = 1e-4  # float32 accumulation tolerance


def _octile(height: int, width: int, cy: int, cx: int) -> NDArray[np.float64]:
    yy, xx = np.mgrid[0:height, 0:width]
    dy = np.abs(yy - cy)
    dx = np.abs(xx - cx)
    diag = math.sqrt(2.0) - 1.0
    result: NDArray[np.float64] = np.maximum(dy, dx) + diag * np.minimum(dy, dx)
    return result


def _make(
    passable: NDArray[np.bool_],
    cost: NDArray[np.float32],
    heights: NDArray[np.int32],
    max_step: int = 2,
    height_factor: float = 0.5,
) -> FlowFieldPathfinder:
    return FlowFieldPathfinder(
        passable, cost, heights, max_step, height_cost_factor=height_factor
    )


def _reference_dijkstra(
    passable: NDArray[np.bool_],
    cost: NDArray[np.float32],
    heights: NDArray[np.int32],
    sources: list[tuple[int, int]],
    max_step: int,
    height_factor: float,
) -> NDArray[np.float32]:
    """Plain lazy-deletion Dijkstra with all arithmetic held in float32."""
    height, width = passable.shape
    field: NDArray[np.float32] = np.full((height, width), np.inf, dtype=np.float32)
    heap: list[tuple[float, int, int]] = []
    for sy, sx in sources:
        field[sy, sx] = np.float32(0.0)
        heapq.heappush(heap, (0.0, sy, sx))
    diag = np.float32(DIAGONAL_EXTRA_COST)
    while heap:
        popped, y, x = heapq.heappop(heap)
        current = field[y, x]
        if np.float32(popped) != current:
            continue
        if current > MAX_PATHFIND_DISTANCE:
            break
        for dy_raw, dx_raw in DIRECTIONS_8.tolist():
            dy = int(dy_raw)
            dx = int(dx_raw)
            ny = y + dy
            nx = x + dx
            if not (0 <= ny < height and 0 <= nx < width) or not passable[ny, nx]:
                continue
            delta_h = abs(int(heights[ny, nx]) - int(heights[y, x]))
            if delta_h > max_step:
                continue
            base = np.float32(cost[ny, nx])
            diag_pen = base * diag if (dy != 0 and dx != 0) else np.float32(0.0)
            new = np.float32(
                current + (base + diag_pen + np.float32(delta_h * height_factor))
            )
            if new < field[ny, nx]:
                field[ny, nx] = new
                heapq.heappush(heap, (float(new), ny, nx))
    return field


def test_open_map_matches_octile_distance_everywhere() -> None:
    size = 40
    ff = _make(
        np.ones((size, size), dtype=bool),
        np.ones((size, size), dtype=np.float32),
        np.zeros((size, size), dtype=np.int32),
    )
    assert ff.compute_field([(20, 20)])
    field = ff.get_integration_field()
    assert np.isfinite(field).all()
    np.testing.assert_allclose(field, _octile(size, size, 20, 20), atol=TOLERANCE)


def test_large_map_correct_beyond_int8_coordinates() -> None:
    size = 300
    ff = _make(
        np.ones((size, size), dtype=bool),
        np.ones((size, size), dtype=np.float32),
        np.zeros((size, size), dtype=np.int32),
    )
    assert ff.compute_field([(150, 150)])
    field = ff.get_integration_field()
    assert math.isclose(float(field[195, 150]), 45.0, abs_tol=TOLERANCE)
    assert math.isclose(float(field[150, 105]), 45.0, abs_tol=TOLERANCE)
    expected_diag = 30.0 * math.sqrt(2.0)
    assert math.isclose(float(field[180, 180]), expected_diag, abs_tol=TOLERANCE)


def test_height_step_limit_and_penalty() -> None:
    passable = np.ones((1, 5), dtype=bool)
    cost = np.ones((1, 5), dtype=np.float32)
    heights = np.array([[0, 1, 4, 1, 0]], dtype=np.int32)
    ff = _make(passable, cost, heights, max_step=2, height_factor=0.5)
    assert ff.compute_field([(0, 0)])
    field = ff.get_integration_field()
    assert math.isclose(float(field[0, 1]), 1.5, abs_tol=TOLERANCE)
    assert np.isinf(field[0, 2:]).all()


def test_matches_reference_dijkstra_on_patterned_map() -> None:
    size = 21
    yy, xx = np.mgrid[0:size, 0:size]
    passable: NDArray[np.bool_] = (yy * 7 + xx * 13) % 11 != 0
    passable[10, 10] = True
    cost: NDArray[np.float32] = (1.0 + ((yy * 3 + xx * 5) % 5) * 0.1).astype(np.float32)
    heights: NDArray[np.int32] = ((yy + 2 * xx) % 3).astype(np.int32)
    sources: list[tuple[int, int]] = [(10, 10)]
    ff = _make(passable, cost, heights, max_step=1, height_factor=0.5)
    assert ff.compute_field(sources)
    expected = _reference_dijkstra(passable, cost, heights, sources, 1, 0.5)
    field = ff.get_integration_field()
    assert np.array_equal(np.isfinite(field), np.isfinite(expected))
    finite = np.isfinite(expected)
    np.testing.assert_allclose(field[finite], expected[finite], atol=TOLERANCE)


def test_multiple_and_duplicate_sources() -> None:
    size = 15
    ff = _make(
        np.ones((size, size), dtype=bool),
        np.ones((size, size), dtype=np.float32),
        np.zeros((size, size), dtype=np.int32),
    )
    assert ff.compute_field([(0, 0), (14, 14), (0, 0)])
    field = ff.get_integration_field()
    expected = np.minimum(_octile(size, size, 0, 0), _octile(size, size, 14, 14))
    np.testing.assert_allclose(field, expected, atol=TOLERANCE)
    assert ff.get_flow_vector(1, 1) == (-1, -1)
