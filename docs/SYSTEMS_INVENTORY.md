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

**Location:** `utils/game_rng.py`

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
- `game/world/fov.py` - Production FOV and callback-driven symmetrical shadowcasting
- `game/world/los.py` - Line of sight

**Sophistication Level:** Very High

**Features:**

1. **Iterative Shadowcasting** (fov.py)
   - 8-directional symmetrical variant
   - Slope-based blocking calculations
   - Numba-accelerated
   - Variable FOV radius
   - Close-range and far-range distance adjustments

2. **Callback Symmetrical Shadowcasting** (fov.py)
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

2. ✅ **CURRENT:** No duplicate `legacy/` or `prototypes/` dungeon generator files are present in the current tree.
   - **Reason:** `Dungeon/core.py`, `Dungeon/processor.py`, and `Dungeon/shaper.py` are the canonical pipeline.

---

## ADDITIONAL SYSTEMS (MEDIUM COMPLEXITY)

### Cellular Automata System
- **Location:** `Dungeon/shaper.py`
- **Use:** Cave passage smoothing
- **Algorithm:** Symmetrical 2D CA with Conway-like rules
- **Optimization:** SciPy convolution with Numba fallback

### Sound System
- **Location:** `game/systems/sound.py`
- **Features:** YAML config, distance falloff, SDL_mixer backend
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
- **Very High Sophistication Systems:** 4 (Perception, AI, GameRNG, FOV/Visibility)
- **High Sophistication Systems:** 5 (Flow Field, Lighting, Magic/Effects, Entity/Component, Rendering)
- **Fully Integrated Systems:** 16+
- **R&D Systems (Not Integrated):** 2 (Community NPC AI, Lighting Research)
- **Development/Tuning Environments:** 1 (GOAP auto/ directory - core already integrated)

---

## RECOMMENDATIONS

### Priority 1: Continue Integration Work
1. ✅ Keep all "Very High" and "High" sophistication systems (already integrated)
2. ✅ Duplicate dungeon generators removed (kept `Dungeon/` production version)
3. ✅ Core GOAP integrated successfully
4. 🔄 Complete Community NPC AI integration when ready
5. 🔒 `lights_dev/` is frozen — migrate selected algorithms to production owners (see DEV MIGRATION issue)

### Priority 2: Documentation & Consistency
1. ✅ Document integration status clearly (completed in this update)
2. ✅ Update README files to reflect current state (completed)
3. 🔄 Document 3D → 2D conversion pipeline in detail
4. ✅ Integration complete for perception → AI → pathfinding
5. 🔄 Document GameRNG usage patterns and best practices

### Priority 3: Address Performance Issues
See `PERFORMANCE_ANALYSIS.md` for detailed recommendations:
1. Fix critical bugs (render_frame, apply_overlays method names)
2. Add bulk component fetching to eliminate N+1 queries
3. Consolidate entity iterations in game state
4. Vectorize light calculations
5. Add spatial hash for entity proximity queries
6. Implement frame rate limiting and dirty rect tracking
7. Cache flow fields and frequently accessed data

### Priority 4: Quality & Validation
1. Validate 3D dungeon generator output
2. Verify perception flow fields with different configurations
3. Validate GOAP planner behavior
4. Profile Numba-accelerated functions
5. Validate Polars DataFrame operations

---

## SYSTEM INTEGRATION MAP

### How Systems Work Together

The integrated systems form a cohesive pipeline from world generation through AI decision-making to rendering:

#### 1. World Generation Pipeline
```
Dungeon Generator (Dungeon/)
  → produces Polars DataFrame with 3D properties
  → GameMap (game/world/game_map.py)
  → tiles, depth/height, walkability, chambers
  → used by all game systems
```

#### 2. Perception → AI → Movement Pipeline
```
Player/Monster actions
  → generate noise/scent emissions
  → Perception Systems (pathfinding/perception_systems.py)
    - BFS-based flow field computation
    - Decay models (scent: 90%, noise: 60%)
    - Radial falloff
  → AI Strategy System (game/ai/strategy.py)
    - Reads structured PerceptionSnapshot facts (LOS, Audio, Scent, Memory)
    - Selects behavior state (HOME, CHARGE, FLEE, SMART_KOBOLD)
  → GOAP Planner (game/ai/goap.py) or ML Policy (game/ai/ml_policy.py)
    - Generates action sequence
  → Flow Field Pathfinding (game/systems/pathfinding/flowfield.py)
    - Dijkstra integration fields
    - Height-based movement costs
  → Movement System (game/systems/movement_system.py)
    - Collision detection
    - Displacement execution
```

