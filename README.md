# Simple RL Project - Simulation-Heavy Game Development

## Overview

This project focuses on the development of a simulation-heavy game, likely a roguelike or RPG, set primarily within vast, procedurally generated cave systems on an isolated continent. Key development goals include creating complex, emergent AI behaviors, realistic environmental interactions, and a persistent world state, all built upon a foundation of high-performance, idiomatic Python.

The project emphasizes robust simulation, leveraging performant libraries and patterns to handle complexity efficiently. Determinism, modularity, and clear code structure are core tenets.

## Core Components

This project is structured into several key component directories, each with its own detailed `README.md`:

* **`simple_rl/Dungeon/`**: The primary procedural generation pipeline for creating complex, multi-featured cave systems using a multi-stage process (Core Graph -> Processing -> Shaping). Outputs Polars DataFrames. ([See README](./simple_rl/Dungeon/README.md))
* **`simple_rl/AI/`**: Implements the AI for **community-based NPCs**, focusing on complex social behaviors, needs, traits, and habit learning. ([See README](./simple_rl/AI/README.md))
* **`simple_rl/auto/`**: Contains the **combat/survival AI** system based on Goal-Oriented Action Planning (GOAP), intended for adventurers and monsters operating in hostile environments. Includes a simulation testbed and development GUI. ([See README](./simple_rl/auto/README.md))
* **`simple_rl/lights_dev/`**: An R&D environment for developing advanced **lighting, Field of View (FOV), and memory fade** mechanics, utilizing Numba for acceleration. Intended for future integration. ([See README](./simple_rl/lights_dev/README.md))
* **`simple_rl/pathfinding/`**: Simulates non-visual **perception systems** (noise propagation, scent tracking) to provide input for AI decision-making and pathfinding routines. ([See README](./simple_rl/pathfinding/README.md))
* **`simple_rl/rng_utils/`**: Provides the foundational `GameRNG` class, a deterministic, high-performance **Random Number Generator** with state management, used throughout the project. ([See README](./simple_rl/rng_utils/README.md))
* **`simple_rl/scripting_engine.py`**: Implements macro expansion and a Brainfuck interpreter, intended to serve as the basis for the **game's spell system**.

## Technical Philosophy

Development prioritizes:

* **Performance:** Utilizing libraries like Polars (for data manipulation), Numba (for JIT compilation on hot paths), NumPy, SciPy, scikit-image, and Joblib/multiprocessing (for parallelism) where appropriate.
* **Determinism:** Employing the custom `GameRNG` for all stochastic processes to ensure reproducibility.
* **Data-Driven Design:** Modeling game state and entity attributes using efficient data structures (e.g., Polars DataFrames).
* **Clarity & Maintainability:** Adhering to Python best practices (PEP 8) and favoring clear, modular code, especially in performance-critical sections.

## Status

This project is **under active development**. Components are at various stages of implementation, testing, and integration. Some elements, like the historical/lore layer for dungeon generation or the full integration of lighting/perception/AI systems, are planned future work.

## Vestigial Components

* **`simple_rl.py`**: An older PySide6 GUI application implementing a basic roguelike loop. Largely superseded by newer components.
* **`simple_rl/dungeon_generator.py`**: A simpler room-and-corridor generator used by `simple_rl.py`.

These files are currently maintained primarily for testing the `simple_rl/scripting_engine.py`.

## Getting Started (Development Focus)

Currently, different components are often run via their respective test harnesses or shell scripts:

* **Dungeon Generation:** `cd simple_rl/Dungeon && ./run.sh`
* **GOAP AI Simulation (Headless):** `cd simple_rl/auto && ./run.sh --mode headless ...`
* **GOAP AI Simulation (GUI):** `cd simple_rl/auto && ./run.sh --mode gui`
* **Lighting/FOV Testbed:** `cd simple_rl/lights_dev && python main_game.py`
* **Perception Testbed:** `cd simple_rl/pathfinding && python test.py`

Ensure required dependencies (Python 3.x, Polars, NumPy, Numba, SciPy, scikit-image, PySide6 for GUI, etc.) are installed. Refer to individual component READMEs for specific requirements.
