"""Skill milestone abilities unlocked at key levels.

Characters unlock special abilities when reaching certain skill milestones.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from skills.models import Skill


@dataclass(frozen=True)
class Ability:
    """A milestone ability."""

    name: str
    description: str
    skill: Skill
    unlock_level: int
    cooldown_turns: int
    effect_type: str  # "active", "passive", "toggle"


# Milestone ability definitions
MILESTONE_ABILITIES: Final[list[Ability]] = [
    # Fighting abilities
    Ability(
        "Cleave",
        "Melee attacks hit adjacent enemies",
        Skill.FIGHTING,
        10,
        0,
        "passive",
    ),
    Ability(
        "Second Wind",
        "Restore 25% HP once per combat",
        Skill.FIGHTING,
        15,
        100,
        "active",
    ),
    Ability(
        "Berserk",
        "Double damage, half defense for 10 turns",
        Skill.FIGHTING,
        20,
        50,
        "active",
    ),
    # Weapon abilities
    Ability(
        "Whirlwind Strike",
        "Attack all adjacent enemies",
        Skill.AXES,
        12,
        20,
        "active",
    ),
    Ability(
        "Precision Strike",
        "Guaranteed critical hit",
        Skill.LONG_BLADES,
        15,
        30,
        "active",
    ),
    Ability(
        "Riposte",
        "Counter-attack on successful dodge",
        Skill.SHORT_BLADES,
        12,
        0,
        "passive",
    ),
    Ability(
        "Impale",
        "Pin enemy in place, preventing movement",
        Skill.POLEARMS,
        14,
        25,
        "active",
    ),
    Ability(
        "Crushing Blow",
        "Ignore 50% of enemy armor",
        Skill.MACES_AND_FLAILS,
        12,
        15,
        "active",
    ),
    # Defensive abilities
    Ability(
        "Iron Skin",
        "+5 armor for rest of combat",
        Skill.ARMOUR,
        12,
        0,
        "passive",
    ),
    Ability(
        "Perfect Dodge",
        "Dodge next attack automatically",
        Skill.DODGING,
        15,
        20,
        "active",
    ),
    Ability(
        "Shield Bash",
        "Stun enemy with shield, 2 turn duration",
        Skill.SHIELDS,
        10,
        15,
        "active",
    ),
    Ability(
        "Shadow Step",
        "Teleport to any visible tile in range 5",
        Skill.STEALTH,
        18,
        30,
        "active",
    ),
    # Magic abilities
    Ability(
        "Spell Echo",
        "Cast spells twice for double effect",
        Skill.SPELLCASTING,
        20,
        50,
        "active",
    ),
    Ability(
        "Mana Shield",
        "Absorb damage using MP instead of HP",
        Skill.SPELLCASTING,
        15,
        0,
        "toggle",
    ),
    Ability(
        "Chain Lightning",
        "Lightning bounces to nearby enemies",
        Skill.CONJURATIONS,
        15,
        0,
        "passive",
    ),
    Ability(
        "Extended Hex",
        "Hexes last 50% longer",
        Skill.HEXES,
        12,
        0,
        "passive",
    ),
    Ability(
        "Summon Army",
        "Summon 3 creatures instead of 1",
        Skill.SUMMONINGS,
        18,
        40,
        "active",
    ),
    Ability(
        "Life Drain",
        "Heal for 50% of necromancy damage dealt",
        Skill.NECROMANCY,
        15,
        0,
        "passive",
    ),
    Ability(
        "Controlled Blink",
        "Choose exact teleport destination",
        Skill.TRANSLOCATIONS,
        14,
        10,
        "active",
    ),
    # Elemental magic
    Ability(
        "Firestorm",
        "Screen-wide fire damage after 3 turn delay",
        Skill.FIRE_MAGIC,
        16,
        60,
        "active",
    ),
    Ability(
        "Blizzard",
        "Freeze all enemies in large radius",
        Skill.ICE_MAGIC,
        16,
        60,
        "active",
    ),
    Ability(
        "Tornado",
        "Knock back and scatter enemies",
        Skill.AIR_MAGIC,
        14,
        40,
        "active",
    ),
    Ability(
        "Earthquake",
        "Massive damage and stun to grounded enemies",
        Skill.EARTH_MAGIC,
        16,
        50,
        "active",
    ),
    # Special abilities
    Ability(
        "Divine Favor",
        "Invoke god for powerful effect",
        Skill.INVOCATIONS,
        15,
        100,
        "active",
    ),
    Ability(
        "Master Shapeshift",
        "Shapeshift instantly, no MP cost",
        Skill.SHAPESHIFTING,
        20,
        20,
        "active",
    ),
    Ability(
        "Dragon Form",
        "Transform into mighty dragon",
        Skill.SHAPESHIFTING,
        24,
        200,
        "active",
    ),
]


def get_milestones_for_skill(skill: Skill) -> list[Ability]:
    """Get all milestone abilities for a skill.

    Args:
        skill: Skill to check

    Returns:
        List of abilities sorted by unlock level
    """
    abilities = [a for a in MILESTONE_ABILITIES if a.skill == skill]
    return sorted(abilities, key=lambda x: x.unlock_level)


def get_unlocked_abilities(
    registry: any,  # EntityRegistry
    entity_id: int,
) -> list[Ability]:
    """Get all abilities unlocked by an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of unlocked abilities
    """
    skills = registry.get_skills(entity_id)
    unlocked: list[Ability] = []

    for ability in MILESTONE_ABILITIES:
        skill_level = (
            skills.get(ability.skill).level if skills.get(ability.skill) else 0
        )
        if skill_level >= ability.unlock_level:
            unlocked.append(ability)

    return unlocked


def has_ability(
    registry: any,
    entity_id: int,
    ability_name: str,
) -> bool:
    """Check if entity has unlocked a specific ability.

    Args:
        registry: Entity registry
        entity_id: Entity to check
        ability_name: Name of ability to check

    Returns:
        True if ability is unlocked
    """
    unlocked = get_unlocked_abilities(registry, entity_id)
    return any(a.name == ability_name for a in unlocked)


def get_ability(ability_name: str) -> Ability | None:
    """Get ability by name.

    Args:
        ability_name: Name of ability

    Returns:
        Ability or None if not found
    """
    for ability in MILESTONE_ABILITIES:
        if ability.name == ability_name:
            return ability
    return None


def get_next_milestones(
    registry: any,
    entity_id: int,
) -> list[tuple[Ability, int]]:
    """Get next abilities that can be unlocked.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of (ability, levels_needed) tuples
    """
    skills = registry.get_skills(entity_id)
    next_abilities: list[tuple[Ability, int]] = []

    for ability in MILESTONE_ABILITIES:
        skill_level = (
            skills.get(ability.skill).level if skills.get(ability.skill) else 0
        )

        if skill_level < ability.unlock_level:
            levels_needed = ability.unlock_level - skill_level
            next_abilities.append((ability, levels_needed))

    # Sort by levels needed (closest first)
    next_abilities.sort(key=lambda x: x[1])

    return next_abilities[:10]  # Return top 10


def format_ability(ability: Ability, include_skill: bool = True) -> str:
    """Format an ability for display.

    Args:
        ability: Ability to format
        include_skill: Whether to include skill name

    Returns:
        Formatted string
    """
    effect_icon = {
        "active": "⚡",
        "passive": "●",
        "toggle": "⇄",
    }.get(ability.effect_type, "?")

    parts = [f"{effect_icon} {ability.name}"]

    if include_skill:
        skill_name = ability.skill.name.replace("_", " ").title()
        parts.append(f"({skill_name} {ability.unlock_level})")

    parts.append(f"- {ability.description}")

    if ability.cooldown_turns > 0 and ability.effect_type == "active":
        parts.append(f"[CD: {ability.cooldown_turns} turns]")

    return " ".join(parts)


def format_unlocked_abilities(
    registry: any,
    entity_id: int,
) -> str:
    """Format all unlocked abilities for an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        Multi-line formatted string
    """
    unlocked = get_unlocked_abilities(registry, entity_id)

    if not unlocked:
        return "No abilities unlocked yet"

    lines: list[str] = []
    lines.append("=== Unlocked Abilities ===")
    lines.append("")
    lines.append("Legend: ⚡ Active  ● Passive  ⇄ Toggle")
    lines.append("")

    # Group by skill
    by_skill: dict[Skill, list[Ability]] = {}
    for ability in unlocked:
        if ability.skill not in by_skill:
            by_skill[ability.skill] = []
        by_skill[ability.skill].append(ability)

    for skill in sorted(by_skill.keys(), key=lambda s: s.value):
        skill_name = skill.name.replace("_", " ").title()
        lines.append(f"--- {skill_name} ---")

        for ability in sorted(by_skill[skill], key=lambda a: a.unlock_level):
            lines.append(format_ability(ability, include_skill=False))

        lines.append("")

    return "\n".join(lines)


def format_next_milestones(
    registry: any,
    entity_id: int,
) -> str:
    """Format next unlockable milestones.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        Multi-line formatted string
    """
    next_abilities = get_next_milestones(registry, entity_id)

    if not next_abilities:
        return "All abilities unlocked!"

    lines: list[str] = []
    lines.append("=== Next Milestones ===")
    lines.append("")

    for ability, levels_needed in next_abilities:
        skill_name = ability.skill.name.replace("_", " ").title()
        lines.append(f"• {ability.name}")
        lines.append(f"  {ability.description}")
        lines.append(
            f"  Requires: {skill_name} {ability.unlock_level} (+{levels_needed} levels)"
        )
        lines.append("")

    return "\n".join(lines)


def format_all_milestones() -> str:
    """Format all milestone abilities for reference.

    Returns:
        Multi-line formatted string
    """
    lines: list[str] = []
    lines.append("=== All Milestone Abilities ===")
    lines.append("")
    lines.append("Legend: ⚡ Active  ● Passive  ⇄ Toggle")
    lines.append("")

    # Group by skill
    by_skill: dict[Skill, list[Ability]] = {}
    for ability in MILESTONE_ABILITIES:
        if ability.skill not in by_skill:
            by_skill[ability.skill] = []
        by_skill[ability.skill].append(ability)

    for skill in sorted(by_skill.keys(), key=lambda s: s.value):
        abilities = sorted(by_skill[skill], key=lambda a: a.unlock_level)

        if not abilities:
            continue

        skill_name = skill.name.replace("_", " ").title()
        lines.append(f"--- {skill_name} ---")

        for ability in abilities:
            lines.append(
                f"  Level {ability.unlock_level}: {format_ability(ability, False)}"
            )

        lines.append("")

    return "\n".join(lines)
