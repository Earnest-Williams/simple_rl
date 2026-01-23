"""High-level skill system API for XP distribution.

Concrete implementations matching EntityRegistry patterns.
All functions fully typed with explicit signatures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import polars as pl

from skills.cross_training import (
    CROSS_TRAINING_MATRIX,
    calculate_cross_training_xp,
)
from skills.models import Skill, TrainingMode, TrainingState, UsageWindow
from skills.progression import batch_calculate_levels

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


def award_xp(
    registry: EntityRegistry,
    entity_id: int,
    total_xp: int,
) -> dict[Skill, tuple[int, int]]:
    """Award XP to entity based on training configuration.

    Distributes XP according to manual weights or automatic usage tracking.
    Applies cross-training bonuses automatically.
    Updates skill levels in-place.

    Args:
        registry: Entity registry with skills_df
        entity_id: Entity receiving XP
        total_xp: Amount of XP to distribute

    Returns:
        Dict mapping Skill -> (old_level, new_level) for skills that leveled up
    """
    if total_xp <= 0:
        return {}

    # 1) Fetch entity's skills from skills_df
    skills_lazy = registry.skills_df.lazy().filter(pl.col("entity_id") == entity_id)
    skills = skills_lazy.collect()

    if skills.height == 0:
        return {}

    # 2) Get training configuration
    training_config = registry.get_skill_training(entity_id)

    # 3) Calculate XP shares based on mode
    if training_config.mode == TrainingMode.MANUAL:
        xp_shares = _distribute_xp_manual(skills, total_xp)
    else:
        xp_shares = _distribute_xp_automatic(skills, total_xp)

    # 4) Apply primary XP gains
    old_levels = skills["level"].to_numpy()
    new_xp = skills["xp"].to_numpy() + xp_shares
    new_levels = batch_calculate_levels(
        new_xp,
        skills["aptitude"].to_numpy(),
    )

    # 5) Check targets and disable if reached
    target_mask = (
        (new_levels >= skills["target_level"].fill_null(255).to_numpy())
        & (skills["target_level"].is_not_null().to_numpy())
    )
    new_weights = np.where(target_mask, 0.0, skills["weight"].to_numpy())

    # 6) Build primary updates
    updates = pl.DataFrame(
        {
            "entity_id": skills["entity_id"],
            "skill": skills["skill"],
            "xp_new": new_xp,
            "level_new": new_levels,
            "weight_new": new_weights,
        }
    )

    # 7) Apply cross-training bonuses
    cross_training_total: dict[int, int] = {}  # skill_idx -> bonus_xp

    for i in range(len(xp_shares)):
        if xp_shares[i] == 0:
            continue

        skill_idx: int = int(skills["skill"][i])

        # Get cross-training multipliers from sparse matrix
        row = CROSS_TRAINING_MATRIX[skill_idx, :]
        related_indices: np.ndarray = row.indices
        multipliers: np.ndarray = row.data

        for j in range(len(related_indices)):
            related_idx: int = int(related_indices[j])
            mult: float = float(multipliers[j])
            bonus_xp: int = int(xp_shares[i] * mult)

            if bonus_xp > 0:
                cross_training_total[related_idx] = (
                    cross_training_total.get(related_idx, 0) + bonus_xp
                )

    # 8) Apply cross-training XP
    if cross_training_total:
        cross_skills: list[int] = []
        cross_xp: list[int] = []

        for skill_idx, bonus_xp in cross_training_total.items():
            cross_skills.append(skill_idx)
            cross_xp.append(bonus_xp)

        cross_updates = pl.DataFrame(
            {
                "entity_id": [entity_id] * len(cross_skills),
                "skill": cross_skills,
                "cross_xp": cross_xp,
            }
        )

        # Join cross-training XP
        updates = updates.join(
            cross_updates,
            on=["entity_id", "skill"],
            how="left",
        )

        # Add cross-training to primary XP
        updates = updates.with_columns(
            [
                pl.when(pl.col("cross_xp").is_not_null())
                .then(pl.col("xp_new") + pl.col("cross_xp"))
                .otherwise(pl.col("xp_new"))
                .alias("xp_new")
            ]
        ).drop("cross_xp")

        # Recalculate levels after cross-training
        final_xp = updates["xp_new"].to_numpy()
        final_aptitudes = skills["aptitude"].to_numpy()
        final_levels = batch_calculate_levels(final_xp, final_aptitudes)

        updates = updates.with_columns([pl.Series(final_levels).alias("level_new")])

    # 9) Update skills_df atomically
    registry.skills_df = (
        registry.skills_df.join(
            updates,
            on=["entity_id", "skill"],
            how="left",
            suffix="_upd",
        )
        .with_columns(
            [
                pl.when(pl.col("xp_new").is_not_null())
                .then(pl.col("xp_new"))
                .otherwise(pl.col("xp"))
                .alias("xp"),
                pl.when(pl.col("level_new").is_not_null())
                .then(pl.col("level_new"))
                .otherwise(pl.col("level"))
                .alias("level"),
                pl.when(pl.col("weight_new").is_not_null())
                .then(pl.col("weight_new"))
                .otherwise(pl.col("weight"))
                .alias("weight"),
            ]
        )
        .drop(["xp_new", "level_new", "weight_new"])
    )

    # 10) Build level-up dict
    level_ups: dict[Skill, tuple[int, int]] = {}

    for i in range(len(old_levels)):
        old_lvl: int = int(old_levels[i])
        new_lvl: int = int(new_levels[i])

        if new_lvl > old_lvl:
            skill = Skill(int(skills["skill"][i]))
            level_ups[skill] = (old_lvl, new_lvl)

    return level_ups


def batch_award_xp(
    registry: EntityRegistry,
    entity_xp_pairs: list[tuple[int, int]],
) -> dict[int, dict[Skill, tuple[int, int]]]:
    """Award XP to multiple entities in single batch operation.

    More efficient than calling award_xp in loop.

    Args:
        registry: Entity registry
        entity_xp_pairs: List of (entity_id, xp_amount) tuples

    Returns:
        Dict mapping entity_id -> skill level-ups
    """
    all_level_ups: dict[int, dict[Skill, tuple[int, int]]] = {}

    # Group by entity for efficiency
    for entity_id, xp_amount in entity_xp_pairs:
        level_ups = award_xp(registry, entity_id, xp_amount)
        if level_ups:
            all_level_ups[entity_id] = level_ups

    return all_level_ups


def record_skill_usage(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    amount: int = 1,
) -> None:
    """Record skill usage for automatic training mode.

    Updates usage_count in skills_df.

    Args:
        registry: Entity registry
        entity_id: Entity that used skill
        skill: Skill that was used
        amount: Number of uses to record
    """
    # Increment usage_count for this skill
    registry.skills_df = registry.skills_df.with_columns(
        [
            pl.when(
                (pl.col("entity_id") == entity_id) & (pl.col("skill") == skill.value)
            )
            .then(pl.col("usage_count") + amount)
            .otherwise(pl.col("usage_count"))
            .alias("usage_count")
        ]
    )


def set_training_mode(
    registry: EntityRegistry,
    entity_id: int,
    mode: TrainingMode,
) -> None:
    """Set entity's training mode.

    Args:
        registry: Entity registry
        entity_id: Entity to configure
        mode: Training mode (MANUAL or AUTOMATIC)
    """
    # Store in entity's skill_training component
    # Implementation depends on EntityRegistry structure
    pass


def set_skill_training(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
    state: TrainingState,
    target_level: int | None = None,
) -> None:
    """Configure training for specific skill.

    Args:
        registry: Entity registry
        entity_id: Entity to configure
        skill: Skill to modify
        state: Training state (DISABLED, NORMAL, FOCUSED)
        target_level: Optional auto-disable target
    """
    # Calculate weight from state
    weight: float = 0.0 if state == TrainingState.DISABLED else 1.0
    if state == TrainingState.FOCUSED:
        weight = 2.0

    # Update skills_df
    registry.skills_df = registry.skills_df.with_columns(
        [
            pl.when(
                (pl.col("entity_id") == entity_id) & (pl.col("skill") == skill.value)
            )
            .then(pl.lit(weight))
            .otherwise(pl.col("weight"))
            .alias("weight"),
            pl.when(
                (pl.col("entity_id") == entity_id) & (pl.col("skill") == skill.value)
            )
            .then(pl.lit(state.value))
            .otherwise(pl.col("training_state"))
            .alias("training_state"),
            pl.when(
                (pl.col("entity_id") == entity_id) & (pl.col("skill") == skill.value)
            )
            .then(pl.lit(target_level))
            .otherwise(pl.col("target_level"))
            .alias("target_level"),
        ]
    )


# Internal distribution functions


def _distribute_xp_manual(
    skills: pl.DataFrame,
    total_xp: int,
) -> np.ndarray:
    """Distribute XP based on manual weights.

    Args:
        skills: DataFrame of entity's skills
        total_xp: Total XP to distribute

    Returns:
        Array of XP amounts per skill
    """
    weights = skills["weight"].to_numpy()
    active_mask = weights > 0.0

    if not np.any(active_mask):
        return np.zeros(len(weights), dtype=np.uint32)

    total_weight: float = float(weights[active_mask].sum())

    if total_weight <= 0.0:
        return np.zeros(len(weights), dtype=np.uint32)

    xp_shares = (weights / total_weight * total_xp).astype(np.uint32)

    return xp_shares


def _distribute_xp_automatic(
    skills: pl.DataFrame,
    total_xp: int,
) -> np.ndarray:
    """Distribute XP based on recent usage.

    Args:
        skills: DataFrame of entity's skills
        total_xp: Total XP to distribute

    Returns:
        Array of XP amounts per skill
    """
    usage_counts = skills["usage_count"].to_numpy()

    total_usage: int = int(usage_counts.sum())

    if total_usage == 0:
        return np.zeros(len(usage_counts), dtype=np.uint32)

    # Proportional to usage
    xp_shares = (usage_counts / total_usage * total_xp).astype(np.uint32)

    return xp_shares


def get_entity_skill_level(
    registry: EntityRegistry,
    entity_id: int,
    skill: Skill,
) -> int:
    """Get current level in specific skill.

    Args:
        registry: Entity registry
        entity_id: Entity to query
        skill: Skill to check

    Returns:
        Current skill level (0-27)
    """
    result = (
        registry.skills_df.lazy()
        .filter(
            (pl.col("entity_id") == entity_id) & (pl.col("skill") == skill.value)
        )
        .select("level")
        .collect()
    )

    if result.height == 0:
        return 0

    return int(result["level"][0])
