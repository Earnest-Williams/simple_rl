"""Skill XP progression formulas with Numba acceleration.

All functions JIT-compiled for performance.
Implements DCSS quadratic XP progression with aptitude modifiers.
"""

from __future__ import annotations

from typing import Final

import numba
import numpy as np

from skills.models import (
    MAX_APTITUDE,
    MAX_SKILL_LEVEL,
    MIN_APTITUDE,
    XP_FORMULA_CONSTANT,
)

# Precomputed aptitude multipliers for O(1) lookup
# Index: aptitude + 5 (offset for negative values)
# Formula: 2^(-aptitude/4)
APTITUDE_MULTIPLIERS: Final[np.ndarray] = np.array(
    [2.0 ** (-apt / 4.0) for apt in range(MIN_APTITUDE, MAX_APTITUDE + 1)],
    dtype=np.float32,
)


@numba.njit(cache=True, fastmath=True, inline="always")
def get_aptitude_multiplier(aptitude: int) -> float:
    """Retrieve aptitude XP multiplier via lookup table.

    Args:
        aptitude: Value from -5 to +11

    Returns:
        Multiplier for XP costs (0.149 for +11, 2.378 for -5)
    """
    # Bounds check
    if aptitude < MIN_APTITUDE:
        aptitude = MIN_APTITUDE
    elif aptitude > MAX_APTITUDE:
        aptitude = MAX_APTITUDE

    idx: int = aptitude - MIN_APTITUDE
    return float(APTITUDE_MULTIPLIERS[idx])


@numba.njit(cache=True, fastmath=True)
def calculate_base_xp_for_level(level: int) -> int:
    """Calculate base XP required for level (before aptitude).

    Formula: XP(L) = 25 * L * (L + 1)

    Args:
        level: Target skill level (0-27)

    Returns:
        Cumulative XP required
    """
    if level <= 0:
        return 0
    if level > MAX_SKILL_LEVEL:
        level = MAX_SKILL_LEVEL

    return XP_FORMULA_CONSTANT * level * (level + 1)


@numba.njit(cache=True, fastmath=True)
def calculate_xp_for_level(level: int, aptitude: int) -> int:
    """Calculate XP required for level with aptitude modifier.

    Args:
        level: Target skill level
        aptitude: Aptitude value (-5 to +11)

    Returns:
        Adjusted XP requirement
    """
    base_xp: int = calculate_base_xp_for_level(level)
    multiplier: float = get_aptitude_multiplier(aptitude)
    return int(base_xp * multiplier)


@numba.njit(cache=True, fastmath=True)
def calculate_level_from_xp(xp: int, aptitude: int) -> int:
    """Determine skill level from current XP.

    Uses binary search for O(log N) complexity.

    Args:
        xp: Current XP in skill
        aptitude: Aptitude modifier

    Returns:
        Skill level (0-27)
    """
    if xp <= 0:
        return 0

    # Binary search for level
    low: int = 0
    high: int = MAX_SKILL_LEVEL

    while low < high:
        mid: int = (low + high + 1) // 2
        required_xp: int = calculate_xp_for_level(mid, aptitude)

        if xp >= required_xp:
            low = mid
        else:
            high = mid - 1

    return low


@numba.njit(cache=True, fastmath=True)
def calculate_xp_to_next_level(current_xp: int, aptitude: int) -> int:
    """Calculate remaining XP to reach next level.

    Args:
        current_xp: Current XP
        aptitude: Aptitude modifier

    Returns:
        XP needed for next level
    """
    current_level: int = calculate_level_from_xp(current_xp, aptitude)

    if current_level >= MAX_SKILL_LEVEL:
        return 0  # Already at max

    next_level_xp: int = calculate_xp_for_level(current_level + 1, aptitude)
    return next_level_xp - current_xp


@numba.njit(cache=True, parallel=True)
def batch_calculate_levels(
    xp_array: np.ndarray,
    aptitude_array: np.ndarray,
) -> np.ndarray:
    """Vectorized level calculation for multiple entities.

    Uses Numba parallel for O(N/cores) performance.

    Args:
        xp_array: Array of XP values, shape (N,)
        aptitude_array: Array of aptitudes, shape (N,)

    Returns:
        Array of levels, shape (N,) dtype: uint8
    """
    n: int = xp_array.shape[0]
    levels: np.ndarray = np.empty(n, dtype=np.uint8)

    for i in numba.prange(n):
        levels[i] = calculate_level_from_xp(
            int(xp_array[i]),
            int(aptitude_array[i]),
        )

    return levels


