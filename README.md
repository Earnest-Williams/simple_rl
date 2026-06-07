# Simple RL Project - Simulation-Heavy Game Development

## Overview

This project focuses on the development of a simulation-heavy game, likely a roguelike or RPG, set primarily within vast, procedurally generated cave systems on an isolated continent. Key development goals include creating complex, emergent AI behaviors, realistic environmental interactions, and a persistent world state, all built upon a foundation of high-performance, idiomatic Python.

The project emphasizes robust simulation, leveraging performant libraries and patterns to handle complexity efficiently. Determinism, modularity, and clear code structure are core tenets.

## Core Components

This project is structured into several key component directories, each with its own detailed `README.md`:

* **`Dungeon/`**: The primary procedural generation pipeline for creating complex, multi-featured cave systems using a multi-stage process (Core Graph → Processing → Shaping). Outputs Polars DataFrames with preserved 3D depth information. ([See README](./Dungeon/README.md))
* **`ai/`**: Implements experimental AI for **community-based NPCs**, focusing on complex social behaviors, needs, traits, and habit learning. Under active development and not yet integrated with the main game. ([See README](./ai/README.md))
* **`auto/`**: Contains a **combat/survival AI test environment** based on Goal-Oriented Action Planning (GOAP). The core GOAP planner has been extracted and integrated into the main game via `game/ai/goap.py`. This directory serves as a simulation testbed and development GUI for training and tuning AI behavior. ([See README](./auto/README.md))
* **`pathfinding/`**: Simulates non-visual **perception systems** (noise propagation, scent tracking) integrated with the main game to provide input for AI decision-making. Production AI now consumes visual, audio, scent, and memory-priority perception signals through these systems. ([See README](./pathfinding/README.md))
* **`utils/game_rng.py`**: Provides the foundational `GameRNG` class, a deterministic, high-performance **Random Number Generator** with state management, used throughout the project. `worldgen/game_rng.py` re-exports the same class for world-generation compatibility. ([See README](./utils/README.md))
* **`scripting_engine.py`**: Implements macro expansion and a Brainfuck interpreter, designed as a foundation for the **game's spell system**. Currently in development; basic effect system is functional.
* **`game/`**: Main game engine integrating all production systems including combat, movement, equipment, AI, effects, entities, and world management.

## Technical Philosophy

Development prioritizes:

* **Performance:** Utilizing libraries like Polars (for data manipulation), Numba (for JIT compilation on hot paths), NumPy, SciPy, scikit-image, and Joblib/multiprocessing (for parallelism) where appropriate.
* **Determinism:** Employing the custom `GameRNG` for all stochastic processes to ensure reproducibility.
* **Data-Driven Design:** Modeling game state with efficient data structures. Polars is used for batch data, exports, snapshots, fixtures, and analysis; hot runtime entity state uses store/array-oriented access where migrated.
* **Clarity & Maintainability:** Adhering to Python best practices (PEP 8) and favoring clear, modular code, especially in performance-critical sections.

## Status

This project is **under active development**. The core game systems are integrated and functional, including dungeon generation, FOV/lighting, combat, equipment, AI (GOAP and strategy-based), pathfinding, and rendering. Some experimental systems remain in dedicated R&D directories for testing and refinement.

### Production-Ready Systems
* **Dungeon Generation**: 3D cave networks with 2D rasterization (fully integrated)
* **Rendering Pipeline**: Tile-based rendering with lighting, FOV, and memory fade
* **Combat & Movement**: Complete systems with equipment, stats, and collision
* **AI Systems**: GOAP planner and strategy-based behaviors for NPCs/monsters, including structured visual/audio/scent/memory perception priority
* **Perception**: Sound and scent propagation systems feeding AI decisions
* **Effects System**: Comprehensive effect handlers and status management

### R&D Systems and Testbeds
* **Community NPC AI** (`ai/`): Advanced trait-based AI for non-combat NPCs with habit learning; not yet integrated.
* **GOAP Test Environment** (`auto/`): Simulation harness for AI training and tuning (core GOAP is already integrated).

### Planned Features
* Historical/lore layer for dungeon generation
* Full spell system based on `scripting_engine.py`
* Community and settlement management systems

## Legacy status

The repository no longer contains a `legacy/` directory or the historical
`simple_rl.py` / `dungeon_generator.py` entrypoints. New development should use
the canonical component entrypoints documented in the directory READMEs:

- `Dungeon/` for procedural cave generation.
- `game/` for integrated production game systems.
- `engine/render_lighting.py`, `game/world/light_fov.py`, and `game/world/memory.py` own production lighting, light-aware FOV, and memory behavior.
- `auto/` for GOAP simulation and tuning.

## Getting Started

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Earnest-Williams/simple_rl.git
   cd simple_rl
   ```

2. **Install dependencies:**
   ```bash
   pip install -e .
   # OR for development:
   pip install -e ".[dev]"
   ```
   
   Python 3.11+ is required. Core dependencies include Polars, NumPy, Numba, SciPy, scikit-image, PySide6, PySDL2, and pysdl2-dll.
   The glyph metadata generator (`scripts/generate_glyphs.py`) requires PyYAML.

3. **Run the main game:**
   ```bash
   python main.py
   ```
   
   Or use the orchestrator for more control:
   ```bash
   python orchestrator.py
   ```

### Development Harnesses

Different components have dedicated development harnesses:

* **Dungeon Generation:** `cd Dungeon && ./run.sh`
* **GOAP AI Development (Headless):** `cd auto && ./run.sh --mode headless`
* **GOAP AI Development (GUI):** `cd auto && ./run.sh --mode gui`
* **Lighting/FOV Regression Tests:** `python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py`
* **Lighting/FOV Visual Tool:** `python -m tools.lighting_fov_tool.main` (see [`tools/lighting_fov_tool/README.md`](./tools/lighting_fov_tool/README.md))

Refer to individual component READMEs for specific requirements and usage details.
Generated font assets and glyph metadata are documented in
[`docs/Asset Pipeline.md`](./docs/Asset%20Pipeline.md).

## Performance & Known Issues

The project prioritizes performance through high-performance libraries (Polars, Numba, NumPy) and efficient data structures. However, some known performance considerations exist:

### Performance Optimization
* Use Numba JIT compilation for hot paths (FOV, lighting, pathfinding)
* Leverage Polars lazy evaluation for large batch/reporting datasets
* Keep hot runtime entity reads on store/array accessors and spatial indexes where migrated
* Profile code with `cProfile` before optimizing
* See [`docs/Performance Analysis.md`](./docs/Performance%20Analysis.md) for detailed analysis and recommendations

### Known Limitations
* Some rendering operations may benefit from caching and dirty-rect tracking
* Non-combat item/equipment DataFrame paths remain unverified and may represent the next dominant turn-processing bottleneck after the entity-store migration
* Flow field pathfinding may benefit from caching when targets are stationary

For detailed performance analysis and optimization recommendations, see
[`docs/Performance Analysis.md`](./docs/Performance%20Analysis.md).
