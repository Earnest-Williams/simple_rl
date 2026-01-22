"""Skill effects on combat, defense, magic, and other mechanics.

Defines how skill levels translate into mechanical bonuses.
"""

from __future__ import annotations

from typing import Dict

from game.skills.models import Skill, SkillProgress


def get_fighting_bonus_hp(fighting_level: int) -> int:
    """Calculate max HP bonus from Fighting skill.

    Args:
        fighting_level: Current Fighting skill level

    Returns:
        Bonus HP to add to max_hp
    """
    # DCSS formula: approximately +1 HP per level
    return fighting_level


def get_fighting_bonus_damage(fighting_level: int) -> float:
    """Calculate damage multiplier from Fighting skill.

    Args:
        fighting_level: Current Fighting skill level

    Returns:
        Damage multiplier (1.0 = no bonus)
    """
    # Roughly +1% per level
    return 1.0 + (fighting_level * 0.01)


def get_fighting_bonus_accuracy(fighting_level: int) -> int:
    """Calculate accuracy bonus from Fighting skill.

    Args:
        fighting_level: Current Fighting skill level

    Returns:
        Accuracy bonus (to-hit modifier)
    """
    # Simple linear scaling
    return fighting_level // 2


def get_weapon_skill_damage_bonus(weapon_skill_level: int) -> float:
    """Calculate damage multiplier from weapon-specific skill.

    Args:
        weapon_skill_level: Level in a specific weapon skill

    Returns:
        Damage multiplier
    """
    # Roughly +2% per level
    return 1.0 + (weapon_skill_level * 0.02)


def get_weapon_skill_accuracy_bonus(weapon_skill_level: int) -> int:
    """Calculate accuracy bonus from weapon-specific skill.

    Args:
        weapon_skill_level: Level in a specific weapon skill

    Returns:
        Accuracy bonus
    """
    return weapon_skill_level


def get_armour_bonus_defense(armour_level: int, base_armor: int) -> int:
    """Calculate defense bonus from Armour skill.

    Higher skill makes armor more effective.

    Args:
        armour_level: Armour skill level
        base_armor: Base armor value from equipment

    Returns:
        Additional armor points
    """
    # Armor skill increases armor effectiveness by ~3% per level
    multiplier = 1.0 + (armour_level * 0.03)
    return int(base_armor * multiplier) - base_armor


def get_dodging_bonus_evasion(dodging_level: int) -> int:
    """Calculate evasion bonus from Dodging skill.

    Args:
        dodging_level: Dodging skill level

    Returns:
        Evasion bonus (reduces chance to be hit)
    """
    # Linear scaling for simplicity
    return dodging_level


def get_shields_bonus_defense(shields_level: int) -> int:
    """Calculate defense bonus from Shields skill.

    Args:
        shields_level: Shields skill level

    Returns:
        Defense bonus from shield proficiency
    """
    return shields_level // 3


def get_stealth_bonus(stealth_level: int) -> int:
    """Calculate stealth rating from Stealth skill.

    Args:
        stealth_level: Stealth skill level

    Returns:
        Stealth rating (affects detection range)
    """
    # Exponential-ish growth for better high-level stealth
    return int(stealth_level * 1.5)


def get_spellcasting_bonus_mp(spellcasting_level: int) -> float:
    """Calculate max mana bonus from Spellcasting skill.

    Args:
        spellcasting_level: Spellcasting skill level

    Returns:
        Bonus mana to add to max_mana
    """
    # DCSS: roughly 1 MP per level
    return float(spellcasting_level)


def get_spellcasting_bonus_power(spellcasting_level: int) -> float:
    """Calculate spell power multiplier from Spellcasting skill.

    Args:
        spellcasting_level: Spellcasting skill level

    Returns:
        Spell power multiplier
    """
    # +1.5% per level
    return 1.0 + (spellcasting_level * 0.015)


def get_magic_school_bonus_power(school_level: int) -> float:
    """Calculate spell power bonus from magic school skill.

    Args:
        school_level: Level in a specific magic school

    Returns:
        Spell power multiplier for that school
    """
    # +2% per level for school specialization
    return 1.0 + (school_level * 0.02)


def get_invocations_bonus_mp(invocations_level: int) -> float:
    """Calculate max mana bonus from Invocations skill.

    Args:
        invocations_level: Invocations skill level

    Returns:
        Bonus mana (MP bonus is max of Spellcasting or Invocations/2)
    """
    # Half the rate of Spellcasting
    return float(invocations_level) / 2.0


