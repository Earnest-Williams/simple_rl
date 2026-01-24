"""Shapeshifting form bonuses and skill modifiers.

Different beast forms provide temporary skill bonuses/penalties while transformed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from skills.models import Skill


@dataclass(frozen=True)
class FormModifiers:
    """Skill modifiers for a specific form."""

    name: str
    skill_bonuses: dict[Skill, int]  # Temporary level bonuses
    skill_penalties: dict[Skill, int]  # Temporary level penalties
    description: str


# Form definitions
FORM_BEAST: Final[FormModifiers] = FormModifiers(
    name="Beast Form",
    skill_bonuses={
        Skill.UNARMED_COMBAT: 5,  # Natural claws
        Skill.DODGING: 2,  # Agile
    },
    skill_penalties={
        Skill.SPELLCASTING: 8,  # Can't cast in beast form
        Skill.RANGED_WEAPONS: 10,  # Can't use weapons
        Skill.SHIELDS: 10,
    },
    description="A savage beast with claws and fangs",
)

FORM_STATUE: Final[FormModifiers] = FormModifiers(
    name="Statue Form",
    skill_bonuses={
        Skill.ARMOUR: 8,  # Stone skin
        Skill.FIGHTING: 3,  # Enhanced strength
    },
    skill_penalties={
        Skill.DODGING: 5,  # Slow and heavy
        Skill.STEALTH: 10,  # Loud footsteps
        Skill.SPELLCASTING: 5,  # Difficult to concentrate
    },
    description="A living statue of immense strength and durability",
)

FORM_DRAGON: Final[FormModifiers] = FormModifiers(
    name="Dragon Form",
    skill_bonuses={
        Skill.FIGHTING: 5,
        Skill.UNARMED_COMBAT: 8,  # Claws and bite
        Skill.FIRE_MAGIC: 4,  # Breathe fire
        Skill.ARMOUR: 5,  # Scales
    },
    skill_penalties={
        Skill.DODGING: 3,  # Large
        Skill.STEALTH: 8,  # Very large
        Skill.RANGED_WEAPONS: 10,  # Can't use equipment
        Skill.SHIELDS: 10,
    },
    description="A mighty dragon with breath weapon and natural armor",
)

FORM_SPIDER: Final[FormModifiers] = FormModifiers(
    name="Spider Form",
    skill_bonuses={
        Skill.DODGING: 4,  # Eight legs
        Skill.STEALTH: 3,  # Quiet
        Skill.UNARMED_COMBAT: 2,  # Venomous bite
    },
    skill_penalties={
        Skill.ARMOUR: 5,  # Can't wear armor
        Skill.SPELLCASTING: 6,  # Spider brain
        Skill.RANGED_WEAPONS: 10,
        Skill.SHIELDS: 10,
    },
    description="A giant spider with venomous fangs",
)

FORM_ICE_BEAST: Final[FormModifiers] = FormModifiers(
    name="Ice Beast",
    skill_bonuses={
        Skill.ICE_MAGIC: 5,  # Frost breath
        Skill.UNARMED_COMBAT: 4,  # Icy claws
        Skill.ARMOUR: 3,  # Ice coating
    },
    skill_penalties={
        Skill.FIRE_MAGIC: 8,  # Weak to fire magic
        Skill.DODGING: 2,  # Bulky
        Skill.RANGED_WEAPONS: 10,
        Skill.SHIELDS: 10,
    },
    description="A beast of living ice with frost powers",
)

FORM_WISP: Final[FormModifiers] = FormModifiers(
    name="Wisp Form",
    skill_bonuses={
        Skill.DODGING: 8,  # Intangible
        Skill.STEALTH: 6,  # Silent
        Skill.SPELLCASTING: 3,  # Magical essence
        Skill.TRANSLOCATIONS: 4,  # Blink easily
    },
    skill_penalties={
        Skill.FIGHTING: 5,  # Physically weak
        Skill.ARMOUR: 10,  # Can't wear armor
        Skill.UNARMED_COMBAT: 3,  # Weak attacks
        Skill.RANGED_WEAPONS: 10,
        Skill.SHIELDS: 10,
    },
    description="An ethereal wisp of magical energy",
)

# Form registry
ALL_FORMS: Final[dict[str, FormModifiers]] = {
    "beast": FORM_BEAST,
    "statue": FORM_STATUE,
    "dragon": FORM_DRAGON,
    "spider": FORM_SPIDER,
    "ice_beast": FORM_ICE_BEAST,
    "wisp": FORM_WISP,
}


def get_form(form_name: str) -> FormModifiers | None:
    """Get form modifiers by name.

    Args:
        form_name: Name of the form (e.g., "beast", "dragon")

    Returns:
        FormModifiers or None if not found
    """
    return ALL_FORMS.get(form_name.lower())


def apply_form_bonuses(
    base_levels: dict[Skill, int],
    form: FormModifiers,
) -> dict[Skill, int]:
    """Apply form bonuses/penalties to skill levels.

    Args:
        base_levels: Base skill levels without form
        form: Form to apply

    Returns:
        Modified skill levels with form bonuses applied
    """
    modified = base_levels.copy()

    # Apply bonuses
    for skill, bonus in form.skill_bonuses.items():
        current = modified.get(skill, 0)
        modified[skill] = current + bonus

    # Apply penalties
    for skill, penalty in form.skill_penalties.items():
        current = modified.get(skill, 0)
        modified[skill] = max(0, current - penalty)  # Don't go below 0

    return modified


def get_effective_skill_level(
    registry: Any,  # EntityRegistry, but avoiding circular import
    entity_id: int,
    skill: Skill,
) -> int:
    """Get effective skill level including form bonuses.

    Args:
        registry: Entity registry
        entity_id: Entity to query
        skill: Skill to check

    Returns:
        Effective skill level with form bonuses applied
    """
    # Get base skill level
    skills = registry.get_skills(entity_id)
    base_level = skills.get(skill).level if skills.get(skill) else 0

    # Check if entity has active form
    current_form = registry.get_entity_component(entity_id, "shapeshifted_form")

    if not current_form:
        return base_level

    # Apply form modifiers
    form = get_form(current_form)
    if not form:
        return base_level

    # Check for bonuses/penalties
    if skill in form.skill_bonuses:
        return base_level + form.skill_bonuses[skill]
    elif skill in form.skill_penalties:
        return max(0, base_level - form.skill_penalties[skill])
    else:
        return base_level


def get_all_effective_levels(
    registry: Any,
    entity_id: int,
) -> dict[Skill, int]:
    """Get all skill levels with form bonuses applied.

    Args:
        registry: Entity registry
        entity_id: Entity to query

    Returns:
        Dict mapping Skill -> effective level
    """
    skills = registry.get_skills(entity_id)
    base_levels = {s: p.level for s, p in skills.items()}

    current_form = registry.get_entity_component(entity_id, "shapeshifted_form")

    if not current_form:
        return base_levels

    form = get_form(current_form)
    if not form:
        return base_levels

    return apply_form_bonuses(base_levels, form)


def shift_form(
    registry: Any,
    entity_id: int,
    form_name: str | None,
) -> bool:
    """Shift into a form (or back to normal if None).

    Args:
        registry: Entity registry
        entity_id: Entity to transform
        form_name: Name of form to shift into, or None for normal

    Returns:
        True if successful, False if form not found
    """
    if form_name is None:
        # Shift back to normal
        registry.set_entity_component(entity_id, "shapeshifted_form", None)
        return True

    # Validate form exists
    form = get_form(form_name)
    if not form:
        return False

    # Set current form
    registry.set_entity_component(entity_id, "shapeshifted_form", form_name)
    return True


def get_current_form(
    registry: Any,
    entity_id: int,
) -> FormModifiers | None:
    """Get entity's current form.

    Args:
        registry: Entity registry
        entity_id: Entity to query

    Returns:
        FormModifiers or None if in normal form
    """
    form_name = registry.get_entity_component(entity_id, "shapeshifted_form")

    if not form_name:
        return None

    return get_form(form_name)


def format_form_info(form: FormModifiers) -> str:
    """Format form information for display.

    Args:
        form: Form to format

    Returns:
        Multi-line formatted string
    """
    lines: list[str] = []
    lines.append(f"=== {form.name} ===")
    lines.append(form.description)
    lines.append("")

    if form.skill_bonuses:
        lines.append("Bonuses:")
        for skill, bonus in sorted(form.skill_bonuses.items(), key=lambda x: -x[1]):
            skill_name = skill.name.replace("_", " ").title()
            lines.append(f"  +{bonus:2d} {skill_name}")
        lines.append("")

    if form.skill_penalties:
        lines.append("Penalties:")
        for skill, penalty in sorted(form.skill_penalties.items(), key=lambda x: -x[1]):
            skill_name = skill.name.replace("_", " ").title()
            lines.append(f"  -{penalty:2d} {skill_name}")

    return "\n".join(lines)


def list_all_forms() -> str:
    """Get formatted list of all available forms.

    Returns:
        Multi-line formatted string
    """
    lines: list[str] = []
    lines.append("Available Shapeshifting Forms:")
    lines.append("")

    for form_name, form in ALL_FORMS.items():
        lines.append(format_form_info(form))
        lines.append("")

    return "\n".join(lines)
