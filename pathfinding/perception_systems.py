#!/usr/bin/env python3
"""Perception systems for noise propagation and scent tracking.

Foundational implementation of noise, smell, and perception systems inspired by
Sil, optimized for Python using NumPy, Numba, Polars, and Joblib.

Designed as a starting point for iteration with custom map data.
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Final, Literal

import numpy as np
import polars as pl
from joblib import Parallel, delayed
from numba import njit
from numpy.typing import NDArray

from common.constants import FeatureType
from common.types import Neighbors8, QueueItem
from game.world.los import line_of_sight as los_line_of_sight
from utils.game_rng import GameRNG

if TYPE_CHECKING:
    from numba.typed import List as NumbaList

# --- Module Constants ---

logger: Final[logging.Logger] = logging.getLogger(__name__)

# Map dimensions (replace with actual dimensions from game configuration)
MAP_HGT: Final[int] = 64
MAP_WID: Final[int] = 64

# Noise propagation parameters (from Sil analysis)
BASE_FLOW_CENTER: Final[int] = 100  # Starting cost at noise source
NOISE_STRENGTH: Final[int] = 80  # Max propagation distance for cost calculation
NOISE_MAX_DIST: Final[int] = 200  # Clamping value for get_noise_dist

# Scent system parameters
SMELL_STRENGTH: Final[int] = 80  # Threshold for scent aging/reset
SCENT_RESET_AGE: Final[int] = 250  # Base age for scent reset cycle

# Parallelism configuration
_cpu_count: Final[int | None] = os.cpu_count()
_safe_cpu_count: Final[int] = _cpu_count if _cpu_count is not None else 1
N_JOBS: Final[int] = max(1, _safe_cpu_count // 2)  # Use half CPU cores

# --- Flow Type Constants (Purely Functional) ---

# Flow field type constants for noise propagation
FLOW_TYPE_PASS_DOORS: Final[int] = 0  # Monsters that can open/bash doors
FLOW_TYPE_NO_DOORS: Final[int] = 1  # Monsters blocked by closed doors
FLOW_TYPE_REAL_NOISE: Final[int] = 2  # Actual noise (dampened by doors)
FLOW_TYPE_MONSTER_NOISE: Final[int] = 3  # Noise originating from monsters

# Type alias for compile-time checking
FlowType = Literal[0, 1, 2, 3]

# Maximum number of flow types
MAX_FLOWS: Final[int] = 4

# Valid flow types for runtime validation
VALID_FLOW_TYPES: Final[frozenset[int]] = frozenset(
    {
        FLOW_TYPE_PASS_DOORS,
        FLOW_TYPE_NO_DOORS,
        FLOW_TYPE_REAL_NOISE,
        FLOW_TYPE_MONSTER_NOISE,
    }
)

# Neighbor offsets for 8-directional movement (Numba-compatible)
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

# Scent adjustment table (5x5 grid centered on player)
# 0=center, 1=adjacent, 2=diagonal/further, 250=ignore
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


# --- Flow Type Validation Functions ---


def is_valid_flow_type(flow_type: int) -> bool:
    """Check if a value is a valid flow type.

    Args:
        flow_type: Integer to validate.

    Returns:
        True if valid, False otherwise.
    """
    return flow_type in VALID_FLOW_TYPES


def validate_flow_type(flow_type: int) -> FlowType:
    """Validate and return a flow type, raising on invalid input.

    Args:
        flow_type: Integer to validate.

    Returns:
        The validated flow type.

    Raises:
        ValueError: If flow_type is not valid.
    """
    if not is_valid_flow_type(flow_type):
        valid_types = sorted(VALID_FLOW_TYPES)
        msg = f"Invalid flow type: {flow_type}. Valid types: {valid_types}"
        raise ValueError(msg)
    return flow_type  # type: ignore[return-value]


# --- Utility Functions (Numba Accelerated) ---


@njit(cache=True, fastmath=True)
def in_bounds(y: int, x: int, height: int, width: int) -> bool:
    """Check if coordinates are within map bounds.

    Args:
        y: Row coordinate.
        x: Column coordinate.
        height: Map height.
        width: Map width.

    Returns:
        True if coordinates are within bounds, False otherwise.
    """
    return 0 <= y < height and 0 <= x < width


@njit(cache=True, fastmath=True)
def cave_closed_door(feature_type: int) -> bool:
    """Check if feature type represents a closed or secret door.

    Args:
        feature_type: Feature type integer from terrain map.

    Returns:
        True if feature is a closed or secret door, False otherwise.

    Note:
        Adapt this to match your FeatureType enum definitions.
    """
    return (
        feature_type == FeatureType.CLOSED_DOOR
        or feature_type == FeatureType.SECRET_DOOR
    )


def terrain_transparency_map(terrain_map: NDArray[np.int32]) -> NDArray[np.bool_]:
    """Return a boolean transparency map from terrain.

    Args:
        terrain_map: 2D array of terrain/feature type integers.

    Returns:
        Boolean array where True indicates transparent tiles.
    """
    transparent_types: Final[frozenset[int]] = frozenset(
        {
            FeatureType.FLOOR,
            FeatureType.OPEN_DOOR,
            # Add other transparent feature types as needed
        }
    )
    return np.isin(terrain_map, list(transparent_types))


# --- Noise Propagation System ---


@njit(cache=True, fastmath=True)
def _propagate_noise_kernel(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    flow_idx: int,
    base_cost: int,
    door_pass_penalty: int,
    door_real_penalty: int,
) -> None:
    """Propagate noise costs from source using flood-fill algorithm.

    This kernel implements a Dijkstra-like flood fill to calculate noise
    propagation costs through terrain. Door penalties are applied based on
    flow type.

    Args:
        cave_cost: 3D cost array to update in-place (MAX_FLOWS, height, width).
        flow_centers: Array storing origin coordinates (MAX_FLOWS, 2).
        terrain_map: Terrain type values (height, width).
        py: Source Y coordinate.
        px: Source X coordinate.
        flow_idx: Which flow layer to update (0-3).
        base_cost: Starting cost value at source.
        door_pass_penalty: Cost for passing through doors (flow 0).
        door_real_penalty: Cost for real noise through doors (flow 2).
    """
    height: int = cave_cost.shape[1]
    width: int = cave_cost.shape[2]

    # Initialize the source cell
    cave_cost[flow_idx, py, px] = base_cost
    flow_centers[flow_idx, 0] = py
    flow_centers[flow_idx, 1] = px

    # Queue for BFS: stores (cost, y, x) tuples
    # Numba doesn't support heapq, so we use a simple deque-like approach
    queue: list[tuple[int, int, int]] = [(base_cost, py, px)]
    head: int = 0

    while head < len(queue):
        current_cost, cy, cx = queue[head]
        head += 1

        # Skip if we've already found a better path
        if cave_cost[flow_idx, cy, cx] < current_cost:
            continue

        # Check all 8 neighbors
        for dy, dx in NEIGHBORS_8:
            ny: int = cy + dy
            nx: int = cx + dx

            if not in_bounds(ny, nx, height, width):
                continue

            # Calculate cost to move to neighbor
            move_cost: int = 1  # Base movement cost
            terrain: int = terrain_map[ny, nx]

            # Apply door penalties based on flow type
            if cave_closed_door(terrain):
                if flow_idx == FLOW_TYPE_PASS_DOORS:
                    move_cost += door_pass_penalty
                elif flow_idx == FLOW_TYPE_REAL_NOISE:
                    move_cost += door_real_penalty
                elif flow_idx == FLOW_TYPE_NO_DOORS:
                    continue  # Cannot pass closed doors

            # Skip walls (assuming high feature type values are walls)
            if terrain == FeatureType.WALL:
                continue

            new_cost: int = current_cost + move_cost

            # Update if this path is better
            if new_cost < cave_cost[flow_idx, ny, nx]:
                cave_cost[flow_idx, ny, nx] = new_cost
                queue.append((new_cost, ny, nx))


def update_noise(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    flow_type: FlowType,
    door_penalties: dict[str, int],
) -> None:
    """Update noise cost map originating from source coordinates.

    Args:
        cave_cost: 3D noise cost array (MAX_FLOWS, height, width).
        flow_centers: Flow center coordinates (MAX_FLOWS, 2).
        terrain_map: Terrain type values (height, width).
        py: Source Y coordinate.
        px: Source X coordinate.
        flow_type: Which flow type to update (0-3).
        door_penalties: Dict with 'pass' and 'real' door costs.

    Raises:
        ValueError: If flow_type is invalid.
    """
    validate_flow_type(flow_type)

    flow_idx: int = flow_type
    door_pass_penalty: int = door_penalties.get("pass", 3)
    door_real_penalty: int = door_penalties.get("real", 5)

    _propagate_noise_kernel(
        cave_cost,
        flow_centers,
        terrain_map,
        py,
        px,
        flow_idx,
        BASE_FLOW_CENTER,
        door_pass_penalty,
        door_real_penalty,
    )


def get_noise_dist(
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    which_flow: FlowType,
    y: int,
    x: int,
) -> int:
    """Get noise distance from flow center to target coordinates.

    Calculates the noise cost distance from the flow's origin to the target.
    Handles boundary checks and clamping based on Sil logic.

    Args:
        cave_cost: 3D array holding all cost maps (MAX_FLOWS, height, width).
        flow_centers: Array storing origin coordinates (MAX_FLOWS, 2).
        which_flow: Which flow type to query (0-3).
        y: Target Y coordinate.
        x: Target X coordinate.

    Returns:
        Noise distance, clamped to NOISE_MAX_DIST if invalid/unreachable.

    Raises:
        ValueError: If which_flow is invalid.
    """
    validate_flow_type(which_flow)

    flow_idx: int = which_flow
    height: int = cave_cost.shape[1]
    width: int = cave_cost.shape[2]

    if not in_bounds(y, x, height, width):
        return NOISE_MAX_DIST

    # Retrieve cost at target and center
    cost_at_target: int = int(cave_cost[flow_idx, y, x])
    cost_at_center: int = BASE_FLOW_CENTER

    # Check if unreachable (infinity value)
    infinity: int = np.iinfo(cave_cost.dtype).max // 2
    if cost_at_target >= infinity:
        return NOISE_MAX_DIST

    # Calculate distance relative to center
    noise_dist: int = cost_at_target - cost_at_center

    # Clamp negative results (shouldn't happen with proper BFS)
    if noise_dist < 0:
        noise_dist = NOISE_MAX_DIST

    return noise_dist


# --- Scent (Smell) System ---


@njit(cache=True, parallel=False)
def _age_scent_kernel(cave_when: NDArray[np.int32]) -> None:
    """Age scent values by decrementing non-zero cells.

    Args:
        cave_when: 2D array storing scent age values (modified in-place).
    """
    height: int = cave_when.shape[0]
    width: int = cave_when.shape[1]

    for y in range(height):
        for x in range(width):
            if cave_when[y, x] > 0:
                cave_when[y, x] -= 1


@njit(cache=True, parallel=False)
def _lay_scent_kernel(
    cave_when: NDArray[np.int32],
    transparency_map: NDArray[np.bool_],
    py: int,
    px: int,
    current_scent_when: int,
    scent_adjust: NDArray[np.int32],
) -> None:
    """Lay down scent in a 5x5 area around the source.

    Args:
        cave_when: 2D array storing scent age (modified in-place).
        transparency_map: 2D boolean array (True = transparent).
        py: Source Y coordinate.
        px: Source X coordinate.
        current_scent_when: Current global scent age value.
        scent_adjust: 5x5 array defining relative scent freshness.
    """
    height: int = cave_when.shape[0]
    width: int = cave_when.shape[1]

    # Iterate over the 5x5 grid centered on (py, px)
    for dy in range(-2, 3):
        for dx in range(-2, 3):
            ny: int = py + dy
            nx: int = px + dx

            if not in_bounds(ny, nx, height, width):
                continue

            # Get adjustment value from table (centered at 2,2)
            adjustment: int = int(scent_adjust[dy + 2, dx + 2])

            # Skip ignored cells
            if adjustment == 250:
                continue

            # Only lay scent on transparent tiles
            if not transparency_map[ny, nx]:
                continue

            # Set scent age with adjustment
            new_scent: int = current_scent_when + adjustment
            if new_scent > cave_when[ny, nx]:
                cave_when[ny, nx] = new_scent


def update_smell(
    cave_when: NDArray[np.int32],
    terrain_map: NDArray[np.int32],
    py: int,
    px: int,
    global_scent_when: int,
) -> int:
    """Update scent system: age existing scent and lay new scent.

    Args:
        cave_when: 2D array storing scent age values.
        terrain_map: 2D array of terrain types.
        py: Source Y coordinate (typically player).
        px: Source X coordinate.
        global_scent_when: Current global scent timer value.

    Returns:
        Updated global scent timer value.
    """
    # Age existing scent
    _age_scent_kernel(cave_when)

    # Decrement global timer
    global_scent_when -= 1

    # Handle scent cycle reset (when timer reaches zero)
    if global_scent_when <= 0:
        reset_offset: int = SCENT_RESET_AGE - SMELL_STRENGTH

        # Erase old scent and reset recent scent
        is_old_scent: NDArray[np.bool_] = cave_when > SMELL_STRENGTH
        is_recent_scent: NDArray[np.bool_] = (cave_when > 0) & (~is_old_scent)

        cave_when[is_old_scent] = 0
        cave_when[is_recent_scent] = reset_offset + cave_when[is_recent_scent]

        global_scent_when = reset_offset
        logger.info(f"Scent cycle reset. New base age: {global_scent_when}")

    # Lay down new scent
    transparency_map: NDArray[np.bool_] = terrain_transparency_map(terrain_map)
    _lay_scent_kernel(
        cave_when,
        transparency_map,
        py,
        px,
        global_scent_when,
        SCENT_ADJUST_TABLE,
    )

    return global_scent_when


def get_scent(cave_when: NDArray[np.int32], y: int, x: int) -> int:
    """Get scent age at specific coordinates.

    Args:
        cave_when: 2D array storing scent age values.
        y: Target Y coordinate.
        x: Target X coordinate.

    Returns:
        Scent age value, or -1 if out of bounds or no scent.
    """
    height: int = cave_when.shape[0]
    width: int = cave_when.shape[1]

    if not in_bounds(y, x, height, width):
        return -1

    age: int = int(cave_when[y, x])
    return age if age > 0 else -1


# --- Monster Data and Perception ---


def initialize_monsters(
    num_monsters: int,
    height: int,
    width: int,
    rng: GameRNG | None = None,
) -> pl.DataFrame:
    """Create a Polars DataFrame with sample monster data.

    Args:
        num_monsters: Number of monsters to create.
        height: Map height for random positioning.
        width: Map width for random positioning.
        rng: Optional GameRNG instance for determinism.

    Returns:
        Polars DataFrame with monster data columns.
    """
    if rng is None:
        rng = GameRNG()

    monster_data: dict[str, NDArray[np.int32] | NDArray[np.bool_] | range] = {
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
    rng: GameRNG | None = None,
    *,
    min_threshold: int = 5,
    max_threshold: int = 95,
    skill_scale: int = 3,
) -> bool:
    """Perform a d100 skill check with tunable thresholds.

    Args:
        actor_skill: Skill value of acting entity (e.g., perception).
        difficulty: Difficulty modifier (e.g., based on distance).
        target_skill: Skill value of target resisting (e.g., stealth).
        rng: Optional GameRNG instance for determinism.
        min_threshold: Minimum success threshold (default: 5%).
        max_threshold: Maximum success threshold (default: 95%).
        skill_scale: Scaling factor for skill difference (default: 3).

    Returns:
        True if check succeeds, False otherwise.
    """
    if rng is None:
        rng = GameRNG()

    diff: int = actor_skill - target_skill
    threshold: int = 50 + (skill_scale * diff) - difficulty
    threshold = max(min_threshold, min(max_threshold, threshold))

    roll: int = rng.get_int(1, 100)
    return roll <= threshold


def warmup_perception_kernels() -> None:
    """Warm up Numba kernels to avoid first-use JIT compilation stutter."""
    tiny_transparency: NDArray[np.bool_] = np.ones((4, 4), dtype=np.bool_)
    los_line_of_sight(0, 0, 1, 1, tiny_transparency)

    cave_when: NDArray[np.int32] = np.zeros((4, 4), dtype=np.int32)
    scent: NDArray[np.int32] = np.ones((5, 5), dtype=np.int32)
    _lay_scent_kernel(cave_when, tiny_transparency, 2, 2, 250, scent)


def _process_monster_perception_chunk(
    monster_df_chunk: pl.DataFrame,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_stealth_skill: int,
    noise_flow_type: FlowType,
    rng: GameRNG | None = None,
) -> list[int]:
    """Process perception checks for a chunk of monsters.

    Called by Joblib workers for parallel processing.

    Args:
        monster_df_chunk: DataFrame subset containing monsters to process.
        cave_cost: 3D array of noise costs.
        flow_centers: Array of flow center coordinates.
        player_stealth_skill: Player's stealth skill value.
        noise_flow_type: Which noise map to use (0-3).
        rng: Optional GameRNG instance for determinism.

    Returns:
        List of monster IDs that successfully detected the player.
    """
    if rng is None:
        rng = GameRNG()

    alerted_monster_ids: list[int] = []

    for row in monster_df_chunk.iter_rows(named=True):
        monster_id: int = row["id"]
        m_y: int = row["fy"]
        m_x: int = row["fx"]
        perception: int = row["perception_stat"]

        # Get noise distance to player
        noise_dist: int = get_noise_dist(
            cave_cost, flow_centers, noise_flow_type, m_y, m_x
        )

        # Perform perception check
        if skill_check(
            perception,
            noise_dist,
            player_stealth_skill,
            rng,
        ):
            alerted_monster_ids.append(monster_id)

    return alerted_monster_ids


def monster_perception(
    monster_df: pl.DataFrame,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
    player_y: int,
    player_x: int,
    player_stealth_skill: int,
    noise_flow_type: FlowType = FLOW_TYPE_REAL_NOISE,
    chunk_size: int = 100,
) -> list[int]:
    """Check which monsters detect the player using parallel processing.

    Args:
        monster_df: Polars DataFrame containing all monster data.
        cave_cost: 3D noise cost array.
        flow_centers: Flow center coordinates array.
        player_y: Player Y coordinate.
        player_x: Player X coordinate.
        player_stealth_skill: Player's stealth skill value.
        noise_flow_type: Which noise flow to use (default: REAL_NOISE).
        chunk_size: Monsters per processing chunk (default: 100).

    Returns:
        List of monster IDs that detected the player.

    Raises:
        ValueError: If noise_flow_type is invalid.
    """
    validate_flow_type(noise_flow_type)

    # Filter out dead monsters
    active_monsters: pl.DataFrame = monster_df.filter(~pl.col("is_dead"))

    if active_monsters.height == 0:
        return []

    # Split into chunks for parallel processing
    df_chunks: list[pl.DataFrame] = [
        active_monsters[i : i + chunk_size]
        for i in range(0, active_monsters.height, chunk_size)
    ]

    # Process chunks in parallel
    results: list[list[int]] = Parallel(n_jobs=N_JOBS, backend="threading")(
        delayed(_process_monster_perception_chunk)(
            chunk,
            cave_cost,
            flow_centers,
            player_stealth_skill,
            noise_flow_type,
            GameRNG(),
        )
        for chunk in df_chunks
    )

    # Flatten results
    all_alerted_ids: list[int] = [
        monster_id for chunk_result in results for monster_id in chunk_result
    ]

    return all_alerted_ids


# --- Main Execution / Example Usage ---


if __name__ == "__main__":
    print("Initializing perception systems demo...")

    # Initialize map data
    terrain_map: NDArray[np.int32] = np.full(
        (MAP_HGT, MAP_WID), FeatureType.FLOOR, dtype=np.int32
    )

    # Add walls and a closed door for testing
    terrain_map[MAP_HGT // 2, MAP_WID // 4 : 3 * MAP_WID // 4] = FeatureType.WALL
    terrain_map[MAP_HGT // 2 + 5, MAP_WID // 2] = FeatureType.CLOSED_DOOR

    # Add boundary walls
    terrain_map[0, :] = FeatureType.WALL
    terrain_map[MAP_HGT - 1, :] = FeatureType.WALL
    terrain_map[:, 0] = FeatureType.WALL
    terrain_map[:, MAP_WID - 1] = FeatureType.WALL

    # Initialize noise cost map
    infinity_val: int = np.iinfo(np.int32).max // 2
    cave_cost: NDArray[np.int32] = np.full(
        (MAX_FLOWS, MAP_HGT, MAP_WID), infinity_val, dtype=np.int32
    )
    flow_centers: NDArray[np.int32] = np.zeros((MAX_FLOWS, 2), dtype=np.int32)

    # Initialize scent map
    cave_when: NDArray[np.int32] = np.zeros((MAP_HGT, MAP_WID), dtype=np.int32)
    global_scent_when: int = SCENT_RESET_AGE

    # Door penalties
    door_penalties: dict[str, int] = {"pass": 3, "real": 5}

    # Initialize player and monsters
    player_y: int = MAP_HGT // 2 + 10
    player_x: int = MAP_WID // 2
    player_stealth_skill: int = 10

    num_monsters: int = 500
    monster_df: pl.DataFrame = initialize_monsters(num_monsters, MAP_HGT, MAP_WID)

    # Ensure monsters don't start in walls
    monster_df = monster_df.with_columns(
        pl.when(terrain_map[pl.col("fy"), pl.col("fx")] == FeatureType.WALL)
        .then(player_y)
        .otherwise(pl.col("fy"))
        .alias("fy"),
        pl.when(terrain_map[pl.col("fy"), pl.col("fx")] == FeatureType.WALL)
        .then(player_x + 1)
        .otherwise(pl.col("fx"))
        .alias("fx"),
    )

    print(f"Map: {MAP_HGT}x{MAP_WID}, Player: ({player_y}, {player_x})")
    print(f"Monsters: {num_monsters}, Jobs: {N_JOBS}")

    # Simulation loop
    for turn in range(5):
        print(f"\n--- Turn {turn + 1} ---")

        # Update noise
        noise_start: float = time.time()
        update_noise(
            cave_cost,
            flow_centers,
            terrain_map,
            player_y,
            player_x,
            FLOW_TYPE_REAL_NOISE,
            door_penalties,
        )
        update_noise(
            cave_cost,
            flow_centers,
            terrain_map,
            player_y,
            player_x,
            FLOW_TYPE_PASS_DOORS,
            door_penalties,
        )
        print(f"Noise update: {time.time() - noise_start:.4f}s")

        # Update smell
        smell_start: float = time.time()
        global_scent_when = update_smell(
            cave_when, terrain_map, player_y, player_x, global_scent_when
        )
        print(f"Smell update: {time.time() - smell_start:.4f}s")

        # Monster perception
        alerted_ids: list[int] = monster_perception(
            monster_df,
            cave_cost,
            flow_centers,
            player_y,
            player_x,
            player_stealth_skill,
        )

        # Example lookups
        if num_monsters > 0:
            example_id: int = 0
            m_info: pl.DataFrame = monster_df.filter(pl.col("id") == example_id)
            if m_info.height > 0:
                m_y: int
                m_x: int
                m_y, m_x = m_info.select(["fy", "fx"]).row(0)
                noise: int = get_noise_dist(
                    cave_cost, flow_centers, FLOW_TYPE_REAL_NOISE, m_y, m_x
                )
                scent: int = get_scent(cave_when, m_y, m_x)
                print(
                    f"Monster {example_id} at ({m_y}, {m_x}): "
                    f"Noise={noise}, Scent={scent}"
                )

        # Simple player movement
        player_x += 1
        if player_x >= MAP_WID - 1:
            player_x = 1

    print("\nDemo finished.")
