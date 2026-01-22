"""Skill progression formulas and XP tables.

Implements DCSS-style quadratic XP progression with aptitude modifiers.
"""

from __future__ import annotations

import math

# Maximum skill level
MAX_SKILL_LEVEL: int = 27

# XP required to reach each skill level (cumulative, at aptitude 0)
# Based on DCSS formula: XP for level L = 25 * L * (L + 1)
# This gives the exact progression shown in DCSS
_BASE_XP_TABLE: dict[int, int] = {
    0: 0,
    1: 50,
    2: 150,
    3: 300,
    4: 500,
    5: 750,
    6: 1050,
    7: 1400,
    8: 1800,
    9: 2250,
    10: 2750,
    11: 3300,
    12: 3900,
    13: 4550,
    14: 5250,
    15: 6000,
    16: 6800,
    17: 7650,
    18: 8550,
    19: 9500,
    20: 10500,
    21: 11550,
    22: 12650,
    23: 13800,
    24: 15000,
    25: 16250,
    26: 17550,
    27: 18900,
}

# Verify the table matches the DCSS formula
for level in range(28):
    expected = 25 * level * (level + 1)
    if level in _BASE_XP_TABLE:
        assert (
            _BASE_XP_TABLE[level] == expected
        ), f"XP table mismatch at level {level}"


def get_xp_for_level(level: int) -> int:
    """Get the cumulative XP required to reach a given skill level (aptitude 0).

    Args:
        level: Target skill level (0-27)

    Returns:
        Cumulative XP required
    """
    level = max(0, min(MAX_SKILL_LEVEL, level))
    return _BASE_XP_TABLE.get(level, 0)


def get_level_from_xp(xp: float) -> int:
    """Determine skill level from invested XP.

    Args:
        xp: Cumulative XP invested in the skill (after aptitude adjustment)

    Returns:
        Skill level (0-27)
    """
    if xp <= 0:
        return 0

    # Search from the highest level downwards to find the correct level
    for level in range(MAX_SKILL_LEVEL, -1, -1):
        if xp >= _BASE_XP_TABLE[level]:
            return level

    return 0


def get_aptitude_multiplier(aptitude: int) -> float:
    """Calculate XP cost multiplier from aptitude.

    Formula: multiplier = 2^(-aptitude/4)
    - Positive aptitude reduces XP cost (trains faster)
    - Negative aptitude increases XP cost (trains slower)
    - Aptitude +4 halves cost, -4 doubles cost

    Args:
        aptitude: Aptitude modifier (-5 to +11, though no hard limit)

    Returns:
        XP cost multiplier
    """
    return math.pow(2.0, -aptitude / 4.0)


def get_skill_xp_cost(
    from_level: int, to_level: int, aptitude: int = 0
) -> float:
    """Calculate XP cost to go from one skill level to another.

    Args:
        from_level: Starting skill level (0-27)
        to_level: Target skill level (0-27)
        aptitude: Aptitude modifier (default 0)

    Returns:
        XP cost (raw XP, not adjusted by aptitude)
    """
    from_level = max(0, min(MAX_SKILL_LEVEL, from_level))
    to_level = max(0, min(MAX_SKILL_LEVEL, to_level))

    if to_level <= from_level:
        return 0.0

    base_cost = get_xp_for_level(to_level) - get_xp_for_level(from_level)
    multiplier = get_aptitude_multiplier(aptitude)

    # The actual XP the player needs to earn (before aptitude adjustment)
    # is base_cost / multiplier
    # But we track invested XP (after adjustment), so we return base_cost
    return float(base_cost)


def apply_xp_to_skill(
    current_xp: float, xp_to_add: float, aptitude: int = 0
) -> tuple[float, int, int]:
    """Apply raw XP to a skill and determine level changes.

    Args:
        current_xp: Current invested XP in the skill
        xp_to_add: Raw XP to invest (will be adjusted by aptitude)
        aptitude: Aptitude modifier

    Returns:
        Tuple of (new_xp_invested, old_level, new_level)
    """
    old_level = get_level_from_xp(current_xp)

    # Adjust XP by aptitude multiplier
    multiplier = get_aptitude_multiplier(aptitude)
    adjusted_xp = xp_to_add / multiplier

    new_xp = current_xp + adjusted_xp
    new_level = get_level_from_xp(new_xp)

    # Cap at max level
    if new_level > MAX_SKILL_LEVEL:
        new_level = MAX_SKILL_LEVEL
        new_xp = float(get_xp_for_level(MAX_SKILL_LEVEL))

    return (new_xp, old_level, new_level)


def get_xp_to_next_level(current_level: int, current_xp: float) -> float:
    """Get XP needed to reach the next skill level.

    Args:
        current_level: Current skill level
        current_xp: Current invested XP

    Returns:
        XP needed to reach next level (0 if at max level)
    """
    if current_level >= MAX_SKILL_LEVEL:
        return 0.0

    next_level_xp = get_xp_for_level(current_level + 1)
    return max(0.0, next_level_xp - current_xp)


__all__ = [
    "MAX_SKILL_LEVEL",
    "get_xp_for_level",
    "get_level_from_xp",
    "get_aptitude_multiplier",
    "get_skill_xp_cost",
    "apply_xp_to_skill",
    "get_xp_to_next_level",
]
