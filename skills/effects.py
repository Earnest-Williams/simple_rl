"""Skill effects on combat, defense, and magic.

All bonus calculations Numba-compiled for performance.
Based on DCSS mechanical formulas.
"""

from __future__ import annotations

import numba
import numpy as np

from skills.models import CombatBonuses, MagicBonuses, Skill


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_fighting_hp_bonus(fighting_level: int) -> int:
    """Fighting grants +1 HP per level."""
    return fighting_level


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_fighting_damage_mult(fighting_level: int) -> float:
    """Fighting grants ~1% damage per level."""
    return 1.0 + (fighting_level * 0.01)


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_fighting_accuracy(fighting_level: int) -> int:
    """Fighting grants accuracy bonus."""
    return fighting_level // 2


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_weapon_damage_mult(weapon_level: int) -> float:
    """Weapon skill grants ~2% damage per level."""
    return 1.0 + (weapon_level * 0.02)


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_weapon_accuracy(weapon_level: int) -> int:
    """Weapon skill grants accuracy bonus."""
    return weapon_level


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_armour_bonus(armour_level: int, base_armor: int) -> int:
    """Armour skill increases armor effectiveness by ~3% per level.

    Args:
        armour_level: Armour skill level
        base_armor: Base AC from equipped armor

    Returns:
        Additional armor points
    """
    multiplier: float = 1.0 + (armour_level * 0.03)
    total_armor: int = int(base_armor * multiplier)
    return total_armor - base_armor


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_dodging_evasion(dodging_level: int) -> int:
    """Dodging grants evasion bonus.

    Linear scaling for simplicity.
    """
    return dodging_level


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_shields_defense(shields_level: int) -> int:
    """Shields grant defense bonus."""
    return shields_level // 3


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_stealth_rating(stealth_level: int) -> int:
    """Stealth skill reduces detection range.

    Returns:
        Stealth rating (higher = harder to detect)
    """
    # 25 points per level (DCSS formula)
    return stealth_level * 25


@numba.njit(cache=True, fastmath=True)
def calculate_total_damage_multiplier(
    fighting_level: int,
    weapon_level: int,
) -> float:
    """Combine Fighting and weapon skill damage bonuses.

    Args:
        fighting_level: Fighting skill level
        weapon_level: Weapon-specific skill level

    Returns:
        Total damage multiplier
    """
    fighting_mult: float = calculate_fighting_damage_mult(fighting_level)
    weapon_mult: float = calculate_weapon_damage_mult(weapon_level)

    # Multiplicative combination
    return fighting_mult * weapon_mult


@numba.njit(cache=True, fastmath=True)
def calculate_combat_bonuses(
    fighting_level: int,
    weapon_level: int,
    armour_level: int,
    dodging_level: int,
    shields_level: int,
    base_armor: int,
) -> tuple[int, float, int, int, int, int]:
    """Compute all combat bonuses in single call.

    Args:
        fighting_level: Fighting skill
        weapon_level: Weapon-specific skill
        armour_level: Armour skill
        dodging_level: Dodging skill
        shields_level: Shields skill
        base_armor: Base AC from equipment

    Returns:
        Tuple: (hp_bonus, damage_mult, accuracy, armor_bonus, evasion, shield_def)
    """
    hp_bonus: int = calculate_fighting_hp_bonus(fighting_level)

    damage_mult: float = calculate_total_damage_multiplier(
        fighting_level,
        weapon_level,
    )

    accuracy: int = calculate_fighting_accuracy(
        fighting_level
    ) + calculate_weapon_accuracy(weapon_level)

    armor_bonus: int = calculate_armour_bonus(armour_level, base_armor)

    evasion: int = calculate_dodging_evasion(dodging_level)

    shield_def: int = calculate_shields_defense(shields_level)

    return (hp_bonus, damage_mult, accuracy, armor_bonus, evasion, shield_def)


