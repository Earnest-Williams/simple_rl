```python
# Enhanced DCSS Skill System for simple_rl

## Overview

Performance-first skill progression system based on Dungeon Crawl Stone Soup mechanics, built for simple_rl's high-performance architecture.

### Design Principles

1. **Type Safety**: Full PEP 604 annotations, mypy --strict compliant
2. **Performance**: Numba JIT compilation, vectorized operations, sparse matrices
3. **Data-Oriented**: Polars DataFrames, NumPy arrays, minimal OOP overhead
4. **Determinism**: All randomness via GameRNG integration
5. **Scalability**: Handles 10,000+ entities with batch operations

---

## Architecture

### Core Components

```
skills/
├── models.py           # Data structures, enums, schemas
├── progression.py      # XP formulas (Numba-accelerated)
├── cross_training.py   # Sparse matrix cross-training
├── effects.py          # Combat/magic bonuses (Numba)
├── training.py         # XP distribution logic (Polars)
└── system.py           # High-level API
```

### Type System

All functions fully annotated with **zero type inference**:

```python
def calculate_xp_for_level(level: int, aptitude: int) -> int:
    """No Optional[X], only X | None."""
    ...

@numba.njit(cache=True, fastmath=True)
def calculate_combat_bonuses(
    fighting_level: int,
    weapon_level: int,
    ...
) -> tuple[int, float, int, int, int, int]:
    """Explicit tuple return, no generic TypeVar."""
    ...
```

---

## Performance Characteristics

### Benchmark Targets

| Operation | Target | Actual (estimated) |
|-----------|--------|-------------------|
| XP calculation | >100k/sec | ~500k/sec |
| Combat bonuses | >50k/sec | ~200k/sec |
| Batch XP distribution (1000 entities) | <10ms | ~5ms |
| Save/load (10k entities) | <100ms | ~50ms |

### Memory Footprint

- **Per entity**: ~200 bytes (29 skills × 7 bytes/skill)
- **1,000 entities**: ~200 KB
- **10,000 entities**: ~2 MB

Polars categorical columns reduce memory by 4x vs. string storage.

---

## Skill Mechanics

### 29 Skills in 4 Categories

**Offensive (10)**
- Fighting (HP, damage, accuracy)
- Weapon types: Axes, Maces & Flails, Polearms, Staves, Long Blades, Short Blades
- Ranged: Ranged Weapons, Throwing
- Unarmed Combat

**Defensive (4)**
- Armour (armor effectiveness)
- Dodging (evasion)
- Shields (blocking)
- Stealth (detection range)

**Magic (12)**
- Spellcasting (MP, spell power, success)
- Schools: Conjurations, Hexes, Summonings, Necromancy, Forgecraft, Translocations, Alchemy
- Elements: Fire, Air, Ice, Earth

**Miscellaneous (3)**
- Evocations (wands, items)
- Invocations (god powers, +MP)
- Shapeshifting (transformations)

### XP Progression

Quadratic formula: **XP(L) = 25 × L × (L + 1)**

| Level | XP (apt 0) | XP (apt +4) | XP (apt -4) |
|-------|-----------|-------------|-------------|
| 1     | 50        | 25          | 100         |
| 10    | 2,750     | 1,375       | 5,500       |
| 20    | 10,500    | 5,250       | 21,000      |
| 27    | 18,900    | 9,450       | 37,800      |

### Aptitude System

Species/background modifiers: **-5 to +11**

**Formula**: `multiplier = 2^(-aptitude/4)`

- **+11**: 6.71× faster (Deep Elf Spellcasting)
- **+4**: 2.00× faster
- **0**: Baseline (human)
- **-4**: 2.00× slower
- **-5**: 2.38× slower (Troll Spellcasting)

### Cross-Training

Related skills train each other automatically:

```python
Axes → Maces & Flails (40%)
Axes → Polearms (25%)
Maces → Staves (40%)
Long Blades ↔ Short Blades (40% bidirectional)
```

Implemented as **scipy.sparse.csr_matrix** for O(nnz) lookups.

---

## Usage Examples

### Initialize Entity Skills

```python
from game.entities import EntityRegistry
from skills.system import initialize_entity_skills

entity_id: int = registry.create_entity(...)

# Initialize with species aptitudes
initialize_entity_skills(
    registry,
    entity_id,
    aptitudes={
        Skill.FIGHTING: 2,
        Skill.AXES: 2,
        Skill.SPELLCASTING: -3,
    }
)
```

### Award XP (Automatic Mode)

```python
from skills.system import award_xp, record_skill_usage

# Player uses Fighting and Axes in combat
record_skill_usage(registry, player_id, Skill.FIGHTING, amount=1)
record_skill_usage(registry, player_id, Skill.AXES, amount=1)

