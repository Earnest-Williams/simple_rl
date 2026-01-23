# Integration Guide: Skill System → simple_rl

## Executive Summary

This guide provides a **concrete, actionable plan** to integrate the DCSS-inspired skill system into simple_rl's EntityRegistry. All recommendations address the specific gaps identified in code review.

**Time Estimate**: 2-3 days for full integration + 1 week for migration testing

**Performance Targets**:
- XP distribution: >10,000 entities/sec
- Save/load (10k entities): <100ms
- Combat bonuses: >50,000 ops/sec

---

## Integration Checklist

### Phase 1: Add Core Infrastructure (Day 1)

- [ ] **1.1** Add `skills_df: pl.DataFrame` to `EntityRegistry.__init__`
  ```python
  # In game/entities/registry.py
  from game.skills.registry_integration import SKILL_TABLE_SCHEMA
  
  class EntityRegistry:
      def __init__(self, ...):
          # ... existing code ...
          self.skills_df = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
          self.use_vectorized_skills = False  # Feature flag
          self._skills_lock = Lock()  # Thread safety
  ```

- [ ] **1.2** Copy `skills/` module to `game/skills/`
  ```bash
  cp -r skills/ simple_rl/game/skills/
  ```

- [ ] **1.3** Add dependencies to `pyproject.toml`
  ```toml
  [project.dependencies]
  scipy = ">=1.11.0"
  msgpack = ">=1.0.7"
  # Numba, Polars, NumPy already present
  ```

- [ ] **1.4** Run Numba warmup at startup
  ```python
  # In main.py or orchestrator.py
  from game.skills.utils import numba_warmup
  
  if __name__ == "__main__":
      numba_warmup()  # ~200ms compilation
      main()
  ```

---

### Phase 2: Implement Dual-Mode APIs (Day 1-2)

- [ ] **2.1** Add `initialize_entity_skills()` to EntityRegistry
  ```python
  # Use mixin from registry_integration.py
  from game.skills.registry_integration import SkillSystemMixin
  
  # Add methods to EntityRegistry
  EntityRegistry.initialize_entity_skills = SkillSystemMixin.initialize_entity_skills
  EntityRegistry.get_skills = SkillSystemMixin.get_skills
  EntityRegistry.set_skills = SkillSystemMixin.set_skills
  ```

- [ ] **2.2** Implement legacy compatibility shims
  ```python
  def _sync_skills_to_legacy(self, entity_id: int, skills_update: pl.DataFrame) -> None:
      """Update entities_df["skills"] dict for backward compat."""
      skills_dict = {}
      for row in skills_update.iter_rows(named=True):
          skill = Skill(row["skill"])
          skills_dict[skill] = SkillProgress(...)
      
      # Update entities_df
      self.entities_df = self.entities_df.with_columns([
          pl.when(pl.col("entity_id") == entity_id)
            .then(pl.lit(skills_dict))  # Replace object
            .otherwise(pl.col("skills"))
            .alias("skills")
      ])
  ```

- [ ] **2.3** Hook `award_xp` into combat system
  ```python
  # In game/systems/combat_system.py
  from game.skills.system import award_xp, record_skill_usage
  from game.skills.models import Skill
  
  def resolve_combat(attacker_id: int, defender_id: int, ...) -> None:
      # ... existing combat logic ...
      
      # Record skill usage (automatic mode)
      record_skill_usage(entity_registry, attacker_id, Skill.FIGHTING)
      record_skill_usage(entity_registry, attacker_id, weapon_skill)
      
      # Award XP (50 XP per hit, 100 per kill)
      xp_amount = 50 if defender_alive else 100
      level_ups = award_xp(entity_registry, attacker_id, xp_amount)
      
      # Log level-ups
      for skill, (old, new) in level_ups.items():
          log.info(f"Level up! {skill.name}: {old} → {new}")
  ```

---

### Phase 3: Serialization Integration (Day 2)

