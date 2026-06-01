#!/usr/bin/env python3
"""
scent_and_sound_flow.py

Functional (non-OO) scent and sound flow helpers for simple_rl.

This module implements three related systems used by simple_rl's AI and world
simulation. It is the lights_dev R&D copy; production sound emission and
audio playback live in `game/systems/sound.py`:

  1. Noise propagation (flow fields).  Flow fields are multi-layer integer
     cost maps which monsters consult to move toward a sound source or a
     remembered target.  We expose `update_noise` to build a single flow slice
     inside a shared `cave_cost` 3-D array (shape = (MAX_FLOWS, H, W)).

  2. Scent (smell) tracking.  Implements Sil's "cave_when" stamp approach:
     a global `scent_when` count that decrements each update and a 5×5 stamp
     placed around the player when they lay fresh scent.  Old scent ages and
     cycles out when the global counter wraps.

  3. Monster perception.  Vectorized/chunked perception checks which ask:
     "Does this monster detect the player from this noise field?"  The check
     is the Sil d10/d10 skill mechanic ((1d10 + skill) - (1d10 + difficulty +
     opposition) > 0).

Implementation decisions and differences from the earlier iteration:

  - Full-slice reset.  This implementation resets the entire flow slice to a
    large "infinity" value before building it.  Earlier code attempted to only
    reset a region.  While region resets are an optimization, they are error-
    prone (leave stale costs at the swept-out fringe).  Sil's implementation
    rebuilds the whole slice each time; the full-slice reset is correct,
    simpler, and safe for 64×64 maps.

  - Array-backed queue inside the Numba kernel.  The kernel uses a pre-
    allocated array queue (qy,qx,qc) rather than Python lists or deques.  That
    avoids Numba fallback to object mode and is deterministic and fast.

  - Preserve BASE_FLOW_CENTER semantics.  We keep the repository's convention
    that the cell cost at the source equals BASE_FLOW_CENTER (100).  The
    reported noise distance is computed as `stored_cost - BASE_FLOW_CENTER +
    geometric_approx_distance`, matching the Sil behavior and the rest of the
    game code.  If desired later we can change the kernel to store center=0
    (simpler for movement), but I preserved the existing contract for parity.

  - Scent LOS correctness.  The 5×5 scent stamping uses the project's Numba
    Bresenham LOS (game.world.los.line_of_sight) for correctness.  Earlier
    attempts tried to shortcut LOS for a few directions and blocked mixed
    offsets (e.g., (2,1)).  For 25 checks per turn the correctness wins —
    the cost is negligible and the result matches Sil's intended behaviour.

  - Skill check changed to Sil style (two d10s).  The earlier Python used a
    d20 roll.  This version implements two d10 rolls (one for attacker/
    monster, one for defender/difficulty) to replicate Sil's logic.

  - Defensive bounds and wall checks.  We protect propagation start when the
    source is inside a wall, and ensure all coordinate accesses are in
    bounds.

Typing & style notes:
  - Functions are fully annotated with types (including return annotations).
  - Numba-jitted helpers carry Python annotations for readability. These
    annotations are purely informational to assist static readers; Numba
    compiles them independently.
  - The module exports clean, small functional primitives so it integrates
    easily into the non-OO portions of simple_rl.

Author: adapted for simple_rl integration with expanded documentation.
"""

from __future__ import annotations

import logging
import os
from typing import Final

import numpy as np
import polars as pl
from joblib import Parallel, delayed  # type: ignore[import-untyped]
from numba import njit  # type: ignore[import-untyped]
from numpy.typing import NDArray

from common.constants import FeatureType
from game.constants import MAX_FLOWS, FlowType
from game.world.los import line_of_sight as los_line_of_sight
from utils.game_rng import GameRNG

logger: Final[logging.Logger] = logging.getLogger(__name__)

FEATURE_WALL: Final[int] = int(FeatureType.WALL)
FEATURE_CLOSED_DOOR: Final[int] = int(FeatureType.CLOSED_DOOR)
FEATURE_SECRET_DOOR: Final[int] = int(FeatureType.SECRET_DOOR)
FLOW_PASS_DOORS: Final[int] = int(FlowType.PASS_DOORS)
FLOW_NO_DOORS: Final[int] = int(FlowType.NO_DOORS)
FLOW_REAL_NOISE: Final[int] = int(FlowType.REAL_NOISE)
FLOW_MONSTER_NOISE: Final[int] = int(FlowType.MONSTER_NOISE)