#### 3. Rendering Pipeline
```
Game State (game/game_state.py)
  → orchestrates all entity/item/map updates
  → FOV/Visibility Systems (game/world/fov.py, los.py)
    - Shadowcasting algorithms
    - Determines what player can see
  → Lighting System (engine/render_lighting.py)
    - Distance-squared falloff
    - Ambient + source lighting
    - Memory fade effects
  → Renderer (engine/renderer.py + render_*.py)
    - Base tile layers
    - Entity sprites
    - Light application
    - Height visualization
  → Window Manager (engine/window_manager.py)
    - SDL2/Pygame output
```

#### 4. GameRNG Integration (Central Randomness)
```
GameRNG (utils/game_rng.py)
  ↓
  ├→ Dungeon Generation (Dungeon/core.py, shaper.py)
  ├→ Perception Systems (pathfinding/perception_systems.py)
  ├→ AI Systems (game/ai/*.py)
  ├→ Combat System (game/systems/combat_system.py)
  ├→ Effects System (game/effects/handlers.py)
  ├→ Loot/Item Generation
  └→ All other randomness
```

**Key Strength:** Deterministic, seeded RNG enables:
- Reproducible world generation
- Replay capability
- Debugging consistency
- Save/load state preservation

#### 5. Entity/Component System Integration
```
Template Registry (game/entities/template_registry.py)
  → defines entity templates in YAML
  → Entity Registry (game/entities/registry.py)
    - Polars DataFrame storage
    - Component-based architecture
  → All game systems read/write entities:
    ├→ Combat System (stats, equipment)
    ├→ Movement System (position, collision)
    ├→ AI System (behavior, perception)
    ├→ Equipment System (slots, bonuses)
    └→ Death System (loot dropping)
```

#### 6. Magic/Effects System Integration
```
Spell Definition (magic/work parser)
  → Art/Substance pairs
  → Work execution framework
  → Ward/Counterseal blocking
  → Effect System (game/effects/handlers.py)
    - Cost checking (mana, fullness, charges)
    - Status application
    - Effect handler registry
  → Applied to Entity Registry
  → Affects Combat, Movement, AI systems
```

---

## INTEGRATION ISSUES

### Critical Issues

#### 1. GameRNG Import Standardization ✅

**Status:** GameRNG imports are standardized across the codebase.

**Standard:** `from utils.game_rng import GameRNG`

**Notes:**
- `utils/game_rng.py` is the canonical implementation and import location.
- `worldgen/game_rng.py` is a compatibility re-export for world-generation modules.
- There is no root-level `game_rng.py` in the current tree.

#### 2. lights_dev/ Development Environment is Non-Deterministic ⚠️

**Status:** The `lights_dev/` R&D environment creates simple maps programmatically for developing lighting and FOV algorithms.

**Location:** `lights_dev/` development environment

**Impact:**
- Simple maps are sufficient for FOV/lighting algorithm development
- For complex dungeon development, the production `Dungeon/` pipeline should be used
- Development environment focuses on rendering algorithms, not dungeon generation

**Note:** This is a non-issue as the development environment's focus is on lighting/FOV/memory systems, not dungeon generation. The production `Dungeon/` pipeline at the repository root uses GameRNG for deterministic generation.

---

## UNINTEGRATED SYSTEMS

These systems exist in the codebase but are **NOT integrated** into the main game. They are standalone development environments or prototypes.

### 1. Community NPC AI System ❌ NOT INTEGRATED

**Location:** `ai/v9.py` + `ai/README.md`

**Purpose:** AI for non-adventurer NPCs in persistent communities (distinct from combat AI)

**Sophistication:** Very High
- Trait-based personality system (Endurance, Ingenuity, Perception, Will, Resonance)
- Needs management (Health, Energy, Thirst, Hunger, Nutrients)
- Physiological simulation (Fatigue, Illness)
- Habit learning from experience
- Planning with adaptive impact estimation
- Identity and cognitive dissonance modeling
- Experience memory system

**Status:**
- ⚠️ **Under active development**
- ❌ **Not integrated** with main game systems
- 🔄 **Planned:** Normalization with player trait system
- 🔄 **Planned:** Allow NPCs to switch between this AI and GOAP AI

