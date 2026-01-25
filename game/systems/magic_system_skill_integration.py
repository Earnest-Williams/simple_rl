"""Magic system skill integration placeholder.

This module provides hooks for integrating spell casting with the skill system.
When the magic system is implemented, use these functions to award XP and
apply spell power bonuses based on Spellcasting and magic school skills.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.effects import get_magic_bonuses_dict
from skills.models import Skill
from skills.system import award_xp, record_skill_usage

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


def award_spell_xp(
    registry: EntityRegistry,
    caster_id: int,
    spell_level: int,
    spell_school: Skill,
    success: bool = True,
) -> dict[Skill, tuple[int, int]]:
    """Award XP for casting a spell.

    Args:
        registry: Entity registry
        caster_id: Entity casting the spell
        spell_level: Level of the spell (1-9)
        spell_school: Magic school skill (e.g., Skill.FIRE_MAGIC)
        success: Whether the cast was successful

    Returns:
        Dict of skill level-ups (skill -> (old_level, new_level))
    """
    # Record skill usage
    record_skill_usage(registry, caster_id, Skill.SPELLCASTING)
    record_skill_usage(registry, caster_id, spell_school)

    # Award XP based on spell level
    # Higher level spells give more XP
    base_xp = spell_level * 10  # 10-90 XP per spell

    if not success:
        # Failed casts give reduced XP
        base_xp = base_xp // 2

    level_ups = award_xp(registry, caster_id, base_xp)
    return level_ups


def get_spell_power_multiplier(
    registry: EntityRegistry,
    caster_id: int,
    spell_school: Skill,
) -> float:
    """Get spell power multiplier from skills.

    Args:
        registry: Entity registry
        caster_id: Entity casting the spell
        spell_school: Magic school skill

    Returns:
        Total spell power multiplier (1.0 = no bonus)
    """
    skills = registry.get_skills(caster_id)

    spellcasting_level = (
        skills.get(Skill.SPELLCASTING).level if skills.get(Skill.SPELLCASTING) else 0
    )
    school_level = skills.get(spell_school).level if skills.get(spell_school) else 0

    bonuses = get_magic_bonuses_dict(
        spellcasting=spellcasting_level,
        school=school_level,
        invocations=0,  # Not used for spell power
        xl_multiplier=1.0,  # Default XL multiplier
        school_weight=1.0,  # Full weight for primary school
    )

    return bonuses.spell_power


def get_caster_max_mp(
    registry: EntityRegistry,
    caster_id: int,
    base_mp: float,
) -> float:
    """Get max MP with skill bonuses.

    Args:
        registry: Entity registry
        caster_id: Entity to query
        base_mp: Base MP before skill bonuses

    Returns:
        Max MP with skill bonuses applied
    """
    skills = registry.get_skills(caster_id)

    spellcasting_level = (
        skills.get(Skill.SPELLCASTING).level if skills.get(Skill.SPELLCASTING) else 0
    )
    invocations_level = (
        skills.get(Skill.INVOCATIONS).level if skills.get(Skill.INVOCATIONS) else 0
    )

    bonuses = get_magic_bonuses_dict(
        spellcasting=spellcasting_level,
        school=0,  # Not used for MP
        invocations=invocations_level,
        xl_multiplier=1.0,  # Default XL multiplier
        school_weight=0.0,  # Not used for MP calculation
    )

    return bonuses.mp_bonus + base_mp


# Example usage for when magic system is implemented:
"""
# In your spell casting function:

def cast_spell(caster_id, target_id, spell_name, registry, game_state):
    # Get spell data
    spell_level = get_spell_level(spell_name)
    spell_school = get_spell_school(spell_name)  # e.g., Skill.FIRE_MAGIC

    # Apply spell power bonus
    power_mult = get_spell_power_multiplier(registry, caster_id, spell_school)
    damage = base_damage * power_mult

    # Execute spell
    success = execute_spell_effect(target_id, damage, game_state)

    # Award XP
    level_ups = award_spell_xp(
        registry, caster_id, spell_level, spell_school, success
    )

    # Show level-up notifications
    if level_ups:
        for skill, (old_lvl, new_lvl) in level_ups.items():
            game_state.add_message(
                f"Your {skill.name} skill increased to level {new_lvl}!",
                (0, 255, 255)  # Cyan
            )
"""
