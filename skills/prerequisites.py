"""Skill prerequisite system.

Some advanced skills require minimum levels in other skills before training.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from skills.models import Skill


@dataclass(frozen=True)
class Prerequisite:
    """A skill prerequisite requirement."""

    required_skill: Skill
    minimum_level: int
    reason: str


# Prerequisite definitions
SKILL_PREREQUISITES: Final[dict[Skill, list[Prerequisite]]] = {
    # Advanced weapon skills require basic fighting
    Skill.LONG_BLADES: [
        Prerequisite(Skill.FIGHTING, 3, "Basic combat training required")
    ],
    Skill.SHORT_BLADES: [
        Prerequisite(Skill.FIGHTING, 3, "Basic combat training required")
    ],
    Skill.AXES: [Prerequisite(Skill.FIGHTING, 3, "Basic combat training required")],
    Skill.MACES_AND_FLAILS: [
        Prerequisite(Skill.FIGHTING, 3, "Basic combat training required")
    ],
    Skill.POLEARMS: [Prerequisite(Skill.FIGHTING, 3, "Basic combat training required")],
    Skill.STAVES: [Prerequisite(Skill.FIGHTING, 2, "Basic combat training required")],
    # Shield use requires some defensive skill
    Skill.SHIELDS: [
        Prerequisite(Skill.DODGING, 2, "Basic defense training required")
    ],
    # Advanced magic schools require spellcasting foundation
    Skill.CONJURATIONS: [
        Prerequisite(Skill.SPELLCASTING, 4, "Spellcasting foundation required")
    ],
    Skill.HEXES: [
        Prerequisite(Skill.SPELLCASTING, 3, "Spellcasting foundation required")
    ],
    Skill.SUMMONINGS: [
        Prerequisite(Skill.SPELLCASTING, 5, "Spellcasting foundation required")
    ],
    Skill.NECROMANCY: [
        Prerequisite(Skill.SPELLCASTING, 4, "Spellcasting foundation required")
    ],
    Skill.TRANSLOCATIONS: [
        Prerequisite(Skill.SPELLCASTING, 5, "Spellcasting foundation required")
    ],
    # Elemental magic schools require spellcasting
    Skill.FIRE_MAGIC: [
        Prerequisite(Skill.SPELLCASTING, 3, "Spellcasting foundation required")
    ],
    Skill.ICE_MAGIC: [
        Prerequisite(Skill.SPELLCASTING, 3, "Spellcasting foundation required")
    ],
    Skill.AIR_MAGIC: [
        Prerequisite(Skill.SPELLCASTING, 3, "Spellcasting foundation required")
    ],
    Skill.EARTH_MAGIC: [
        Prerequisite(Skill.SPELLCASTING, 3, "Spellcasting foundation required")
    ],
    # Advanced skills
    Skill.SHAPESHIFTING: [
        Prerequisite(Skill.SPELLCASTING, 6, "High magical aptitude required"),
        Prerequisite(Skill.UNARMED_COMBAT, 4, "Physical prowess required"),
    ],
}


def get_prerequisites(skill: Skill) -> list[Prerequisite]:
    """Get all prerequisites for a skill.

    Args:
        skill: Skill to check

    Returns:
        List of prerequisites (empty if none)
    """
    return SKILL_PREREQUISITES.get(skill, [])


def has_prerequisites(skill: Skill) -> bool:
    """Check if a skill has any prerequisites.

    Args:
        skill: Skill to check

    Returns:
        True if skill has prerequisites
    """
    return skill in SKILL_PREREQUISITES


def check_prerequisites(
    registry: any,  # EntityRegistry
    entity_id: int,
    skill: Skill,
) -> tuple[bool, list[str]]:
    """Check if entity meets prerequisites for a skill.

    Args:
        registry: Entity registry
        entity_id: Entity to check
        skill: Skill to check prerequisites for

    Returns:
        Tuple of (all_met, list of unmet requirement messages)
    """
    prerequisites = get_prerequisites(skill)

    if not prerequisites:
        return True, []

    skills = registry.get_skills(entity_id)
    unmet: list[str] = []

    for prereq in prerequisites:
        current_level = (
            skills.get(prereq.required_skill).level
            if skills.get(prereq.required_skill)
            else 0
        )

        if current_level < prereq.minimum_level:
            req_skill_name = prereq.required_skill.name.replace("_", " ").title()
            msg = f"Requires {req_skill_name} {prereq.minimum_level} ({prereq.reason})"
            unmet.append(msg)

    return len(unmet) == 0, unmet


def can_train_skill(
    registry: any,
    entity_id: int,
    skill: Skill,
) -> bool:
    """Check if entity can train a skill (meets prerequisites).

    Args:
        registry: Entity registry
        entity_id: Entity to check
        skill: Skill to check

    Returns:
        True if prerequisites are met or skill has no prerequisites
    """
    met, _ = check_prerequisites(registry, entity_id, skill)
    return met


def get_locked_skills(
    registry: any,
    entity_id: int,
) -> list[Skill]:
    """Get list of skills that are locked due to unmet prerequisites.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of locked skills
    """
    locked: list[Skill] = []

    for skill in Skill:
        if has_prerequisites(skill) and not can_train_skill(registry, entity_id, skill):
            locked.append(skill)

    return locked


def get_unlockable_skills(
    registry: any,
    entity_id: int,
) -> list[tuple[Skill, list[str]]]:
    """Get skills that could be unlocked with more training.

    Args:
        registry: Entity registry
        entity_id: Entity to check

    Returns:
        List of (skill, requirements) tuples for locked skills
    """
    unlockable: list[tuple[Skill, list[str]]] = []

    for skill in Skill:
        if has_prerequisites(skill):
            met, unmet = check_prerequisites(registry, entity_id, skill)
            if not met:
                unlockable.append((skill, unmet))

    return unlockable


def format_prerequisite_info(skill: Skill) -> str:
    """Format prerequisite information for a skill.

    Args:
        skill: Skill to format

    Returns:
        Formatted string describing prerequisites
    """
    prerequisites = get_prerequisites(skill)

    if not prerequisites:
        return f"{skill.name}: No prerequisites"

    lines: list[str] = []
    skill_name = skill.name.replace("_", " ").title()
    lines.append(f"{skill_name} requires:")

    for prereq in prerequisites:
        req_name = prereq.required_skill.name.replace("_", " ").title()
        lines.append(f"  - {req_name} {prereq.minimum_level}+ ({prereq.reason})")

    return "\n".join(lines)


def format_all_prerequisites() -> str:
    """Format all skill prerequisites for reference.

    Returns:
        Multi-line formatted string
    """
    lines: list[str] = []
    lines.append("=== Skill Prerequisites ===")
    lines.append("")

    # Group by category
    categories = {
        "Weapons": [
            Skill.LONG_BLADES,
            Skill.SHORT_BLADES,
            Skill.AXES,
            Skill.MACES_AND_FLAILS,
            Skill.POLEARMS,
            Skill.STAVES,
        ],
        "Defense": [Skill.SHIELDS],
        "Magic Schools": [
            Skill.CONJURATIONS,
            Skill.HEXES,
            Skill.SUMMONINGS,
            Skill.NECROMANCY,
            Skill.TRANSLOCATIONS,
            Skill.FIRE_MAGIC,
            Skill.ICE_MAGIC,
            Skill.AIR_MAGIC,
            Skill.EARTH_MAGIC,
        ],
        "Advanced": [Skill.SHAPESHIFTING],
    }

    for category, skills in categories.items():
        has_prereqs = any(has_prerequisites(s) for s in skills)
        if not has_prereqs:
            continue

        lines.append(f"--- {category} ---")
        for skill in skills:
            if has_prerequisites(skill):
                lines.append(format_prerequisite_info(skill))
                lines.append("")

    return "\n".join(lines)
