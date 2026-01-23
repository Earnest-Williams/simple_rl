"""Concurrency and thread safety guidelines for skill system.

CRITICAL: Read this before using skills in multi-threaded contexts.
"""

# Concurrency Guidelines for Skill System

## Overview

The skill system uses **Polars DataFrames** for storage, which have specific concurrency semantics that differ from thread-safe data structures. This document outlines safe usage patterns.

---

## Core Principle: Single-Threaded Writes

**RULE**: All writes to `EntityRegistry.skills_df` must be single-threaded or protected by a registry-level lock.

### Why?

Polars DataFrames are **not thread-safe for mutations**. Concurrent writes can cause:
- Data corruption
- Race conditions
- Undefined behavior

### Safe Patterns

```python
from threading import Lock

class EntityRegistry:
    def __init__(self) -> None:
        self.skills_df: pl.DataFrame = ...
        self._skills_lock: Lock = Lock()
    
    def award_xp(self, entity_id: int, xp: int) -> dict[Skill, tuple[int, int]]:
        """Thread-safe XP award."""
        with self._skills_lock:
            # All skills_df updates happen atomically
            return award_xp(self, entity_id, xp)
```

---

## Read Concurrency

**Reads are safe** without locking due to Polars lazy evaluation:

```python
# SAFE: Multiple threads can read simultaneously
thread_1: skills_a = registry.get_skills(entity_1)
thread_2: skills_b = registry.get_skills(entity_2)

# Each creates independent lazy query
# No shared mutable state
```

### Implementation Detail

```python
def get_skills(self, entity_id: int) -> dict[Skill, SkillProgress]:
    """Safe for concurrent reads."""
    skills_rows = (
        self.skills_df.lazy()  # Creates new lazy frame
        .filter(pl.col("entity_id") == entity_id)
        .collect()  # Materializes independent result
    )
    # ... build dict ...
```

---

## Batch Operations

Batch operations are **preferred** for both performance and concurrency:

```python
# GOOD: Single lock acquisition for batch
with registry._skills_lock:
    batch_award_xp(registry, [
        (entity_1, 100),
        (entity_2, 150),
        (entity_3, 200),
    ])

# BAD: Multiple lock acquisitions
for entity_id, xp in awards:
    with registry._skills_lock:  # Lock thrashing!
        award_xp(registry, entity_id, xp)
```

---

## Polars Atomicity Pattern

Use **lazy evaluation + atomic replacement** for safe updates:

```python
def safe_update_pattern(registry: EntityRegistry) -> None:
    """Atomic DataFrame replacement pattern."""
    with registry._skills_lock:
        # 1. Build update lazily (no mutations)
        updated = (
            registry.skills_df
            .lazy()
            .with_columns([...])  # Transformations
            .collect()  # Materialize new DataFrame
        )
        
        # 2. Atomic replacement
        registry.skills_df = updated  # Single assignment
```

### Why This Works

- Polars `.lazy()` creates immutable query plan
- `.with_columns()` builds transformation pipeline
- `.collect()` materializes **new** DataFrame
- Assignment replaces reference atomically

### Anti-Pattern (Dangerous)

```python
# WRONG: Incremental mutation
registry.skills_df["xp"] = registry.skills_df["xp"] + 100  # Not atomic!
```

---

## Multi-Process Considerations

If using `multiprocessing` or `Ray` for parallel AI:

### Option A: Message Passing

```python
from multiprocessing import Queue

def ai_worker(entity_id: int, result_queue: Queue) -> None:
    """AI decides on action, sends result to main process."""
    action_xp = decide_action(entity_id)
    result_queue.put((entity_id, action_xp))

# Main process collects and awards in batch
results = []
while not result_queue.empty():
    results.append(result_queue.get())

with registry._skills_lock:
    batch_award_xp(registry, results)
```

### Option B: Per-Process Registry (Read-Only)

```python
# Each worker gets read-only snapshot
def ai_worker(skills_snapshot: pl.DataFrame, entity_id: int) -> int:
    """Use immutable snapshot for decision making."""
    my_skills = skills_snapshot.filter(pl.col("entity_id") == entity_id)
    return calculate_action_value(my_skills)

# Main process owns mutable registry
with registry._skills_lock:
    snapshot = registry.skills_df.clone()

with multiprocessing.Pool() as pool:
    results = pool.starmap(ai_worker, [(snapshot, eid) for eid in entities])
```

