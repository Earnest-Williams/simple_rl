"""
Adapter shim so simple_rl.py can use either:
  - your real dungeon generator module (preferred), or
  - a small fallback generator for testing.

Set environment variable DUNGEON_GENERATOR_MODULE to the real module name if needed.
"""

from __future__ import annotations

import importlib
import os
import warnings
from functools import lru_cache
from types import ModuleType
from typing import Any, Dict, List, Tuple


@lru_cache(maxsize=1)
def _load_real_module() -> tuple[ModuleType | None, str | None]:
    candidates: List[str] = []
    env_module = os.environ.get("DUNGEON_GENERATOR_MODULE")
    if env_module:
        candidates.append(env_module)
    candidates.extend(
        [
            "dungeon_generator_real",
            "dungeon_gen",
            "dungeon_tool",
            "dungeon",
            "real_dungeon_generator",
        ]
    )

    import_errors: List[str] = []
    for name in candidates:
        try:
            module = importlib.import_module(name)
        except ImportError as exc:
            import_errors.append(f"{name}: {exc}")
            continue
        return module, name

    if import_errors:
        details = "; ".join(import_errors)
        warnings.warn(
            "No real dungeon generator module found; using fallback generator. "
            f"Import errors: {details}",
            RuntimeWarning,
            stacklevel=2,
        )
    return None, None


def _get_real_module() -> ModuleType | None:
    module, _name = _load_real_module()
    return module


# -------------------------
# Public API
# -------------------------

def create_dungeon(
    *,
    width: int,
    height: int,
    num_rooms: int,
    min_room_size: int,
    max_room_size: int,
    room_gap: int,
    rng: Any,
) -> Tuple[List[List[str]], List[Tuple[List[Tuple[int, int]], Tuple[int, int]]]]:
    """
    Return (dungeon_grid, room_data)
    - dungeon_grid: list of rows (each row a list of single-char strings, '.' walkable,
      '#' wall)
    - room_data: list of (room_tiles, center) pairs where room_tiles is list of (x,y)
    """
    real = _get_real_module()
    if real:
        if hasattr(real, "create_dungeon"):
            return real.create_dungeon(
                width=width,
                height=height,
                num_rooms=num_rooms,
                min_room_size=min_room_size,
                max_room_size=max_room_size,
                room_gap=room_gap,
                rng=rng,
            )
        if hasattr(real, "generate_dungeon"):
            return real.generate_dungeon(
                width=width,
                height=height,
                num_rooms=num_rooms,
                min_room_size=min_room_size,
                max_room_size=max_room_size,
                room_gap=room_gap,
                rng=rng,
            )
        if hasattr(real, "generate"):
            try:
                return real.generate(
                    width=width,
                    height=height,
                    num_rooms=num_rooms,
                    min_room_size=min_room_size,
                    max_room_size=max_room_size,
                    room_gap=room_gap,
                    rng=rng,
                )
            except TypeError as exc:
                warnings.warn(
                    "Real generator 'generate' signature did not match; "
                    f"falling back. Error: {exc}",
                    RuntimeWarning,
                    stacklevel=2,
                )
                return real.generate(width, height, rng)

        if hasattr(real, "DungeonGenerator"):
            dg = real.DungeonGenerator()
            if hasattr(dg, "create_dungeon"):
                return dg.create_dungeon(
                    width=width,
                    height=height,
                    num_rooms=num_rooms,
                    min_room_size=min_room_size,
                    max_room_size=max_room_size,
                    room_gap=room_gap,
                    rng=rng,
                )
            if hasattr(dg, "generate"):
                return dg.generate(width, height, rng=rng)

    return _fallback_create_dungeon(
        width=width,
        height=height,
        num_rooms=num_rooms,
        min_room_size=min_room_size,
        max_room_size=max_room_size,
        room_gap=room_gap,
        rng=rng,
    )


def is_valid_position(dungeon: List[List[str]] | Any, x: int, y: int) -> bool:
    """True if the dungeon position is in-bounds and walkable '.'"""
    grid: List[List[str]] | None = None
    if isinstance(dungeon, list):
        grid = dungeon
    elif hasattr(dungeon, "grid"):
        grid = dungeon.grid

    if grid is None or not grid or not grid[0]:
        return False

    height = len(grid)
    width = len(grid[0])
    if x < 0 or x >= width or y < 0 or y >= height:
        return False
    return grid[y][x] == "."


