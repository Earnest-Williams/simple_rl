# Simple RL Project - Simulation-Heavy Game Development

## Overview

This project focuses on the development of a simulation-heavy game, likely a roguelike or RPG, set primarily within vast, procedurally generated cave systems on an isolated continent. Key development goals include creating complex, emergent AI behaviors, realistic environmental interactions, and a persistent world state, all built upon a foundation of high-performance, idiomatic Python.

The project emphasizes robust simulation, leveraging performant libraries and patterns to handle complexity efficiently. Determinism, modularity, and clear code structure are core tenets.

## Core Components

This project is structured into several key component directories, each with its own detailed `README.md`:

* **`Dungeon/`**: The primary procedural generation pipeline for creating complex, multi-featured cave systems using a multi-stage process (Core Graph → Processing → Shaping). Outputs Polars DataFrames with preserved 3D depth information. ([See README](./Dungeon/README.md))
* **`AI/`**: Implements experimental AI for **community-based NPCs**, focusing on complex social behaviors, needs, traits, and habit learning. Under active development and not yet integrated with the main game. ([See README](./AI/README.md))
* **`auto/`**: Contains a **combat/survival AI test environment** based on Goal-Oriented Action Planning (GOAP). The core GOAP planner has been extracted and integrated into the main game via `game/ai/goap.py`. This directory serves as a simulation testbed and development GUI for training and tuning AI behavior. ([See README](./auto/README.md))
* **`lights_dev/`**: An R&D environment for developing advanced **lighting, Field of View (FOV), and memory fade** mechanics, utilizing Numba for acceleration. Contains experimental features for future integration. Note: Uses Python's standard `random` module rather than `GameRNG` for rapid prototyping. ([See README](./lights_dev/README.md))
* **`pathfinding/`**: Simulates non-visual **perception systems** (noise propagation, scent tracking) integrated with the main game to provide input for AI decision-making. ([See README](./pathfinding/README.md))
* **`game_rng.py`** & **`utils/game_rng.py`**: Provides the foundational `GameRNG` class, a deterministic, high-performance **Random Number Generator** with state management, used throughout the project. The main implementation is at the root level, with a thin wrapper in utils/ for convenient importing. ([See README](./utils/README.md))
* **`scripting_engine.py`**: Implements macro expansion and a Brainfuck interpreter, designed as a foundation for the **game's spell system**. Currently in development; basic effect system is functional.
* **`game/`**: Main game engine integrating all production systems including combat, movement, equipment, AI, effects, entities, and world management.

## Technical Philosophy

Development prioritizes:

* **Performance:** Utilizing libraries like Polars (for data manipulation), Numba (for JIT compilation on hot paths), NumPy, SciPy, scikit-image, and Joblib/multiprocessing (for parallelism) where appropriate.
* **Determinism:** Employing the custom `GameRNG` for all stochastic processes to ensure reproducibility.
* **Data-Driven Design:** Modeling game state and entity attributes using efficient data structures (e.g., Polars DataFrames).
* **Clarity & Maintainability:** Adhering to Python best practices (PEP 8) and favoring clear, modular code, especially in performance-critical sections.

## Status

This project is **under active development**. The core game systems are integrated and functional, including dungeon generation, FOV/lighting, combat, equipment, AI (GOAP and strategy-based), pathfinding, and rendering. Some experimental systems remain in dedicated R&D directories for testing and refinement before integration.

### Production-Ready Systems
* **Dungeon Generation**: 3D cave networks with 2D rasterization (fully integrated)
* **Rendering Pipeline**: Tile-based rendering with lighting, FOV, and memory fade
* **Combat & Movement**: Complete systems with equipment, stats, and collision
* **AI Systems**: GOAP planner and strategy-based behaviors for NPCs/monsters
* **Perception**: Sound and scent propagation systems feeding AI decisions
* **Effects System**: Comprehensive effect handlers and status management

### R&D Systems (Not Yet Integrated)
* **Community NPC AI** (`AI/`): Advanced trait-based AI for non-combat NPCs with habit learning
* **Lighting Testbed** (`lights_dev/`): Experimental octant FOV and colored lighting research
* **GOAP Test Environment** (`auto/`): Simulation harness for AI training and tuning (core GOAP is already integrated)

### Planned Features
* Historical/lore layer for dungeon generation
* Full spell system based on `scripting_engine.py`
* Advanced memory fade influenced by agent traits
* Community and settlement management systems

## Vestigial Components

* **`simple_rl.py`**: An older PySide6 GUI application implementing a basic roguelike loop. Largely superseded by newer components but maintained for testing purposes.
* **`dungeon_generator.py`**: A simpler room-and-corridor generator used by `simple_rl.py`.

These files are currently maintained primarily for testing `scripting_engine.py` and may be deprecated in future releases.

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
   pip install -r requirements.txt
   ```
   
   Python 3.11+ is required. Core dependencies include Polars, NumPy, Numba, SciPy, scikit-image, PySide6, and Pygame.

3. **Run the main game:**
   ```bash
   python main.py
   ```
   
   Or use the orchestrator for more control:
   ```bash
   python orchestrator.py
   ```

### Testing Components

Different components have dedicated test harnesses for development:

* **Dungeon Generation:** `cd Dungeon && ./run.sh`
* **GOAP AI Testing (Headless):** `cd auto && ./run.sh --mode headless`
* **GOAP AI Testing (GUI):** `cd auto && ./run.sh --mode gui`
* **Lighting/FOV Testbed:** `cd lights_dev && python main_game.py`
* **Perception Testbed:** `cd pathfinding && python test.py`
* **Legacy GUI:** `python simple_rl.py` (maintained for scripting_engine.py testing)

### Running Tests

```bash
pytest
```

Tests cover pathfinding, effects, perception, inventory, AI, and other core systems. Refer to individual component READMEs for specific requirements and usage details.