- [ ] **3.1** Add skills to EntityRegistry.save()
  ```python
  # In game/entities/registry.py
  from game.skills.utils import integrate_with_registry_save
  
  def save(self, path: Path) -> None:
      with self._skills_lock:
          save_dict = {
              "entities": self._serialize_entities_df(),
              "items": self._serialize_items_df(),
              # ... other registries ...
          }
          
          # Add skills_table_v1
          save_dict = integrate_with_registry_save(save_dict, self.skills_df)
          
          packed = msgpack.packb(save_dict)
          path.write_bytes(packed)
  ```

- [ ] **3.2** Add skills to EntityRegistry.load()
  ```python
  from game.skills.utils import extract_from_registry_save
  
  def load(self, path: Path) -> None:
      with self._skills_lock:
          packed = path.read_bytes()
          save_dict = msgpack.unpackb(packed, raw=False)
          
          # Load legacy registries
          self._deserialize_entities_df(save_dict["entities"])
          # ...
          
          # Load skills_df
          skills_df = extract_from_registry_save(save_dict)
          if skills_df is not None:
              self.skills_df = skills_df
              self.use_vectorized_skills = True  # Enable if present
  ```

---

### Phase 4: Combat Bonus Integration (Day 2-3)

- [ ] **4.1** Calculate bonuses in combat system
  ```python
  # In game/systems/combat_system.py
  from game.skills.effects import get_combat_bonuses_dict
  
  def calculate_damage(attacker_id: int, weapon_skill: Skill, base_damage: int) -> int:
      skills = entity_registry.get_skills(attacker_id)
      
      bonuses = get_combat_bonuses_dict(
          fighting=skills.get(Skill.FIGHTING, 0),
          weapon=skills.get(weapon_skill, 0),
          armour=skills.get(Skill.ARMOUR, 0),
          dodging=skills.get(Skill.DODGING, 0),
          shields=skills.get(Skill.SHIELDS, 0),
          base_armor=get_equipped_armor_value(attacker_id),
      )
      
      # Apply multiplier
      final_damage = int(base_damage * bonuses.damage_multiplier)
      return final_damage
  ```

- [ ] **4.2** Apply HP bonus to max_hp
  ```python
  # In entity creation or stat calculation
  def get_max_hp(entity_id: int) -> int:
      base_hp = get_base_hp(entity_id)
      
      if entity_registry.use_vectorized_skills:
          skills = entity_registry.get_skills(entity_id)
          from game.skills.effects import calculate_fighting_hp_bonus
          hp_bonus = calculate_fighting_hp_bonus(
              skills.get(Skill.FIGHTING, 0)
          )
          return base_hp + hp_bonus
      
      return base_hp
  ```

---

### Phase 5: Testing & Validation (Day 3 + Week 1)

- [ ] **5.1** Run parity tests
  ```bash
  pytest game/skills/test_parity.py -v
  ```

- [ ] **5.2** Run performance benchmarks
  ```bash
  pytest game/skills/test_parity.py -v -m benchmark
  ```
  
  **Required Targets**:
  - [ ] Batch XP (100 entities): <10ms
  - [ ] Save/load (10k entities): <100ms
  - [ ] Combat bonuses: >50k ops/sec

- [ ] **5.3** Integration smoke tests
  ```python
  # tests/test_skill_integration.py
  def test_combat_awards_xp():
      """Verify combat system awards XP correctly."""
      registry = EntityRegistry()
      player_id = create_test_player(registry)
      enemy_id = create_test_enemy(registry)
      
      # Combat
      resolve_combat(player_id, enemy_id, ...)
      
      # Verify XP awarded
      skills = registry.get_skills(player_id)
      assert skills[Skill.FIGHTING].xp > 0
  ```