---

## Game Loop Integration

Simple_rl uses parallel AI via Ray. Recommended pattern:

```python
class GameState:
    def __init__(self) -> None:
        self.registry: EntityRegistry = EntityRegistry()
        self.registry._skills_lock = Lock()
    
    def turn_sequence(self) -> None:
        """Single-threaded turn processing."""
        
        # 1. Parallel AI decisions (read-only)
        ai_actions = self.ai_system.decide_all_actions()
        
        # 2. Execute actions (generates XP awards)
        xp_awards: list[tuple[int, int]] = []
        for action in ai_actions:
            result = self.execute_action(action)
            xp_awards.append((action.entity_id, result.xp_gained))
        
        # 3. Batch award XP (single lock)
        with self.registry._skills_lock:
            batch_award_xp(self.registry, xp_awards)
```

---

## Numba Thread Safety

Numba-compiled functions are **thread-safe** for pure computation:

```python
# SAFE: Multiple threads calling Numba function
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(
        calculate_combat_bonuses,
        fighting_levels,
        weapon_levels,
        ...
    ))
```

However, **avoid** calling Numba functions during first compilation from multiple threads (race condition in JIT compiler).

**Solution**: Call `numba_warmup()` during startup before spawning threads.

---

## Save/Load Concurrency

Save and load operations must be **exclusive**:

```python
class EntityRegistry:
    def save(self, path: Path) -> None:
        """Acquire lock for duration of save."""
        with self._skills_lock:
            # Serialize entire DataFrame atomically
            data = serialize_skills(self.skills_df)
            path.write_bytes(data)
    
    def load(self, path: Path) -> None:
        """Acquire lock for load."""
        with self._skills_lock:
            data = path.read_bytes()
            self.skills_df = deserialize_skills(data)
```

---

## Performance Impact

### Lock Contention

If profiling shows lock contention:

1. **Increase batch sizes** - Fewer lock acquisitions
2. **Reader-writer lock** - Multiple readers, single writer
3. **Per-entity sharding** - Partition skills_df by entity_id range

### Example: RW Lock

```python
from threading import RLock

class EntityRegistry:
    def __init__(self) -> None:
        self._skills_rw_lock = RWLock()  # Custom implementation
    
    def get_skills(self, entity_id: int) -> dict[Skill, SkillProgress]:
        with self._skills_rw_lock.read():
            # Multiple readers allowed
            return self._get_skills_impl(entity_id)
    
    def award_xp(self, entity_id: int, xp: int) -> ...:
        with self._skills_rw_lock.write():
            # Exclusive writer
            return award_xp(self, entity_id, xp)
```

---

## Testing Concurrency

Use `pytest-xdist` for parallel test execution:

```python
# test_concurrency.py

import pytest
from concurrent.futures import ThreadPoolExecutor

def test_concurrent_reads(registry: EntityRegistry) -> None:
    """Verify reads don't interfere."""
    
    def read_skills(entity_id: int) -> dict[Skill, SkillProgress]:
        return registry.get_skills(entity_id)
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(read_skills, i) for i in range(100)]
        results = [f.result() for f in futures]
    
    # All reads should succeed
    assert len(results) == 100

def test_sequential_writes(registry: EntityRegistry) -> None:
    """Verify writes are atomic."""
    
    # Award XP to same entity from multiple threads
    # Should result in deterministic total
    
    entity_id = 1
    awards = [(entity_id, 100) for _ in range(10)]
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(registry.award_xp, eid, xp)
            for eid, xp in awards
        ]
        [f.result() for f in futures]
    
    # Total should be 1000 XP distributed
    # (exact distribution depends on training mode)
```

---

## Summary

| Operation | Thread Safety | Recommendation |
|-----------|---------------|----------------|
| `get_skills()` | ✅ Safe | Read freely |
| `award_xp()` | ⚠️ Needs lock | Use `_skills_lock` |
| `batch_award_xp()` | ⚠️ Needs lock | Preferred for multiple updates |
| Numba functions | ✅ Safe (after warmup) | Warmup at startup |
| Save/Load | ⚠️ Exclusive | Acquire lock |
| DataFrame replacement | ✅ Atomic | Use lazy + collect pattern |

**Golden Rule**: Treat `skills_df` as append-only log during turn processing, batch all mutations at turn boundaries.