def calculate_total_combat_bonuses(
    skills: Dict[Skill, SkillProgress],
    weapon_skill: Skill | None = None,
    base_armor: int = 0,
) -> Dict[str, int | float]:
    """Calculate total combat bonuses from all relevant skills.

    Args:
        skills: Entity's skill progress mapping
        weapon_skill: The weapon skill being used (if any)
        base_armor: Base armor value from equipment (for Armour skill bonus)

    Returns:
        Dictionary of bonus values:
        - hp_bonus: Extra max HP
        - damage_multiplier: Total damage multiplier
        - accuracy_bonus: To-hit bonus
        - defense_bonus: Defense bonus
        - armor_bonus: Armor effectiveness bonus
        - evasion_bonus: Evasion bonus
    """
    bonuses: Dict[str, int | float] = {
        "hp_bonus": 0.0,
        "damage_multiplier": 1.0,
        "accuracy_bonus": 0,
        "defense_bonus": 0,
        "armor_bonus": 0,
        "evasion_bonus": 0,
    }

    # Fighting skill
    fighting = skills.get(Skill.FIGHTING)
    if fighting:
        bonuses["hp_bonus"] += get_fighting_bonus_hp(fighting.level)
        bonuses["damage_multiplier"] *= get_fighting_bonus_damage(fighting.level)
        bonuses["accuracy_bonus"] += get_fighting_bonus_accuracy(fighting.level)

    # Weapon skill
    if weapon_skill and weapon_skill in skills:
        weapon_progress = skills[weapon_skill]
        bonuses["damage_multiplier"] *= get_weapon_skill_damage_bonus(
            weapon_progress.level
        )
        bonuses["accuracy_bonus"] += get_weapon_skill_accuracy_bonus(
            weapon_progress.level
        )

    # Armour skill
    armour = skills.get(Skill.ARMOUR)
    if armour and base_armor > 0:
        bonuses["armor_bonus"] += get_armour_bonus_defense(armour.level, base_armor)

    # Dodging
    dodging = skills.get(Skill.DODGING)
    if dodging:
        bonuses["evasion_bonus"] += get_dodging_bonus_evasion(dodging.level)

    # Shields
    shields = skills.get(Skill.SHIELDS)
    if shields:
        bonuses["defense_bonus"] += get_shields_bonus_defense(shields.level)

    return bonuses


def calculate_total_magic_bonuses(
    skills: Dict[Skill, SkillProgress], magic_school: Skill | None = None
) -> Dict[str, float]:
    """Calculate total magic bonuses from all relevant skills.

    Args:
        skills: Entity's skill progress mapping
        magic_school: The magic school being used (if any)

    Returns:
        Dictionary of bonus values:
        - mp_bonus: Extra max mana
        - spell_power_multiplier: Total spell power multiplier
    """
    bonuses = {
        "mp_bonus": 0.0,
        "spell_power_multiplier": 1.0,
    }

    # Spellcasting
    spellcasting = skills.get(Skill.SPELLCASTING)
    spellcasting_mp = 0.0
    if spellcasting:
        spellcasting_mp = get_spellcasting_bonus_mp(spellcasting.level)
        bonuses["spell_power_multiplier"] *= get_spellcasting_bonus_power(
            spellcasting.level
        )

    # Invocations (MP bonus is max of Spellcasting or Invocations/2)
    invocations = skills.get(Skill.INVOCATIONS)
    invocations_mp = 0.0
    if invocations:
        invocations_mp = get_invocations_bonus_mp(invocations.level)

    bonuses["mp_bonus"] = max(spellcasting_mp, invocations_mp)

    # Magic school specialization
    if magic_school and magic_school in skills:
        school_progress = skills[magic_school]
        bonuses["spell_power_multiplier"] *= get_magic_school_bonus_power(
            school_progress.level
        )

    return bonuses


def get_skill_level(skills: Dict[Skill, SkillProgress], skill: Skill) -> int:
    """Helper to safely get a skill level.

    Args:
        skills: Entity's skill progress mapping
        skill: Skill to check

    Returns:
        Skill level (0 if not found)
    """
    progress = skills.get(skill)
    return progress.level if progress else 0


__all__ = [
    "get_fighting_bonus_hp",
    "get_fighting_bonus_damage",
    "get_fighting_bonus_accuracy",
    "get_weapon_skill_damage_bonus",
    "get_weapon_skill_accuracy_bonus",
    "get_armour_bonus_defense",
    "get_dodging_bonus_evasion",
    "get_shields_bonus_defense",
    "get_stealth_bonus",
    "get_spellcasting_bonus_mp",
    "get_spellcasting_bonus_power",
    "get_magic_school_bonus_power",
    "get_invocations_bonus_mp",
    "calculate_total_combat_bonuses",
    "calculate_total_magic_bonuses",
    "get_skill_level",
]
