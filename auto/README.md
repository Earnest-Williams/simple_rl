# simple_rl/auto - GOAP AI Development & Tuning Environment

## Purpose

This directory contains the simulation environment and development tools for **combat-oriented agents** (adventurers, monsters) designed to operate within hostile environments like the procedurally generated dungeons (`Dungeon/`). It utilizes the Goal-Oriented Action Planning (GOAP) paradigm to drive agent behavior.

**Important:** The core GOAP AI system has been **fully integrated** into the main game engine at `game/ai/goap.py` and `game/ai/goap_adapter.py`. This `auto/` directory now serves as a **development and tuning environment** for the AI before deploying behavior changes to the main game. It provides a standalone simulation with multiprocessing support and a GUI for visualization and debugging.

## Status: Development & Tuning Environment

* ✅ **Core GOAP System**: Fully integrated into production game (`game/ai/goap.py`, `game/ai/goap_adapter.py`)
* ✅ **This Directory**: Standalone development harness for AI development
* ✅ **Purpose**: Train action weights, develop behaviors, profile performance
* ✅ **GUI Tool**: PySide6 interface for real-time visualization of AI plans and decisions

## Core Functionality

* **Simulation Environment (`simulation.py`):**
    * Defines a grid-based `World` using `numpy` (implicitly via Polars) and standard Python collections.
    * Manages `Entity` states (Agent, Enemy, Slime, Item) efficiently using a **Polars DataFrame** (`world.entity_df`) for scalable state storage and querying.
    * Includes basic physics/interactions: movement, health/hunger tracking, simple combat, item interaction (pickup, consume, equip), enemy spawning, and food respawning.
    * Provides an A\* pathfinding implementation (`world.find_path`) using `heapq`.
    * Uses Numba (`@njit`) to accelerate distance calculations.
* **GOAP AI (`simulation.py` + `goap_engine.py`):**
    * **`Action`:** Represents atomic actions agents can perform (MoveTo, Attack, Flee, Pickup, Consume, Equip, Wait, Explore) with defined costs, preconditions, and effects.
    * **`GOAPPlanner` (in `goap_engine.py`):** Implements an A\* search over the available actions to find a sequence (plan) that achieves a desired goal state from the current world state. Action costs are weighted based on learned effectiveness.
    * **`AgentAI` (in `goap_engine.py`):** Orchestrates the agent's turn. It determines the current goal (`_select_goal`), requests a plan from the `GOAPPlanner`, executes the plan step-by-step, validates plan validity, handles replanning, and triggers learning. The `plan_for` method is used by the game adapter to return plans without executing them.
    * **Learning:** The AI learns by adjusting the weights associated with actions (`planner.action_weights`). After a simulation run, weights are updated based on the agent's survival outcome (turns survived, final health), making successful action sequences cheaper (more likely to be chosen) in the future. Unlike the community AI (`simple_rl/ai`), this system starts with functional knowledge (e.g., how to eat) and learns the *value* and consequences of actions.
* **Execution & Development (`main.py`, `run.sh`):**
    * `main.py` provides a headless runner capable of executing multiple simulation runs in parallel using `multiprocessing.Pool`.
    * Supports different learning modes (`independent` vs. `shared` weights across runs).
    * Collects and summarizes simulation results (survival rates, turns, final weights).
    * Includes optional `cProfile` integration for performance analysis.
    * `run.sh` provides a convenient wrapper to execute `main.py`.
* **GUI (`gui/` subfolder):**
    * A PySide6-based graphical interface (`main_window.py`, `gui_widgets.py`) for visualizing the simulation state and agent plans in real-time.
    * Uses a separate thread (`worker.py`) to run the simulation, preventing GUI freezes.
    * Primarily intended as a **development and tuning tool**, not for final gameplay integration.

## Dependencies

* **Python:** 3.x
* **Core Libraries:**
    * `polars`: For efficient entity state management.
    * `numpy`: Used by Polars and potentially in other calculations.
    * `numba`: For JIT-accelerating the distance function.
* **GUI Specific (Optional):**
    * `PySide6`: For the graphical interface.
* **Development:**
    * `random`: Used for world events like spawning (Consider replacing with `GameRNG` for full determinism if needed within this simulation).
    * Standard libraries: `collections`, `heapq`, `time`, `uuid`, `argparse`, `multiprocessing`, `cProfile`, `io`, `pstats`, `sys`, `os`.

## Usage

* **Headless Mode (for batch runs/development):**
    ```bash
    ./run.sh --mode headless -n <num_runs> -w <num_workers> --learn <independent|shared>
    # Example: ./run.sh --mode headless -n 100 -w 4 --learn shared
    ```
* **GUI Mode (for visualization/debugging):**
    ```bash
    ./run.sh --mode gui
    ```

## Integration

The core GOAP AI is **fully integrated** into the main game engine. This development environment is used to:
* Train and tune action weights before deploying to production
* Develop new behaviors in isolation
* Profile AI performance
* Visualize agent decision-making for debugging
* Run parallel simulations for learning

The main game consumes the GOAP planner via `game/ai/goap_adapter.py`, which translates game state into GOAP world state and executes plans within the main game loop.