# -----------------------------------------------------------------------------
# Constants (documented)
# -----------------------------------------------------------------------------
# BASE_FLOW_CENTER:
#   The cost value assigned at the source cell when a flow is built.  Sil and
#   the current Python port use a nonzero "center" (100).  We retain that
#   convention so the rest of the codebase (get_noise_dist, perception checks)
#   can keep the exact same arithmetic as existing tests and references.
BASE_FLOW_CENTER: Final[int] = 100

# NOISE_STRENGTH:
#   Maximum propagation depth of the noise builder measured as cost difference
#   from BASE_FLOW_CENTER.  Values beyond this make tiles unreachable for noise.
NOISE_STRENGTH: Final[int] = 80

# NOISE_MAX_DIST:
#   Clamping value returned by get_noise_dist for unreachable/very distant tiles.
NOISE_MAX_DIST: Final[int] = 200

# SMELL_STRENGTH:
#   The scent window size used during the scent reset cycle. This mirrors Sil's
#   convention (scent older than SMELL_STRENGTH is considered early-cycle).
SMELL_STRENGTH: Final[int] = 80

# SCENT_RESET_AGE:
#   The global cycle size for the scent stamp counter. Sil uses a similar
#   global counter that decrements and loops to avoid per-cell age updates.
SCENT_RESET_AGE: Final[int] = 250

# NEIGHBORS_8:
#   8-way neighbor offsets as (dy, dx).  This tuple is Numba-friendly (immutable
#   tuple of tuples) and is used across kernels.
NEIGHBORS_8: Final[tuple[tuple[int, int], ...]] = (
    (-1, -1),
    (-1, 0),
    (-1, 1),
    (0, -1),
    (0, 1),
    (1, -1),
    (1, 0),
    (1, 1),
)

# SCENT_ADJUST_TABLE:
#   5×5 integer adjustments laid around the player when new scent is placed.
#   A value 250 is used in Sil to indicate "do not lay scent" (corners in
#   Sil are excluded). We preserve that sentinel for parity with the engine.
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


# -----------------------------------------------------------------------------
# Low-level helpers (Numba friendly)
# -----------------------------------------------------------------------------
@njit(cache=True, fastmath=True)  # type: ignore[misc]
def in_bounds(y: int, x: int, height: int, width: int) -> bool:
    """
    Return True if (y,x) lies inside a map of the given height and width.

    This simple helper centralizes bounds tests.  It is used from both Numba
    kernels and pure-Python functions for consistent semantics.
    """
    return 0 <= y < height and 0 <= x < width


@njit(cache=True, fastmath=True)  # type: ignore[misc]
def cave_closed_door(feature_type: int) -> bool:
    """
    Return True for closed doors or secret doors.

    The game represents doors as FeatureType.CLOSED_DOOR and FeatureType.SECRET_DOOR.
    Both should be treated as 'closed' for propagation penalties.  We expose this
    small predicate so the kernel is easier to read and so any future door
    semantics changes stay concentrated here.
    """
    return feature_type in (FEATURE_CLOSED_DOOR, FEATURE_SECRET_DOOR)


@njit(cache=True, fastmath=True)  # type: ignore[misc]
def _sil_distance(y1: int, x1: int, y2: int, x2: int) -> int:
    """
    Sil's integer approximate geometric distance.

    Sil approximates euclidean distance with: max(dy,dx) + min(dy,dx)/2.
    We use that here to compute the geometric portion that Sil adds to
    the flow-derived metric when computing perceived noise distance.
    """
    ay = abs(y1 - y2)
    ax = abs(x1 - x2)
    return max(ay, ax) + min(ay, ax) // 2


