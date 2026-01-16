# Simple RL - Systems Inventory

**Date:** 2026-01-16
**Purpose:** Comprehensive inventory of all systems in the merged codebase

---

## PRIMARY COMPONENT: 3D Dungeon Generator

### Overview
The most important and sophisticated component - generates 3D cave networks and converts them to 2D rasters with full 3D properties preserved.

### Files
- **Core Generation:** `Dungeon/core.py` - CaveGenerator class
- **Geometry Processing:** `Dungeon/processor.py` - process_backbone_graph()
- **Rasterization:** `Dungeon/shaper.py` - Grid conversion and refinement

### Pipeline
1. **Backbone Generation** (core.py)
   - Probabilistic cave network using node-based backbone graph
   - KDTree spatial indexing for convergence detection
   - Supports 1, 2, and 3-way branching with momentum bias
   - Features: cliff edges, shaft openings, big rooms

2. **Geometry Processing** (processor.py)
   - Calculates segment geometry: length_xy, incline_rate, delta_depth_m
   - Preserves feature flags
   - Augments nodes with geometric properties

3. **Rasterization** (shaper.py)
   - Converts 3D backbone to 2D grid (1.0m per cell resolution)
   - Generates: grid, depth_grid, type_grid arrays
   - Material types: solid rock, cave floor, shaft opening, cliff edge

4. **Refinement** (shaper.py)
   - Cellular automata smoothing (8 iterations default)
   - Conway-like rules optimized with SciPy/Numba
   - Birth threshold: 5 non-solid neighbors
   - Survival threshold: 4 non-solid neighbors

5. **Output Format**
   - Polars DataFrame with columns:
     - x, y (2D coordinates)
     - floor_depth, height, ceiling_depth (3D properties)
     - material_id, walkable, chamber_id
     - open_above (shaft/vertical connectivity)

### 3D Properties Preserved
- **Depth in meters** - Z-axis position (4-6m typical per level)
- **Height/ceiling depths** - Variable ceiling heights (2-8m)
- **Incline rates** - Slope calculations from depth deltas
- **Cliff edges** - Vertical drop features
- **Shaft openings** - Vertical connectivity between levels

---

## MOST SOPHISTICATED SYSTEMS (RETAIN THESE)

### 1. Sound/Smell Flow Pathfinding System ⭐⭐⭐⭐⭐

**Location:** `pathfinding/perception_systems.py`

**Sophistication Level:** Very High

**Features:**
- BFS-based flow field computation
- Multiple flow field types:
  - PASS_DOORS - Monster pathfinding through doors
  - NO_DOORS - Blocked by closed doors
  - REAL_NOISE - Environmental noise with dampening
  - MONSTER_NOISE - Creature-generated noise
- Sophisticated decay models:
  - Scent: 90% decay per frame
  - Noise: 60% decay per frame
- Radial falloff with distance
- Numba-accelerated propagation
- Joblib parallelization support

**Configuration:**
- BASE_FLOW_CENTER: 100
- NOISE_STRENGTH: 80
- SCENT_RESET_AGE: 250

**Use Case:** AI perception and tracking through environmental cues

---

### 2. AI Systems ⭐⭐⭐⭐⭐

**Location:** `game/ai/`

**Sophistication Level:** Very High

**Implementations:**

1. **GOAP System** (`goap.py`)
   - Goal-Oriented Action Planning
   - State preconditions/effects
   - Priority-weighted action selection
   - World state tracking

2. **ML Policy** (`ml_policy.py`)
   - Machine learning-based decision making
   - Neural network action selection

3. **Strategy System** (`strategy.py`)
   - State machine: HOME, CHARGE, SMART_KOBOLD, FLEE
   - Behavior dispatch based on perception
   - Integration with noise/scent/LOS

4. **Specialized Behaviors:**
   - `bird.py` - Flying creature behavior
   - `mammal.py` - Land creature behavior
   - `insect.py` - Small creature behavior
   - `plant.py` - Static/rooted entities
   - `reptile.py` - Cold-blooded behavior
   - `community.py` - Group behaviors

---

### 3. GameRNG System ⭐⭐⭐⭐⭐

**Location:** `game_rng.py`

**Sophistication Level:** Very High

**Features:**
- Deterministic PRNG using numpy.random.default_rng
- Seeded initialization for reproducibility
- Comprehensive distributions:
  - Uniform (integers, floats)
  - Bell curve (normal)
  - Triangle distribution
  - Power distribution (configurable exponent)
  - Exponential distribution (configurable lambda)
