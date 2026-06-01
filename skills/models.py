"""Skill system models with strict typing and zero type inference.

All types explicitly declared per maximalist standards.
Complies with mypy --strict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Final

import numpy as np


class Skill(IntEnum):
    """All 29 skills in the game.

    Using IntEnum for:
    - Memory efficiency (int8 storage)
    - Fast equality checks
    - Direct array indexing
    """

    # Offensive (10 skills)
    FIGHTING = 0
    AXES = auto()
    MACES_AND_FLAILS = auto()
    POLEARMS = auto()
    STAVES = auto()
    LONG_BLADES = auto()
    SHORT_BLADES = auto()
    RANGED_WEAPONS = auto()
    THROWING = auto()
    UNARMED_COMBAT = auto()

    # Defensive (4 skills)
    ARMOUR = auto()
    DODGING = auto()
    SHIELDS = auto()
    STEALTH = auto()

    # Magic Schools (12 skills)
    SPELLCASTING = auto()
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

    # Miscellaneous (3 skills)
    EVOCATIONS = auto()
    INVOCATIONS = auto()
    SHAPESHIFTING = auto()


# Number of skills derived from the Skill enum to avoid a hard-coded literal.
SKILL_COUNT: Final[int] = len(Skill)


class SkillCategory(IntEnum):
    """Skill category groupings."""

    OFFENSIVE = 0
    DEFENSIVE = auto()
    MAGIC = auto()
    MISCELLANEOUS = auto()


class TrainingMode(IntEnum):
    """XP distribution mode for entity."""

    AUTOMATIC = 0  # Based on recent usage
    MANUAL = auto()  # Explicit weight assignments


class TrainingState(IntEnum):
    """Per-skill training state."""

    DISABLED = 0  # No XP allocation
    NORMAL = auto()  # Standard weight
    FOCUSED = auto()  # Double weight


# Constants
from common.tuning import MAX_SKILL_LEVEL as MAX_SKILL_LEVEL  # noqa: E402

MIN_APTITUDE: Final[int] = -5
MAX_APTITUDE: Final[int] = 11
XP_FORMULA_CONSTANT: Final[int] = 25


@dataclass(frozen=True, slots=True)
class SkillProgress:
    """Immutable snapshot of skill progression state.

    All fields explicitly typed, no inference.
    """

    skill: Skill
    level: int
    xp: int
    aptitude: int

    def __post_init__(self) -> None:
        """Validate ranges at construction."""
        if not (0 <= self.level <= MAX_SKILL_LEVEL):
            raise ValueError(f"Invalid level: {self.level}")
        if not (MIN_APTITUDE <= self.aptitude <= MAX_APTITUDE):
            raise ValueError(f"Invalid aptitude: {self.aptitude}")
        if self.xp < 0:
            raise ValueError(f"Invalid XP: {self.xp}")


@dataclass(frozen=True, slots=True)
class SkillTarget:
    """Training target configuration.

    Auto-disables skill when target level reached.
    """

    skill: Skill
    target_level: int

    def __post_init__(self) -> None:
        """Validate target range."""
        if not (1 <= self.target_level <= MAX_SKILL_LEVEL):
            raise ValueError(f"Invalid target: {self.target_level}")


@dataclass(frozen=False, slots=True)
class SkillTrainingConfig:
    """Entity training configuration.

    Mutable state container for training mode and weights.
    """

    mode: TrainingMode
    weights: dict[Skill, float] = field(default_factory=dict)
    targets: dict[Skill, int] = field(default_factory=dict)

    def set_weight(self, skill: Skill, weight: float) -> None:
        """Set training weight for skill.

        Args:
            skill: Skill to configure
            weight: 0.0 (disabled), 1.0 (normal), 2.0 (focused)
        """
        if weight not in (0.0, 1.0, 2.0):
            raise ValueError(f"Invalid weight: {weight}. Must be 0.0, 1.0, or 2.0")
        self.weights[skill] = weight

    def set_target(self, skill: Skill, target_level: int) -> None:
        """Set auto-disable target for skill."""
        if not (1 <= target_level <= MAX_SKILL_LEVEL):
            raise ValueError(f"Invalid target: {target_level}")
        self.targets[skill] = target_level

    def clear_target(self, skill: Skill) -> None:
        """Remove target for skill."""
        self.targets.pop(skill, None)


@dataclass(frozen=True, slots=True)
class CrossTrainingPair:
    """Defines cross-training relationship between skills."""

    from_skill: Skill
    to_skill: Skill
    multiplier: float

    def __post_init__(self) -> None:
        """Validate multiplier range."""
        if not (0.0 <= self.multiplier <= 1.0):
            raise ValueError(f"Invalid multiplier: {self.multiplier}")


# Cross-training definitions (DCSS canonical values)
CROSS_TRAINING_PAIRS: Final[tuple[CrossTrainingPair, ...]] = (
    # Weapon Skills
    # Axes <-> Maces & Flails
    CrossTrainingPair(Skill.AXES, Skill.MACES_AND_FLAILS, 0.40),
    CrossTrainingPair(Skill.MACES_AND_FLAILS, Skill.AXES, 0.40),
    # Axes <-> Polearms
    CrossTrainingPair(Skill.AXES, Skill.POLEARMS, 0.25),
    CrossTrainingPair(Skill.POLEARMS, Skill.AXES, 0.25),
    # Maces & Flails <-> Staves
    CrossTrainingPair(Skill.MACES_AND_FLAILS, Skill.STAVES, 0.40),
    CrossTrainingPair(Skill.STAVES, Skill.MACES_AND_FLAILS, 0.40),
    # Polearms <-> Staves
    CrossTrainingPair(Skill.POLEARMS, Skill.STAVES, 0.25),
    CrossTrainingPair(Skill.STAVES, Skill.POLEARMS, 0.25),
    # Long Blades <-> Short Blades
    CrossTrainingPair(Skill.LONG_BLADES, Skill.SHORT_BLADES, 0.40),
    CrossTrainingPair(Skill.SHORT_BLADES, Skill.LONG_BLADES, 0.40),
    # Magic Schools
    # Opposing elemental schools have minor cross-training (0.10)
    # Fire <-> Ice (opposing elements, minor synergy from understanding both)
    CrossTrainingPair(Skill.FIRE_MAGIC, Skill.ICE_MAGIC, 0.10),
    CrossTrainingPair(Skill.ICE_MAGIC, Skill.FIRE_MAGIC, 0.10),
    # Air <-> Earth (opposing elements, minor synergy)
    CrossTrainingPair(Skill.AIR_MAGIC, Skill.EARTH_MAGIC, 0.10),
    CrossTrainingPair(Skill.EARTH_MAGIC, Skill.AIR_MAGIC, 0.10),
)


@dataclass(frozen=True, slots=True)
class CombatBonuses:
    """All combat-related skill bonuses.

    Returned by skill effect calculations.
    """

    hp_bonus: int
    damage_multiplier: float
    accuracy_bonus: int
    armor_bonus: int
    evasion_bonus: int
    shield_defense: int


@dataclass(frozen=True, slots=True)
class MagicBonuses:
    """All magic-related skill bonuses."""

    mp_bonus: float
    spell_power: float
    success_modifier: float


@dataclass(frozen=True, slots=True)
class ManualBonus:
    """Temporary aptitude boost from skill manual.

    Consumed as XP is spent training the skill.
    """

    skill: Skill
    bonus_aptitude: int
    remaining_xp: int

    def __post_init__(self) -> None:
        """Validate fields."""
        if self.bonus_aptitude <= 0:
            raise ValueError(f"Invalid bonus: {self.bonus_aptitude}")
        if self.remaining_xp <= 0:
            raise ValueError(f"Invalid remaining XP: {self.remaining_xp}")

    def consume(self, xp_used: int) -> ManualBonus | None:
        """Reduce remaining XP, return None if depleted.

        Args:
            xp_used: Amount of XP spent while manual active

        Returns:
            Updated manual if XP remains, None if depleted
        """
        new_remaining: int = self.remaining_xp - xp_used

        if new_remaining <= 0:
            return None

        return ManualBonus(
            skill=self.skill,
            bonus_aptitude=self.bonus_aptitude,
            remaining_xp=new_remaining,
        )


@dataclass(frozen=False, slots=True)
class UsageWindow:
    """Ring buffer tracking recent skill usage for automatic mode.

    Maintains last N uses per skill for proportional XP distribution.
    """

    window_size: int
    counts: np.ndarray  # Shape: (SKILL_COUNT,) dtype: uint32
    total_usage: int = 0

    def __post_init__(self) -> None:
        """Initialize counts array if not provided."""
        if self.counts.shape != (SKILL_COUNT,):
            raise ValueError(f"Invalid counts shape: {self.counts.shape}")
        if self.counts.dtype != np.uint32:
            raise ValueError(f"Invalid counts dtype: {self.counts.dtype}")

    @classmethod
    def create(cls, window_size: int = 1000) -> UsageWindow:
        """Factory method for new window."""
        counts: np.ndarray = np.zeros(SKILL_COUNT, dtype=np.uint32)
        return cls(window_size=window_size, counts=counts)

    def record(self, skill: Skill, amount: int = 1) -> None:
        """Record skill usage (mutates in-place).

        Args:
            skill: Skill that was used
            amount: Number of uses to record
        """
        self.counts[skill.value] += amount
        self.total_usage += amount

        # Decay if window exceeded
        if self.total_usage > self.window_size:
            self._decay()

    def _decay(self) -> None:
        """Apply exponential decay to all counts.

        Multiplies all counts by decay_factor (0.99), then casts to uint32.
        This causes an implicit floor operation - fractional results are truncated.

        IMPORTANT: This intentional flooring means small counts (1-10) will erode
        quickly after ~100 decay cycles. This is acceptable for usage tracking
        where we want recent activity to dominate, and very old activity to be
        forgotten. The decay creates a sliding window effect.

        If precise fractional tracking is needed, consider storing counts as
        float32 internally, or use integer decay (e.g., subtract a fixed amount).
        The current float→uint32 cast is deterministic and intentional.
        """
        decay_factor: float = 0.99
        # Intentional floor via astype - see docstring for rationale
        self.counts = (self.counts * decay_factor).astype(np.uint32)
        self.total_usage = int(self.counts.sum())

    def get_weights(self) -> np.ndarray:
        """Normalize counts to weight distribution.

        Returns:
            Array of shape (SKILL_COUNT,) dtype: float32 summing to 1.0
        """
        total: int = int(self.counts.sum())

        if total == 0:
            return np.zeros(SKILL_COUNT, dtype=np.float32)

        return (self.counts / total).astype(np.float32)


# Skill category mappings
SKILL_CATEGORIES: Final[dict[Skill, SkillCategory]] = {
    Skill.FIGHTING: SkillCategory.OFFENSIVE,
    Skill.AXES: SkillCategory.OFFENSIVE,
    Skill.MACES_AND_FLAILS: SkillCategory.OFFENSIVE,
    Skill.POLEARMS: SkillCategory.OFFENSIVE,
    Skill.STAVES: SkillCategory.OFFENSIVE,
    Skill.LONG_BLADES: SkillCategory.OFFENSIVE,
    Skill.SHORT_BLADES: SkillCategory.OFFENSIVE,
    Skill.RANGED_WEAPONS: SkillCategory.OFFENSIVE,
    Skill.THROWING: SkillCategory.OFFENSIVE,
    Skill.UNARMED_COMBAT: SkillCategory.OFFENSIVE,
    Skill.ARMOUR: SkillCategory.DEFENSIVE,
    Skill.DODGING: SkillCategory.DEFENSIVE,
    Skill.SHIELDS: SkillCategory.DEFENSIVE,
    Skill.STEALTH: SkillCategory.DEFENSIVE,
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
    Skill.EVOCATIONS: SkillCategory.MISCELLANEOUS,
    Skill.INVOCATIONS: SkillCategory.MISCELLANEOUS,
    Skill.SHAPESHIFTING: SkillCategory.MISCELLANEOUS,
}
