"""Core data models for the skill system.

Based on DCSS skill mechanics with 27 level cap, aptitudes, and training modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict


class SkillCategory(Enum):
    """Major skill categories."""

    OFFENSE = auto()
    DEFENSE = auto()
    MAGIC = auto()
    MISCELLANEOUS = auto()


class Skill(Enum):
    """All available skills in the game.

    Based on DCSS skill list with adaptations for this game's mechanics.
    """

    # OFFENSE
    FIGHTING = auto()  # General melee damage/accuracy, +HP
    AXES = auto()
    MACES_AND_FLAILS = auto()
    POLEARMS = auto()
    STAVES = auto()
    LONG_BLADES = auto()
    SHORT_BLADES = auto()
    RANGED_WEAPONS = auto()
    THROWING = auto()
    UNARMED_COMBAT = auto()

    # DEFENSE
    ARMOUR = auto()
    DODGING = auto()
    SHIELDS = auto()
    STEALTH = auto()

    # MAGIC
    SPELLCASTING = auto()  # +MP, spell power/success, memorization slots
    CONJURATIONS = auto()
    HEXES = auto()
    SUMMONINGS = auto()
    NECROMANCY = auto()
    FORGECRAFT = auto()
    TRANSLOCATIONS = auto()
    ALCHEMY = auto()
    FIRE_MAGIC = auto()
    AIR_MAGIC = auto()
    ICE_MAGIC = auto()
    EARTH_MAGIC = auto()

    # MISCELLANEOUS
    EVOCATIONS = auto()  # Wands and evocable items
    INVOCATIONS = auto()  # God powers
    SHAPESHIFTING = auto()  # Form transformations


# Skill category mapping
SKILL_CATEGORIES: Dict[Skill, SkillCategory] = {
    # Offense
    Skill.FIGHTING: SkillCategory.OFFENSE,
    Skill.AXES: SkillCategory.OFFENSE,
    Skill.MACES_AND_FLAILS: SkillCategory.OFFENSE,
    Skill.POLEARMS: SkillCategory.OFFENSE,
    Skill.STAVES: SkillCategory.OFFENSE,
    Skill.LONG_BLADES: SkillCategory.OFFENSE,
    Skill.SHORT_BLADES: SkillCategory.OFFENSE,
    Skill.RANGED_WEAPONS: SkillCategory.OFFENSE,
    Skill.THROWING: SkillCategory.OFFENSE,
    Skill.UNARMED_COMBAT: SkillCategory.OFFENSE,
    # Defense
    Skill.ARMOUR: SkillCategory.DEFENSE,
    Skill.DODGING: SkillCategory.DEFENSE,
    Skill.SHIELDS: SkillCategory.DEFENSE,
    Skill.STEALTH: SkillCategory.DEFENSE,
    # Magic
    Skill.SPELLCASTING: SkillCategory.MAGIC,
    Skill.CONJURATIONS: SkillCategory.MAGIC,
    Skill.HEXES: SkillCategory.MAGIC,
    Skill.SUMMONINGS: SkillCategory.MAGIC,
    Skill.NECROMANCY: SkillCategory.MAGIC,
    Skill.FORGECRAFT: SkillCategory.MAGIC,
    Skill.TRANSLOCATIONS: SkillCategory.MAGIC,
    Skill.ALCHEMY: SkillCategory.MAGIC,
    Skill.FIRE_MAGIC: SkillCategory.MAGIC,
    Skill.AIR_MAGIC: SkillCategory.MAGIC,
    Skill.ICE_MAGIC: SkillCategory.MAGIC,
    Skill.EARTH_MAGIC: SkillCategory.MAGIC,
    # Miscellaneous
    Skill.EVOCATIONS: SkillCategory.MISCELLANEOUS,
    Skill.INVOCATIONS: SkillCategory.MISCELLANEOUS,
    Skill.SHAPESHIFTING: SkillCategory.MISCELLANEOUS,
}

# Cross-training bonuses: skill -> list of (related_skill, bonus_percentage)
# e.g., training Maces & Flails also trains Axes and Staves at reduced rate
CROSS_TRAINING: Dict[Skill, list[tuple[Skill, float]]] = {
    Skill.MACES_AND_FLAILS: [
        (Skill.AXES, 0.25),
        (Skill.STAVES, 0.25),
    ],
    Skill.AXES: [
        (Skill.MACES_AND_FLAILS, 0.25),
        (Skill.POLEARMS, 0.25),
    ],
    Skill.POLEARMS: [
        (Skill.AXES, 0.25),
        (Skill.STAVES, 0.25),
    ],
    Skill.STAVES: [
        (Skill.MACES_AND_FLAILS, 0.25),
        (Skill.POLEARMS, 0.25),
    ],
    Skill.LONG_BLADES: [
        (Skill.SHORT_BLADES, 0.20),
    ],
    Skill.SHORT_BLADES: [
        (Skill.LONG_BLADES, 0.20),
    ],
    # Magic schools have some cross-training too
    Skill.FIRE_MAGIC: [
        (Skill.ICE_MAGIC, 0.10),  # Opposite elements train each other a bit
    ],
    Skill.ICE_MAGIC: [
        (Skill.FIRE_MAGIC, 0.10),
    ],
    Skill.AIR_MAGIC: [
        (Skill.EARTH_MAGIC, 0.10),
    ],
    Skill.EARTH_MAGIC: [
        (Skill.AIR_MAGIC, 0.10),
    ],
}


class TrainingMode(Enum):
    """How XP is distributed among skills."""

    AUTOMATIC = auto()  # Based on recent skill usage
    MANUAL = auto()  # Player explicitly selects which skills to train


class TrainingState(Enum):
    """Training state for individual skills."""

    DISABLED = auto()  # No training (- in DCSS)
    ENABLED = auto()  # Normal training (grey in DCSS)
    FOCUSED = auto()  # Extra training, 2x XP share (* in DCSS)


@dataclass
class SkillProgress:
    """Tracks progress in a single skill."""

    level: int = 0  # Current skill level (0-27)
    xp_invested: float = 0.0  # Total XP invested in this skill (after aptitude)
    aptitude: int = 0  # Species/background bonus (-5 to +11)

    def xp_progress_to_next_level(self, xp_for_next: float) -> float:
        """Calculate percentage progress to next level (0.0 to 1.0)."""
        if self.level >= 27:
            return 1.0
        # Need to import to avoid circular dependency
        from game.skills.progression import get_xp_for_level

        xp_for_current = get_xp_for_level(self.level)
        if xp_for_next <= xp_for_current:
            return 1.0
        progress = (self.xp_invested - xp_for_current) / (xp_for_next - xp_for_current)
        return max(0.0, min(1.0, progress))


@dataclass
class SkillTrainingConfig:
    """Configuration for how skills are trained."""

    mode: TrainingMode = TrainingMode.AUTOMATIC
    # Skill -> TrainingState mapping
    training_states: Dict[Skill, TrainingState] = field(default_factory=dict)
    # Skill -> target level (auto-disable when reached)
    target_levels: Dict[Skill, int] = field(default_factory=dict)
    # Track recent skill usage for automatic mode (skill -> usage_count)
    recent_usage: Dict[Skill, int] = field(default_factory=dict)

    def get_training_state(self, skill: Skill) -> TrainingState:
        """Get the training state for a skill, defaulting to ENABLED."""
        return self.training_states.get(skill, TrainingState.ENABLED)

    def set_training_state(self, skill: Skill, state: TrainingState) -> None:
        """Set the training state for a skill."""
        self.training_states[skill] = state

    def get_target_level(self, skill: Skill) -> int | None:
        """Get the target level for a skill, or None if no target."""
        return self.target_levels.get(skill)

    def set_target_level(self, skill: Skill, level: int) -> None:
        """Set a target level for a skill (0-27)."""
        self.target_levels[skill] = max(0, min(27, level))

    def clear_target_level(self, skill: Skill) -> None:
        """Clear the target level for a skill."""
        self.target_levels.pop(skill, None)

    def record_usage(self, skill: Skill, amount: int = 1) -> None:
        """Record that a skill was used (for automatic mode)."""
        self.recent_usage[skill] = self.recent_usage.get(skill, 0) + amount

    def clear_usage(self) -> None:
        """Clear usage tracking (called after XP distribution)."""
        self.recent_usage.clear()


__all__ = [
    "Skill",
    "SkillCategory",
    "TrainingMode",
    "TrainingState",
    "SkillProgress",
    "SkillTrainingConfig",
    "SKILL_CATEGORIES",
    "CROSS_TRAINING",
]
