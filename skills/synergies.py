"""Skill synergy system for combination bonuses.

Certain skill combinations provide bonus effects beyond their individual contributions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from skills.models import Skill


@dataclass(frozen=True)
class Synergy:
    """A skill synergy bonus."""

    skill1: Skill
    skill2: Skill
    min_level_each: int
    bonus_type: str
    bonus_amount: float
    description: str


# Synergy definitions
SYNERGIES: Final[list[Synergy]] = [
    # Combat synergies
    Synergy(
        Skill.FIGHTING,
        Skill.ARMOUR,
        10,
        "hp_bonus",
        5.0,
        "Tough warrior: +5 HP when both skills at 10+",
    ),
    Synergy(
        Skill.DODGING,
        Skill.STEALTH,
        8,
        "evasion_bonus",
        3.0,
        "Shadow dancer: +3 evasion when both at 8+",
    ),
    Synergy(
        Skill.FIGHTING,
        Skill.UNARMED_COMBAT,
        12,
        "damage_multiplier",
        0.15,
        "Martial artist: +15% unarmed damage",
    ),
    Synergy(
        Skill.SHIELDS,
        Skill.FIGHTING,
        10,
        "block_chance",
        0.10,
        "Defender: +10% block chance",
    ),
    # Magic synergies
    Synergy(
        Skill.SPELLCASTING,
        Skill.INVOCATIONS,
        10,
        "mp_bonus",
        10.0,
        "Magical devotee: +10 MP",
    ),
    Synergy(
        Skill.FIRE_MAGIC,
        Skill.ICE_MAGIC,
        12,
        "spell_power",
        0.20,
        "Elemental master: +20% spell power for both schools",
    ),
    Synergy(
        Skill.AIR_MAGIC,
        Skill.EARTH_MAGIC,
        12,
        "spell_power",
        0.20,
        "Elemental master: +20% spell power for both schools",
    ),
    Synergy(
        Skill.CONJURATIONS,
        Skill.SPELLCASTING,
        15,
        "spell_power",
        0.25,
        "Archmage: +25% conjuration power",
    ),
    # Hybrid synergies
    Synergy(
        Skill.FIGHTING,
        Skill.SPELLCASTING,
        10,
        "versatility",
        1.0,
        "Battle mage: Can cast while wearing armor",
    ),
    Synergy(
        Skill.STEALTH,
        Skill.HEXES,
        8,
        "hex_duration",
        0.30,
        "Trickster: +30% hex duration",
    ),
    Synergy(
        Skill.NECROMANCY,
        Skill.INVOCATIONS,
        10,
        "summon_duration",
        0.40,
        "Dark priest: +40% undead summon duration",
    ),
    # Specialist synergies
    Synergy(
        Skill.LONG_BLADES,
        Skill.DODGING,
        10,
        "riposte_chance",
        0.15,
        "Duelist: 15% chance to riposte after dodge",
    ),
    Synergy(
        Skill.RANGED_WEAPONS,
        Skill.STEALTH,
        10,
        "crit_chance",
        0.20,
        "Sniper: +20% crit chance from stealth",
    ),
    Synergy(
        Skill.TRANSLOCATIONS,
        Skill.DODGING,
        12,
        "blink_frequency",
        0.30,
        "Blink master: Dodge triggers automatic blink",
    ),
]


def get_active_synergies(
    registry: Any,  # EntityRegistry
    entity_id: int,
) -> list[Synergy]:
    """Get all active synergies for an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of active synergies
    """
    skills = registry.get_skills(entity_id)
    active: list[Synergy] = []

    for synergy in SYNERGIES:
        level1 = (
            skills.get(synergy.skill1).level if skills.get(synergy.skill1) else 0
        )
        level2 = (
            skills.get(synergy.skill2).level if skills.get(synergy.skill2) else 0
        )

        if level1 >= synergy.min_level_each and level2 >= synergy.min_level_each:
            active.append(synergy)

    return active


def has_synergy(
    registry: Any,
    entity_id: int,
    skill1: Skill,
    skill2: Skill,
) -> bool:
    """Check if entity has a specific synergy active.

    Args:
        registry: Entity registry
        entity_id: Entity to check
        skill1: First skill
        skill2: Second skill

    Returns:
        True if synergy is active
    """
    active = get_active_synergies(registry, entity_id)

    for synergy in active:
        if (synergy.skill1 == skill1 and synergy.skill2 == skill2) or (
            synergy.skill1 == skill2 and synergy.skill2 == skill1
        ):
            return True

    return False


def get_synergy_bonuses(
    registry: Any,
    entity_id: int,
    bonus_type: str,
) -> float:
    """Get total bonus from synergies of a specific type.

    Args:
        registry: Entity registry
        entity_id: Entity to check
        bonus_type: Type of bonus (e.g., "hp_bonus", "damage_multiplier")

    Returns:
        Total bonus amount
    """
    active = get_active_synergies(registry, entity_id)
    total = 0.0

    for synergy in active:
        if synergy.bonus_type == bonus_type:
            total += synergy.bonus_amount

    return total


def get_available_synergies(
    registry: Any,
    entity_id: int,
) -> list[tuple[Synergy, int, int]]:
    """Get synergies that could be unlocked with more training.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of (synergy, levels_needed_skill1, levels_needed_skill2) tuples
    """
    skills = registry.get_skills(entity_id)
    available: list[tuple[Synergy, int, int]] = []

    for synergy in SYNERGIES:
        level1 = (
            skills.get(synergy.skill1).level if skills.get(synergy.skill1) else 0
        )
        level2 = (
            skills.get(synergy.skill2).level if skills.get(synergy.skill2) else 0
        )

        # Check if not yet active but could be
        if level1 < synergy.min_level_each or level2 < synergy.min_level_each:
            needed1 = max(0, synergy.min_level_each - level1)
            needed2 = max(0, synergy.min_level_each - level2)
            available.append((synergy, needed1, needed2))

    return available


def format_synergy(synergy: Synergy) -> str:
    """Format a synergy for display.

    Args:
        synergy: Synergy to format

    Returns:
        Formatted string
    """
    skill1_name = synergy.skill1.name.replace("_", " ").title()
    skill2_name = synergy.skill2.name.replace("_", " ").title()

    return (
        f"{skill1_name} + {skill2_name} "
        f"({synergy.min_level_each}+ each): "
        f"{synergy.description}"
    )


def format_active_synergies(
    registry: Any,
    entity_id: int,
) -> str:
    """Format all active synergies for an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        Multi-line formatted string
    """
    active = get_active_synergies(registry, entity_id)

    if not active:
        return "No active synergies"

    lines: list[str] = []
    lines.append("=== Active Synergies ===")
    lines.append("")

    for synergy in active:
        lines.append(f"• {format_synergy(synergy)}")

    return "\n".join(lines)


def format_available_synergies(
    registry: Any,
    entity_id: int,
) -> str:
    """Format available (not yet unlocked) synergies.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        Multi-line formatted string
    """
    available = get_available_synergies(registry, entity_id)

    if not available:
        return "All synergies unlocked or unavailable"

    lines: list[str] = []
    lines.append("=== Available Synergies ===")
    lines.append("")

    # Sort by closest to unlocking
    available.sort(key=lambda x: x[1] + x[2])

    for synergy, needed1, needed2 in available[:10]:  # Show top 10
        skill1_name = synergy.skill1.name.replace("_", " ").title()
        skill2_name = synergy.skill2.name.replace("_", " ").title()

        needs: list[str] = []
        if needed1 > 0:
            needs.append(f"{skill1_name} +{needed1}")
        if needed2 > 0:
            needs.append(f"{skill2_name} +{needed2}")

        need_str = ", ".join(needs)
        lines.append(f"• {synergy.description}")
        lines.append(f"  Requires: {need_str}")
        lines.append("")

    return "\n".join(lines)


def format_all_synergies() -> str:
    """Format all possible synergies for reference.

    Returns:
        Multi-line formatted string
    """
    lines: list[str] = []
    lines.append("=== All Skill Synergies ===")
    lines.append("")

    # Group by category
    combat = []
    magic = []
    hybrid = []

    for synergy in SYNERGIES:
        # Categorize based on skills involved
        s1 = synergy.skill1
        s2 = synergy.skill2

        combat_skills = {
            Skill.FIGHTING,
            Skill.AXES,
            Skill.MACES_AND_FLAILS,
            Skill.POLEARMS,
            Skill.LONG_BLADES,
            Skill.SHORT_BLADES,
            Skill.UNARMED_COMBAT,
            Skill.ARMOUR,
            Skill.DODGING,
            Skill.SHIELDS,
            Skill.STEALTH,
        }

        magic_skills = {
            Skill.SPELLCASTING,
            Skill.CONJURATIONS,
            Skill.HEXES,
            Skill.SUMMONINGS,
            Skill.NECROMANCY,
            Skill.FORGECRAFT,
            Skill.TRANSLOCATIONS,
            Skill.ALCHEMY,
            Skill.FIRE_MAGIC,
            Skill.AIR_MAGIC,
            Skill.ICE_MAGIC,
            Skill.EARTH_MAGIC,
            Skill.INVOCATIONS,
        }

        both_combat = s1 in combat_skills and s2 in combat_skills
        both_magic = s1 in magic_skills and s2 in magic_skills

        if both_combat:
            combat.append(synergy)
        elif both_magic:
            magic.append(synergy)
        else:
            hybrid.append(synergy)

    # Format by category
    if combat:
        lines.append("--- Combat Synergies ---")
        for syn in combat:
            lines.append(format_synergy(syn))
        lines.append("")

    if magic:
        lines.append("--- Magic Synergies ---")
        for syn in magic:
            lines.append(format_synergy(syn))
        lines.append("")

    if hybrid:
        lines.append("--- Hybrid Synergies ---")
        for syn in hybrid:
            lines.append(format_synergy(syn))
        lines.append("")

    return "\n".join(lines)