# -----------------------------------------------------------------------------
# Numba kernel: noise propagation
# -----------------------------------------------------------------------------
@njit(cache=True, nogil=True)  # type: ignore[misc]
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
    """
    Build a single noise flow slice (in-place into `cost_grid`).

    Implementation notes and differences from the earlier iteration:
      - This kernel resets the entire 2-D cost slice (`cost_grid.fill(inf)`).
        The earlier code attempted to reset only a radius region. Resetting the
        entire slice guarantees no stale values remain and exactly mirrors Sil's
        semantics (and the intended game semantics).
      - We use a preallocated array-backed queue (qy,qx,qc).  Earlier code used
        Python lists/Deque in Numba which can cause Numba to operate in object
        mode or be unreliable.  Using fixed arrays keeps the kernel nopython.
      - The kernel avoids starting propagation from inside a wall; this is
        defensive and matches Sil's behavior in practice.
      - Door handling:
          * FlowType.NO_DOORS => closed doors block propagation entirely
          * FlowType.PASS_DOORS => closed doors add `door_pass_penalty`
          * FlowType.REAL_NOISE/MONSTER_NOISE => closed doors add `door_real_penalty`
      - Diagonals are treated as cost 1 for simplicity (same as Sil-port).
    """
    height, width = cost_grid.shape
    infinity = np.iinfo(np.int32).max // 2

    # Full-slice reset to infinity (clear previous flow).
    for yy in range(height):
        for xx in range(width):
            cost_grid[yy, xx] = infinity

    # Guard: out-of-bounds or invalid start -> nothing to do
    if not in_bounds(start_y, start_x, height, width):
        return

    # Guard: do not propagate if source is inside a wall.
    if terrain_map[start_y, start_x] == FEATURE_WALL:
        return

    # Initialize source cell
    cost_grid[start_y, start_x] = start_cost

    # SPFA-style queue.  Each coordinate can appear in the queue at most once,
    # so a fixed-size circular buffer of all cells is enough even when weighted
    # door penalties cause a cell's cost to improve after it was processed.
    max_q = height * width
    qy = np.empty(max_q, dtype=np.int32)
    qx = np.empty(max_q, dtype=np.int32)
    head = 0
    tail = 0
    count = 0
    in_queue = np.zeros((height, width), dtype=np.bool_)

    # enqueue source
    qy[tail] = start_y
    qx[tail] = start_x
    tail = (tail + 1) % max_q
    count += 1
    in_queue[start_y, start_x] = True

    # Weighted shortest-path propagation with relaxation.
    while count > 0:
        y = qy[head]
        x = qx[head]
        head = (head + 1) % max_q
        count -= 1
        in_queue[y, x] = False
        current_cost = cost_grid[y, x]

        # Respect propagation distance cap (relative to starting cost)
        if current_cost - start_cost >= max_dist_prop:
            continue

        # Inspect 8 neighbors
        for idx in range(8):
            dy = NEIGHBORS_8[idx][0]
            dx = NEIGHBORS_8[idx][1]
            ny = y + dy
            nx = x + dx

            if not in_bounds(ny, nx, height, width):
                continue

            terrain_feature = terrain_map[ny, nx]

            # Walls block propagation (except secret doors are handled by
            # cave_closed_door; here we treat an explicit wall as blocking)
            if terrain_feature == FEATURE_WALL:
                continue

            # Base movement cost
            cost_increase = 1

            # Door penalties / blocking based on flow type semantics
            is_closed = cave_closed_door(terrain_feature)
            if is_closed:
                if flow_type_val == FLOW_NO_DOORS:
                    # Blocked for this flow type
                    continue
                elif flow_type_val == FLOW_PASS_DOORS:
                    cost_increase += door_pass_penalty
                elif flow_type_val in (FLOW_REAL_NOISE, FLOW_MONSTER_NOISE):
                    cost_increase += door_real_penalty

            new_cost = current_cost + cost_increase

            # Relaxation: if the new path produces a lower cost, update and enqueue
            if new_cost < cost_grid[ny, nx]:
                cost_grid[ny, nx] = new_cost
                if new_cost - start_cost < max_dist_prop and not in_queue[ny, nx]:
                    qy[tail] = ny
                    qx[tail] = nx
                    tail = (tail + 1) % max_q
                    count += 1
                    in_queue[ny, nx] = True