**Integration Steps Needed:**
1. Normalize trait systems between ai/ and game/ implementations
2. Create community environment system for NPCs to inhabit
3. Integrate with game/game_state.py orchestrator
4. Add NPC spawning/management to entity registry
5. Connect with resource management, time, weather systems

**Dependencies:**
- numpy
- GameRNG
- Needs: Home, Field, CROPS, Weather, Calendar, Behavior definitions

---

### 2. Lighting/FOV/Memory R&D Environment 🔒 FROZEN — PENDING RETIREMENT

**Location:** `lights_dev/` directory

> **`lights_dev` is frozen R&D pending retirement.** Do not add production imports from it.
> Migrate selected algorithms into production owners (`engine/render_lighting.py`,
> `game/world/fov.py`), then delete or archive the folder. See the DEV MIGRATION issue
> for the full phase-by-phase migration plan.
>
> **Ownership boundaries:**
> - `engine/render_lighting.py` — production lighting owner
> - `game/world/fov.py` — production FOV/LOS owner
> - Memory simulation belongs in a production state/system module, not the renderer

**Purpose:** R&D environment for advanced visual and memory systems (historical)

**Sophistication:** High
- Octant-based shadowcasting FOV (Numba-accelerated)
- Dynamic colored lighting with inverse square falloff
- Multi-source RGB light blending
- Novel memory fade system with sigmoid decay
- Memory influenced by traits/conditions (planned)

**Status:**
- 🔒 **Frozen** — no new production imports allowed
- ❌ **Not integrated** into main game engine
- 🗑️ **Planned for deletion** after migrations and tests pass

**Migration Map:**

| lights_dev source | Production target | Status |
|---|---|---|
| `lighting.py::LightContext` cache | `engine/render_lighting.py::LightContributionCache` | In progress |
| `lighting.py` RGB blending policy | `engine/render_lighting.py` blend abstraction | In progress |
| `generate_varied_test.py` fixtures | `tests/fixtures/fov_scenarios.py`, `tests/fixtures/lighting_scenarios.py` | In progress |
| `memory.py::MemorySystem` | `game/world/memory.py` (if accepted) | Deferred |
| `fov.py` side-bit FOV | `game/world/fov.py` (if needed) | Deferred |
| R&D runner/CLI/`GameState`/entities | — | Discard |

---

### 3. GOAP AI Simulation Environment ✅ PARTIALLY INTEGRATED

**Location:** `auto/` directory

**Purpose:** Development and tuning environment for Goal-Oriented Action Planning AI

**Sophistication:** High
- Complete GOAP implementation with A* planning
- Action learning through weight adjustment
- Polars DataFrame entity management
- A* pathfinding
- Multiprocessing parallel simulation
- PySide6 GUI for visualization/debugging

**Status:**
- ⚠️ **Development environment** - tuning GOAP AI
- ✅ **Core GOAP Fully Integrated** - game/ai/goap.py is production code
- ✅ **Adapter Integrated** - game/ai/goap_adapter.py connects to main game
- ❌ **Standalone simulation separate** - auto/simulation.py is development environment only
- ❌ **GUI for development only** - auto/gui/ not for gameplay

**Files:**
- `goap_engine.py` - Core GOAP planner (extracted to game/ai/)
- `simulation.py` - Standalone world simulation (development environment)
- `main.py` - Headless runner with multiprocessing
- `gui/` - PySide6 visualization tool
- `run.sh` - Execution wrapper

**Integration Status:**
- ✅ **GOAP Planner:** Fully integrated in game/ai/goap.py
- ✅ **AI Strategy:** Fully integrated in game/ai/strategy.py
- ✅ **Adapter:** game/ai/goap_adapter.py connects game state to GOAP
- ❌ **Standalone simulation:** auto/simulation.py is separate development environment
- ❌ **GUI:** auto/gui/ is development-only, not for gameplay

**Use Case:**
- Core GOAP drives NPC/monster decision making in production
- auto/ environment used for training, tuning, and developing new behaviors

**Note:** The core GOAP AI is **fully integrated**. The auto/ directory serves as a **development and tuning environment** for the AI before deploying changes to the main game.

---

### 4. Simulation Zone Manager ✅ INTEGRATED

**Location:** `simulation/zone_manager.py`

**Status:** ✅ **INTEGRATED**

**Used By:**
- `game/game_state.py`
- `engine/main_loop.py`
- `auto/main.py`

**Purpose:** Zone-based world management (integrated successfully)

---

## DIRECTORY ORGANIZATION

### Production Systems (Integrated)