# Magic skill effects


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_spellcasting_mp(spellcasting_level: int, xl_multiplier: float) -> float:
    """Spellcasting grants MP based on level and XL multiplier.

    Args:
        spellcasting_level: Spellcasting skill
        xl_multiplier: Species-specific XL multiplier (0.5-1.0)

    Returns:
        MP contribution from Spellcasting
    """
    return spellcasting_level * xl_multiplier


@numba.njit(cache=True, fastmath=True, inline="always")
def calculate_invocations_mp(invocations_level: int, xl_multiplier: float) -> float:
    """Invocations grants MP at half the rate of Spellcasting.

    Args:
        invocations_level: Invocations skill
        xl_multiplier: Species XL multiplier

    Returns:
        MP contribution from Invocations
    """
    return (invocations_level / 2.0) * xl_multiplier


@numba.njit(cache=True, fastmath=True)
def calculate_max_mp(
    spellcasting_level: int,
    invocations_level: int,
    xl_multiplier: float,
) -> int:
    """Calculate total max MP from skills.

    Formula: max(Spellcasting, Invocations/2) × XL_multiplier

    Args:
        spellcasting_level: Spellcasting skill
        invocations_level: Invocations skill
        xl_multiplier: Species XL multiplier

    Returns:
        Maximum MP
    """
    spell_mp: float = calculate_spellcasting_mp(spellcasting_level, xl_multiplier)
    invoke_mp: float = calculate_invocations_mp(invocations_level, xl_multiplier)

    return int(max(spell_mp, invoke_mp))


@numba.njit(cache=True, fastmath=True)
def calculate_spell_power(
    spellcasting_level: int,
    school1_level: int,
    school2_level: int,
    school1_weight: float,
    school2_weight: float,
) -> float:
    """Calculate total spell power from Spellcasting and magic schools.

    Args:
        spellcasting_level: Spellcasting skill
        school1_level: Primary magic school level
        school2_level: Secondary magic school level (0 if single-school)
        school1_weight: Weight for primary school (typically 2.0-8.0)
        school2_weight: Weight for secondary school (0.0 if single-school)

    Returns:
        Total spell power
    """
    base_power: float = float(spellcasting_level)

    school_power: float = (school1_level * school1_weight) + (
        school2_level * school2_weight
    )

    return base_power + school_power


@numba.njit(cache=True, fastmath=True)
def calculate_spell_failure_rate(
    spell_difficulty: int,
    total_skill: float,
    intelligence: int,
    armor_penalty: float,
) -> float:
    """Calculate spell failure rate.

    Formula: Base × 2^(-skill/difficulty_factor) + armor_penalty - int_bonus

    Args:
        spell_difficulty: Spell level × base difficulty factor
        total_skill: Combined Spellcasting + average school skills
        intelligence: Intelligence stat
        armor_penalty: Penalty from equipped armor (0.0-0.4)

    Returns:
        Failure rate (0.0-1.0)
    """
    base_failure: float = float(spell_difficulty)

    # Exponential decay with skill
    skill_reduction: float = 2.0 ** (-total_skill / (spell_difficulty * 0.5))
    failure: float = base_failure * skill_reduction

    # Intelligence reduces failure (~1% per point above 8)
    int_bonus: float = max(0.0, float(intelligence - 8)) * 0.01
    failure -= int_bonus

    # Armor adds penalty
    failure += armor_penalty

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, failure))


@numba.njit(cache=True, fastmath=True)
def calculate_magic_bonuses(
    spellcasting_level: int,
    school_level: int,
    invocations_level: int,
    xl_multiplier: float,
    school_weight: float,
) -> tuple[float, float]:
    """Calculate MP and spell power for single-school spell.

    Args:
        spellcasting_level: Spellcasting skill
        school_level: Relevant magic school
        invocations_level: Invocations skill
        xl_multiplier: Species XL multiplier
        school_weight: Weight for this school

    Returns:
        Tuple: (mp_bonus, spell_power)
    """
    mp_bonus: float = float(
        calculate_max_mp(spellcasting_level, invocations_level, xl_multiplier)
    )

    spell_power: float = calculate_spell_power(
        spellcasting_level,
        school_level,
        0,  # No secondary school
        school_weight,
        0.0,
    )

    return (mp_bonus, spell_power)