@numba.njit(cache=True, parallel=True)
def batch_calculate_xp_to_next(
    xp_array: np.ndarray,
    aptitude_array: np.ndarray,
) -> np.ndarray:
    """Batch calculate XP remaining to next level.

    Args:
        xp_array: Current XP values, shape (N,)
        aptitude_array: Aptitudes, shape (N,)

    Returns:
        XP to next level, shape (N,) dtype: uint32
    """
    n: int = xp_array.shape[0]
    remaining: np.ndarray = np.empty(n, dtype=np.uint32)

    for i in numba.prange(n):
        remaining[i] = calculate_xp_to_next_level(
            int(xp_array[i]),
            int(aptitude_array[i]),
        )

    return remaining


@numba.njit(cache=True, fastmath=True)
def calculate_training_speed_ratio(
    aptitude_a: int,
    aptitude_b: int,
) -> float:
    """Calculate relative training speed between two aptitudes.

    Args:
        aptitude_a: First aptitude
        aptitude_b: Second aptitude (baseline)

    Returns:
        Speed ratio (>1.0 = A trains faster than B)
    """
    mult_a: float = get_aptitude_multiplier(aptitude_a)
    mult_b: float = get_aptitude_multiplier(aptitude_b)

    # Lower multiplier = faster training
    return mult_b / mult_a


# XP table for common breakpoints (precomputed for display)
def generate_xp_table(aptitude: int = 0) -> dict[int, int]:
    """Generate XP requirements for all levels at given aptitude.

    Not Numba-compiled - for initialization/display only.

    Args:
        aptitude: Aptitude modifier (default: 0)

    Returns:
        Dictionary mapping level -> cumulative XP
    """
    table: dict[int, int] = {}

    for level in range(MAX_SKILL_LEVEL + 1):
        table[level] = calculate_xp_for_level(level, aptitude)

    return table


# Common level breakpoints for reference
LEVEL_BREAKPOINTS: Final[tuple[int, ...]] = (
    1,
    3,
    5,
    8,
    10,
    13,
    15,
    18,
    20,
    23,
    25,
    27,
)


def format_xp_requirements(aptitude: int = 0) -> str:
    """Format XP table as readable string.

    Args:
        aptitude: Aptitude modifier

    Returns:
        Formatted table string
    """
    table: dict[int, int] = generate_xp_table(aptitude)
    lines: list[str] = [f"XP Requirements (aptitude {aptitude:+d}):", ""]

    for level in LEVEL_BREAKPOINTS:
        xp: int = table[level]
        pct: float = (xp / table[MAX_SKILL_LEVEL]) * 100.0
        lines.append(f"Level {level:2d}: {xp:6,d} XP ({pct:5.1f}% of max)")

    return "\n".join(lines)


@numba.njit(cache=True, fastmath=True)
def estimate_training_time(
    current_xp: int,
    target_level: int,
    aptitude: int,
    xp_per_turn: float,
) -> int:
    """Estimate turns required to reach target level.

    Args:
        current_xp: Current XP
        target_level: Desired level
        aptitude: Aptitude modifier
        xp_per_turn: Average XP gain per turn

    Returns:
        Estimated turns needed
    """
    current_level: int = calculate_level_from_xp(current_xp, aptitude)

    if current_level >= target_level:
        return 0

    target_xp: int = calculate_xp_for_level(target_level, aptitude)
    xp_needed: int = target_xp - current_xp

    if xp_per_turn <= 0.0:
        return 0

    return int(xp_needed / xp_per_turn)


@numba.njit(cache=True, fastmath=True)
def calculate_skill_xp_percentage(current_xp: int, aptitude: int) -> float:
    """Calculate percentage progress through current level.

    Args:
        current_xp: Current XP
        aptitude: Aptitude modifier

    Returns:
        Percentage (0.0 to 1.0) through current level
    """
    current_level: int = calculate_level_from_xp(current_xp, aptitude)

    if current_level >= MAX_SKILL_LEVEL:
        return 1.0

    level_start_xp: int = calculate_xp_for_level(current_level, aptitude)
    next_level_xp: int = calculate_xp_for_level(current_level + 1, aptitude)

    level_xp_range: int = next_level_xp - level_start_xp

    if level_xp_range <= 0:
        return 0.0

    progress: int = current_xp - level_start_xp
    return float(progress) / float(level_xp_range)
