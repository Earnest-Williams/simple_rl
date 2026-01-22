"""High-level skill system interface for game integration.

Provides convenience functions for awarding XP, initializing skills, and
applying skill bonuses to entity stats.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict

import structlog

from game.skills.models import (
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)
from game.skills.training import distribute_xp

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry

log = structlog.get_logger(__name__)


def initialize_entity_skills(
    entity_registry: EntityRegistry,
    entity_id: int,
    initial_skills: Dict[Skill, tuple[int, int]] | None = None,
    training_mode: TrainingMode = TrainingMode.MANUAL,
) -> None:
    """Initialize skill system for an entity.

    Args:
        entity_registry: The entity registry
        entity_id: Entity to initialize
        initial_skills: Dict of Skill -> (level, aptitude) for starting skills
        training_mode: Initial training mode (default: MANUAL)
    """
    # Initialize skills dict
    skills: Dict[Skill, SkillProgress] = {}

    if initial_skills:
        for skill, (level, aptitude) in initial_skills.items():
            from game.skills.progression import get_xp_for_level

            xp_needed = get_xp_for_level(level)
            skills[skill] = SkillProgress(
                level=level, xp_invested=float(xp_needed), aptitude=aptitude
            )

    # Initialize training config
    config = SkillTrainingConfig(mode=training_mode)

    # Set in entity registry
    entity_registry.set_skills(entity_id, skills)
    entity_registry.set_skill_training(entity_id, config)

    log.info(
        "Initialized entity skills",
        entity_id=entity_id,
        initial_skills=len(skills),
        mode=training_mode.name,
    )


def award_xp(
    entity_registry: EntityRegistry, entity_id: int, xp_amount: int
) -> Dict[Skill, tuple[int, int]]:
    """Award XP to an entity and distribute it among trained skills.

    Args:
        entity_registry: The entity registry
        entity_id: Entity receiving XP
        xp_amount: Amount of XP to award

    Returns:
        Dictionary of Skill -> (old_level, new_level) for skills that leveled up
    """
    if xp_amount <= 0:
        return {}

    # Get current skills and training config
    skills = entity_registry.get_skills(entity_id)
    config = entity_registry.get_skill_training(entity_id)

    if skills is None or config is None:
        log.warning(
            "Entity has no skill system initialized", entity_id=entity_id, xp=xp_amount
        )
        # Auto-initialize with manual mode
        initialize_entity_skills(entity_registry, entity_id)
        skills = entity_registry.get_skills(entity_id)
        config = entity_registry.get_skill_training(entity_id)

    if skills is None or config is None:
        log.error("Failed to initialize skills for entity", entity_id=entity_id)
        return {}

    # Distribute XP
    level_changes = distribute_xp(float(xp_amount), skills, config)

    # Update entity registry
    entity_registry.set_skills(entity_id, skills)
    entity_registry.set_skill_training(entity_id, config)

    # Update total XP tracking
    current_xp = entity_registry.get_entity_component(entity_id, "xp") or 0
    entity_registry.set_entity_component(entity_id, "xp", current_xp + xp_amount)

    if level_changes:
        log.info(
            "Entity gained skill levels",
            entity_id=entity_id,
            xp_awarded=xp_amount,
            level_changes={k.name: v for k, v in level_changes.items()},
        )

    return level_changes


def set_skill_training(
    entity_registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    state: TrainingState | None = None,
    target_level: int | None = None,
) -> None:
    """Configure training for a specific skill.

    Args:
        entity_registry: The entity registry
        entity_id: Entity to configure
        skill: Skill to configure
        state: New training state (or None to keep current)
        target_level: New target level (or None to clear/keep current)
    """
    config = entity_registry.get_skill_training(entity_id)
    if config is None:
        log.warning("Entity has no skill training config", entity_id=entity_id)
        initialize_entity_skills(entity_registry, entity_id)
        config = entity_registry.get_skill_training(entity_id)
        if config is None:
            return

    from game.skills.training import update_skill_training

    update_skill_training(entity_id, {}, config, skill, state, target_level)
    entity_registry.set_skill_training(entity_id, config)


def set_training_mode(
    entity_registry: EntityRegistry, entity_id: int, mode: TrainingMode
) -> None:
    """Set the training mode for an entity.

    Args:
        entity_registry: The entity registry
        entity_id: Entity to configure
        mode: New training mode
    """
    config = entity_registry.get_skill_training(entity_id)
    if config is None:
        log.warning("Entity has no skill training config", entity_id=entity_id)
        initialize_entity_skills(entity_registry, entity_id, training_mode=mode)
        return

    config.mode = mode
    entity_registry.set_skill_training(entity_id, config)
    log.info(
        "Updated entity training mode", entity_id=entity_id, mode=mode.name
    )


def record_skill_usage(
    entity_registry: EntityRegistry, entity_id: int, skill: Skill, amount: int = 1
) -> None:
    """Record that an entity used a skill (for automatic training mode).

    Args:
        entity_registry: The entity registry
        entity_id: Entity that used the skill
        skill: Skill that was used
        amount: Usage amount (default 1)
    """
    config = entity_registry.get_skill_training(entity_id)
    if config is None:
        return

    if config.mode == TrainingMode.AUTOMATIC:
        config.record_usage(skill, amount)
        entity_registry.set_skill_training(entity_id, config)


def get_entity_skill_level(
    entity_registry: EntityRegistry, entity_id: int, skill: Skill
) -> int:
    """Get an entity's level in a specific skill.

    Args:
        entity_registry: The entity registry
        entity_id: Entity to query
        skill: Skill to check

    Returns:
        Skill level (0 if not trained)
    """
    skills = entity_registry.get_skills(entity_id)
    if skills is None:
        return 0

    progress = skills.get(skill)
    return progress.level if progress else 0


__all__ = [
    "initialize_entity_skills",
    "award_xp",
    "set_skill_training",
    "set_training_mode",
    "record_skill_usage",
    "get_entity_skill_level",
]