# Award 100 XP at end of turn
award_xp(registry, player_id, 100)
# XP distributed proportionally to recent usage
```

### Manual Training Mode

```python
from skills.system import set_training_mode, set_skill_training
from skills.models import TrainingMode, TrainingState

# Switch to manual mode
set_training_mode(registry, player_id, TrainingMode.MANUAL)

# Configure training
set_skill_training(
    registry,
    player_id,
    Skill.FIGHTING,
    TrainingState.NORMAL,  # 1.0× weight
)
set_skill_training(
    registry,
    player_id,
    Skill.AXES,
    TrainingState.FOCUSED,  # 2.0× weight
)

# Set target levels (auto-disables when reached)
set_skill_target(registry, player_id, Skill.AXES, target_level=15)
```

### Calculate Combat Bonuses

```python
from skills.effects import get_combat_bonuses_dict

skills: dict[Skill, int] = registry.get_skills(player_id)

bonuses = get_combat_bonuses_dict(
    fighting=skills.get(Skill.FIGHTING, 0),
    weapon=skills.get(Skill.AXES, 0),
    armour=skills.get(Skill.ARMOUR, 0),
    dodging=skills.get(Skill.DODGING, 0),
    shields=skills.get(Skill.SHIELDS, 0),
    base_armor=10,  # From equipment
)

# Apply to combat
final_damage: int = int(base_damage * bonuses.damage_multiplier)
hit_chance: float = calculate_hit_chance(
    base_accuracy + bonuses.accuracy_bonus,
    enemy_evasion,
)
```

### Batch Operations

```python
from skills.progression import batch_calculate_levels

# Get all entities' skill data
skill_df: pl.DataFrame = registry.skills_df

# Extract arrays
xp_array: np.ndarray = skill_df["xp"].to_numpy()
aptitude_array: np.ndarray = skill_df["aptitude"].to_numpy()

# Vectorized level calculation (Numba parallel)
levels: np.ndarray = batch_calculate_levels(xp_array, aptitude_array)

# Update DataFrame
skill_df = skill_df.with_columns([
    pl.Series(levels, dtype=pl.UInt8).alias("level")
])
```

---

## Integration with simple_rl Systems

### Combat System

```python
# game/systems/combat_system.py

from skills.effects import get_combat_bonuses_dict

def calculate_damage(
    attacker_id: int,
    defender_id: int,
    weapon_skill: Skill,
) -> int:
    # Get attacker skills
    attacker_skills = entity_registry.get_skills(attacker_id)
    
    # Calculate bonuses
    bonuses = get_combat_bonuses_dict(
        fighting=attacker_skills.get(Skill.FIGHTING, 0),
        weapon=attacker_skills.get(weapon_skill, 0),
        ...
    )
    
    # Apply to damage
    base_damage: int = roll_weapon_damage(weapon)
    final_damage: int = int(base_damage * bonuses.damage_multiplier)
    
    # Record usage for automatic training
    record_skill_usage(entity_registry, attacker_id, Skill.FIGHTING)
    record_skill_usage(entity_registry, attacker_id, weapon_skill)
    
    return final_damage
```

### AI System (GOAP)

```python
# game/ai/goap_adapter.py

from skills.effects import calculate_combat_bonuses

def evaluate_combat_action(
    entity_id: int,
    target_id: int,
) -> float:
    """GOAP utility calculation based on skill levels."""
    entity_skills = registry.get_skills(entity_id)
    target_skills = registry.get_skills(target_id)
    
    # Calculate power levels
    our_power = (
        entity_skills.get(Skill.FIGHTING, 0) +
        max(entity_skills.get(s, 0) for s in weapon_skills)
    )
    
    enemy_power = (
        target_skills.get(Skill.FIGHTING, 0) +
        max(target_skills.get(s, 0) for s in weapon_skills)
    )
    
    # Utility: >1.0 = favorable, <1.0 = unfavorable
    return our_power / max(enemy_power, 1.0)
```

### Save/Load

```python
import msgpack
from pathlib import Path

def save_skills(registry: EntityRegistry, save_path: Path) -> None:
    """Save skills using msgpack for speed."""
    data: dict[str, Any] = {
        "entity_id": registry.skills_df["entity_id"].to_numpy(),
        "skill": registry.skills_df["skill"].cast(pl.UInt8).to_numpy(),
        "level": registry.skills_df["level"].to_numpy(),
        "xp": registry.skills_df["xp"].to_numpy(),
        "aptitude": registry.skills_df["aptitude"].to_numpy(),
    }
    
    packed: bytes = msgpack.packb(data, use_bin_type=True)
    save_path.write_bytes(packed)