- [ ] **5.4** Load testing with 10k entities
  ```python
  def test_10k_entities_performance():
      registry = EntityRegistry()
      
      # Create 10k entities
      for i in range(10000):
          entity_id = registry.create_entity(...)
          registry.initialize_entity_skills(entity_id)
      
      # Benchmark operations
      # ... (see test_parity.py)
  ```

---

### Phase 6: Migration Cutover (Week 2)

- [ ] **6.1** Enable vectorized mode in dev
  ```python
  # In EntityRegistry.__init__ or config
  self.use_vectorized_skills = True  # Flip the switch
  ```

- [ ] **6.2** Run full game test suite
  ```bash
  pytest tests/ -v
  ```

- [ ] **6.3** Profile for regressions
  ```bash
  python -m cProfile -o profile.stats main.py
  python -m pstats profile.stats
  ```

- [ ] **6.4** Remove legacy code paths (after stable)
  - Remove `entities_df["skills"]` Object column
  - Remove `_sync_skills_to_legacy()` shims
  - Remove `use_vectorized_skills` flag

---

## Concrete Code Examples

### Example 1: Combat System Integration

```python
# game/systems/combat_system.py

from game.skills.effects import get_combat_bonuses_dict
from game.skills.models import Skill
from game.skills.system import award_xp, record_skill_usage

def melee_attack(
    attacker_id: int,
    defender_id: int,
    weapon_skill: Skill,
    registry: EntityRegistry,
) -> int:
    """Execute melee attack with skill bonuses."""
    
    # 1. Get attacker skills
    attacker_skills = registry.get_skills(attacker_id)
    
    # 2. Calculate bonuses
    bonuses = get_combat_bonuses_dict(
        fighting=attacker_skills.get(Skill.FIGHTING, SkillProgress(...)).level,
        weapon=attacker_skills.get(weapon_skill, SkillProgress(...)).level,
        armour=0,  # Not used for attacker
        dodging=0,
        shields=0,
        base_armor=0,
    )
    
    # 3. Roll damage
    base_damage = roll_weapon_damage(weapon_id)
    final_damage = int(base_damage * bonuses.damage_multiplier)
    
    # 4. Apply to defender
    apply_damage(defender_id, final_damage, registry)
    
    # 5. Record skill usage (for automatic mode)
    record_skill_usage(registry, attacker_id, Skill.FIGHTING)
    record_skill_usage(registry, attacker_id, weapon_skill)
    
    # 6. Award XP
    xp_amount = 50  # Per successful hit
    if is_dead(defender_id):
        xp_amount += 100  # Kill bonus
    
    level_ups = award_xp(registry, attacker_id, xp_amount)
    
    # 7. Announce level-ups
    if level_ups:
        for skill, (old_lvl, new_lvl) in level_ups.items():
            announce_level_up(attacker_id, skill, old_lvl, new_lvl)
    
    return final_damage
```

### Example 2: GOAP AI Integration