# -----------------------------------------------------------------------------
# Public API: update_noise
# -----------------------------------------------------------------------------
def update_noise(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    cy: int,
    cx: int,
    which_flow: FlowType,
    penalties: dict[str, int],
) -> None:
    """
    Build the noise flow for a single flow type and store its center.

    Parameters
    ----------
    cave_cost : ndarray[int32]
        3D array of shape (MAX_FLOWS, H, W) used to store cost slices. The
        caller is responsible for allocating this with dtype=int32.
    flow_centers : ndarray[int32]
        Array shape (MAX_FLOWS,2) used to record each flow's origin as (y,x).
    terrain_map : ndarray[int32]
        2D map of FeatureType values.
    cy, cx : int
        Y and X coordinates of the noise source.
    which_flow : FlowType
        Which flow slice to update.
    penalties : dict[str,int]
        Contains door penalties: 'pass' and 'real' (integer costs).
    """
    flow_idx = int(which_flow)
    if not (0 <= flow_idx < MAX_FLOWS):
        raise ValueError(f"Invalid flow index: {flow_idx}")

    # Save the center coordinates so callers can compute distances consistently.
    flow_centers[flow_idx, 0] = cy
    flow_centers[flow_idx, 1] = cx

    # Call the Numba kernel.  We pass the int penalties; defaults are provided by
    # the caller if any are missing.
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


# -----------------------------------------------------------------------------
# Noise distance helpers
# -----------------------------------------------------------------------------
@njit(cache=True, fastmath=True)  # type: ignore[misc]
def get_noise_dist_scalar(
    cost_at_target: int,
    flow_center_y: int,
    flow_center_x: int,
    target_y: int,
    target_x: int,
) -> int:
    """
    Convert the stored flow cost at a location into the perceived noise distance.

    Sil's formula (and the existing repo semantics) are:
        noise_dist = stored_cost - BASE_FLOW_CENTER + geometric_approx_distance

    The function clamps unreachable tiles (infinity sentinel) to NOISE_MAX_DIST
    and also clamps very large results to NOISE_MAX_DIST. Negative results are
    clamped to NOISE_MAX_DIST to preserve Sil's behavior for pathological cases.
    """
    infinity = np.iinfo(np.int32).max // 2
    if cost_at_target >= infinity:
        return NOISE_MAX_DIST

    base_dist = _sil_distance(flow_center_y, flow_center_x, target_y, target_x)
    noise_dist = int(cost_at_target - BASE_FLOW_CENTER + base_dist)

    if noise_dist > NOISE_MAX_DIST:
        return NOISE_MAX_DIST
    if noise_dist < 0:
        # Maintain Sil's behavior: negative distances clamp to NOISE_MAX_DIST.
        return NOISE_MAX_DIST
    return noise_dist


def get_noise_dist(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    which_flow: FlowType,
    y: int,
    x: int,
) -> int:
    """
    Convenience wrapper returning the noise distance at (y,x) for a given flow.
    Performs bounds checks and returns NOISE_MAX_DIST for out-of-bounds.
    """
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


# -----------------------------------------------------------------------------
# Scent system
# -----------------------------------------------------------------------------
def terrain_transparency_map(
    terrain_map: NDArray[np.int32],
) -> NDArray[np.bool_]:  # type: ignore[type-arg]
    """
    Create a boolean transparency map suitable for `los_line_of_sight`:

      True => transparent (not wall).
      False => opaque (wall).

    The LOS helper expects coordinates as x,y when called; this helper returns
    a boolean map so callers can call los_line_of_sight correctly.
    """
    transparency_map: NDArray[np.bool_] = terrain_map != FEATURE_WALL  # type: ignore[type-arg]
    return transparency_map


