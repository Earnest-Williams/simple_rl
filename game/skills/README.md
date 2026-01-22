# Skill System

A DCSS-inspired skill progression system for character development.

## Overview

The skill system provides classless character progression where XP is distributed among trained skills. Skills range from level 0 to 27, with quadratic XP costs that increase as skills advance. The system supports:

- **29 Skills** across 4 categories (Offense, Defense, Magic, Miscellaneous)
- **Aptitude System** - Species/background modifiers affect training speed
- **Training Modes** - Manual (player choice) or Automatic (usage-based)
- **Cross-Training** - Related skills train each other at reduced rates
- **Skill Effects** - Combat bonuses, magic power, HP/MP increases

## Skill Categories

### Offense (10 skills)
- **Fighting** - General melee damage/accuracy, grants +1 HP per level
- **Weapon Skills**: Axes, Maces & Flails, Polearms, Staves, Long Blades, Short Blades, Ranged Weapons, Throwing, Unarmed Combat

### Defense (4 skills)
- **Armour** - Improves armor effectiveness
- **Dodging** - Increases evasion
- **Shields** - Shield proficiency and blocking
- **Stealth** - Reduces detection range

### Magic (12 skills)
- **Spellcasting** - +1 MP per level, spell power/success
- **Schools**: Conjurations, Hexes, Summonings, Necromancy, Forgecraft, Translocations, Alchemy
- **Elements**: Fire Magic, Air Magic, Ice Magic, Earth Magic

### Miscellaneous (3 skills)
- **Evocations** - Wands and evocable items
- **Invocations** - God powers, grants +0.5 MP per level
- **Shapeshifting** - Form transformations

## XP Progression

Skills use quadratic progression following the formula: `XP = 25 * L * (L + 1)`

| Level | XP Needed | Level | XP Needed | Level | XP Needed |
|-------|-----------|-------|-----------|-------|-----------|
| 1     | 50        | 10    | 2,750     | 20    | 10,500    |
| 5     | 750       | 15    | 6,000     | 27    | 18,900    |

## Aptitude System

Aptitudes modify XP costs via: `multiplier = 2^(-aptitude/4)`

| Aptitude | Multiplier | Training Speed |
|----------|------------|----------------|
| +4       | 0.500      | 2× faster      |
| +2       | 0.707      | 1.41× faster   |
| 0        | 1.000      | Baseline       |
| -2       | 1.414      | 1.41× slower   |
| -4       | 2.000      | 2× slower      |

Positive aptitudes make skills train faster, negative aptitudes slow training.

## Training Modes

### Manual Mode (Recommended)
- XP splits evenly among enabled skills
- **States**:
  - `ENABLED` - Normal training (1× share)
  - `FOCUSED` - Priority training (2× share)
  - `DISABLED` - No training
- **Targets**: Set level goals; auto-disables when reached

### Automatic Mode
- XP distributed based on recent skill usage
- Focused skills receive minimum 10% share even if unused
- Usage tracking cleared after each XP distribution

## Cross-Training

Related skills train each other at 25% efficiency:

- **Maces & Flails** ↔ Axes, Staves
- **Axes** ↔ Maces & Flails, Polearms
- **Polearms** ↔ Axes, Staves
- **Staves** ↔ Maces & Flails, Polearms
- **Long Blades** ↔ Short Blades (20%)
- **Fire Magic** ↔ Ice Magic (10%)
- **Air Magic** ↔ Earth Magic (10%)

## Skill Effects

### Combat Bonuses

**Fighting**:
- +1 HP per level
- +1% damage per level
- +0.5 accuracy per level

**Weapon Skills**:
- +2% damage per level
- +1 accuracy per level

**Armour**:
- +3% armor effectiveness per level

**Dodging**:
- +1 evasion per level

**Shields**:
- +0.33 defense per level

### Magic Bonuses

**Spellcasting**:
- +1 MP per level
- +1.5% spell power per level

**Magic Schools**:
- +2% spell power per level (for that school)

**Invocations**:
- +0.5 MP per level
- (MP bonus = max of Spellcasting or Invocations/2)

## Usage Examples

### Initialize Skills for an Entity

```python
from game.skills import initialize_entity_skills, Skill, TrainingMode

# Start with no skills (all at 0)
initialize_entity_skills(entity_registry, player_id, training_mode=TrainingMode.MANUAL)

# Start with some initial skills
initial_skills = {
    Skill.FIGHTING: (3, 0),      # Level 3, aptitude 0
    Skill.SHORT_BLADES: (5, 2),  # Level 5, aptitude +2
    Skill.DODGING: (2, 1),       # Level 2, aptitude +1
}
initialize_entity_skills(
    entity_registry,
    player_id,
    initial_skills=initial_skills,
    training_mode=TrainingMode.MANUAL
)
```

### Award XP

