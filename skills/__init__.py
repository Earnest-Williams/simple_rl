"""Skill system for simple_rl.

A high-performance, vectorized skill system implementing DCSS-style mechanics:
- 29 skills across offensive, defensive, magic, and misc categories
- Quadratic XP progression with aptitude modifiers
- Cross-training between related weapon skills
- Manual and automatic training modes
- Numba-accelerated calculations for combat/magic bonuses

Key modules:
  - models: Core data structures and skill definitions
  - progression: XP formulas and level calculations
  - effects: Combat and magic bonus calculations
  - cross_training: Related skill XP bonuses
  - system: High-level XP distribution API
  - registry_integration: EntityRegistry integration mixin
  - utils: Serialization and Numba warmup utilities

Usage:
    from skills.system import award_xp, set_skill_training
    from skills.models import Skill, TrainingState

    # Award XP to entity
    level_ups = award_xp(registry, entity_id, 1000)

    # Configure training
    set_skill_training(registry, entity_id, Skill.FIGHTING, TrainingState.FOCUSED)
"""

from __future__ import annotations

from skills.models import (
    MAX_APTITUDE,
    MAX_SKILL_LEVEL,
    MIN_APTITUDE,
    XP_FORMULA_CONSTANT,
    CombatBonuses,
    CrossTrainingPair,
    MagicBonuses,
    ManualBonus,
    Skill,
    SkillCategory,
    SkillProgress,
    SkillTarget,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
    UsageWindow,
)
from skills.progression import (
    batch_calculate_levels,
    calculate_level_from_xp,
    calculate_xp_for_level,
    calculate_xp_to_next_level,
)
from skills.system import (
    award_xp,
    batch_award_xp,
    get_entity_skill_level,
    record_skill_usage,
    set_skill_training,
    set_training_mode,
)

__all__ = [
    # Constants
    "MAX_APTITUDE",
    "MAX_SKILL_LEVEL",
    "MIN_APTITUDE",
    "XP_FORMULA_CONSTANT",
    # Enums
    "Skill",
    "SkillCategory",
    "TrainingMode",
    "TrainingState",
    # Data models
    "CombatBonuses",
    "CrossTrainingPair",
    "MagicBonuses",
    "ManualBonus",
    "SkillProgress",
    "SkillTarget",
    "SkillTrainingConfig",
    "UsageWindow",
    # Progression functions
    "batch_calculate_levels",
    "calculate_level_from_xp",
    "calculate_xp_for_level",
    "calculate_xp_to_next_level",
    # System API
    "award_xp",
    "batch_award_xp",
    "get_entity_skill_level",
    "record_skill_usage",
    "set_skill_training",
    "set_training_mode",
]
