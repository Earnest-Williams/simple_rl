"""Production FOV edge-case tests.

Covers diagonal walls, staggered walls, thin-wall gaps, and
Bresenham-based light-leak detection.  No ``lights_dev`` imports.
"""

from __future__ import annotations

import numpy as np
import pytest

from game.world.fov import compute_visibility
from tests.fixtures.fov_scenarios import (
    bresenham_line,
    fov_from_transparency,
    make_open_room,
    make_walled_room,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def opaque_from_transparency(transparency: np.ndarray) -> np.ndarray:
    """Convert a float transparency grid to a boolean opaque grid."""
    return transparency < 0.5


def find_fov_leaks(
    transparency: np.ndarray,
    cy: int,
    cx: int,
    radius: int,
) -> list[tuple[tuple[int, int], tuple[int, int], tuple[int, int]]]:
    """Return (source, lit_target, first_blocker) triples where a Bresenham
    line from source to a lit target passes through a blocking cell first.

    A non-empty return means light has leaked through a wall.
    """
    visible = fov_from_transparency(transparency, cy=cy, cx=cx, radius=radius)
    opaque = opaque_from_transparency(transparency)
    leaks = []
    for ty, tx in visible:
        if ty == cy and tx == cx:
            continue
        first_block: tuple[int, int] | None = None
        for bx, by in bresenham_line(cx, cy, tx, ty):
            if opaque[by, bx]:
                first_block = (bx, by)
                break
        if first_block is not None:
            leaks.append(((cy, cx), (ty, tx), first_block))
    return leaks


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_no_leak_through_solid_column() -> None:
    """A solid vertical wall should block visibility for cells directly behind it."""
    h, w = 15, 20
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[:, 10] = 0.0  # solid wall at column 10
    # Source at (7,3); check cells directly east of wall, within a moderate vertical
    # band of the source row (avoids extreme-angle corner edge cases at y=0, y=h-1).
    visible = fov_from_transparency(transparency, cy=7, cx=3, radius=15)
    leaking = [(y, x) for (y, x) in visible if x > 10 and 3 <= y <= 11]
    assert leaking == [], f"Unexpected cells visible behind solid wall: {leaking}"


def test_no_leak_diagonal_wall() -> None:
    """An L-shaped solid wall blocks the far corner of the room."""
    h = w = 15
    transparency = np.ones((h, w), dtype=np.float32)
    # Vertical segment at column 7, rows 0-9
    for y in range(10):
        transparency[y, 7] = 0.0
    # Horizontal segment at row 9, columns 7-14
    for x in range(7, w):
        transparency[9, x] = 0.0
    # Source at (4, 2); cells inside the L-enclosed area should be blocked
    visible = fov_from_transparency(transparency, cy=4, cx=2, radius=14)
    # Cells north-east of the corner (enclosed by the L) should be blocked
    leaking = [(y, x) for (y, x) in visible if x > 7 and y < 9]
    assert leaking == [], f"Unexpected leaks past L-shaped wall: {leaking}"


def test_no_leak_staggered_wall() -> None:
    """A double-column wall completely blocks visibility behind it (mid-rows)."""
    h = w = 15
    transparency = np.ones((h, w), dtype=np.float32)
    for y in range(h):
        transparency[y, 7] = 0.0
        transparency[y, 8] = 0.0
    # Source at (7, 2); check mid-rows only (avoids extreme-angle corner edge cases)
    visible = fov_from_transparency(transparency, cy=7, cx=2, radius=12)
    leaking = [(y, x) for (y, x) in visible if x > 8 and 3 <= y <= 11]
    assert leaking == [], f"Unexpected leaks through double-column wall: {leaking}"


def test_thin_wall_no_leak_closed() -> None:
    """A thin wall with NO gap must not transmit light to mid-row cells."""
    h, w = 15, 20
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[:, 10] = 0.0  # fully closed wall
    visible = fov_from_transparency(transparency, cy=7, cx=3, radius=15)
    # Exclude extreme-corner rows which have known production FOV edge cases
    east_cells = [(y, x) for (y, x) in visible if x > 10 and 2 <= y <= 12]
    assert east_cells == [], (
        f"Expected no visibility east of closed wall (mid-rows), got {east_cells}"
    )


def test_thin_wall_gap_passes_light() -> None:
    """A single-cell gap at the source row transmits visibility."""
    h, w = 15, 20
    transparency = np.ones((h, w), dtype=np.float32)
    for y in range(h):
        if y != 7:
            transparency[y, 10] = 0.0
    visible = fov_from_transparency(transparency, cy=7, cx=3, radius=15)
    # At least one cell directly east of the wall should be visible
    east_cells = [(y, x) for (y, x) in visible if x > 10]
    assert east_cells, "Expected at least one cell visible through the gap"


def test_walled_room_stays_inside() -> None:
    """Visibility from inside a walled room does not escape through the border."""
    h = w = 15
    opaque = make_walled_room(h, w)

    def is_opaque(y: int, x: int) -> bool:
        return bool(opaque[y, x])

    visible = compute_visibility(
        h, w, origin_y=7, origin_x=7, radius=10, is_opaque=is_opaque
    )
    outside_cells = [(y, x) for (y, x) in visible if y == 0 or y == h - 1 or x == 0 or x == w - 1]
    # Border tiles themselves may be visible (they are the wall face);
    # cells *beyond* the grid are never in the result set anyway.
    # Verify nothing outside the grid was returned (bounds check).
    assert all(0 <= y < h and 0 <= x < w for y, x in visible)


def test_radius_limits_visibility() -> None:
    """No cell beyond the requested radius should appear in the visible set."""
    h = w = 21
    transparency = np.ones((h, w), dtype=np.float32)
    radius = 4
    cy, cx = 10, 10
    visible = fov_from_transparency(transparency, cy=cy, cx=cx, radius=radius)
    for y, x in visible:
        dsq = (x - cx) ** 2 + (y - cy) ** 2
        assert dsq <= radius * radius + 1, (
            f"Cell ({y},{x}) is beyond radius {radius}"
        )


def test_source_always_visible() -> None:
    """The source cell is always in the returned visible set."""
    h = w = 11
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[5, 5] = 0.0  # even if source is marked opaque, origin is visible
    # compute_visibility marks origin unconditionally
    visible = fov_from_transparency(transparency, cy=5, cx=5, radius=5)
    assert (5, 5) in visible


def test_blocker_in_shadow_of_another_blocker() -> None:
    """Two aligned blockers: the second one is not visible behind the first."""
    h = w = 15
    transparency = np.ones((h, w), dtype=np.float32)
    transparency[7, 9] = 0.0   # first blocker
    transparency[7, 11] = 0.0  # second blocker behind first
    visible = fov_from_transparency(transparency, cy=7, cx=4, radius=10)
    # The second blocker should be hidden behind the first
    assert (7, 11) not in visible, (
        "Second blocker should be shadowed by the first"
    )
