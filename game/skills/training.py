"""Training mode logic and XP distribution.

Handles automatic and manual training modes, focus multipliers, and cross-training.
"""

from __future__ import annotations

from typing import Dict

import structlog

from game.skills.models import (
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
    CROSS_TRAINING,
)
from game.skills.progression import apply_xp_to_skill

log = structlog.get_logger(__name__)


def distribute_xp(
    xp_pool: float,
    skills: Dict[Skill, SkillProgress],
    config: SkillTrainingConfig,
) -> Dict[Skill, tuple[int, int]]:
    """Distribute XP pool among skills based on training configuration.

    Args:
        xp_pool: Total XP to distribute
        skills: Current skill progress mapping
        config: Training configuration

    Returns:
        Dictionary mapping Skill -> (old_level, new_level) for skills that leveled up
    """
    if xp_pool <= 0:
        return {}

    # Determine which skills receive XP and their weights
    skill_weights: Dict[Skill, float] = {}

    if config.mode == TrainingMode.MANUAL:
        # Manual mode: distribute evenly among enabled/focused skills
        for skill in Skill:
            state = config.get_training_state(skill)
            if state == TrainingState.DISABLED:
                continue
            elif state == TrainingState.ENABLED:
                skill_weights[skill] = 1.0
            elif state == TrainingState.FOCUSED:
                skill_weights[skill] = 2.0  # Focused gets double share
    else:
        # Automatic mode: distribute based on recent usage
        total_usage = sum(config.recent_usage.values())
        if total_usage > 0:
            for skill, usage in config.recent_usage.items():
                state = config.get_training_state(skill)
                if state == TrainingState.DISABLED:
                    continue

                base_weight = usage / total_usage
                if state == TrainingState.FOCUSED:
                    # Focused skills get extra XP even if not used recently
                    base_weight = max(base_weight, 0.1)  # Minimum 10% share
                    base_weight *= 1.5  # 50% bonus

                skill_weights[skill] = base_weight

    # If no skills are being trained, return empty
    if not skill_weights:
        log.warning("No skills being trained", mode=config.mode.name)
        return {}

    # Normalize weights to sum to 1.0
    total_weight = sum(skill_weights.values())
    for skill in skill_weights:
        skill_weights[skill] /= total_weight

    # Distribute XP and track level-ups
    level_changes: Dict[Skill, tuple[int, int]] = {}

    for skill, weight in skill_weights.items():
        skill_xp = xp_pool * weight
        if skill_xp <= 0:
            continue

        # Get current progress or create new
        progress = skills.get(skill)
        if progress is None:
            progress = SkillProgress()
            skills[skill] = progress

        # Apply XP
        new_xp, old_level, new_level = apply_xp_to_skill(
            progress.xp_invested, skill_xp, progress.aptitude
        )

        progress.xp_invested = new_xp
        progress.level = new_level

        # Track level changes
        if new_level > old_level:
            level_changes[skill] = (old_level, new_level)
            log.info(
                "Skill leveled up",
                skill=skill.name,
                old_level=old_level,
                new_level=new_level,
            )

            # Check if we hit a target level
            target = config.get_target_level(skill)
            if target is not None and new_level >= target:
                config.set_training_state(skill, TrainingState.DISABLED)
                config.clear_target_level(skill)
                log.info(
                    "Skill reached target, disabling training",
                    skill=skill.name,
                    level=new_level,
                )

        # Apply cross-training bonuses
        if skill in CROSS_TRAINING:
            for related_skill, bonus_pct in CROSS_TRAINING[skill]:
                bonus_xp = skill_xp * bonus_pct

                related_progress = skills.get(related_skill)
                if related_progress is None:
                    related_progress = SkillProgress()
                    skills[related_skill] = related_progress

                new_xp_rel, old_level_rel, new_level_rel = apply_xp_to_skill(
                    related_progress.xp_invested, bonus_xp, related_progress.aptitude
                )

                related_progress.xp_invested = new_xp_rel
                related_progress.level = new_level_rel

                if new_level_rel > old_level_rel:
                    level_changes[related_skill] = (old_level_rel, new_level_rel)
                    log.info(
                        "Cross-trained skill leveled up",
                        skill=related_skill.name,
                        old_level=old_level_rel,
                        new_level=new_level_rel,
                        from_skill=skill.name,
                    )

    # Clear usage tracking for next distribution
    if config.mode == TrainingMode.AUTOMATIC:
        config.clear_usage()

    return level_changes


def update_skill_training(
    entity_id: int,
    skills: Dict[Skill, SkillProgress],
    config: SkillTrainingConfig,
    skill: Skill,
    state: TrainingState | None = None,
    target_level: int | None = None,
) -> None:
    """Update training configuration for a specific skill.

    Args:
        entity_id: Entity ID (for logging)
        skills: Current skill progress
        config: Training configuration to modify
        skill: Skill to update
        state: New training state (or None to keep current)
        target_level: New target level (or None to clear/keep current)
    """
    if state is not None:
        config.set_training_state(skill, state)
        log.info(
            "Updated skill training state",
            entity_id=entity_id,
            skill=skill.name,
            state=state.name,
        )

    if target_level is not None:
        if target_level <= 0:
            config.clear_target_level(skill)
        else:
            config.set_target_level(skill, target_level)
            log.info(
                "Set skill target level",
                entity_id=entity_id,
                skill=skill.name,
                target=target_level,
            )


__all__ = [
    "distribute_xp",
    "update_skill_training",
]