- Weighted choice with CDF caching
- Weighted sampling (ARES algorithm)
- Dice rolling (NdM+modifier)
- Noise generation (1D and 2D)
- Loot table generation
- State save/load

**Advanced Features:**
- Metrics collection (background thread)
- Operation counts tracking
- Cache hit/miss rates
- Operations per second monitoring
- Thread-safe queue-based updates

**Use Case:** All randomness in game - generation, combat, AI, effects

---

### 4. FOV/Visibility Systems ⭐⭐⭐⭐⭐

**Locations:**
- `game/world/fov.py` - Iterative shadowcasting
- `game/world/visibility.py` - Symmetrical shadowcasting
- `game/world/los.py` - Line of sight

**Sophistication Level:** Very High

**Features:**

1. **Iterative Shadowcasting** (fov.py)
   - 8-directional symmetrical variant
   - Slope-based blocking calculations
   - Numba-accelerated
   - Variable FOV radius
   - Close-range and far-range distance adjustments

2. **Symmetrical Shadowcasting** (visibility.py)
   - Generic callback architecture
   - Custom blocking/visibility callbacks
   - Transformation coefficients for 8 octants
   - Recursive light casting

3. **Line of Sight** (los.py)
   - Bresenham-style rasterization
   - Fast 2D line tracing

**Use Case:** Player vision, AI perception, lighting calculations

---

### 5. Flow Field Pathfinding ⭐⭐⭐⭐

**Location:** `game/systems/pathfinding/flowfield.py`

**Sophistication Level:** High

**Features:**
- Dijkstra's algorithm for integration fields
- Flow vector calculation (8-directional)
- Height-based movement costs (0.5x multiplier)
- Diagonal movement: sqrt(2) ≈ 1.414
- Numba-accelerated core algorithms
- Efficient priority queue (heapq)
- Memory-efficient flow vectors (int8)

**Use Case:** AI pathfinding, monster movement

---

### 6. Lighting System ⭐⭐⭐⭐

**Location:** `engine/render_lighting.py`

**Sophistication Level:** Medium-High

**Features:**
- Distance-squared based falloff
- Numba-accelerated intensity computation
- Configurable ambient lighting
- Intensity interpolation for smooth gradients
- Memory fade effects (fog of war)
- Height-based lighting visualization

**Algorithm:**
```
intensity = max(0, (1 - distance/radius)^falloff_power)
```

**Configuration:**
- Ambient light level
- FOV radius (squared)
- Falloff power (curve control)
- Minimum light level

**Use Case:** Visual rendering, atmospheric effects

---

### 7. Magic/Effects System ⭐⭐⭐⭐

**Locations:**
- `magic/` - Magical work system
- `game/effects/` - Effect execution

**Sophistication Level:** High

**Features:**

1. **Magical Work System** (magic/)
   - Work execution framework
   - Ward/Counterseal blocking
   - Friction event system (quiver, warp, shiver, backlash)
   - Art/Substance pair-based spells
   - Work parser for spell definitions

2. **Effect System** (game/effects/)
   - Context-based targeting
   - Cost checking (mana, fullness, charges)
   - Status application (buffs/debuffs)
   - Effect handler registry
   - Passive effects
   - Cooldown management

**Use Case:** Spell casting, magical effects, status effects

---

### 8. Entity/Component System ⭐⭐⭐⭐

**Location:** `game/entities/`

**Sophistication Level:** High

**Features:**
- Registry-based entity management
- Component-based architecture (ECS-like)
- Template spawning from YAML
- Polars DataFrame storage
- Static and dynamic attributes
- Status effect integration

**Files:**
- `registry.py` - Main entity registry
- `template_registry.py` - Template definitions
- `components.py` - Component definitions

**Use Case:** All game entities (player, monsters, items)

---

### 9. Rendering System ⭐⭐⭐⭐

**Locations:**
- `engine/renderer.py` - Main rendering
- `engine/render_base_layers.py` - Tile layers
- `engine/render_entities.py` - Entity sprites
- `engine/window_manager.py` - SDL2/Pygame window

**Sophistication Level:** High

**Render Pipeline:**
1. Prepare base tile layers
2. Pack ground items
3. Pack entity sprites
4. Apply lighting effects
5. Apply height visualization (optional)
6. Apply memory fade (optional)

**Features:**
- Tile-based rendering to PIL Image
- Viewport management with scrolling
- Multi-layer composition
- Configuration-driven pipeline

**Use Case:** Visual output

---

### 10. Game Mechanics Systems ⭐⭐⭐

**Location:** `game/systems/`

**Sophistication Level:** Medium-High

