"""Skills system constants - all tuneable parameters and magic numbers.

This module centralizes all numerical constants used throughout the skills system.
Each constant is grouped by purpose with clear documentation on what it does
and how tuning it would affect gameplay.

All values marked Final are immutable after module initialization.
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# CORE SKILL PROGRESSION
# =============================================================================

# Maximum skill level achievable
# Tuning: Higher values extend the progression curve and power ceiling
# Lower values make skills cap out sooner, encouraging broader builds
MAX_SKILL_LEVEL: Final[int] = 27

# Minimum aptitude modifier (most difficult to learn)
# Tuning: More negative makes species differentiation more extreme
# Less negative reduces penalty for "bad" skills
MIN_APTITUDE: Final[int] = -5

# Maximum aptitude modifier (easiest to learn)
# Tuning: Higher values make "good" skills train much faster
# Lower values reduce species advantages
MAX_APTITUDE: Final[int] = 11

# Base XP formula constant: XP(L) = CONSTANT * L * (L + 1)
# Tuning: Higher values slow down all skill progression globally
# Lower values speed up progression, making max level more achievable
XP_FORMULA_CONSTANT: Final[int] = 25

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
AUTOMATIC_MODE_WINDOW_SIZE: Final[int] = 1000

# Decay factor applied when usage window exceeds size (exponential decay)
# Tuning: Values closer to 1.0 preserve older usage data longer
# Values closer to 0.0 heavily discount old actions
AUTOMATIC_MODE_DECAY_FACTOR: Final[float] = 0.99

# =============================================================================
# CROSS-TRAINING MULTIPLIERS
# =============================================================================

# High cross-training rate for closely related weapon skills
# Used for: Axes↔Maces, Maces↔Staves, Long↔Short Blades
# Tuning: Higher values reward specializing in related weapon types
# Lower values reduce benefit of weapon skill synergy
CROSS_TRAINING_HIGH: Final[float] = 0.40

# Medium cross-training rate for moderately related weapon skills
# Used for: Axes↔Polearms, Polearms↔Staves
# Tuning: Adjusts mid-tier weapon synergies independently of high/low tiers
CROSS_TRAINING_MEDIUM: Final[float] = 0.25

# Low cross-training rate for opposing elemental schools
# Used for: Fire↔Ice, Air↔Earth (opposing elements with minor synergy)
# Tuning: Higher values reward studying contrasting magic schools
# Lower values emphasize specialization over broad magical knowledge
CROSS_TRAINING_LOW: Final[float] = 0.10

# =============================================================================
# COMBAT SKILL EFFECTS
# =============================================================================

# Fighting skill HP bonus: +1 HP per level
# Tuning: Higher values make Fighting more valuable for survivability
# Lower values reduce importance of Fighting for HP
FIGHTING_HP_PER_LEVEL: Final[int] = 1

# Fighting skill damage multiplier: +1% damage per level
# Tuning: Higher values make Fighting more impactful for damage output
# Lower values reduce Fighting's offensive contribution
FIGHTING_DAMAGE_PCT_PER_LEVEL: Final[float] = 0.01

# Fighting skill accuracy bonus: level // 2
# Tuning: Divisor controls how much Fighting improves hit chance
# Smaller divisor = more accuracy per level
FIGHTING_ACCURACY_DIVISOR: Final[int] = 2

# Weapon skill damage multiplier: +2% damage per level
# Tuning: Higher values make weapon specialization more rewarding
# Lower values reduce difference between skilled and unskilled fighters
WEAPON_DAMAGE_PCT_PER_LEVEL: Final[float] = 0.02

# Weapon skill accuracy bonus: +1 per level
# Tuning: Higher values make weapon skills more reliable for hitting
# Lower values reduce importance of weapon skill for accuracy
WEAPON_ACCURACY_PER_LEVEL: Final[int] = 1

# Armour skill AC multiplier: +3% armor effectiveness per level
# Tuning: Higher values make Armour skill dramatically increase AC
# Lower values reduce scaling of heavy armor builds
ARMOUR_EFFECTIVENESS_PCT_PER_LEVEL: Final[float] = 0.03

# Dodging skill evasion bonus: +1 EV per level
# Tuning: Higher values make Dodging more powerful for avoidance
# Lower values reduce light armor/dodge build effectiveness
DODGING_EVASION_PER_LEVEL: Final[int] = 1

# Shields skill defense bonus: level // 3
# Tuning: Smaller divisor increases shield block effectiveness
# Larger divisor reduces shield skill impact
SHIELDS_DEFENSE_DIVISOR: Final[int] = 3

# Stealth skill rating: 25 points per level
# Tuning: Higher values make each Stealth level much more impactful
# Lower values require more investment for stealth effectiveness
STEALTH_POINTS_PER_LEVEL: Final[int] = 25

# =============================================================================
# MAGIC SKILL EFFECTS
# =============================================================================

# Invocations MP contribution relative to Spellcasting (half rate)
# Tuning: Higher values make Invocations better for MP scaling
# Lower values emphasize Spellcasting for MP growth
INVOCATIONS_MP_MULTIPLIER: Final[float] = 0.5

# Intelligence spell failure reduction: -1% per point above 8
# Tuning: Higher values make Intelligence more valuable for casters
# Lower values reduce stat dependency for magic users
INTELLIGENCE_FAILURE_REDUCTION_PER_POINT: Final[float] = 0.01

# Base Intelligence threshold for failure reduction
# Tuning: Higher threshold delays when INT starts helping failure rates
# Lower threshold makes INT useful earlier
INTELLIGENCE_FAILURE_BASE_THRESHOLD: Final[int] = 8

# Spell failure skill reduction divisor
# Tuning: Controls exponential decay rate of failure with skill
# Higher values slow down failure reduction from skill investment
SPELL_FAILURE_SKILL_DIVISOR: Final[float] = 0.5

# =============================================================================
# SKILL MANUALS
# =============================================================================

# XP duration for common skill manuals
# Tuning: Higher values make common manuals last longer
# Lower values reduce their impact
MANUAL_XP_COMMON: Final[int] = 150

# XP duration for rare skill manuals
# Tuning: Higher values extend rare manual benefits
# Lower values bring them closer to common manual value
MANUAL_XP_RARE: Final[int] = 300

# XP duration for legendary skill manuals
# Tuning: Higher values make legendary finds extremely valuable
# Lower values reduce rarity power gap
MANUAL_XP_LEGENDARY: Final[int] = 500

# Aptitude bonus granted by all skill manuals
# Tuning: Higher values make manuals more impactful
# Lower values reduce their training speed boost
MANUAL_APTITUDE_BONUS: Final[int] = 4

# =============================================================================
# SHAPESHIFTING FORMS - BEAST FORM
# =============================================================================

# Beast Form unarmed combat bonus (natural claws)
# Tuning: Higher values make beast form better for combat
FORM_BEAST_UNARMED_BONUS: Final[int] = 5

# Beast Form dodging bonus (agile)
# Tuning: Higher values improve beast form mobility
FORM_BEAST_DODGING_BONUS: Final[int] = 2

# Beast Form spellcasting penalty (can't cast effectively)
# Tuning: Higher values make beast form worse for casters
FORM_BEAST_SPELLCASTING_PENALTY: Final[int] = 8

# Beast Form weapon penalties (can't use equipment)
# Tuning: Higher values enforce pure beast form playstyle
FORM_BEAST_EQUIPMENT_PENALTY: Final[int] = 10

# =============================================================================
# SHAPESHIFTING FORMS - STATUE FORM
# =============================================================================

# Statue Form armor bonus (stone skin)
# Tuning: Higher values make statue form tankier
FORM_STATUE_ARMOUR_BONUS: Final[int] = 8

# Statue Form fighting bonus (enhanced strength)
# Tuning: Higher values improve statue combat prowess
FORM_STATUE_FIGHTING_BONUS: Final[int] = 3

# Statue Form dodging penalty (slow and heavy)
# Tuning: Higher values emphasize tank vs. agile tradeoff
FORM_STATUE_DODGING_PENALTY: Final[int] = 5

# Statue Form stealth penalty (loud footsteps)
# Tuning: Higher values prevent statue stealth gameplay
FORM_STATUE_STEALTH_PENALTY: Final[int] = 10

# Statue Form spellcasting penalty (concentration difficulty)
# Tuning: Higher values discourage battle mage statue builds
FORM_STATUE_SPELLCASTING_PENALTY: Final[int] = 5

# =============================================================================
# SHAPESHIFTING FORMS - DRAGON FORM
# =============================================================================

# Dragon Form fighting bonus
# Tuning: Higher values make dragon form more powerful in melee
FORM_DRAGON_FIGHTING_BONUS: Final[int] = 5

# Dragon Form unarmed combat bonus (claws and bite)
# Tuning: Higher values improve dragon natural weapons
FORM_DRAGON_UNARMED_BONUS: Final[int] = 8

# Dragon Form fire magic bonus (breathe fire)
# Tuning: Higher values synergize dragon form with fire magic
FORM_DRAGON_FIRE_BONUS: Final[int] = 4

# Dragon Form armor bonus (scales)
# Tuning: Higher values increase dragon tankiness
FORM_DRAGON_ARMOUR_BONUS: Final[int] = 5

# Dragon Form dodging penalty (large size)
# Tuning: Higher values penalize dragon agility
FORM_DRAGON_DODGING_PENALTY: Final[int] = 3

# Dragon Form stealth penalty (very large)
# Tuning: Higher values prevent dragon stealth
FORM_DRAGON_STEALTH_PENALTY: Final[int] = 8

# Dragon Form equipment penalty (can't use gear)
# Tuning: Must be high to enforce transformation restrictions
FORM_DRAGON_EQUIPMENT_PENALTY: Final[int] = 10

# =============================================================================
# SHAPESHIFTING FORMS - SPIDER FORM
# =============================================================================

# Spider Form dodging bonus (eight legs)
# Tuning: Higher values make spider form more evasive
FORM_SPIDER_DODGING_BONUS: Final[int] = 4

# Spider Form stealth bonus (quiet)
# Tuning: Higher values enable spider stealth builds
FORM_SPIDER_STEALTH_BONUS: Final[int] = 3

# Spider Form unarmed bonus (venomous bite)
# Tuning: Higher values improve spider combat
FORM_SPIDER_UNARMED_BONUS: Final[int] = 2

# Spider Form armor penalty (can't wear armor)
# Tuning: Higher values emphasize spider fragility
FORM_SPIDER_ARMOUR_PENALTY: Final[int] = 5

# Spider Form spellcasting penalty (spider brain)
# Tuning: Higher values prevent spider caster builds
FORM_SPIDER_SPELLCASTING_PENALTY: Final[int] = 6

# Spider Form equipment penalty
# Tuning: Must be high to enforce transformation restrictions
FORM_SPIDER_EQUIPMENT_PENALTY: Final[int] = 10

# =============================================================================
# SHAPESHIFTING FORMS - ICE BEAST
# =============================================================================

# Ice Beast ice magic bonus (frost breath)
# Tuning: Higher values synergize ice beast with ice magic
FORM_ICE_BEAST_ICE_BONUS: Final[int] = 5

# Ice Beast unarmed bonus (icy claws)
# Tuning: Higher values improve ice beast melee
FORM_ICE_BEAST_UNARMED_BONUS: Final[int] = 4

# Ice Beast armor bonus (ice coating)
# Tuning: Higher values make ice beast tankier
FORM_ICE_BEAST_ARMOUR_BONUS: Final[int] = 3

# Ice Beast fire magic penalty (weak to fire)
# Tuning: Higher values create fire vulnerability
FORM_ICE_BEAST_FIRE_PENALTY: Final[int] = 8

# Ice Beast dodging penalty (bulky)
# Tuning: Higher values reduce ice beast mobility
FORM_ICE_BEAST_DODGING_PENALTY: Final[int] = 2

# Ice Beast equipment penalty
# Tuning: Must be high to enforce transformation restrictions
FORM_ICE_BEAST_EQUIPMENT_PENALTY: Final[int] = 10

# =============================================================================
# SHAPESHIFTING FORMS - WISP FORM
# =============================================================================

# Wisp Form dodging bonus (intangible)
# Tuning: Higher values make wisp extremely evasive
FORM_WISP_DODGING_BONUS: Final[int] = 8

# Wisp Form stealth bonus (silent)
# Tuning: Higher values enable ultimate stealth
FORM_WISP_STEALTH_BONUS: Final[int] = 6

# Wisp Form spellcasting bonus (magical essence)
# Tuning: Higher values make wisp ideal for casters
FORM_WISP_SPELLCASTING_BONUS: Final[int] = 3

# Wisp Form translocations bonus (blink easily)
# Tuning: Higher values improve wisp mobility spells
FORM_WISP_TRANSLOCATIONS_BONUS: Final[int] = 4

# Wisp Form fighting penalty (physically weak)
# Tuning: Higher values prevent wisp melee builds
FORM_WISP_FIGHTING_PENALTY: Final[int] = 5

# Wisp Form armor penalty (can't wear armor)
# Tuning: Must be high to prevent armor use
FORM_WISP_ARMOUR_PENALTY: Final[int] = 10

# Wisp Form unarmed penalty (weak attacks)
# Tuning: Higher values discourage wisp melee
FORM_WISP_UNARMED_PENALTY: Final[int] = 3

# Wisp Form equipment penalty
# Tuning: Must be high to enforce transformation restrictions
FORM_WISP_EQUIPMENT_PENALTY: Final[int] = 10

# =============================================================================
# MILESTONE ABILITIES - UNLOCK LEVELS
# =============================================================================

# Fighting milestones
# Tuning: Lower levels make abilities unlock earlier
MILESTONE_FIGHTING_CLEAVE: Final[int] = 10
MILESTONE_FIGHTING_SECOND_WIND: Final[int] = 15
MILESTONE_FIGHTING_BERSERK: Final[int] = 20

# Weapon skill milestones
# Tuning: Adjusts progression pace for weapon specialists
MILESTONE_AXES_WHIRLWIND: Final[int] = 12
MILESTONE_LONG_BLADES_PRECISION: Final[int] = 15
MILESTONE_SHORT_BLADES_RIPOSTE: Final[int] = 12
MILESTONE_POLEARMS_IMPALE: Final[int] = 14
MILESTONE_MACES_CRUSHING_BLOW: Final[int] = 12

# Defensive skill milestones
# Tuning: Controls when defensive abilities become available
MILESTONE_ARMOUR_IRON_SKIN: Final[int] = 12
MILESTONE_DODGING_PERFECT_DODGE: Final[int] = 15
MILESTONE_SHIELDS_BASH: Final[int] = 10
MILESTONE_STEALTH_SHADOW_STEP: Final[int] = 18

# Magic milestones
# Tuning: Balances when powerful magic abilities unlock
MILESTONE_SPELLCASTING_SPELL_ECHO: Final[int] = 20
MILESTONE_SPELLCASTING_MANA_SHIELD: Final[int] = 15
MILESTONE_CONJURATIONS_CHAIN: Final[int] = 15
MILESTONE_HEXES_EXTENDED: Final[int] = 12
MILESTONE_SUMMONINGS_ARMY: Final[int] = 18
MILESTONE_NECROMANCY_LIFE_DRAIN: Final[int] = 15
MILESTONE_TRANSLOCATIONS_CONTROLLED_BLINK: Final[int] = 14

# Elemental magic milestones
# Tuning: Controls access to screen-wide elemental powers
MILESTONE_FIRE_FIRESTORM: Final[int] = 16
MILESTONE_ICE_BLIZZARD: Final[int] = 16
MILESTONE_AIR_TORNADO: Final[int] = 14
MILESTONE_EARTH_EARTHQUAKE: Final[int] = 16

# Special milestones
# Tuning: Gates access to unique powerful abilities
MILESTONE_INVOCATIONS_DIVINE_FAVOR: Final[int] = 15
MILESTONE_SHAPESHIFTING_MASTER: Final[int] = 20
MILESTONE_SHAPESHIFTING_DRAGON: Final[int] = 24

# =============================================================================
# MILESTONE ABILITIES - COOLDOWNS (in turns)
# =============================================================================

# Combat ability cooldowns
# Tuning: Higher values limit how often abilities can be used
COOLDOWN_SECOND_WIND: Final[int] = 100
COOLDOWN_BERSERK: Final[int] = 50
COOLDOWN_WHIRLWIND: Final[int] = 20
COOLDOWN_PRECISION_STRIKE: Final[int] = 30
COOLDOWN_IMPALE: Final[int] = 25
COOLDOWN_CRUSHING_BLOW: Final[int] = 15
COOLDOWN_PERFECT_DODGE: Final[int] = 20
COOLDOWN_SHIELD_BASH: Final[int] = 15
COOLDOWN_SHADOW_STEP: Final[int] = 30

# Magic ability cooldowns
# Tuning: Balances frequency of powerful magic abilities
COOLDOWN_SPELL_ECHO: Final[int] = 50
COOLDOWN_SUMMON_ARMY: Final[int] = 40
COOLDOWN_CONTROLLED_BLINK: Final[int] = 10
COOLDOWN_FIRESTORM: Final[int] = 60
COOLDOWN_BLIZZARD: Final[int] = 60
COOLDOWN_TORNADO: Final[int] = 40
COOLDOWN_EARTHQUAKE: Final[int] = 50

# Special ability cooldowns
# Tuning: Controls access to unique powerful effects
COOLDOWN_DIVINE_FAVOR: Final[int] = 100
COOLDOWN_MASTER_SHAPESHIFT: Final[int] = 20
COOLDOWN_DRAGON_FORM: Final[int] = 200

# =============================================================================
# MILESTONE ABILITIES - EFFECT MAGNITUDES
# =============================================================================

# Second Wind HP restoration (percentage of max HP)
# Tuning: Higher values make Second Wind stronger
SECOND_WIND_HP_RESTORE_PCT: Final[float] = 0.25

# Berserk damage multiplier
# Tuning: Higher values increase berserk damage boost
BERSERK_DAMAGE_MULT: Final[float] = 2.0

# Berserk defense penalty (half normal defense)
# Tuning: Higher penalty makes berserk riskier
BERSERK_DEFENSE_MULT: Final[float] = 0.5

# Berserk duration in turns
# Tuning: Higher values extend berserk state
BERSERK_DURATION: Final[int] = 10

# Iron Skin armor bonus
# Tuning: Higher values make Iron Skin more powerful
IRON_SKIN_ARMOR_BONUS: Final[int] = 5

# Shield Bash stun duration
# Tuning: Higher values make stun more impactful
SHIELD_BASH_STUN_DURATION: Final[int] = 2

# Shadow Step range
# Tuning: Higher values increase teleport flexibility
SHADOW_STEP_RANGE: Final[int] = 5

# Crushing Blow armor ignore percentage
# Tuning: Higher values make ability more effective vs. armor
CRUSHING_BLOW_ARMOR_IGNORE_PCT: Final[float] = 0.50

# Elemental Master spell power bonus
# Tuning: Higher values reward dual-element mastery
ELEMENTAL_MASTER_POWER_BONUS_PCT: Final[float] = 0.20

# Archmage conjuration power bonus
# Tuning: Higher values reward high Spellcasting + Conjurations
ARCHMAGE_POWER_BONUS_PCT: Final[float] = 0.25

# Summon Army creature count multiplier
# Tuning: Higher values summon more creatures
SUMMON_ARMY_MULTIPLIER: Final[int] = 3

# Life Drain heal percentage
# Tuning: Higher values make necromancy more sustaining
LIFE_DRAIN_HEAL_PCT: Final[float] = 0.50

# =============================================================================
# SYNERGY BONUSES - MINIMUM LEVELS
# =============================================================================

# Combat synergy minimum levels
# Tuning: Lower values make synergies unlock earlier
SYNERGY_TOUGH_WARRIOR_MIN_LEVEL: Final[int] = 10
SYNERGY_SHADOW_DANCER_MIN_LEVEL: Final[int] = 8
SYNERGY_MARTIAL_ARTIST_MIN_LEVEL: Final[int] = 12
SYNERGY_DEFENDER_MIN_LEVEL: Final[int] = 10
SYNERGY_DUELIST_MIN_LEVEL: Final[int] = 10
SYNERGY_SNIPER_MIN_LEVEL: Final[int] = 10

# Magic synergy minimum levels
# Tuning: Controls when magical combinations become effective
SYNERGY_MAGICAL_DEVOTEE_MIN_LEVEL: Final[int] = 10
SYNERGY_ELEMENTAL_MASTER_MIN_LEVEL: Final[int] = 12
SYNERGY_ARCHMAGE_MIN_LEVEL: Final[int] = 15
SYNERGY_TRICKSTER_MIN_LEVEL: Final[int] = 8
SYNERGY_DARK_PRIEST_MIN_LEVEL: Final[int] = 10
SYNERGY_BLINK_MASTER_MIN_LEVEL: Final[int] = 12

# Hybrid synergy minimum levels
# Tuning: Balances hybrid build progression
SYNERGY_BATTLE_MAGE_MIN_LEVEL: Final[int] = 10

# =============================================================================
# SYNERGY BONUSES - EFFECT MAGNITUDES
# =============================================================================

# Tough Warrior HP bonus
# Tuning: Higher values reward Fighting + Armour builds
SYNERGY_TOUGH_WARRIOR_HP: Final[float] = 5.0

# Shadow Dancer evasion bonus
# Tuning: Higher values improve Dodging + Stealth synergy
SYNERGY_SHADOW_DANCER_EVASION: Final[float] = 3.0

# Martial Artist damage bonus
# Tuning: Higher values boost unarmed combat builds
SYNERGY_MARTIAL_ARTIST_DAMAGE_PCT: Final[float] = 0.15

# Defender block chance bonus
# Tuning: Higher values make shield tanks more effective
SYNERGY_DEFENDER_BLOCK_PCT: Final[float] = 0.10

# Magical Devotee MP bonus
# Tuning: Higher values reward Spellcasting + Invocations
SYNERGY_MAGICAL_DEVOTEE_MP: Final[float] = 10.0

# Trickster hex duration bonus
# Tuning: Higher values extend hex effects for stealth builds
SYNERGY_TRICKSTER_HEX_DURATION_PCT: Final[float] = 0.30

# Dark Priest summon duration bonus
# Tuning: Higher values make undead summons last longer
SYNERGY_DARK_PRIEST_SUMMON_DURATION_PCT: Final[float] = 0.40

# Duelist riposte chance
# Tuning: Higher values trigger counterattacks more often
SYNERGY_DUELIST_RIPOSTE_PCT: Final[float] = 0.15

# Sniper critical hit chance from stealth
# Tuning: Higher values reward stealth archery
SYNERGY_SNIPER_CRIT_PCT: Final[float] = 0.20

# Blink Master frequency bonus
# Tuning: Higher values make blink trigger more reliably
SYNERGY_BLINK_MASTER_FREQUENCY_PCT: Final[float] = 0.30

# =============================================================================
# PREREQUISITE MINIMUM LEVELS
# =============================================================================

# Weapon skill prerequisites (require Fighting)
# Tuning: Higher values delay weapon specialization
PREREQ_LONG_BLADES_FIGHTING: Final[int] = 3
PREREQ_SHORT_BLADES_FIGHTING: Final[int] = 3
PREREQ_AXES_FIGHTING: Final[int] = 3
PREREQ_MACES_FIGHTING: Final[int] = 3
PREREQ_POLEARMS_FIGHTING: Final[int] = 3
PREREQ_STAVES_FIGHTING: Final[int] = 2

# Shield prerequisite
# Tuning: Higher values require more defensive skill for shields
PREREQ_SHIELDS_DODGING: Final[int] = 2

# Magic school prerequisites (require Spellcasting)
# Tuning: Higher values delay access to magic schools
PREREQ_CONJURATIONS_SPELLCASTING: Final[int] = 4
PREREQ_HEXES_SPELLCASTING: Final[int] = 3
PREREQ_SUMMONINGS_SPELLCASTING: Final[int] = 5
PREREQ_NECROMANCY_SPELLCASTING: Final[int] = 4
PREREQ_TRANSLOCATIONS_SPELLCASTING: Final[int] = 5

# Elemental magic prerequisites
# Tuning: Controls when elemental magic becomes available
PREREQ_FIRE_SPELLCASTING: Final[int] = 3
PREREQ_ICE_SPELLCASTING: Final[int] = 3
PREREQ_AIR_SPELLCASTING: Final[int] = 3
PREREQ_EARTH_SPELLCASTING: Final[int] = 3

# Shapeshifting prerequisites (requires both magic and combat)
# Tuning: Higher values make shapeshifting a late-game specialization
PREREQ_SHAPESHIFTING_SPELLCASTING: Final[int] = 6
PREREQ_SHAPESHIFTING_UNARMED: Final[int] = 4