def update_smell(
    cave_when: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    global_scent_when: int,
) -> int:
    """
    Update the scent (cave_when) map and return the updated global_scent_when.

    Semantics (Sil-compatible):
      1. Decrement the global_scent_when first.
      2. If global_scent_when <= 0, perform a cycle:
         - Erase earlier portion of the previous cycle (values > SMELL_STRENGTH).
         - Remap the recent scent portion with an offset so freshness ordering
           is preserved across cycles.
      3. Lay down a 5x5 stamp about (py,px) with SCENT_ADJUST_TABLE where:
         - The target tile is not a wall.
         - The LOS from (px,py) to (x,y) is clear (use project LOS).
         - The SCENT_ADJUST_TABLE cell is not the sentinel 250.

    Differences vs earlier iteration:
      - This implementation uses the project's `los_line_of_sight` helper for
        correctness. Earlier a fast-cardinal-only LOS was used and it falsely
        blocked certain 5×5 offsets. Because we perform only 25 LOS calls per
        player update, correctness is preferred here.
      - We represent scent as an int32 stamp (same as Sil's `cave_when`).
    """
    height = cave_when.shape[0]
    width = cave_when.shape[1]

    # Age globally according to Sil order (age first, then lay new scent).
    global_scent_when -= 1

    # Periodic reset cycle (wrap)
    if global_scent_when <= 0:
        for y in range(height):
            for x in range(width):
                v = int(cave_when[y, x])
                if v == 0:
                    continue
                if v > SMELL_STRENGTH:
                    # Erase earlier part of previous cycle
                    cave_when[y, x] = 0
                else:
                    # Reset ages of recent scent, preserving relative order
                    cave_when[y, x] = SCENT_RESET_AGE - SMELL_STRENGTH + v
        global_scent_when = SCENT_RESET_AGE - SMELL_STRENGTH

    # Build transparency map (True for transparent tiles)
    transparency_map = terrain_transparency_map(terrain_map)

    # Lay new scent using the 5x5 table
    for i in range(5):
        for j in range(5):
            y = py - 2 + i
            x = px - 2 + j
            if not (0 <= y < height and 0 <= x < width):
                continue

            # Walls cannot hold scent
            if terrain_map[y, x] == FEATURE_WALL:
                continue

            scent_adjust = int(SCENT_ADJUST_TABLE[i, j])
            if scent_adjust == 250:
                # sentinel for corners that Sil excludes
                continue

            # LOS check using project's LOS helper: it expects (x0,y0,x1,y1,transparency)
            if not los_line_of_sight(px, py, x, y, transparency_map):
                continue

            cave_when[y, x] = int(global_scent_when + scent_adjust)

    return int(global_scent_when)


def get_scent(cave_when: NDArray[np.int32], y: int, x: int) -> int:
    """
    Return the raw scent stamp at (y,x) (0 means no scent).  The stamp can be
    compared directly: larger value => fresher scent (Sil semantics).
    """
    if not in_bounds(y, x, cave_when.shape[0], cave_when.shape[1]):
        return 0
    return int(cave_when[y, x])


# -----------------------------------------------------------------------------
# Perception: skill checks and vectorized chunked processing
# -----------------------------------------------------------------------------
def _sil_skill_check_with_rng(
    skill: int, difficulty: int, opposition: int, rng: GameRNG
) -> bool:
    """
    Sil's skill check implemented deterministically with GameRNG.

    Mechanics:
       - Roll 1d10 (monster) + skill
       - Roll 1d10 (difficulty) + difficulty + opposition
       - Success if (monster_total - defender_total) > 0

    This mirrors the C code's two d10 approach. The earlier Python iteration
    used one d20; this version restores Sil's original mechanic.
    """
    r1 = rng.get_int(1, 10)
    r2 = rng.get_int(1, 10)
    lhs = r1 + skill
    rhs = r2 + difficulty + opposition
    return (lhs - rhs) > 0


def _process_monster_perception_chunk(
    monster_df_chunk: pl.DataFrame,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_stealth_skill: int,
    noise_flow_type: FlowType,
    chunk_seed: int,
) -> NDArray[np.int32]:
    """
    Process one chunk of monsters for perception checks.

    Parameters:
      - monster_df_chunk: polars DataFrame slice containing columns:
          'id', 'fy', 'fx', 'perception_stat', 'is_dead'
      - cave_cost, flow_centers: flow state used to compute noise distances
      - player_stealth_skill: integer opposition value used in the roll
      - noise_flow_type: which flow to consult for noise
      - chunk_seed: deterministic seed for this chunk's GameRNG

    Returns:
      - numpy int32 array listing monster IDs that detected the player.

    Notes:
      - This function is pure Python and therefore safe to call in parallel via
        Joblib.  The inner noise -> noise_dist computation relies on the
        Njit'd `get_noise_dist_scalar` to guarantee consistent arithmetic.
    """
    if monster_df_chunk.height == 0:
        return np.array([], dtype=np.int32)

    ids = monster_df_chunk["id"].to_numpy().astype(np.int32)
    ys = monster_df_chunk["fy"].to_numpy().astype(np.int32)
    xs = monster_df_chunk["fx"].to_numpy().astype(np.int32)
    percs = monster_df_chunk["perception_stat"].to_numpy().astype(np.int32)

    rng = GameRNG(seed=chunk_seed)

    flow_idx = int(noise_flow_type)
    center_y = int(flow_centers[flow_idx, 0])
    center_x = int(flow_centers[flow_idx, 1])

    alerted: list[int] = []
    height = cave_cost.shape[1]
    width = cave_cost.shape[2]

    for i in range(len(ids)):
        my = int(ys[i])
        mx = int(xs[i])
        perc = int(percs[i])

        if not in_bounds(my, mx, height, width):
            continue

        cost = int(cave_cost[flow_idx, my, mx])
        noise_dist = int(get_noise_dist_scalar(cost, center_y, center_x, my, mx))

        success = _sil_skill_check_with_rng(perc, noise_dist, player_stealth_skill, rng)
        if success:
            alerted.append(int(ids[i]))

    if len(alerted) == 0:
        return np.array([], dtype=np.int32)
    return np.array(alerted, dtype=np.int32)