```python
from game.skills import award_xp

# Award 1000 XP (distributes among trained skills)
level_changes = award_xp(entity_registry, player_id, 1000)

# Returns dict of {Skill: (old_level, new_level)} for skills that leveled
if level_changes:
    for skill, (old, new) in level_changes.items():
        print(f"{skill.name}: {old} -> {new}")
```

### Configure Training

```python
from game.skills import set_skill_training, set_training_mode, TrainingState

# Enable training for a skill
set_skill_training(entity_registry, player_id, Skill.FIGHTING, state=TrainingState.ENABLED)

# Focus on a skill (2× XP share)
set_skill_training(entity_registry, player_id, Skill.SHORT_BLADES, state=TrainingState.FOCUSED)

# Set target level (auto-disables when reached)
set_skill_training(entity_registry, player_id, Skill.DODGING, target_level=10)

# Disable a skill
set_skill_training(entity_registry, player_id, Skill.ARMOUR, state=TrainingState.DISABLED)

# Switch to automatic mode
set_training_mode(entity_registry, player_id, TrainingMode.AUTOMATIC)
```

### Record Skill Usage (for Automatic Mode)

```python
from game.skills import record_skill_usage

# Record that player used Fighting (in combat)
record_skill_usage(entity_registry, player_id, Skill.FIGHTING, amount=1)

# Record multiple uses (e.g., cast 5 fire spells)
record_skill_usage(entity_registry, player_id, Skill.FIRE_MAGIC, amount=5)
```

### Query Skill Levels

```python
from game.skills import get_entity_skill_level

# Get current level in a skill
fighting_level = get_entity_skill_level(entity_registry, player_id, Skill.FIGHTING)
print(f"Fighting level: {fighting_level}")
```

### Calculate Combat/Magic Bonuses

```python
from game.skills import calculate_total_combat_bonuses, calculate_total_magic_bonuses

# Get entity's skills
skills = entity_registry.get_skills(player_id)

# Calculate combat bonuses (specify weapon skill being used)
combat_bonuses = calculate_total_combat_bonuses(skills, weapon_skill=Skill.LONG_BLADES)
print(f"HP Bonus: {combat_bonuses['hp_bonus']}")
print(f"Damage Multiplier: {combat_bonuses['damage_multiplier']}")
print(f"Accuracy Bonus: {combat_bonuses['accuracy_bonus']}")

# Calculate magic bonuses (specify school being used)
magic_bonuses = calculate_total_magic_bonuses(skills, magic_school=Skill.FIRE_MAGIC)
print(f"MP Bonus: {magic_bonuses['mp_bonus']}")
print(f"Spell Power: {magic_bonuses['spell_power_multiplier']}")
```

## Integration with Combat System

To integrate skill bonuses into combat:

1. **Before combat**: Calculate bonuses and apply to entity stats
2. **During combat**: Use modified stats for damage/accuracy calculations
3. **After combat**: Record skill usage for automatic training

```python
from game.skills import calculate_total_combat_bonuses, record_skill_usage

# 1. Get bonuses
skills = entity_registry.get_skills(attacker_id)
bonuses = calculate_total_combat_bonuses(skills, weapon_skill=Skill.AXES)

# 2. Apply bonuses to combat
base_damage = roll_dice("1d8")
final_damage = int(base_damage * bonuses['damage_multiplier'])
accuracy = base_accuracy + bonuses['accuracy_bonus']

# 3. Record usage (if automatic training)
config = entity_registry.get_skill_training(attacker_id)
if config.mode == TrainingMode.AUTOMATIC:
    record_skill_usage(entity_registry, attacker_id, Skill.FIGHTING)
    record_skill_usage(entity_registry, attacker_id, Skill.AXES)
```

## Module Structure

```
game/skills/
├── __init__.py          # Public API exports
├── models.py            # Skill definitions, enums, data structures
├── progression.py       # XP tables and level calculations
├── training.py          # Training mode logic and XP distribution
├── effects.py           # Skill bonus calculations
├── system.py            # High-level interface for game integration
└── README.md            # This file
```

## Testing

Run tests with:

```bash
pytest tests/test_skills.py -v
```

Tests cover:
- XP progression formulas
- Aptitude calculations
- Manual and automatic training modes
- Cross-training bonuses
- Skill effect calculations
- Target level auto-disable
- Focus multipliers

## Design Philosophy

Based on DCSS skill mechanics:

1. **Classless progression** - No rigid class restrictions
2. **Opportunity cost** - Training one skill means less XP for others
3. **Diminishing returns** - Quadratic costs make specialization expensive
4. **Flexibility** - Switch training focus anytime
5. **Meaningful choices** - Different builds viable through skill selection

## Future Extensions

Potential enhancements:

- **Skill prerequisites** - Require minimum levels before unlocking advanced skills
- **Skill synergies** - Special bonuses for skill combinations
- **Temporary boosts** - Items/spells that grant skill bonuses
- **Skill rust** - Skills decay if unused (optional hardcore mode)
- **Manuals** - Consumable items granting +4 aptitude temporarily
- **Species-specific aptitudes** - Different races excel at different skills
