import numpy as np
import pytest

from game.world.fov import (
    compute_fov_into,
    compute_visibility,
    compute_visibility_into,
    is_visible,
    iter_visible_cells,
)


def test_compute_visibility_empty_room_radius_boundary() -> None:
    visible = compute_visibility(
        7,
        7,
        origin_y=3,
        origin_x=3,
        radius=2,
        is_opaque=lambda y, x: False,
    )

    assert (3, 3) in visible
    assert (3, 5) in visible
    assert (1, 3) in visible
    assert (3, 6) not in visible
    assert (0, 0) not in visible


def test_compute_visibility_wall_occlusion_and_blocker_visible() -> None:
    blockers = {(3, 5)}
    visible = compute_visibility(
        7,
        8,
        origin_y=3,
        origin_x=3,
        radius=5,
        is_opaque=lambda y, x: (y, x) in blockers,
    )

    assert (3, 5) in visible
    assert (3, 6) not in visible


def test_compute_visibility_radius_zero_marks_origin_only() -> None:
    visible = compute_visibility(
        5,
        5,
        origin_y=2,
        origin_x=2,
        radius=0,
        is_opaque=lambda y, x: False,
    )

    assert visible == {(2, 2)}


def test_compute_visibility_into_supports_custom_distance_and_blockers() -> None:
    visible_grid = np.zeros((5, 5), dtype=np.bool_)
    blockers = {(2, 3)}

    def chessboard_distance(
        origin_y: int, origin_x: int, target_y: int, target_x: int
    ) -> float:
        return float(max(abs(target_y - origin_y), abs(target_x - origin_x)))

    def mark_visible(y: int, x: int) -> None:
        visible_grid[y, x] = True

    compute_visibility_into(
        5,
        5,
        origin_y=2,
        origin_x=2,
        radius=1,
        is_opaque=lambda y, x: (y, x) in blockers,
        mark_visible=mark_visible,
        distance=chessboard_distance,
    )

    assert visible_grid[2, 2]
    assert visible_grid[2, 3]
    assert visible_grid[1, 2]
    assert not visible_grid[0, 2]


def test_visibility_helpers_report_visible_cells() -> None:
    visible_grid = np.zeros((3, 3), dtype=np.bool_)
    visible_grid[0, 1] = True
    visible_grid[2, 2] = True

    assert list(iter_visible_cells(visible_grid)) == [(0, 1), (2, 2)]
    assert is_visible(visible_grid, 2, 2)
    assert not is_visible(visible_grid, 3, 2)


def test_compute_visibility_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="radius"):
        compute_visibility(
            3,
            3,
            origin_y=1,
            origin_x=1,
            radius=-1,
            is_opaque=lambda y, x: False,
        )

    with pytest.raises(ValueError, match="origin"):
        compute_visibility(
            3,
            3,
            origin_y=4,
            origin_x=1,
            radius=1,
            is_opaque=lambda y, x: False,
        )


def test_production_compute_fov_into_marks_origin_and_reuses_output() -> None:
    opaque = np.zeros((5, 5), dtype=np.bool_)
    height_map = np.zeros((5, 5), dtype=np.int64)
    ceiling_map = np.full((5, 5), 10, dtype=np.int64)
    visible = np.ones((5, 5), dtype=np.bool_)
    explored = np.zeros((5, 5), dtype=np.bool_)

    compute_fov_into((2, 2), 0, opaque, height_map, ceiling_map, 0, visible, explored)

    assert visible[2, 2]
    assert explored[2, 2]
    assert np.count_nonzero(visible) == 1