def monster_perception(
    monster_df: pl.DataFrame,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_y: int,
    player_x: int,
    player_stealth_skill: int,
    master_rng: GameRNG,
    noise_flow_type: FlowType = FlowType.REAL_NOISE,
    chunk_size: int = 100,
    parallel_threshold: int = 500,
) -> NDArray[np.int32]:
    """
    Top-level perception routine.  Returns an int32 numpy array of alerted monster IDs.

    Behavior:
      - Filters out dead monsters.
      - For small numbers of monsters (< parallel_threshold) runs a single chunk
        (fast path).  For large counts uses Joblib to run multiple chunks in
        parallel.  Seeds for each chunk are derived deterministically from
        `master_rng` so behavior is reproducible.

    Notes:
      - `player_y` / `player_x` are accepted to align with other API shapes,
        but perception uses noise fields (the flow center recorded by update_noise)
        for distance metrics.
    """
    # Filter out dead monsters
    active_monsters = monster_df.filter(~pl.col("is_dead"))
    if active_monsters.height == 0:
        return np.array([], dtype=np.int32)

    # Fast path
    if active_monsters.height < parallel_threshold:
        seed = master_rng.get_int(0, 2**32 - 1)
        return _process_monster_perception_chunk(
            active_monsters,
            cave_cost,
            flow_centers,
            player_stealth_skill,
            noise_flow_type,
            seed,
        )

    # Parallel path
    df_chunks = [
        active_monsters[i : i + chunk_size]
        for i in range(0, active_monsters.height, chunk_size)
    ]
    num_chunks = len(df_chunks)
    chunk_seeds = [master_rng.get_int(0, 2**32 - 1) for _ in range(num_chunks)]

    results = Parallel(n_jobs=max(1, (os.cpu_count() or 1) // 2), backend="threading")(
        delayed(_process_monster_perception_chunk)(
            df_chunks[i],
            cave_cost,
            flow_centers,
            player_stealth_skill,
            noise_flow_type,
            chunk_seeds[i],
        )
        for i in range(num_chunks)
    )

    if len(results) == 0:
        return np.array([], dtype=np.int32)
    return np.concatenate(results)


# -----------------------------------------------------------------------------
# Utility: choose a neighbor by flow cost (stateless helper)
# -----------------------------------------------------------------------------
def choose_step_by_flow(
    game_tiles: NDArray[np.int32], flow_costs_slice: NDArray[np.int32], my: int, mx: int
) -> tuple[int, int]:
    """
    Choose the neighbor with strictly smaller flow cost than the current tile.

    Returns (ny,nx) for the chosen neighbor, or (my,mx) if none reduces cost.

    Notes:
      - This helper is intentionally stateless and small. A caller should check
        walkability and apply movement constraints (open doors, bashing, etc.)
        according to the monster's abilities before actually moving the monster.
      - We treat walls as impassable.
    """
    h, w = flow_costs_slice.shape
    if not (0 <= my < h and 0 <= mx < w):
        return my, mx

    cur_cost = int(flow_costs_slice[my, mx])
    best_y, best_x = my, mx

    for dy, dx in NEIGHBORS_8:
        ny = my + dy
        nx = mx + dx
        if not (0 <= ny < h and 0 <= nx < w):
            continue
        # Skip walls
        if game_tiles[ny, nx] == FEATURE_WALL:
            continue
        neigh_cost = int(flow_costs_slice[ny, nx])
        if neigh_cost < cur_cost:
            cur_cost = neigh_cost
            best_y, best_x = ny, nx

    return best_y, best_x


# End of module
