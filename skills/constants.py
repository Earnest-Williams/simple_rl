"""Skills system constants - tuneable parameters for game balance.

This module centralizes magic numbers and tuneable constants that appear
in the skills system implementation. Well-structured data (like FormModifiers,
Ability definitions, Synergy definitions) remain in their respective modules.

Core progression constants (MAX_SKILL_LEVEL, aptitudes, XP formula) are
defined in skills/models.py where they're used for validation.

All values marked Final are immutable after module initialization.
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# TRAINING SYSTEM
# =============================================================================

# Training weight for disabled skills
# Tuning: Must be 0.0 to prevent XP allocation to disabled skills
TRAINING_WEIGHT_DISABLED: Final[float] = 0.0

# Training weight for normal priority skills
# Tuning: Baseline weight - increasing raises floor for non-focused skills
# Decreasing makes focused training more impactful
TRAINING_WEIGHT_NORMAL: Final[float] = 1.0

# Training weight for focused skills (double XP allocation)
# Tuning: Higher values concentrate XP more heavily on focused skills
# Lower values reduce benefit of focusing vs. normal training
TRAINING_WEIGHT_FOCUSED: Final[float] = 2.0

# Number of recent actions tracked for automatic training mode
# Tuning: Higher values smooth out XP distribution over longer periods
# Lower values make training more reactive to recent behavior
# Currently defined in UsageWindow.create() in models.py as default value
AUTOMATIC_MODE_WINDOW_SIZE: Final[int] = 1000

# Decay factor applied when usage window exceeds size (exponential decay)
# Tuning: Values closer to 1.0 preserve older usage data longer
# Values closer to 0.0 heavily discount old actions
# Currently hardcoded in UsageWindow._decay() in models.py
AUTOMATIC_MODE_DECAY_FACTOR: Final[float] = 0.99

# =============================================================================
# CROSS-TRAINING MULTIPLIERS
# =============================================================================

# High cross-training rate for closely related weapon skills
# Used for: Axes↔Maces, Maces↔Staves, Long↔Short Blades
# Tuning: Higher values reward specializing in related weapon types
# Lower values reduce benefit of weapon skill synergy
# Defined in CROSS_TRAINING_PAIRS in models.py
CROSS_TRAINING_HIGH: Final[float] = 0.40

# Medium cross-training rate for moderately related weapon skills
# Used for: Axes↔Polearms, Polearms↔Staves
# Tuning: Adjusts mid-tier weapon synergies independently of high/low tiers
# Defined in CROSS_TRAINING_PAIRS in models.py
CROSS_TRAINING_MEDIUM: Final[float] = 0.25

# Low cross-training rate for opposing elemental schools
# Used for: Fire↔Ice, Air↔Earth (opposing elements with minor synergy)
# Tuning: Higher values reward studying contrasting magic schools
# Lower values emphasize specialization over broad magical knowledge
# Defined in CROSS_TRAINING_PAIRS in models.py
CROSS_TRAINING_LOW: Final[float] = 0.10

# =============================================================================
# COMBAT SKILL EFFECTS
# =============================================================================

# Fighting skill HP bonus: +1 HP per level
# Tuning: Higher values make Fighting more valuable for survivability
# Lower values reduce importance of Fighting for HP
# Implemented in effects.calculate_fighting_hp_bonus()
FIGHTING_HP_PER_LEVEL: Final[int] = 1

# Fighting skill damage multiplier: +1% damage per level
# Tuning: Higher values make Fighting more impactful for damage output
# Lower values reduce Fighting's offensive contribution
# Implemented in effects.calculate_fighting_damage_mult()
FIGHTING_DAMAGE_PCT_PER_LEVEL: Final[float] = 0.01

# Fighting skill accuracy divisor for bonus calculation
# Formula: accuracy_bonus = fighting_level // FIGHTING_ACCURACY_DIVISOR
# Tuning: Smaller divisor = more accuracy per level (2 = +1 per 2 levels)
# Implemented in effects.calculate_fighting_accuracy()
FIGHTING_ACCURACY_DIVISOR: Final[int] = 2

# Weapon skill damage multiplier: +2% damage per level
# Tuning: Higher values make weapon specialization more rewarding
# Lower values reduce difference between skilled and unskilled fighters
# Implemented in effects.calculate_weapon_damage_mult()
WEAPON_DAMAGE_PCT_PER_LEVEL: Final[float] = 0.02

# Weapon skill accuracy bonus: +1 per level
# Tuning: Higher values make weapon skills more reliable for hitting
# Lower values reduce importance of weapon skill for accuracy
# Implemented in effects.calculate_weapon_accuracy()
WEAPON_ACCURACY_PER_LEVEL: Final[int] = 1

# Armour skill AC multiplier: +3% armour effectiveness per level
# Tuning: Higher values make Armour skill dramatically increase AC
# Lower values reduce scaling of heavy armour builds
# Implemented in effects.calculate_armour_bonus()
ARMOUR_EFFECTIVENESS_PCT_PER_LEVEL: Final[float] = 0.03

# Dodging skill evasion bonus: +1 EV per level
# Tuning: Higher values make Dodging more powerful for avoidance
# Lower values reduce light armour/dodge build effectiveness
# Implemented in effects.calculate_dodging_evasion()
DODGING_EVASION_PER_LEVEL: Final[int] = 1

# Shields skill defense divisor for bonus calculation
# Formula: shield_defense = shields_level // SHIELDS_DEFENSE_DIVISOR
# Tuning: Smaller divisor increases shield block effectiveness (3 = +1 per 3 levels)
# Implemented in effects.calculate_shields_defense()
SHIELDS_DEFENSE_DIVISOR: Final[int] = 3

# Stealth skill rating: 25 points per level
# Tuning: Higher values make each Stealth level much more impactful
# Lower values require more investment for stealth effectiveness
# Implemented in effects.calculate_stealth_rating()
STEALTH_POINTS_PER_LEVEL: Final[int] = 25

# =============================================================================
# MAGIC SKILL EFFECTS
# =============================================================================

# Invocations MP contribution relative to Spellcasting (half rate)
# Tuning: Higher values make Invocations better for MP scaling
# Lower values emphasize Spellcasting for MP growth
# Implemented in effects.calculate_max_mp()
INVOCATIONS_MP_MULTIPLIER: Final[float] = 0.5

# Intelligence spell failure reduction: -1% per point above threshold
# Tuning: Higher values make Intelligence more valuable for casters
# Lower values reduce stat dependency for magic users
# Implemented in effects.calculate_spell_failure()
INTELLIGENCE_FAILURE_REDUCTION_PER_POINT: Final[float] = 0.01

# Base Intelligence threshold for failure reduction
# Tuning: Higher threshold delays when INT starts helping failure rates
# Lower threshold makes INT useful earlier
# Implemented in effects.calculate_spell_failure()
INTELLIGENCE_FAILURE_BASE_THRESHOLD: Final[int] = 8

# Spell failure skill reduction divisor
# Controls exponential decay rate: failure *= exp(-skill / divisor)
# Tuning: Higher values slow down failure reduction from skill investment
# Lower values make skills reduce failure more rapidly
# Implemented in effects.calculate_spell_failure()
SPELL_FAILURE_SKILL_DIVISOR: Final[float] = 0.5

# =============================================================================
# SKILL MANUALS
# =============================================================================

# XP duration for common skill manuals
# Tuning: Higher values make common manuals last longer
# Lower values reduce their impact
# Defined in manuals.MANUAL_XP_COMMON
MANUAL_XP_COMMON: Final[int] = 150

# XP duration for rare skill manuals
# Tuning: Higher values extend rare manual benefits
# Lower values bring them closer to common manual value
# Defined in manuals.MANUAL_XP_RARE
MANUAL_XP_RARE: Final[int] = 300

# XP duration for legendary skill manuals
# Tuning: Higher values make legendary finds extremely valuable
# Lower values reduce rarity power gap
# Defined in manuals.MANUAL_XP_LEGENDARY
MANUAL_XP_LEGENDARY: Final[int] = 500

# Aptitude bonus granted by all skill manuals
# Tuning: Higher values make manuals more impactful
# Lower values reduce their training speed boost
# Hardcoded in multiple places in manuals.py
MANUAL_APTITUDE_BONUS: Final[int] = 4

# =============================================================================
# NOTES ON STRUCTURED DATA
# =============================================================================

# The following game data is intentionally NOT flattened into individual constants
# because maintaining it as structured dataclasses improves code clarity:
#
# - Shapeshifting form modifiers: See skills/shapeshifting.py
#   Defined as FormModifiers dataclasses (FORM_BEAST, FORM_DRAGON, etc.)
#   Each form has skill_bonuses and skill_penalties dicts
#
# - Milestone abilities: See skills/milestones.py
#   Defined as Ability dataclasses in MILESTONE_ABILITIES list
#   Each ability has unlock_level, cooldown_turns, and effect parameters
#
# - Skill synergies: See skills/synergies.py
#   Defined as Synergy dataclasses in SYNERGIES list
#   Each synergy has min_level_each, bonus_type, and bonus_amount
#
# - Skill prerequisites: See skills/prerequisites.py
#   Defined as Prerequisite dataclasses in SKILL_PREREQUISITES dict
#   Each prereq has required_skill, minimum_level, and reason
#
# - Cross-training pairs: See skills/models.py
#   Defined as CrossTrainingPair tuples in CROSS_TRAINING_PAIRS
#   Each pair specifies from_skill, to_skill, and multiplier
#
# To modify these values, edit the structured definitions in their respective files.
