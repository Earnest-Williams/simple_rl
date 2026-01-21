"""
Adapter shim so simple_rl.py can use either:
  - your real dungeon generator module (preferred), or
  - a small fallback generator for testing.

The adapter now prefers the in-repo Dungeon package (simple_rl.Dungeon or Dungeon.core)
and will attempt to use CaveGenerator if present.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import warnings
from functools import lru_cache
from types import ModuleType
from typing import Any

# Prefer the local/Django package names first so the repo's Dungeon/ is picked up.
_DEFAULT_CANDIDATES = [
    os.environ.get("DUNGEON_GENERATOR_MODULE"),  # optional env override
    "simple_rl.Dungeon.core",
    "Dungeon.core",
    "simple_rl.Dungeon",
    "Dungeon",
    "dungeon_generator_real",
    "dungeon_gen",
    "dungeon_tool",
    "dungeon",
    "real_dungeon_generator",
]


@lru_cache(maxsize=1)
def _load_real_module() -> tuple[ModuleType | None, str | None]:
    """Try to import a real generator module, prefer local Dungeon.* packages."""
    candidates: list[str] = [c for c in _DEFAULT_CANDIDATES if c]
    import_errors: list[str] = []
    for name in candidates:
        try:
            module = importlib.import_module(name)
            return module, name
        except Exception as exc:
            import_errors.append(f"{name}: {exc}")

    # As a last resort attempt a file import at ./Dungeon/core.py
    here = os.path.dirname(__file__)
    alt_path = os.path.join(here, "Dungeon", "core.py")
    if os.path.isfile(alt_path):
        try:
            spec = importlib.util.spec_from_file_location("Dungeon_core_from_path", alt_path)
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore
                return mod, alt_path
        except Exception as exc:
            import_errors.append(f"file:{alt_path}: {exc}")

    if import_errors:
        details = "; ".join(import_errors[:5])  # avoid giant messages
        warnings.warn(
            "No real dungeon generator module found/importable; using fallback generator. "
            f"Recent import errors: {details}",
            RuntimeWarning,
            stacklevel=2,
        )
    return None, None


def _get_real_module() -> ModuleType | None:
    module, _ = _load_real_module()
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
) -> tuple[list[list[str]], list[tuple[list[tuple[int, int]], tuple[int, int]]]]:
    """
    Return (dungeon_grid, room_data)
    - dungeon_grid: list of rows (each row a list of single-char strings, '.' walkable, '#' wall)
    - room_data: list of (room_tiles, center) pairs where room_tiles is list of (x,y)
    """
    real = _get_real_module()
    if real:
        # Common module-level entrypoints
        try:
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
                except TypeError:
                    # older signatures often look like generate(width, height, rng)
                    return real.generate(width, height, rng)
        except Exception as exc:
            warnings.warn(f"Real generator top-level call failed: {exc}", RuntimeWarning, stacklevel=2)

        # Try exporter classes
        # 1) 'DungeonGenerator' (legacy)
        try:
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
        except Exception as exc:
            warnings.warn(f"Real DungeonGenerator call failed: {exc}", RuntimeWarning, stacklevel=2)

        # 2) CaveGenerator (the real Dungeon/core.py exports this class)
        try:
            CaveGenerator = getattr(real, "CaveGenerator", None)
            # If we imported the package instead of the core module, check submodule
            if CaveGenerator is None and hasattr(real, "core"):
                CaveGenerator = getattr(real.core, "CaveGenerator", None)
            if CaveGenerator:
                # pick conservative parameters
                max_nodes = max(200, num_rooms * 12)
                max_depth = max(8, int(max(8, num_rooms / 2)))
                # instantiate with rng (core.CaveGenerator expects rng as 3rd arg)
                cg = CaveGenerator(max_nodes, max_depth, rng)
                # Try common runner names; call the first available
                runner_names = ["run", "generate", "grow", "execute", "run_generation", "generate_backbone"]
                for rn in runner_names:
                    if hasattr(cg, rn):
                        try:
                            getattr(cg, rn)()
                        except TypeError:
                            # try with parameters if needed
                            try:
                                getattr(cg, rn)(max_nodes, max_depth)
                            except Exception:
                                pass
                        break
                # At this point we expect cg.nodes or cg.node_map to be populated
                raw_nodes = getattr(cg, "nodes", None)
                if raw_nodes is None:
                    node_map = getattr(cg, "node_map", None)
                    raw_nodes = list(node_map.values()) if node_map else None

                if raw_nodes:
                    # Rasterize a simple grid from backbone nodes as fallback renderer.
                    return _rasterize_from_nodes(raw_nodes, width, height, num_rooms, min_room_size, max_room_size, rng)
        except Exception as exc:
            warnings.warn(f"Real CaveGenerator usage failed: {exc}", RuntimeWarning, stacklevel=2)

    # Nothing workable from real generator; use fallback
    return _fallback_create_dungeon(
        width=width,
        height=height,
        num_rooms=num_rooms,
        min_room_size=min_room_size,
        max_room_size=max_room_size,
        room_gap=room_gap,
        rng=rng,
    )


def _rasterize_from_nodes(raw_nodes, width, height, num_rooms, min_room_size, max_room_size, rng):
    """
    Build a simple '#' / '.' grid from backbone nodes.
    raw_nodes: sequence of objects (CaveNode) or dicts with x,y,id,parent_id
    """
    # normalize nodes to dicts with x,y,id,parent_id
    norm = []
    for n in raw_nodes:
        if isinstance(n, dict):
            d = n
            norm.append({"id": d.get("id"), "x": float(d.get("x", 0)), "y": float(d.get("y", 0)), "parent_id": d.get("parent_id")})
        else:
            # try attributes or to_dict
            if hasattr(n, "to_dict"):
                d = n.to_dict()
                norm.append({"id": d.get("id"), "x": float(d.get("x", 0)), "y": float(d.get("y", 0)), "parent_id": d.get("parent_id")})
            else:
                pid = getattr(n, "parent", None)
                pid_val = pid.id if pid else getattr(n, "parent_id", None)
                norm.append({"id": getattr(n, "id", None), "x": float(getattr(n, "x", 0.0)), "y": float(getattr(n, "y", 0.0)), "parent_id": pid_val})

    xs = [n["x"] for n in norm]
    ys = [n["y"] for n in norm]
    if not xs or not ys:
        return _fallback_create_dungeon(width, height, num_rooms, min_room_size, max_room_size, room_gap, rng)

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    world_w = max(1.0, max_x - min_x)
    world_h = max(1.0, max_y - min_y)

    margin = 2
    scale_x = (width - 2 * margin - 1) / world_w
    scale_y = (height - 2 * margin - 1) / world_h
    scale = min(scale_x, scale_y) if world_w > 0 and world_h > 0 else 1.0

    def world_to_grid(xf, yf):
        gx = int(round((xf - min_x) * scale)) + margin
        gy = int(round((yf - min_y) * scale)) + margin
        gx = max(0, min(width - 1, gx))
        gy = max(0, min(height - 1, gy))
        return gx, gy

    grid = [["#" for _ in range(width)] for _ in range(height)]
    room_data = []
    chosen = norm[:num_rooms] if len(norm) >= num_rooms else norm
    id_to_coord = {}
    for n in chosen:
        gx, gy = world_to_grid(n["x"], n["y"])
        id_to_coord[n["id"]] = (gx, gy)
        # choose radius using rng
        try:
            rmin = max(1, int(min_room_size // 2))
            rmax = max(1, int(max_room_size // 2))
            radius = rng.get_int(rmin, rmax) if hasattr(rng, "get_int") else max(1, (rmin + rmax) // 2)
        except Exception:
            radius = max(1, int((min_room_size + max_room_size) // 4))

        tiles = []
        r2 = radius * radius
        for dy in range(-radius, radius + 1):
            yy = gy + dy
            if yy < 0 or yy >= height:
                continue
            for dx in range(-radius, radius + 1):
                xx = gx + dx
                if xx < 0 or xx >= width:
                    continue
                if dx * dx + dy * dy <= r2:
                    grid[yy][xx] = "."
                    tiles.append((xx, yy))
        room_data.append((tiles, (gx, gy)))

    # draw corridors (simple Bresenham)
    def _bresenham(x0, y0, x1, y1):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        x, y = x0, y0
        sx = 1 if x1 >= x0 else -1
        sy = 1 if y1 >= y0 else -1
        if dx >= dy:
            err = dx // 2
            while True:
                yield x, y
                if x == x1:
                    break
                err -= dy
                if err < 0:
                    y += sy
                    err += dx
                x += sx
        else:
            err = dy // 2
            while True:
                yield x, y
                if y == y1:
                    break
                err -= dx
                if err < 0:
                    x += sx
                    err += dy
                y += sy

    for n in chosen:
        pid = n.get("parent_id")
        if pid is None:
            continue
        if n["id"] not in id_to_coord or pid not in id_to_coord:
            continue
        x0, y0 = id_to_coord[pid]
        x1, y1 = id_to_coord[n["id"]]
        for x, y in _bresenham(x0, y0, x1, y1):
            if 0 <= x < width and 0 <= y < height:
                grid[y][x] = "."

    return grid, room_data


def is_valid_position(dungeon: list[list[str]] | Any, x: int, y: int) -> bool:
    grid: list[list[str]] | None = None
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


def find_empty_position(dungeon: list[list[str]], room: list[tuple[int, int]], rng: Any) -> tuple[int, int] | None:
    real = _get_real_module()
    if real and hasattr(real, "find_empty_position"):
        try:
            return real.find_empty_position(dungeon, room, rng)
        except Exception:
            pass

    if not dungeon or not dungeon[0]:
        return None

    height = len(dungeon)
    width = len(dungeon[0])
    floor_tiles = [
        tile
        for tile in room
        if 0 <= tile[0] < width and 0 <= tile[1] < height and dungeon[tile[1]][tile[0]] == "."
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

    warnings.warn("RNG does not provide choice or get_int; using first available tile.", RuntimeWarning, stacklevel=2)
    return floor_tiles[0]


def line_of_sight(dungeon: list[list[str]], x1: int, y1: int, x2: int, y2: int) -> bool:
    real = _get_real_module()
    if real and hasattr(real, "line_of_sight"):
        try:
            return real.line_of_sight(dungeon, x1, y1, x2, y2)
        except Exception:
            pass

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


def get_dungeon_string(dungeon: list[list[str]], entities: dict[str, Any]) -> str:
    real = _get_real_module()
    if real:
        try:
            if hasattr(real, "get_dungeon_string"):
                return real.get_dungeon_string(dungeon, entities)
            if hasattr(real, "render"):
                return real.render(dungeon, entities)
        except Exception:
            pass

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
# Fallback generator impl (unchanged)
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
) -> tuple[list[list[str]], list[tuple[list[tuple[int, int]], tuple[int, int]]]]:
    dungeon = [["#" for _ in range(width)] for _ in range(height)]
    rooms: list[tuple[int, int, int, int]] = []
    room_data: list[tuple[list[tuple[int, int]], tuple[int, int]]] = []

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
        tiles: list[tuple[int, int]] = []
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
