"""Skill screen UI for displaying and managing character skills.

Provides text-based UI for viewing skill levels, XP progress, and training configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from skills.models import (
    Skill,
    SkillCategory,
    SkillProgress,
    TrainingMode,
    TrainingState,
)
from skills.progression import calculate_xp_to_next_level

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


def format_skill_line(
    skill: Skill,
    progress: SkillProgress,
    training_state: TrainingState | None = None,
    target_level: int | None = None,
) -> str:
    """Format a single skill line for display.

    Args:
        skill: The skill to display
        progress: Current skill progress
        training_state: Optional training state (DISABLED, NORMAL, FOCUSED)
        target_level: Optional target level for auto-disable

    Returns:
        Formatted string showing skill name, level, XP, and training status
    """
    # Skill name (padded to 20 chars)
    name = skill.name.replace("_", " ").title()
    name_padded = f"{name:<20}"

    # Level display
    level_str = f"Lv {progress.level:2d}"

    # XP to next level
    if progress.level >= 27:
        xp_str = "  (MAX)  "
    else:
        xp_to_next = calculate_xp_to_next_level(progress.xp, progress.aptitude)
        xp_str = f"({xp_to_next:5d} XP)"

    # Training status indicator
    if training_state == TrainingState.DISABLED:
        status = " [OFF]"
    elif training_state == TrainingState.FOCUSED:
        status = " [***]"
    elif target_level is not None and progress.level < target_level:
        status = f" [→{target_level}]"
    else:
        status = "      "

    return f"{name_padded} {level_str} {xp_str}{status}"


def get_skill_screen_text(
    registry: EntityRegistry,
    entity_id: int,
) -> str:
    """Generate full skill screen text for an entity.

    Args:
        registry: Entity registry
        entity_id: Entity to display skills for

    Returns:
        Multi-line string with formatted skill display
    """
    skills = registry.get_skills(entity_id)
    training_config = registry.get_skill_training(entity_id)

    if not skills:
        return "No skills initialized for this entity."

    lines: list[str] = []

    # Header
    lines.append("=" * 60)
    entity_name = registry.get_entity_component(entity_id, "name") or "Unknown"
    lines.append(f"Skills for {entity_name}")
    lines.append("=" * 60)
    lines.append("")

    # Training mode indicator
    if training_config:
        mode_name = (
            "Manual" if training_config.mode == TrainingMode.MANUAL else "Automatic"
        )
        lines.append(f"Training Mode: {mode_name}")
        lines.append("")

    # Group skills by category
    categories = [
        (SkillCategory.OFFENSIVE, "Offensive Skills"),
        (SkillCategory.DEFENSIVE, "Defensive Skills"),
        (SkillCategory.MAGIC, "Magic Skills"),
        (SkillCategory.MISCELLANEOUS, "Miscellaneous Skills"),
    ]

    for category, category_name in categories:
        category_skills = [
            skill for skill in Skill if _get_skill_category(skill) == category
        ]

        # Filter to skills that exist in the entity's skill dict
        category_skills = [s for s in category_skills if s in skills]

        if not category_skills:
            continue

        lines.append(f"--- {category_name} ---")
        lines.append("")

        for skill in category_skills:
            progress = skills[skill]

            # Get training state and target if available
            training_state = None
            target_level = None

            if training_config:
                weight = training_config.weights.get(skill, 1.0)
                if weight == 0.0:
                    training_state = TrainingState.DISABLED
                elif weight >= 2.0:
                    training_state = TrainingState.FOCUSED
                else:
                    training_state = TrainingState.NORMAL

                target_level = training_config.targets.get(skill)

            skill_line = format_skill_line(
                skill, progress, training_state, target_level
            )
            lines.append(f"  {skill_line}")

        lines.append("")

    # Footer with legend
    lines.append("=" * 60)
    lines.append("Legend:")
    lines.append("  [OFF] - Disabled    [***] - Focused    [→X] - Target level X")
    lines.append("  XP shown is amount needed to reach next level")
    lines.append("=" * 60)

    return "\n".join(lines)


def _get_skill_category(skill: Skill) -> SkillCategory:
    """Get the category for a skill.

    Args:
        skill: Skill to categorize

    Returns:
        The skill's category
    """
    offensive = [
        Skill.FIGHTING,
        Skill.AXES,
        Skill.MACES_AND_FLAILS,
        Skill.POLEARMS,
        Skill.STAVES,
        Skill.LONG_BLADES,
        Skill.SHORT_BLADES,
        Skill.RANGED_WEAPONS,
        Skill.THROWING,
        Skill.UNARMED_COMBAT,
    ]

    defensive = [
        Skill.ARMOUR,
        Skill.DODGING,
        Skill.SHIELDS,
        Skill.STEALTH,
    ]

    magic = [
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
    ]

    if skill in offensive:
        return SkillCategory.OFFENSIVE
    elif skill in defensive:
        return SkillCategory.DEFENSIVE
    elif skill in magic:
        return SkillCategory.MAGIC
    else:
        return SkillCategory.MISCELLANEOUS


def print_skill_screen(
    registry: EntityRegistry,
    entity_id: int,
) -> None:
    """Print skill screen to console.

    Args:
        registry: Entity registry
        entity_id: Entity to display skills for
    """
    screen_text = get_skill_screen_text(registry, entity_id)
    print(screen_text)


def get_skill_summary(
    registry: EntityRegistry,
    entity_id: int,
    max_skills: int = 5,
) -> str:
    """Get a brief skill summary showing highest skills.

    Args:
        registry: Entity registry
        entity_id: Entity to query
        max_skills: Maximum number of skills to show

    Returns:
        Brief summary string
    """
    skills = registry.get_skills(entity_id)

    if not skills:
        return "No skills"

    # Sort by level (descending)
    sorted_skills = sorted(
        skills.items(),
        key=lambda x: (x[1].level, x[1].xp),
        reverse=True,
    )

    # Take top N
    top_skills = sorted_skills[:max_skills]

    skill_strs = [
        f"{skill.name.replace('_', ' ').title()} {progress.level}"
        for skill, progress in top_skills
    ]

    return ", ".join(skill_strs)
