# simple_rl/lights_dev - Lighting, FOV, and Memory Simulation R&D

## Purpose

This directory serves as a dedicated research and development testbed for advanced visual and memory systems intended for the main Simple RL game. It focuses on implementing and iterating upon:

1.  **Field of View (FOV) / Line of Sight (LOS):** A shadow-casting algorithm (octant-based) inspired by Brogue, designed for performance using Numba.
2.  **Dynamic Lighting:** Simulation of colored light sources with inverse square falloff, supporting blending of multiple sources for True Color illumination. Future plans include animating light sources (e.g., flickering torches).
3.  **Memory Fade:** A novel system where the player's memory of explored areas fades over time based on a sigmoid decay function. The accuracy and retention of memory are planned to be influenced by agent traits and conditions (e.g., intelligence, illness, magic).

The components developed here are intended for eventual integration into the main game engine.

## Core Components

* **`runner.py`:** The primary embedding API (`GameRunner`) for front-ends. It manages initialization, precompile warm-up, stepping, and rendering without configuring logging.
* **`renderer.py`:** Console renderer that turns a `GameState` into a text frame using ANSI True Color codes.
* **`cli.py`:** Debug / profiling runner that wraps `GameRunner` for local smoke tests (optional `readchar`).
* **`main_game.py`:** Compatibility entrypoint that forwards to the debug CLI.
* **`dungeon_data.py`:** Defines the `Dungeon` **Numba jitclass**. This high-performance data structure holds the core grid arrays (`tiles`, `visible`, `memory_intensity`, `last_seen_time`) and is passed to Numba-accelerated functions.
* **`constants.py`:** Contains constants specific to this R&D environment, including rendering characters, True Color RGB values, memory fade parameters, and the `LIGHT_LEVEL_DATA` structure mapping light intensity to gameplay visibility checks.

**Note:** The testbed creates simple procedural test maps within `main_game.py` for testing lighting and FOV algorithms. For production-quality dungeon generation with complex cave systems, use the `Dungeon/` pipeline at the repository root.

## Key Mechanics & Implementation

* **FOV/LOS:** Octant-based recursive shadow casting implemented in Numba (`_compute_octant_for_boolean_array`) for performance. Relies on the `Dungeon.blocks_light` method.
* **Lighting:** Calculates light spread and intensity using an inverse square falloff. Blends RGB values from multiple sources. Implemented in Numba (`_compute_octant_for_color`).
* **Memory Fade:** Uses elapsed time (`Dungeon.current_time`, `Dungeon.last_seen_time`) and a sigmoid function (`_update_memory_fade_internal` in Numba) to decay `Dungeon.memory_intensity` for non-visible tiles. Intensity affects rendering character choice.
* **Rendering:** Outputs to console using ANSI True Color escape codes, blending lighting with intuitive base colors per tile/entity and dimmed memory colors for recalled tiles.

## Dependencies

* **Python:** 3.x
* **Core Libraries:** `numpy`, `numba`
* **Optional:** `readchar` (for interactive mode in `cli.py`)

## Status & Integration

This component is under active development and refinement. The core algorithms for FOV, lighting, and memory are functional but require testing in more complex environments and further iteration (e.g., light animation, trait integration for memory).

## GameRunner Integration (example)

```python
runner = GameRunner(80, 30, seed=12345)
runner.initialize()
runner.precompile()
runner.step(dt)
frame = runner.render()
```

For a pygame/SDL loop, call `runner.step(dt)` each tick, then use
`LightingSystem.compute_final_rgb_map(...)` to get an RGB buffer for blitting.

**Current Status:**
* ⚠️ **Active R&D**: Experimental systems being refined
* ❌ **Not Integrated**: Standalone testbed separate from production engine
* 🔄 **Planned Integration**: Systems will merge with main game rendering pipeline

**Integration Roadmap:**
1. Merge FOV algorithms with `game/world/fov.py` and `game/world/visibility.py`
2. Integrate lighting system with `engine/render_lighting.py`
3. Add memory fade to main rendering pipeline
4. Connect memory system to agent traits
5. Remove or archive standalone `main_game.py` after integration

The systems developed here are planned for integration into the main simulation, potentially combined with perception systems from `pathfinding/` under a unified orchestrator. The memory system might be separated due to its complexity and interactions with other game states.
