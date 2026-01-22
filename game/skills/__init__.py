"""Skill system for character progression."""

from game.skills.models import (
    Skill,
    SkillCategory,
    TrainingMode,
    TrainingState,
    SkillProgress,
    SkillTrainingConfig,
)
from game.skills.progression import (
    get_xp_for_level,
    get_level_from_xp,
    get_aptitude_multiplier,
    get_skill_xp_cost,
)
from game.skills.training import distribute_xp, update_skill_training
from game.skills.system import (
    initialize_entity_skills,
    award_xp,
    set_skill_training,
    set_training_mode,
    record_skill_usage,
    get_entity_skill_level,
)
from game.skills.effects import (
    calculate_total_combat_bonuses,
    calculate_total_magic_bonuses,
    get_skill_level,
)

__all__ = [
    # Models
    "Skill",
    "SkillCategory",
    "TrainingMode",
    "TrainingState",
    "SkillProgress",
    "SkillTrainingConfig",
    # Progression
    "get_xp_for_level",
    "get_level_from_xp",
    "get_aptitude_multiplier",
    "get_skill_xp_cost",
    # Training
    "distribute_xp",
    "update_skill_training",
    # System (high-level interface)
    "initialize_entity_skills",
    "award_xp",
    "set_skill_training",
    "set_training_mode",
    "record_skill_usage",
    "get_entity_skill_level",
    # Effects
    "calculate_total_combat_bonuses",
    "calculate_total_magic_bonuses",
    "get_skill_level",
]