**Systems:**
- **Combat** (`combat_system.py`) - Melee, weapons, hit calculations
- **Movement** (`movement_system.py`) - Collision, displacement, walkability
- **Equipment** (`equipment_system.py`) - Slots, stat bonuses, encumbrance
- **Death** (`death_system.py`) - Loot dropping, corpse management
- **AI Scheduler** (`ai_system.py`) - Parallel action execution

**Architecture:** Component-based, well-separated concerns

**Use Case:** Core game loop mechanics

---

## DUPLICATE SYSTEMS (CLEANUP CANDIDATES)

### Dungeon Generator Duplicates

1. ✅ **KEEP:** `Dungeon/core.py` + `Dungeon/processor.py` + `Dungeon/shaper.py`
   - **Reason:** Most sophisticated, 3D properties, complete pipeline

2. ❌ **REMOVE:** `dungeon_generator.py`
   - **Type:** Simple BSP with room placement
   - **Reason:** Less sophisticated than 3D variant

3. ❌ **REMOVE:** `lights_dev/dungeon_generator.py`
   - **Type:** Copy of BSP variant
   - **Reason:** Duplicate of #2

4. ❌ **REMOVE:** `prototypes/lights_dev/dungeon_generator.py`
   - **Type:** Prototype/experimental
   - **Reason:** Old prototype

5. ❌ **REMOVE:** `prototypes/Dungeon/core.py` and `prototypes/Dungeon/shaper.py`
   - **Type:** Old prototype of main system
   - **Reason:** Superseded by production version

---

## ADDITIONAL SYSTEMS (MEDIUM COMPLEXITY)

### Cellular Automata System
- **Location:** `Dungeon/shaper.py`
- **Use:** Cave passage smoothing
- **Algorithm:** Symmetrical 2D CA with Conway-like rules
- **Optimization:** SciPy convolution with Numba fallback

### Sound System
- **Location:** `game/systems/sound.py`
- **Features:** YAML config, distance falloff, multi-backend (pyopenal, pygame, simpleaudio)
- **Use:** Audio effects and background music

### Game State Management
- **Location:** `game/game_state.py`
- **Purpose:** Central orchestration
- **Manages:** Entities, items, map, turns, FOV, perception events

### Game Map System
- **Location:** `game/world/game_map.py`
- **Features:** Tiles, depth/height, walkability, chambers, visibility, noise/scent layers

---

## ARCHITECTURE OVERVIEW

### Core Technologies
- **Data:** Polars DataFrames (entities, items, map)
- **Performance:** Numba JIT (FOV, lighting, pathfinding, perception)
- **Logging:** Structlog (comprehensive logging)
- **Randomness:** NumPy default_rng (deterministic, reproducible)

### Integration Points
- GameRNG used throughout all systems
- Entity/Component system interfaces with all game mechanics
- Flow fields connect AI → Pathfinding → Movement
- Perception systems feed AI decision making
- Rendering pipeline consumes all game state

### Unique Strengths
1. **3D dungeon generation** with probabilistic branching and convergence detection
2. **Multi-layer perception** combining noise, scent, and line-of-sight
3. **Flexible AI** supporting FSM, GOAP, and ML approaches
4. **Comprehensive RNG** with metrics and noise generation
5. **Sophisticated pathfinding** with flow fields and perception integration

---

## STATISTICS

- **Total Lines:** ~18,400
- **Python Files:** 60+
- **Primary Systems:** 16
- **Very High Sophistication Systems:** 4
- **High Sophistication Systems:** 5
- **Duplicate Systems Found:** 5

---

## RECOMMENDATIONS

### Priority 1: Organize Core Systems
1. Keep all "Very High" and "High" sophistication systems
2. Remove duplicate dungeon generators (keep `Dungeon/`)
3. Consolidate prototypes folder (archive or delete old versions)

### Priority 2: Documentation
1. Document 3D → 2D conversion pipeline
2. Create integration guide for perception → AI → pathfinding
3. Document RNG system usage patterns

### Priority 3: Testing
1. Add tests for 3D dungeon generator
2. Test perception flow fields with different configurations
3. Validate AI GOAP planner

### Priority 4: Performance
1. Profile Numba-accelerated functions
2. Optimize Polars DataFrame operations
3. Cache expensive calculations (already doing CDF caching in RNG)

---

## CONCLUSION

This is a sophisticated, production-quality roguelike engine with exceptional implementations of:
- 3D procedural generation
- Multi-sensory AI perception
- Advanced pathfinding algorithms
- Flexible AI architectures
- Comprehensive game systems

The codebase shows evidence of multiple merged projects with some duplication that can be cleaned up while preserving the most sophisticated implementations.