def load_skills(save_path: Path) -> pl.DataFrame:
    """Load skills from msgpack."""
    packed: bytes = save_path.read_bytes()
    data: dict[str, Any] = msgpack.unpackb(packed, raw=False)
    
    return pl.DataFrame({
        "entity_id": pl.Series(data["entity_id"], dtype=pl.UInt32),
        "skill": pl.Series(data["skill"], dtype=pl.UInt8).cast(pl.Categorical),
        ...
    })
```

---

## Testing

### Run Tests

```bash
# All tests
pytest skills/test_skills.py -v

# Property-based tests only
pytest skills/test_skills.py -v -k "test_xp_formula"

# Benchmarks
pytest skills/test_skills.py -v -m benchmark
```

### Coverage

```bash
pytest skills/test_skills.py --cov=skills --cov-report=html
```

Target: **>95% coverage** on all modules.

---

## Advanced Features

### Skill Manuals

Temporary +4 aptitude boost:

```python
from skills.models import ManualBonus

manual = ManualBonus(
    skill=Skill.FIRE_MAGIC,
    bonus_aptitude=4,
    remaining_xp=2500,
)

# Apply manual (halves training cost)
registry.active_manuals[entity_id] = manual

# Manual auto-consumes as XP is spent
```

### Shapeshifting Forms

```python
from skills.forms import FormModifiers, calculate_bonuses_with_form

bonuses = calculate_bonuses_with_form(
    base_skills=entity_skills,
    active_form="dragon_form",
)

# Form modifiers:
# - Unarmed +10
# - Armor +20
# - HP ×2.0
```

### Cross-Training Analysis

```python
from skills.cross_training import get_synergistic_skill_groups

groups = get_synergistic_skill_groups()
# Returns: [{Axes, Maces, Polearms, Staves}, {Long Blades, Short Blades}]
```

---

## Migration from Existing System

### Phase 1: Dual Mode

Enable new system alongside existing:

```python
class EntityRegistry:
    use_vectorized_skills: bool = False  # Feature flag
```

### Phase 2: Parity Testing

```python
def test_parity() -> None:
    """Ensure new implementation matches legacy."""
    # Run both systems side-by-side
    legacy_result = legacy_distribute_xp(...)
    new_result = distribute_xp_manual(...)
    
    assert_frames_equal(legacy_result, new_result)
```

### Phase 3: Performance Validation

```bash
python -m cProfile -o profile.stats skills/benchmark.py
python -m pstats profile.stats
```

Target: **≥2× speedup** over existing implementation.

---

## Performance Tuning

### Numba Compilation

All hot paths JIT-compiled:

```python
@numba.njit(cache=True, fastmath=True)
def calculate_xp_for_level(level: int, aptitude: int) -> int:
    ...
```

**First run**: ~200ms compilation overhead
**Subsequent runs**: <1μs per call

### Polars Lazy Evaluation

```python
skill_df = (
    skill_df
    .lazy()
    .filter(pl.col("entity_id") == entity_id)
    .with_columns([...])
    .collect()
)
```

Defers computation until `.collect()` for zero-copy operations.

### Memory-Mapped Tables

Precomputed XP tables loaded via mmap:

```python
from skills.mmap_cache import SKILL_TABLE

# O(1) lookup, no deserialization
xp = SKILL_TABLE.get(level=10, aptitude=0)
```

---

## Configuration

```python
from pydantic import BaseModel

class SkillConfig(BaseModel):
    max_level: int = 27
    xp_formula_constant: int = 25
    cross_train_axes_maces: float = 0.40
    fighting_hp_per_level: int = 1
    
    class Config:
        frozen = True  # Immutable
```

Load from TOML:

```toml
[skills]
max_level = 27
xp_formula_constant = 25

[skills.cross_training]
axes_maces = 0.40
axes_polearms = 0.25
```

---

## Future Enhancements

1. **Skill Prerequisites**: Require minimum levels before advanced training
2. **Skill Synergies**: Bonus effects when combining specific skills
3. **Rust Mechanic**: Skills decay if unused (hardcore mode)
4. **Dynamic Aptitudes**: Mutations/effects that modify aptitudes
5. **Skill Trees**: Unlock special abilities at level milestones

---

## References

- [DCSS Skill Documentation](http://crawl.chaosforge.org/Skill)
- [DCSS Aptitude Tables](http://crawl.chaosforge.org/Aptitude)
- [simple_rl Architecture](../README.md)
- [Numba Performance Guide](https://numba.pydata.org/numba-doc/latest/user/performance-tips.html)
- [Polars API Reference](https://pola-rs.github.io/polars/py-polars/html/reference/)

---

## License

Same as simple_rl main project.

## Contributors

Based on DCSS skill mechanics (Crawl Dev Team, 2006-2024).
Adapted for simple_rl with performance optimizations.
```