# Batch operations for multiple entities


@numba.njit(cache=True, parallel=True)
def batch_calculate_combat_bonuses(
    fighting_levels: np.ndarray,
    weapon_levels: np.ndarray,
    armour_levels: np.ndarray,
    dodging_levels: np.ndarray,
    shields_levels: np.ndarray,
    base_armors: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized combat bonus calculation for N entities.

    All input arrays must have shape (N,).

    Returns:
        Tuple of arrays: (hp_bonus, damage_mult, accuracy, armor_bonus, evasion, shield_def)
    """
    n: int = fighting_levels.shape[0]

    hp_bonuses: np.ndarray = np.empty(n, dtype=np.int32)
    damage_mults: np.ndarray = np.empty(n, dtype=np.float32)
    accuracies: np.ndarray = np.empty(n, dtype=np.int32)
    armor_bonuses: np.ndarray = np.empty(n, dtype=np.int32)
    evasions: np.ndarray = np.empty(n, dtype=np.int32)
    shield_defs: np.ndarray = np.empty(n, dtype=np.int32)

    for i in numba.prange(n):
        result = calculate_combat_bonuses(
            int(fighting_levels[i]),
            int(weapon_levels[i]),
            int(armour_levels[i]),
            int(dodging_levels[i]),
            int(shields_levels[i]),
            int(base_armors[i]),
        )

        hp_bonuses[i] = result[0]
        damage_mults[i] = result[1]
        accuracies[i] = result[2]
        armor_bonuses[i] = result[3]
        evasions[i] = result[4]
        shield_defs[i] = result[5]

    return (hp_bonuses, damage_mults, accuracies, armor_bonuses, evasions, shield_defs)


# Python wrapper functions (non-JIT)


def get_combat_bonuses_dict(
    fighting: int,
    weapon: int,
    armour: int,
    dodging: int,
    shields: int,
    base_armor: int,
) -> CombatBonuses:
    """Python wrapper returning CombatBonuses dataclass."""
    result: tuple[int, float, int, int, int, int] = calculate_combat_bonuses(
        fighting, weapon, armour, dodging, shields, base_armor
    )

    return CombatBonuses(
        hp_bonus=result[0],
        damage_multiplier=result[1],
        accuracy_bonus=result[2],
        armor_bonus=result[3],
        evasion_bonus=result[4],
        shield_defense=result[5],
    )


def get_magic_bonuses_dict(
    spellcasting: int,
    school: int,
    invocations: int,
    xl_multiplier: float,
    school_weight: float,
) -> MagicBonuses:
    """Python wrapper returning MagicBonuses dataclass."""
    mp_bonus, spell_power = calculate_magic_bonuses(
        spellcasting, school, invocations, xl_multiplier, school_weight
    )

    return MagicBonuses(
        mp_bonus=mp_bonus,
        spell_power=spell_power,
        success_modifier=0.0,  # Calculated separately via failure rate function
    )


# Skill level extraction helpers


def get_skill_level(skills: dict[Skill, int], skill: Skill) -> int:
    """Safe skill level lookup with default 0."""
    return skills.get(skill, 0)


def extract_weapon_skill_level(
    skills: dict[Skill, int],
    weapon_type: Skill,
) -> int:
    """Extract weapon skill level, validating it's actually a weapon skill."""
    weapon_skills: tuple[Skill, ...] = (
        Skill.AXES,
        Skill.MACES_AND_FLAILS,
        Skill.POLEARMS,
        Skill.STAVES,
        Skill.LONG_BLADES,
        Skill.SHORT_BLADES,
        Skill.RANGED_WEAPONS,
        Skill.THROWING,
        Skill.UNARMED_COMBAT,
    )

    if weapon_type not in weapon_skills:
        return 0

    return skills.get(weapon_type, 0)
