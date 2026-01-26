# Memory Fade System Documentation

## Overview

The Memory Fade System is a sophisticated visual memory simulation for roguelike
games. It models how a player character's recollection of explored areas
gradually degrades over time, creating a more immersive and realistic fog-of-war
experience.

Rather than the traditional binary "explored/unexplored" approach, this system
provides a continuous decay from vivid recall to complete forgetting, with the
rate of decay influenced by agent traits like intelligence, conditions, and
magical effects.

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Mathematical Model](#mathematical-model)
3. [Trait Modifiers](#trait-modifiers)
4. [Performance Optimizations](#performance-optimizations)
5. [API Reference](#api-reference)
6. [Integration Guide](#integration-guide)
7. [Configuration Reference](#configuration-reference)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Core Concepts

### Memory Intensity

Each tile on the map has a **memory intensity** value ranging from 0.0 to 1.0:

| Intensity | Meaning                              |
|-----------|--------------------------------------|
| 1.0       | Just seen / perfect recall           |
| 0.8       | Recent memory, clear details         |
| 0.5       | Fading memory, some details lost     |
| 0.2       | Vague memory, mostly forgotten       |
| 0.0       | Completely forgotten / never seen    |

### Decay Levels

Memory intensity maps to **5 visual decay levels** for rendering:

| Level | Intensity Range | Wall Char | Floor Char | Description      |
|-------|-----------------|-----------|------------|------------------|
| 0     | 0.8 - 1.0       | ▓         | .          | Fresh memory     |
| 1     | 0.6 - 0.8       | ▒         | ·          | Clear memory     |
| 2     | 0.4 - 0.6       | ░         | ⋅          | Fading memory    |
| 3     | 0.2 - 0.4       | ⋅         | (space)    | Vague memory     |
| 4     | 0.0 - 0.2       | (space)   | (space)    | Almost forgotten |

### Time Tracking

The system tracks two time values per tile:

- **last_seen_time**: When the tile was last within the player's field of view
- **current_time**: The global simulation clock

The difference (elapsed time) determines how much the memory has decayed.

---

## Mathematical Model

### Sigmoid Decay Function

Memory decay follows a **sigmoid (logistic) function**:

```
intensity = 1 / (1 + e^(steepness × (elapsed - midpoint)))
```

Where:
- `elapsed` = current_time - last_seen_time
- `steepness` = controls how sharp the transition is
- `midpoint` = when intensity reaches 0.5

### Why Sigmoid?

The sigmoid provides psychologically realistic memory decay:

1. **Initial Plateau**: Memory stays strong for a while after seeing something
2. **Rapid Middle Decay**: Active forgetting happens relatively quickly
3. **Slow Final Fade**: Last traces of memory linger before complete loss

```
Intensity
    1.0 |████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    0.8 |                ░░░░████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
    0.6 |                        ░░░░████░░░░░░░░░░░░░░░░░░░░░░░
    0.4 |                                ░░░░████░░░░░░░░░░░░░░░
    0.2 |                                        ░░░░████░░░░░░░
    0.0 |________________________________________________████████
        0    10   20   30   40   50   60   70   80   90  100
                            Time (seconds)
```

### Base Parameters

| Parameter           | Value   | Description                          |
|---------------------|---------|--------------------------------------|
| BASE_MEMORY_DURATION| 90.0    | Time for near-complete fade          |
| BASE_SIGMOID_MIDPOINT| 45.0   | Time when intensity = 0.5            |
| BASE_SIGMOID_STEEPNESS| 0.056 | Rate of transition (gentler curve)   |

---

## Trait Modifiers

The decay rate can be modified by agent traits, allowing for gameplay
differentiation between characters.

### Available Traits

#### Intelligence (1-30, base 10)

Higher intelligence means better memory retention.

```
Modifier = BASE_INT / current_intelligence

Examples:
- INT 5:  modifier = 2.0  (2x faster decay, memories last half as long)
- INT 10: modifier = 1.0  (base decay rate)
- INT 15: modifier = 0.67 (33% slower decay)
- INT 20: modifier = 0.5  (memories last twice as long)
```

#### Confusion (boolean)

When confused or disoriented, memory decays twice as fast.

```python
if has_confusion:
    modifier *= 2.0
```

#### Illness (boolean)

Fever, poison, or other illness increases decay by 50%.

```python
if has_illness:
    modifier *= 1.5
```

#### Fatigue Level (0.0 - 1.0)

Tiredness impairs memory formation and retention.

```
modifier *= 1.0 + (fatigue × 0.5)

Examples:
- fatigue 0.0 (rested):    modifier *= 1.0
- fatigue 0.5 (tired):     modifier *= 1.25
- fatigue 1.0 (exhausted): modifier *= 1.5
```

#### Magic Memory Bonus (0.0 - 10.0)

Magical enhancement to memory (spells, potions, artifacts).

```
modifier /= (1.0 + magic_memory_bonus)

Examples:
- bonus 0.5: modifier /= 1.5 (33% slower decay)
- bonus 1.0: modifier /= 2.0 (50% slower decay)
- bonus 2.0: modifier /= 3.0 (67% slower decay)
```

#### Location Familiarity (0.0 - 1.0)

Familiar areas are remembered better (home base, frequently visited).

```
modifier *= 1.0 - (familiarity × 0.5)

Examples:
- familiarity 0.0 (unknown):  modifier *= 1.0
- familiarity 0.5 (visited):  modifier *= 0.75
- familiarity 1.0 (home):     modifier *= 0.5
```

### Combined Modifier Calculation

All modifiers combine multiplicatively:

```python
def compute_decay_modifier(traits):
    modifier = 1.0
    modifier *= BASE_INTELLIGENCE / traits.intelligence
    if traits.has_confusion:
        modifier *= 2.0
    if traits.has_illness:
        modifier *= 1.5
    modifier *= 1.0 + (traits.fatigue_level * 0.5)
    modifier /= 1.0 + traits.magic_memory_bonus
    modifier *= 1.0 - (traits.location_familiarity * 0.5)
    return max(0.01, modifier)  # Minimum bound
```

### Effect on Parameters

The combined modifier adjusts the sigmoid parameters:

```python
effective_steepness = BASE_STEEPNESS × modifier
effective_midpoint = BASE_MIDPOINT / modifier
```

Higher modifier = faster decay (steeper curve, earlier midpoint)

### Example Scenarios

| Scenario                        | Modifier | Effective Duration |
|---------------------------------|----------|-------------------|
| Average character               | 1.0      | 90 seconds        |
| Genius wizard (INT 20)          | 0.5      | 180 seconds       |
| Sick, confused fighter (INT 8)  | 3.75     | 24 seconds        |
| Ranger in home forest           | 0.5      | 180 seconds       |
| Exhausted, poisoned thief       | 2.25     | 40 seconds        |

---

## Performance Optimizations

### 1. Vectorized Numba Execution

The core update loop uses Numba's `@jit(nopython=True, parallel=True)`
decorator for SIMD and multi-threaded execution.

```python
@numba.jit(nopython=True, parallel=True, cache=True)
def _update_memory_vectorized(...):
    for y in numba.prange(height):  # Parallel over rows
        for x in range(width):
            # ... decay logic
```

**Performance**: ~10-50x faster than pure Python for large maps.

### 2. Sparse Tile Tracking

Only tiles that need updating are processed:

```python
# Skip if already forgotten or currently visible
if intensity <= min_threshold or visible[y, x]:
    continue
```

On a 200×200 map where only 5% of tiles have active memory:
- Naive: 40,000 iterations
- Sparse: ~2,000 iterations

### 3. Quantized Batch Updates

Memory doesn't need per-frame precision. The system supports:

- **Update Interval**: Only process decay every N milliseconds
- **Batch Count**: Split map into N horizontal slices, process one per frame

```python
# Process one quarter of the map per frame
system = MemorySystem(width=200, height=200, batch_count=4)
```

### 4. JIT-Compiled Character Lookup

Character indices are computed in Numba, returning integers rather than
strings. The actual character lookup happens once at render time.

```python
# Returns int8 array: -1 (visible), -2 (unseen), 0-4 (decay level)
indices = _compute_character_indices(tiles, intensity, visible, 5)
```

### 5. Cached Parameters

Sigmoid parameters are pre-computed when traits change, not every frame:

```python
def set_traits(self, traits):
    self.traits = traits
    self._update_cached_parameters()  # Compute once
```

---

## API Reference

### MemoryTraits

Dataclass for agent trait configuration.

```python
@dataclass(frozen=True, slots=True)
class MemoryTraits:
    intelligence: int = 10         # 1-30
    has_confusion: bool = False
    has_illness: bool = False
    fatigue_level: float = 0.0     # 0.0-1.0
    magic_memory_bonus: float = 0.0 # 0.0-10.0
    location_familiarity: float = 0.0  # 0.0-1.0
```

**Methods:**

- `compute_decay_modifier() -> float`: Get combined decay rate modifier
- `get_effective_parameters() -> tuple[float, float]`: Get (steepness, midpoint)

### MemorySystem

Main memory management class.

```python
@dataclass
class MemorySystem:
    width: int
    height: int
    traits: MemoryTraits = MemoryTraits()
    update_interval: float = 0.1   # Seconds between updates
    batch_count: int = 0           # 0 = no batching
```

**Core Methods:**

| Method | Description |
|--------|-------------|
| `update(dt, visible, force=False)` | Update memory state for one frame |
| `set_traits(traits)` | Update agent traits |
| `reset()` | Clear all memory state |

**Query Methods:**

| Method | Description |
|--------|-------------|
| `get_intensity(x, y)` | Get memory intensity at location |
| `get_intensity_array()` | Get full intensity array (read-only) |
| `get_active_tile_count()` | Count non-forgotten tiles |

**Rendering Methods:**

| Method | Description |
|--------|-------------|
| `get_character_indices(tile_ids)` | Compute render indices |
| `get_character_indices_with_visible(tiles, visible)` | With explicit visibility |
| `get_memory_character(tile_id, index)` | Get display character |

**Utility Methods:**

| Method | Description |
|--------|-------------|
| `clear_tile(x, y)` | Force-forget a tile |
| `refresh_tile(x, y)` | Force-remember a tile |

**Properties:**

| Property | Description |
|----------|-------------|
| `current_time` | Current simulation time |
| `effective_duration` | Memory duration after traits |
| `effective_steepness` | Sigmoid steepness after traits |
| `effective_midpoint` | Sigmoid midpoint after traits |

### Factory Functions

```python
def create_memory_system(
    width: int,
    height: int,
    intelligence: int = 10,
    update_interval: float = 0.1,
    batch_count: int = 0,
) -> MemorySystem
```

```python
def get_memory_level_characters(tile_id: int) -> tuple[str, ...]
```

---

## Integration Guide

### Basic Integration

```python
from memory import MemorySystem, MemoryTraits

# 1. Create system at game start
memory = MemorySystem(width=dungeon.width, height=dungeon.height)

# 2. Each frame in game loop:
def update(dt: float):
    # Compute FOV
    visible = compute_fov(player_pos, dungeon)

    # Update memory
    refreshed, decayed = memory.update(dt, visible)

# 3. During rendering:
def render():
    indices = memory.get_character_indices_with_visible(
        dungeon.tiles, fov_visible
    )

    for y in range(height):
        for x in range(width):
            idx = indices[y, x]
            if idx == -1:
                # Currently visible - render normally
                render_visible_tile(x, y)
            elif idx == -2:
                # Unseen - render nothing
                pass
            else:
                # Memory - render faded
                char = memory.get_memory_character(tiles[y, x], idx)
                render_memory_tile(x, y, char)
```

### Integration with Trait System

```python
# When player stats change:
def on_player_stats_changed(player):
    traits = MemoryTraits(
        intelligence=player.intelligence,
        has_confusion=player.has_status("confused"),
        has_illness=player.has_status("poisoned") or player.has_status("sick"),
        fatigue_level=player.fatigue / player.max_fatigue,
        magic_memory_bonus=player.get_equipment_bonus("memory"),
        location_familiarity=world.get_familiarity(player.current_zone),
    )
    memory_system.set_traits(traits)
```

### Integration with Save/Load

```python
def save_game(game_state):
    # Save memory arrays
    np.save("memory_intensity.npy", memory._memory_intensity)
    np.save("memory_last_seen.npy", memory._last_seen_time)
    save_float("memory_time", memory._current_time)

def load_game(game_state):
    memory._memory_intensity = np.load("memory_intensity.npy")
    memory._last_seen_time = np.load("memory_last_seen.npy")
    memory._current_time = load_float("memory_time")
```

### Integration with Map Changes

When the map changes (doors open, walls destroyed):

```python
def on_tile_revealed(x, y):
    # Tile was hidden, now accessible - clear stale memory
    memory.clear_tile(x, y)

def on_magical_reveal(area):
    # Clairvoyance spell - instant memory of area
    for x, y in area:
        memory.refresh_tile(x, y)
```

---

## Configuration Reference

### Constants

| Constant | Default | Description |
|----------|---------|-------------|
| `BASE_MEMORY_DURATION` | 90.0 | Base time for full fade (seconds) |
| `BASE_SIGMOID_MIDPOINT` | 45.0 | Time when intensity = 0.5 |
| `BASE_SIGMOID_STEEPNESS` | 0.056 | Curve sharpness |
| `MEMORY_LEVEL_COUNT` | 5 | Number of visual decay levels |
| `MIN_INTENSITY_THRESHOLD` | 0.001 | Below this = forgotten |
| `DEFAULT_UPDATE_INTERVAL` | 0.1 | Seconds between decay updates |

### Character Arrays

```python
MEMORY_WALL_CHARS   = ("▓", "▒", "░", "⋅", " ")
MEMORY_PILLAR_CHARS = ("▤", "▥", "▫", "◦", " ")
MEMORY_FLOOR_CHARS  = (".", "·", "⋅", " ", " ")
MEMORY_LIGHT_CHAR   = "+"
UNSEEN_CHAR         = " "
```

### Tile IDs

```python
TILE_WALL   = 0
TILE_FLOOR  = 1
TILE_PILLAR = 2
```

---

## Examples

### Example 1: Basic Usage

```python
from memory import MemorySystem
import numpy as np

# Create 50x50 dungeon with memory system
memory = MemorySystem(width=50, height=50)

# Simulate player seeing some tiles
visible = np.zeros((50, 50), dtype=np.bool_)
visible[20:30, 20:30] = True  # 10x10 visible area

# First update - tiles become remembered
memory.update(0.016, visible)
print(f"Active tiles: {memory.get_active_tile_count()}")  # 100

# Move player away
visible.fill(False)
visible[40:45, 40:45] = True  # New location

# After 45 seconds of game time
for _ in range(2700):  # 2700 frames at 60fps = 45 seconds
    memory.update(0.016, visible)

# Check old location
print(f"Old area intensity: {memory.get_intensity(25, 25)}")  # ~0.5
```

### Example 2: Character with Traits

```python
from memory import MemorySystem, MemoryTraits

# Brilliant wizard with memory enhancement
wizard_traits = MemoryTraits(
    intelligence=18,
    magic_memory_bonus=1.0,  # +100% duration from enchantment
)
wizard_memory = MemorySystem(100, 100, traits=wizard_traits)
print(f"Wizard memory duration: {wizard_memory.effective_duration:.1f}s")
# Output: ~324 seconds (3.6x base)

# Confused, sick goblin
goblin_traits = MemoryTraits(
    intelligence=6,
    has_confusion=True,
    has_illness=True,
)
goblin_memory = MemorySystem(100, 100, traits=goblin_traits)
print(f"Goblin memory duration: {goblin_memory.effective_duration:.1f}s")
# Output: ~18 seconds (0.2x base)
```

### Example 3: Performance Tuning

```python
from memory import MemorySystem

# Large map with batched updates for smooth frame times
big_map_memory = MemorySystem(
    width=500,
    height=500,
    update_interval=0.2,  # Update every 200ms
    batch_count=8,        # Process 1/8 of map per update
)

# Each update only processes ~31,250 tiles maximum
# Spread across 8 frames = ~3,906 tiles per frame
```

### Example 4: Debug Rendering

```python
def render_memory_debug(memory: MemorySystem, tiles: np.ndarray):
    """Render memory intensities as numbers for debugging."""
    indices = memory.get_character_indices(tiles)

    for y in range(memory.height):
        row = []
        for x in range(memory.width):
            intensity = memory.get_intensity(x, y)
            if intensity > 0:
                row.append(f"{intensity:.1f}")
            else:
                row.append("   ")
        print(" ".join(row))
```

---

## Troubleshooting

### Memory Not Decaying

**Symptom**: Tiles stay at full intensity forever.

**Causes**:
1. Not calling `update()` each frame
2. Tiles are always in `visible` array
3. `dt` parameter is 0 or very small

**Solution**:
```python
# Ensure dt accumulates real time
memory.update(actual_delta_time, visible)
```

### Performance Issues

**Symptom**: Frame rate drops during memory updates.

**Solutions**:
1. Enable batching: `batch_count=4`
2. Increase update interval: `update_interval=0.2`
3. Check Numba compilation: first call is slow (JIT compilation)

### Incorrect Character Display

**Symptom**: Wrong characters shown for memory tiles.

**Causes**:
1. Tile IDs don't match constants (TILE_WALL=0, TILE_FLOOR=1, TILE_PILLAR=2)
2. Using wrong method for getting characters

**Solution**:
```python
# Ensure tile IDs match
assert dungeon.WALL_ID == memory.TILE_WALL
```

### Memory Resets Unexpectedly

**Symptom**: Memory disappears when it shouldn't.

**Causes**:
1. `reset()` called unintentionally
2. New MemorySystem created (arrays not preserved)
3. Map dimensions changed

**Solution**: Preserve memory system instance across level transitions or
implement save/load for memory arrays.

---

## Version History

| Version | Changes |
|---------|---------|
| 1.0.0   | Initial implementation with trait modifiers |
| -       | Vectorized Numba updates |
| -       | Batch processing support |
| -       | Slowed base decay (60s → 90s) |

---

## See Also

- `lights_dev/README.md` - Overall lighting/FOV system documentation
- `lights_dev/fov.py` - Field of view implementation
- `lights_dev/constants.py` - Shared constants for rendering