```
Repository root
├── game/                    # Main game systems (INTEGRATED)
│   ├── ai/                  # Production AI (GOAP, Strategy, ML, behaviors)
│   ├── effects/             # Magic effects system
│   ├── entities/            # Entity/component system
│   ├── items/               # Item management
│   ├── systems/             # Core mechanics, including pathfinding/flowfield.py
│   └── world/               # Game map, FOV, visibility, LOS
├── engine/                  # Rendering engine (INTEGRATED)
│   ├── renderer.py          # Main renderer
│   ├── render_*.py          # Layer rendering
│   ├── window_manager.py    # SDL2 window management
│   └── window_manager_modules/
├── pathfinding/             # Perception systems (INTEGRATED)
│   └── perception_systems.py  # Sound/smell flow fields
├── Dungeon/                 # 3D dungeon generator (INTEGRATED)
│   ├── core.py              # CaveGenerator
│   ├── processor.py         # Geometry processing
│   └── shaper.py            # Rasterization & CA smoothing
├── magic/                   # Magic system (INTEGRATED)
├── simulation/              # Zone manager (INTEGRATED)
├── utils/                   # Utilities, including canonical GameRNG
├── worldgen/                # World generation utilities and GameRNG re-export
├── common/                  # Common constants/utilities
├── config/                  # Configuration files
└── data/                    # Game data
```

### Development/R&D Systems (NOT Integrated)

```
├── ai/                      # Community NPC AI (NOT INTEGRATED)
│   ├── v9.py                # Advanced trait-based NPC AI
│   └── README.md
├── auto/                    # GOAP development environment (NOT INTEGRATED)
│   ├── simulation.py        # Development world
│   ├── main.py              # Headless runner
│   ├── gui/                 # Visualization tool
│   └── README.md
├── lights_dev/              # Lighting R&D environment (NOT INTEGRATED)
│   ├── main_game.py         # Standalone development environment
│   ├── dungeon_data.py      # Numba jitclass
│   └── README.md
```

### Support Directories

```
├── docs/                    # Documentation
├── fonts/                   # Font assets
├── notes/                   # Development notes
├── scripts/                 # Utility scripts
└── tools/                   # Development tools
```

### Cleanup Status

**Moved (archived) (2026-01-16):**
- ✅ No `legacy/dungeon_generator.py` or `legacy/lights_dev/dungeon_generator.py` files are present in the current tree.
- ✅ `prototypes/` - Entire directory (old prototypes, superseded implementations)
  - Contained: lights_dev/, Dungeon/, ai/, pathfinding/, auto/ variants

**Kept:**
- ✅ `Dungeon/` (root) - Most sophisticated 3D generator
- 🔒 `lights_dev/` - Frozen R&D, pending retirement after algorithm migration
- ✅ `auto/` - AI testing environment, core already integrated
- ✅ `ai/` - Community NPC AI under development

---

## CONCLUSION

This is a sophisticated, production-quality roguelike engine with exceptional implementations of:
- 3D procedural generation with depth preservation
- Multi-sensory AI perception (sight, sound, scent)
- Advanced pathfinding algorithms (flow fields, A*)
- Flexible AI architectures (GOAP, FSM, ML-ready)
- Comprehensive game systems (combat, equipment, effects, items)
- High-performance rendering with lighting and memory fade
- Deterministic simulation with GameRNG

The codebase has evolved from multiple merged projects and now has clear separation between production systems and R&D environments.

### Integration Summary

**Fully Integrated Systems (Production):** 16+ primary systems working together
- Dungeon generation, FOV/visibility, lighting, pathfinding
- Combat, movement, equipment, death systems
- Entity/component management, effects system
- GOAP AI, strategy-based AI, perception systems
- Rendering pipeline with multiple stages
- Deterministic RNG throughout

**R&D Systems (Not Yet Integrated):** 2 systems with clear integration paths
- Community NPC AI (ai/v9.py) - Advanced trait-based behaviors
- Lighting/FOV/Memory testbed (lights_dev/) - Experimental rendering features

**Test/Tuning Environments:** 1 environment
- GOAP test harness (auto/) - Core already integrated, used for AI training

**Critical Improvements Needed:**
- Address performance issues documented in PERFORMANCE_ANALYSIS.md
- Fix method name mismatches (render_frame, apply_overlays)
- Implement caching and bulk operations to eliminate N+1 patterns
- Add spatial indexing for entity queries
- Standardize GameRNG usage in all components (including lights_dev/)