```python
# game/ai/goap_adapter.py

from game.skills.effects import calculate_total_damage_multiplier
from game.skills.models import Skill

def evaluate_attack_utility(
    entity_id: int,
    target_id: int,
    registry: EntityRegistry,
) -> float:
    """Calculate GOAP utility for attacking target."""
    
    # Get our combat power
    our_skills = registry.get_skills(entity_id)
    our_fighting = our_skills.get(Skill.FIGHTING, SkillProgress(...)).level
    our_weapon = max(
        our_skills.get(Skill.AXES, SkillProgress(...)).level,
        our_skills.get(Skill.LONG_BLADES, SkillProgress(...)).level,
        our_skills.get(Skill.MACES_AND_FLAILS, SkillProgress(...)).level,
    )
    
    our_power = calculate_total_damage_multiplier(our_fighting, our_weapon)
    
    # Get target combat power
    target_skills = registry.get_skills(target_id)
    target_fighting = target_skills.get(Skill.FIGHTING, SkillProgress(...)).level
    target_weapon = max(
        target_skills.get(Skill.AXES, SkillProgress(...)).level,
        target_skills.get(Skill.LONG_BLADES, SkillProgress(...)).level,
    )
    
    target_power = calculate_total_damage_multiplier(target_fighting, target_weapon)
    
    # Utility: ratio of power levels
    # >1.0 = we're stronger, <1.0 = they're stronger
    return our_power / max(target_power, 1.0)
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting Cross-Training

**Problem**: Skills trained but related skills don't level up.

**Solution**: `award_xp()` applies cross-training automatically. No additional calls needed.

### Pitfall 2: Concurrent DataFrame Mutations

**Problem**: Race conditions when multiple threads award XP.

**Solution**: Use `registry._skills_lock` for all write operations. See `CONCURRENCY.md`.

### Pitfall 3: Numba Compilation Lag

**Problem**: First combat action has 200ms spike.

**Solution**: Call `numba_warmup()` at startup. Add to main.py.

### Pitfall 4: Skills Not Saving

**Problem**: Skills reset on load.

**Solution**: Hook `serialize_skills()` into EntityRegistry.save(). See Phase 3.

### Pitfall 5: Wrong Weapon Skill Applied

**Problem**: Damage bonuses don't match equipped weapon.

**Solution**: Pass correct `weapon_skill` parameter to `get_combat_bonuses_dict()`.

---

## Performance Validation Checklist

After integration, verify these metrics:

- [ ] **Startup time**: Numba warmup adds ~200ms
- [ ] **Combat FPS**: No regression vs baseline
- [ ] **Turn processing**: Batch XP awards <10ms for 100 entities
- [ ] **Save time**: <50ms for 10k entities
- [ ] **Load time**: <50ms for 10k entities
- [ ] **Memory usage**: +2MB per 10k entities (acceptable)

---

## Rollback Plan

If issues arise during migration:

1. **Immediate**: Set `use_vectorized_skills = False`
2. **Short-term**: Skills revert to legacy `entities_df["skills"]`
3. **Investigation**: Check parity tests, review logs
4. **Fix**: Address specific issue, re-enable flag
5. **Validation**: Run benchmark suite again

---

## Documentation Updates

After successful integration:

- [ ] Update `SYSTEMS_INVENTORY.md` with skill system entry
- [ ] Add skill system to `README.md` features list
- [ ] Document skill commands in player guide
- [ ] Add skill screen keybindings to `keybindings.toml`

---

## Next Steps After Integration

Once core system is stable:

1. **UI Layer**: Add skill screen (`m` key in DCSS)
2. **Training UI**: Manual mode controls
3. **Skill Milestones**: Special abilities at key levels
4. **Manuals**: Temporary +4 aptitude items
5. **Species Aptitudes**: Different racial bonuses

---

## Support & Troubleshooting

**Questions?** Check:
1. `skills/README.md` - API documentation
2. `skills/CONCURRENCY.md` - Thread safety
3. `skills/test_parity.py` - Integration examples

**Issues?** Verify:
1. Numba warmup called
2. Lock held during writes
3. Parity tests passing
4. Benchmark targets met

---

## Summary

| Component | File | Status |
|-----------|------|--------|
| Data model | `skills/models.py` | ✅ Complete |
| XP formulas | `skills/progression.py` | ✅ Complete |
| Cross-training | `skills/cross_training.py` | ✅ Complete |
| Combat bonuses | `skills/effects.py` | ✅ Complete |
| High-level API | `skills/system.py` | ✅ Complete |
| Registry integration | `skills/registry_integration.py` | ✅ Complete |
| Serialization | `skills/utils.py` | ✅ Complete |
| Tests | `skills/test_*.py` | ✅ Complete |
| Documentation | `skills/*.md` | ✅ Complete |

**Ready for integration**: All components implemented and tested.

**Estimated integration effort**: 2-3 days core work + 1 week validation.

**Risk level**: Low (dual-mode operation, parity tests, rollback plan).