def find_empty_position(
    dungeon: List[List[str]],
    room: List[Tuple[int, int]],
    rng: Any,
) -> Tuple[int, int] | None:
    """
    Choose a random '.' tile from the provided room tile list.
    If the real generator provides a helper, attempt to use it.
    """
    real = _get_real_module()
    if real and hasattr(real, "find_empty_position"):
        return real.find_empty_position(dungeon, room, rng)

    if not dungeon or not dungeon[0]:
        return None

    height = len(dungeon)
    width = len(dungeon[0])
    floor_tiles = [
        tile
        for tile in room
        if 0 <= tile[0] < width
        and 0 <= tile[1] < height
        and dungeon[tile[1]][tile[0]] == "."
    ]
    if not floor_tiles:
        return None

    rng_choice = getattr(rng, "choice", None)
    if callable(rng_choice):
        return rng_choice(floor_tiles)

    rng_get_int = getattr(rng, "get_int", None)
    if callable(rng_get_int):
        idx = rng_get_int(0, len(floor_tiles) - 1)
        return floor_tiles[idx]

    warnings.warn(
        "RNG does not provide choice or get_int; using first available tile.",
        RuntimeWarning,
        stacklevel=2,
    )
    return floor_tiles[0]


def line_of_sight(
    dungeon: List[List[str]],
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> bool:
    """Bresenham line check for walls '#'. If the real lib has one, prefer it."""
    real = _get_real_module()
    if real and hasattr(real, "line_of_sight"):
        return real.line_of_sight(dungeon, x1, y1, x2, y2)

    if not dungeon or not dungeon[0]:
        return False

    height = len(dungeon)
    width = len(dungeon[0])
    if not (0 <= x1 < width and 0 <= y1 < height):
        return False
    if not (0 <= x2 < width and 0 <= y2 < height):
        return False

    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    x = x1
    y = y1
    sx = 1 if x2 >= x1 else -1
    sy = 1 if y2 >= y1 else -1

    if dx >= dy:
        err = dx / 2.0
        while x != x2:
            if dungeon[y][x] == "#":
                return False
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y2:
            if dungeon[y][x] == "#":
                return False
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy

    return dungeon[y2][x2] != "#"


def get_dungeon_string(dungeon: List[List[str]], entities: Dict[str, Any]) -> str:
    """
    Render dungeon, overlaying:
      - player as '@'
      - enemies as 's'
    Entities dict expected: {'player': <obj with x,y>, 'enemies': [<obj>,...]}
    """
    real = _get_real_module()
    if real:
        if hasattr(real, "get_dungeon_string"):
            return real.get_dungeon_string(dungeon, entities)
        if hasattr(real, "render"):
            return real.render(dungeon, entities)

    height = len(dungeon)
    width = len(dungeon[0]) if height else 0
    grid = [row[:] for row in dungeon]

    player = entities.get("player")
    if player and 0 <= player.x < width and 0 <= player.y < height:
        grid[player.y][player.x] = "@"

    enemies = entities.get("enemies", [])
    for enemy in enemies or []:
        if 0 <= enemy.x < width and 0 <= enemy.y < height:
            if grid[enemy.y][enemy.x] != "@":
                grid[enemy.y][enemy.x] = "s"
    return "\n".join("".join(row) for row in grid)


# -------------------------
# Fallback generator impl
# -------------------------

def _fallback_create_dungeon(
    *,
    width: int,
    height: int,
    num_rooms: int,
    min_room_size: int,
    max_room_size: int,
    room_gap: int,
    rng: Any,
) -> Tuple[List[List[str]], List[Tuple[List[Tuple[int, int]], Tuple[int, int]]]]:
    dungeon = [["#" for _ in range(width)] for _ in range(height)]
    rooms: List[Tuple[int, int, int, int]] = []
    room_data: List[Tuple[List[Tuple[int, int]], Tuple[int, int]]] = []

    def overlaps(
        *,
        x1: int,
        y1: int,
        w1: int,
        h1: int,
        x2: int,
        y2: int,
        w2: int,
        h2: int,
        gap: int,
    ) -> bool:
        return not (
            x1 + w1 + gap <= x2
            or x2 + w2 + gap <= x1
            or y1 + h1 + gap <= y2
            or y2 + h2 + gap <= y1
        )

    attempts = 0
    max_attempts = max(1000, num_rooms * 50)
    while len(rooms) < num_rooms and attempts < max_attempts:
        attempts += 1
        w = rng.get_int(min_room_size, max_room_size)
        h = rng.get_int(min_room_size, max_room_size)
        x = rng.get_int(1, max(1, width - w - 2))
        y = rng.get_int(1, max(1, height - h - 2))

        if any(
            overlaps(
                x1=x,
                y1=y,
                w1=w,
                h1=h,
                x2=rx,
                y2=ry,
                w2=rw,
                h2=rh,
                gap=room_gap,
            )
            for (rx, ry, rw, rh) in rooms
        ):
            continue

        rooms.append((x, y, w, h))
        tiles: List[Tuple[int, int]] = []
        for yy in range(y, min(y + h, height - 1)):
            for xx in range(x, min(x + w, width - 1)):
                dungeon[yy][xx] = "."
                tiles.append((xx, yy))
        cx = x + w // 2
        cy = y + h // 2
        room_data.append((tiles, (cx, cy)))

    if not room_data:
        cx = width // 2
        cy = height // 2
        dungeon[cy][cx] = "."
        room_data = [([(cx, cy)], (cx, cy))]

    return dungeon, room_data
