#!/usr/bin/env python3
"""Production pathfinding perception fields for sound, scent, and detection.

This module owns the pathfinding-oriented perception state used by monsters and
AI systems: multi-slice sound flow fields, Sil-compatible scent stamps, and
monster detection helpers that query those fields. Callers allocate and retain
the NumPy arrays; public update functions mutate only their documented output
slices and use deterministic update semantics for reproducible simulation.

All coordinates are accepted and returned in ``(y, x)`` order unless a docstring
explicitly states otherwise. Terrain arrays store integer ``FeatureType`` values.
Walls block sound and scent. Secret doors block scent. Closed doors attenuate
scent by 95%. Closed and secret doors continue to use flow-specific rules for
sound propagation.
"""

import logging
import os
import time
from enum import IntEnum
from typing import Final

import numpy as np
import polars as pl
from joblib import Parallel, delayed
from numba import njit
from numpy.typing import NDArray

from common.constants import FeatureType
from common.types import Neighbors8
from game.world.los import line_of_sight as los_line_of_sight
from utils.game_rng import GameRNG

logger: Final[logging.Logger] = logging.getLogger(__name__)

MAP_HGT: Final[int] = 64
MAP_WID: Final[int] = 64
BASE_FLOW_CENTER: Final[int] = 100
NOISE_STRENGTH: Final[int] = 80
NOISE_MAX_DIST: Final[int] = 200
SMELL_STRENGTH: Final[int] = 80
SCENT_CLOSED_DOOR_REDUCTION_PERCENT: Final[int] = 95
# Stamp-based scent stores freshness, so closed-door attenuation is an integer
# freshness penalty rather than a floating-point smell intensity multiplier.
SCENT_CLOSED_DOOR_PENALTY: Final[int] = (
    SMELL_STRENGTH * SCENT_CLOSED_DOOR_REDUCTION_PERCENT // 100
)
SCENT_RESET_AGE: Final[int] = 250
FEATURE_WALL: Final[int] = int(FeatureType.WALL)
FEATURE_CLOSED_DOOR: Final[int] = int(FeatureType.CLOSED_DOOR)
FEATURE_SECRET_DOOR: Final[int] = int(FeatureType.SECRET_DOOR)
_cpu_count: int | None = os.cpu_count()
_safe_cpu_count: int = _cpu_count if _cpu_count is not None else 1
DEFAULT_NUM_JOBS: Final[int] = max(1, _safe_cpu_count // 2)


class FlowType(IntEnum):
    """Flow field types for pathfinding-oriented noise propagation."""

    PASS_DOORS = 0  # Door-capable monsters pay a closed-door passage penalty.
    NO_DOORS = 1  # Door-blocked monsters cannot propagate through closed doors.
    REAL_NOISE = 2  # Player/world noise is dampened by closed doors.
    MONSTER_NOISE = 3  # Monster-originated noise uses real-noise door dampening.


MAX_FLOWS: Final[int] = len(FlowType)
FLOW_PASS_DOORS: Final[int] = int(FlowType.PASS_DOORS)
FLOW_NO_DOORS: Final[int] = int(FlowType.NO_DOORS)
FLOW_REAL_NOISE: Final[int] = int(FlowType.REAL_NOISE)
FLOW_MONSTER_NOISE: Final[int] = int(FlowType.MONSTER_NOISE)

NEIGHBORS_8: Final[Neighbors8] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

SCENT_ADJUST_TABLE: Final[NDArray[np.int32]] = np.array(
    [
        [250, 2, 2, 2, 250],
        [2, 1, 1, 1, 2],
        [2, 1, 0, 1, 2],
        [2, 1, 1, 1, 2],
        [250, 2, 2, 2, 250],
    ],
    dtype=np.int32,
)


@njit(cache=True, fastmath=True)  # type: ignore[untyped-decorator]
def in_bounds(y: int, x: int, height: int, width: int) -> bool:
    """Return whether ``(y, x)`` is inside a map of ``height`` by ``width``."""
    return 0 <= y < height and 0 <= x < width


@njit(cache=True, fastmath=True)  # type: ignore[untyped-decorator]
def cave_closed_door(feature_type: int) -> bool:
    """Return ``True`` for closed or secret doors."""
    return feature_type in (FEATURE_CLOSED_DOOR, FEATURE_SECRET_DOOR)


@njit(cache=True, fastmath=True)  # type: ignore[untyped-decorator]
def _sil_distance(y1: int, x1: int, y2: int, x2: int) -> int:
    """Return Sil's integer geometric approximation for two coordinates."""
    ay = abs(y1 - y2)
    ax = abs(x1 - x2)
    return max(ay, ax) + min(ay, ax) // 2


def terrain_transparency_map(terrain_map: NDArray[np.int32]) -> NDArray[np.bool_]:
    """Return scent LOS transparency where only hard scent blockers are opaque."""
    blocking_mask = (terrain_map == FEATURE_WALL) | (terrain_map == FEATURE_SECRET_DOOR)
    transparency_map: NDArray[np.bool_] = ~blocking_mask
    return transparency_map


def _count_closed_doors_on_line(
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    target_y: int,
    target_x: int,
) -> int:
    """Count closed-door cells crossed by the Bresenham line after the origin."""
    dx = abs(target_x - px)
    dy = -abs(target_y - py)
    sx = 1 if px < target_x else -1
    sy = 1 if py < target_y else -1
    err = dx + dy

    x = px
    y = py
    steps = max(dx, -dy)
    closed_doors = 0

    for _ in range(steps):
        e2 = 2 * err
        next_x = x
        next_y = y
        step_x = False
        step_y = False

        if e2 >= dy:
            if x == target_x:
                break
            err += dy
            next_x += sx
            step_x = True

        if e2 <= dx:
            if y == target_y:
                break
            err += dx
            next_y += sy
            step_y = True

        check_x = x
        check_y = y
        if step_x:
            check_x += sx
        if step_y:
            check_y += sy

        if terrain_map[check_y, check_x] == FEATURE_CLOSED_DOOR:
            closed_doors += 1

        x = check_x
        y = check_y
        if x == target_x and y == target_y:
            break

    return closed_doors


def scent_path_penalty(
    terrain_map: NDArray[np.int32],
    transparency_map: NDArray[np.bool_],
    py: int,
    px: int,
    target_y: int,
    target_x: int,
) -> int | None:
    """Return the scent attenuation penalty from player to target.

    Returns ``None`` when the line is blocked by a wall, secret door,
    out-of-bounds coordinate, or failed LOS. Closed doors do not block scent;
    each closed door crossed adds ``SCENT_CLOSED_DOOR_PENALTY``.
    """
    height, width = terrain_map.shape
    if not (
        0 <= py < height
        and 0 <= px < width
        and 0 <= target_y < height
        and 0 <= target_x < width
    ):
        return None

    target_feature = int(terrain_map[target_y, target_x])
    if target_feature in (FEATURE_WALL, FEATURE_SECRET_DOOR):
        return None

    if not los_line_of_sight(px, py, target_x, target_y, transparency_map):
        return None

    closed_doors = _count_closed_doors_on_line(terrain_map, py, px, target_y, target_x)
    return closed_doors * SCENT_CLOSED_DOOR_PENALTY


def line_of_sight(
    y1: int, x1: int, y2: int, x2: int, terrain_map: NDArray[np.int32]
) -> bool:
    """Return LOS for callers using ``(y, x)`` coordinate ordering."""
    height, width = terrain_map.shape
    if not (
        0 <= y1 < height and 0 <= x1 < width and 0 <= y2 < height and 0 <= x2 < width
    ):
        return False

    transparency_map = terrain_transparency_map(terrain_map)
    return bool(los_line_of_sight(x1, y1, x2, y2, transparency_map))


@njit(cache=True, nogil=True)  # type: ignore[untyped-decorator]
def _propagate_noise_kernel(
    cost_grid: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    start_y: int,
    start_x: int,
    start_cost: int,
    max_dist_prop: int,
    door_pass_penalty: int,
    door_real_penalty: int,
    flow_type_val: int,
) -> None:
    """Build one noise flow slice in place with an array-backed queue."""
    height, width = cost_grid.shape
    infinity = np.iinfo(np.int32).max // 2

    for yy in range(height):
        for xx in range(width):
            cost_grid[yy, xx] = infinity

    if not in_bounds(start_y, start_x, height, width):
        return
    if terrain_map[start_y, start_x] == FEATURE_WALL:
        return

    cost_grid[start_y, start_x] = start_cost

    max_q = height * width
    qy = np.empty(max_q, dtype=np.int32)
    qx = np.empty(max_q, dtype=np.int32)
    head = 0
    tail = 0
    count = 0
    in_queue = np.zeros((height, width), dtype=np.bool_)

    qy[tail] = start_y
    qx[tail] = start_x
    tail = (tail + 1) % max_q
    count += 1
    in_queue[start_y, start_x] = True

    while count > 0:
        y = qy[head]
        x = qx[head]
        head = (head + 1) % max_q
        count -= 1
        in_queue[y, x] = False
        current_cost = cost_grid[y, x]

        if current_cost - start_cost >= max_dist_prop:
            continue

        for idx in range(8):
            dy = NEIGHBORS_8[idx][0]
            dx = NEIGHBORS_8[idx][1]
            ny = y + dy
            nx = x + dx

            if not in_bounds(ny, nx, height, width):
                continue

            terrain_feature = terrain_map[ny, nx]
            if terrain_feature == FEATURE_WALL:
                continue

            cost_increase = 1
            is_closed = cave_closed_door(terrain_feature)
            if is_closed:
                if flow_type_val == FLOW_NO_DOORS:
                    continue
                if flow_type_val == FLOW_PASS_DOORS:
                    cost_increase += door_pass_penalty
                elif flow_type_val in (FLOW_REAL_NOISE, FLOW_MONSTER_NOISE):
                    cost_increase += door_real_penalty

            new_cost = current_cost + cost_increase
            if new_cost < cost_grid[ny, nx]:
                cost_grid[ny, nx] = new_cost
                if new_cost - start_cost < max_dist_prop and not in_queue[ny, nx]:
                    qy[tail] = ny
                    qx[tail] = nx
                    tail = (tail + 1) % max_q
                    count += 1
                    in_queue[ny, nx] = True


def update_noise(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    cy: int,
    cx: int,
    which_flow: FlowType,
    penalties: dict[str, int],
) -> None:
    """Fully reset and rebuild exactly one noise flow slice."""
    flow_idx = int(which_flow)
    if not (0 <= flow_idx < MAX_FLOWS):
        raise ValueError(f"Invalid flow index: {flow_idx}")

    flow_centers[flow_idx, 0] = cy
    flow_centers[flow_idx, 1] = cx

    _propagate_noise_kernel(
        cave_cost[flow_idx],
        terrain_map,
        cy,
        cx,
        BASE_FLOW_CENTER,
        NOISE_STRENGTH,
        int(penalties.get("pass", 3)),
        int(penalties.get("real", 5)),
        flow_idx,
    )


@njit(cache=True, fastmath=True)  # type: ignore[untyped-decorator]
def get_noise_dist_scalar(
    cost_at_target: int,
    flow_center_y: int,
    flow_center_x: int,
    target_y: int,
    target_x: int,
) -> int:
    """Convert a stored flow cost to Sil-compatible perceived noise distance."""
    infinity = np.iinfo(np.int32).max // 2
    if cost_at_target >= infinity:
        return NOISE_MAX_DIST

    base_dist = _sil_distance(flow_center_y, flow_center_x, target_y, target_x)
    noise_dist = int(cost_at_target - BASE_FLOW_CENTER + base_dist)
    if noise_dist > NOISE_MAX_DIST or noise_dist < 0:
        return NOISE_MAX_DIST
    return noise_dist


def get_noise_dist(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    which_flow: FlowType,
    y: int,
    x: int,
) -> int:
    """Return the perceived noise distance at ``(y, x)`` for one flow slice."""
    flow_idx = int(which_flow)
    height = cave_cost.shape[1]
    width = cave_cost.shape[2]

    if not (0 <= flow_idx < MAX_FLOWS):
        return NOISE_MAX_DIST
    if not in_bounds(y, x, height, width):
        return NOISE_MAX_DIST

    cost = int(cave_cost[flow_idx, y, x])
    center_y = int(flow_centers[flow_idx, 0])
    center_x = int(flow_centers[flow_idx, 1])
    return int(get_noise_dist_scalar(cost, center_y, center_x, y, x))


def _lay_scent_stamp(
    cave_when: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    transparency_map: NDArray[np.bool_],
    py: int,
    px: int,
    current_scent_when: int,
    scent_adjust: NDArray[np.int32],
) -> None:
    """Lay a 5x5 scent stamp around ``(py, px)`` in place."""
    height, width = cave_when.shape
    table_size = scent_adjust.shape[0]
    offset = table_size // 2

    for i in range(table_size):
        for j in range(table_size):
            y = py + i - offset
            x = px + j - offset
            if not in_bounds(y, x, height, width):
                continue

            adjustment = int(scent_adjust[i, j])
            if adjustment == 250:
                continue

            path_penalty = scent_path_penalty(
                terrain_map, transparency_map, py, px, y, x
            )
            if path_penalty is None:
                continue

            scent_value = current_scent_when + adjustment - path_penalty
            if scent_value > 0:
                cave_when[y, x] = scent_value


def update_smell(
    cave_when: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    global_scent_when: int,
) -> int:
    """Age the global scent counter and lay a Sil-compatible player scent stamp."""
    global_scent_when -= 1

    if global_scent_when <= 0:
        reset_offset = SCENT_RESET_AGE - SMELL_STRENGTH
        is_old_scent = cave_when > SMELL_STRENGTH
        is_recent_scent = (cave_when > 0) & ~is_old_scent
        cave_when[is_old_scent] = 0
        cave_when[is_recent_scent] = reset_offset + cave_when[is_recent_scent]
        global_scent_when = reset_offset

    transparency_map = terrain_transparency_map(terrain_map)
    _lay_scent_stamp(
        cave_when,
        terrain_map,
        transparency_map,
        py,
        px,
        global_scent_when,
        SCENT_ADJUST_TABLE,
    )
    return global_scent_when


def get_scent(cave_when: NDArray[np.int32], y: int, x: int) -> int:
    """Return the raw scent stamp, or ``0`` for no scent/out-of-bounds."""
    height, width = cave_when.shape
    if not in_bounds(y, x, height, width):
        return 0
    return int(cave_when[y, x])


def initialize_monsters(
    num_monsters: int, height: int, width: int, rng: GameRNG | None = None
) -> pl.DataFrame:
    """Create a Polars DataFrame with sample monster perception data."""
    if rng is None:
        rng = GameRNG()
    monster_data = {
        "id": range(num_monsters),
        "r_idx": np.array([rng.get_int(1, 4) for _ in range(num_monsters)]),
        "fy": np.array([rng.get_int(0, height - 1) for _ in range(num_monsters)]),
        "fx": np.array([rng.get_int(0, width - 1) for _ in range(num_monsters)]),
        "is_dead": np.zeros(num_monsters, dtype=bool),
        "perception_stat": np.array([rng.get_int(5, 14) for _ in range(num_monsters)]),
        "alertness": np.array([rng.get_int(-10, 0) for _ in range(num_monsters)]),
        "flags": np.zeros(num_monsters, dtype=np.uint32),
        "heard_player": np.zeros(num_monsters, dtype=bool),
    }
    return pl.DataFrame(monster_data)


def skill_check(
    actor_skill: int,
    difficulty: int,
    target_skill: int,
    rng_seed: int,
) -> bool:
    """Return Sil's two-d10 skill check outcome for deterministic seed input."""
    rng = GameRNG(seed=rng_seed)
    return _sil_skill_check_with_rng(actor_skill, difficulty, target_skill, rng)


def _sil_skill_check_with_rng(
    skill: int, difficulty: int, opposition: int, rng: GameRNG
) -> bool:
    """Return ``(1d10 + skill) - (1d10 + difficulty + opposition) > 0``."""
    actor_total = rng.get_int(1, 10) + skill
    defender_total = rng.get_int(1, 10) + difficulty + opposition
    return (actor_total - defender_total) > 0


def _require_monster_columns(monster_df: pl.DataFrame) -> None:
    """Validate the monster perception DataFrame schema used by this adapter."""
    required_columns: Final[frozenset[str]] = frozenset(
        {"id", "fy", "fx", "is_dead", "perception_stat"}
    )
    missing_columns = required_columns.difference(monster_df.columns)
    if missing_columns:
        missing_display = ", ".join(sorted(missing_columns))
        raise ValueError(f"monster_df missing required columns: {missing_display}")


def _process_monster_perception_chunk(
    monster_df_chunk: pl.DataFrame,
    *,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_stealth_skill: int,
    noise_flow_type: FlowType,
    rng_seeds: list[int],
    chunk_index: int,
) -> tuple[int, list[int]]:
    """Process one deterministic chunk of monster perception checks."""
    num_monsters = monster_df_chunk.height
    if len(rng_seeds) != num_monsters:
        raise ValueError(
            f"Length mismatch: rng_seeds has {len(rng_seeds)} elements but "
            f"monster_df_chunk has {num_monsters} rows"
        )

    alerted_monster_ids: list[int] = []
    height = cave_cost.shape[1]
    width = cave_cost.shape[2]

    ids = monster_df_chunk["id"].to_numpy().astype(np.int64)
    ys = monster_df_chunk["fy"].to_numpy().astype(np.int64)
    xs = monster_df_chunk["fx"].to_numpy().astype(np.int64)
    perceptions = monster_df_chunk["perception_stat"].to_numpy().astype(np.int64)

    for idx in range(num_monsters):
        monster_id = int(ids[idx])
        m_y = int(ys[idx])
        m_x = int(xs[idx])
        perception = int(perceptions[idx])
        if not in_bounds(m_y, m_x, height, width):
            continue

        noise_dist = get_noise_dist(cave_cost, flow_centers, noise_flow_type, m_y, m_x)
        if noise_dist >= NOISE_MAX_DIST:
            continue

        per_seed = rng_seeds[idx]
        if skill_check(perception, noise_dist, player_stealth_skill, per_seed):
            alerted_monster_ids.append(monster_id)

    return chunk_index, alerted_monster_ids


def monster_perception(
    monster_df: pl.DataFrame,
    *,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_y: int,
    player_x: int,
    player_stealth_skill: int,
    rng: GameRNG | None = None,
    num_jobs: int | None = None,
    deterministic: bool = True,
    noise_flow_type: FlowType = FlowType.REAL_NOISE,
) -> list[int]:
    """Return deterministically ordered monster IDs alerted by a noise flow."""
    del player_y, player_x
    start_time = time.monotonic()
    _require_monster_columns(monster_df)

    active_monsters_df = monster_df.filter(~pl.col("is_dead")).sort("id")
    num_monsters = active_monsters_df.height
    if num_monsters == 0:
        return []

    resolved_jobs = num_jobs if num_jobs is not None else DEFAULT_NUM_JOBS
    if deterministic:
        resolved_jobs = 1
    resolved_jobs = max(1, resolved_jobs)

    n_chunks = min(num_monsters, resolved_jobs * 4)
    chunk_size = (num_monsters + n_chunks - 1) // n_chunks
    df_chunks = [
        active_monsters_df.slice(chunk_index * chunk_size, chunk_size)
        for chunk_index in range(n_chunks)
    ]

    master_rng = rng if rng is not None else GameRNG()
    seeds_for_chunks: list[list[int]] = []
    for chunk in df_chunks:
        ids_in_chunk = chunk["id"].to_numpy().astype(np.int64)
        seeds_for_chunks.append(
            [master_rng.derive_seed(int(monster_id)) for monster_id in ids_in_chunk]
        )

    if resolved_jobs <= 1:
        results = [
            _process_monster_perception_chunk(
                chunk,
                cave_cost=cave_cost,
                flow_centers=flow_centers,
                player_stealth_skill=player_stealth_skill,
                noise_flow_type=noise_flow_type,
                rng_seeds=seeds,
                chunk_index=index,
            )
            for index, (chunk, seeds) in enumerate(
                zip(df_chunks, seeds_for_chunks, strict=True)
            )
        ]
    else:
        results = Parallel(n_jobs=resolved_jobs, backend="loky")(
            delayed(_process_monster_perception_chunk)(
                chunk,
                cave_cost=cave_cost,
                flow_centers=flow_centers,
                player_stealth_skill=player_stealth_skill,
                noise_flow_type=noise_flow_type,
                rng_seeds=seeds,
                chunk_index=index,
            )
            for index, (chunk, seeds) in enumerate(
                zip(df_chunks, seeds_for_chunks, strict=True)
            )
        )

    ordered_chunks = [chunk for _, chunk in sorted(results, key=lambda pair: pair[0])]
    all_alerted_ids = [item for sublist in ordered_chunks for item in sublist]

    duration_s = time.monotonic() - start_time
    logger.info(
        "Monster perception for %d monsters took %.4fs using %d jobs.",
        num_monsters,
        duration_s,
        resolved_jobs,
    )
    if all_alerted_ids:
        logger.info("Monsters alerted: %s", all_alerted_ids)
    return all_alerted_ids


def choose_step_by_flow(
    game_tiles: NDArray[np.int32], flow_costs_slice: NDArray[np.int32], my: int, mx: int
) -> tuple[int, int]:
    """Choose an adjacent coordinate descending a flow field without moving."""
    height, width = flow_costs_slice.shape
    if not (0 <= my < height and 0 <= mx < width):
        return my, mx

    current_cost = int(flow_costs_slice[my, mx])
    best_y = my
    best_x = mx

    for dy, dx in NEIGHBORS_8:
        ny = my + dy
        nx = mx + dx
        if not (0 <= ny < height and 0 <= nx < width):
            continue
        if game_tiles[ny, nx] == FEATURE_WALL:
            continue
        neighbor_cost = int(flow_costs_slice[ny, nx])
        if neighbor_cost < current_cost:
            current_cost = neighbor_cost
            best_y = ny
            best_x = nx

    return best_y, best_x


def warmup_perception_kernels() -> None:
    """Warm Numba kernels used by perception gameplay paths."""
    terrain_map = np.full((4, 4), FEATURE_WALL, dtype=np.int32)
    terrain_map[1:3, 1:3] = int(FeatureType.FLOOR)
    cave_cost = np.empty((MAX_FLOWS, 4, 4), dtype=np.int32)
    flow_centers = np.zeros((MAX_FLOWS, 2), dtype=np.int32)
    update_noise(cave_cost, flow_centers, terrain_map, 1, 1, FlowType.REAL_NOISE, {})
    get_noise_dist(cave_cost, flow_centers, FlowType.REAL_NOISE, 1, 1)

    transparency_map = terrain_transparency_map(terrain_map)
    los_line_of_sight(1, 1, 2, 2, transparency_map)
    cave_when = np.zeros((4, 4), dtype=np.int32)
    _lay_scent_stamp(
        cave_when,
        terrain_map,
        transparency_map,
        1,
        1,
        SCENT_RESET_AGE,
        SCENT_ADJUST_TABLE,
    )


if __name__ == "__main__":
    print("Initializing perception systems demo...")
    terrain_map = np.full((MAP_HGT, MAP_WID), FeatureType.FLOOR, dtype=np.int32)
    terrain_map[MAP_HGT // 2, MAP_WID // 4 : 3 * MAP_WID // 4] = FeatureType.WALL
    terrain_map[MAP_HGT // 2 + 5, MAP_WID // 2] = FeatureType.CLOSED_DOOR
    terrain_map[0, :] = FeatureType.WALL
    terrain_map[MAP_HGT - 1, :] = FeatureType.WALL
    terrain_map[:, 0] = FeatureType.WALL
    terrain_map[:, MAP_WID - 1] = FeatureType.WALL

    infinity_val = np.iinfo(np.int32).max // 2
    cave_cost = np.full((MAX_FLOWS, MAP_HGT, MAP_WID), infinity_val, dtype=np.int32)
    flow_centers = np.zeros((MAX_FLOWS, 2), dtype=np.int32)
    cave_when = np.zeros((MAP_HGT, MAP_WID), dtype=np.int32)
    global_scent_when = SCENT_RESET_AGE
    door_penalties = {"pass": 3, "real": 5}

    player_y = MAP_HGT // 2 + 10
    player_x = MAP_WID // 2
    player_stealth_skill = 10
    num_monsters = 500
    monster_df = initialize_monsters(num_monsters, MAP_HGT, MAP_WID)

    print(
        f"Map: {MAP_HGT}x{MAP_WID}, Player: ({player_y}, {player_x}), "
        f"Monsters: {num_monsters}"
    )
    print(f"Using {DEFAULT_NUM_JOBS} parallel jobs for perception.")

    for turn in range(5):
        print(f"\n--- Turn {turn + 1} ---")
        noise_start_time = time.monotonic()
        update_noise(
            cave_cost,
            flow_centers,
            terrain_map,
            player_y,
            player_x,
            FlowType.REAL_NOISE,
            door_penalties,
        )
        update_noise(
            cave_cost,
            flow_centers,
            terrain_map,
            player_y,
            player_x,
            FlowType.PASS_DOORS,
            door_penalties,
        )
        print(f"Noise update took: {time.monotonic() - noise_start_time:.4f}s")

        smell_start_time = time.monotonic()
        global_scent_when = update_smell(
            cave_when, terrain_map, player_y, player_x, global_scent_when
        )
        print(f"Smell update took: {time.monotonic() - smell_start_time:.4f}s")

        alerted_ids = monster_perception(
            monster_df,
            cave_cost=cave_cost,
            flow_centers=flow_centers,
            player_y=player_y,
            player_x=player_x,
            player_stealth_skill=player_stealth_skill,
        )
        print(f"Alerted monsters this turn: {len(alerted_ids)}")

        if num_monsters > 0:
            example_monster_id = 0
            m_info = monster_df.filter(pl.col("id") == example_monster_id)
            if m_info.height > 0:
                m_y, m_x = m_info.select(["fy", "fx"]).row(0)
                noise = get_noise_dist(
                    cave_cost, flow_centers, FlowType.REAL_NOISE, m_y, m_x
                )
                scent = get_scent(cave_when, m_y, m_x)
                print(
                    f"Example Monster {example_monster_id} at ({m_y}, {m_x}): "
                    f"Noise Dist={noise}, Scent Age={scent}"
                )

        player_x += 1
        if player_x >= MAP_WID - 1:
            player_x = 1

    print("\nDemo finished.")
