# simple_rl

> *« Je fis une prière de reconnaissance à Dieu, car il m’avait conduit parmi ces immensités sombres au seul point peut-être où la voix de mes compagnons pouvait me parvenir. »*
> — Jules Verne, Voyage au centre de la Terre, chap. XXVIII.
> 
> *“It is not down on any map; true places never are.”*
> — Herman Melville, Moby-Dick

A simulation-heavy roguelike/RPG research project emphasizing determinism, complex AI, multi-stage 3D cave generation, and deep perception systems.

## Milestone & Status Summary

Active. Canonical roguelike/RPG research project.

- **Entity Store Architecture**: Transitioned the engine to a robust, array-oriented entity store.
- **First Playable Expedition Loop**: Fully functional overland map and expedition flow (surveying, navigating blockages, discovering locations).
- **Cave Handoff and Minimal Interior**: Completed the vertical slice for transitioning between the overland map and a generated interior cave map, including tracking transition metadata (cave types, seasonal flow states) and looping back to the surface to complete an expedition.

## Core Game Systems

- **Procedural Generation (`Dungeon/`, `worldgen/`)**: Polars/graph-based multi-stage cave generation preserving 3D depth, and robust overland map generation.
- **Perception & AI (`ai/`, `auto/`, `pathfinding/`)**: Multi-sense perception (visual, audio, scent, memory) feeding into a GOAP (Goal-Oriented Action Planning) testbed and production AI.
- **Main Engine (`game/`, `engine/`)**: Integrated combat, movement, equipment, and world management systems.
- **Magic & Effects (`magic/`)**: A scripting foundation (macro expansion + Brainfuck interpreter) for esoteric spell systems.

## Project Layout

```text
simple_rl/
  ai/             Experimental community-based NPC AI.
  auto/           GOAP-based combat/survival AI testbed.
  docs/           Extensive architecture, lore, and planning notes.
  Dungeon/        Procedural cave generation pipeline (Graph → Processing → Shaping).
  engine/         Core action handling, rendering layers, and base loops.
  game/           Main integrated game engine and runtime state.
  magic/          Experimental scripting foundation for spell systems.
  pathfinding/    Non-visual perception (noise, scent) and pathfinding algorithms.
  scripts/        Development helper scripts.
  tests/          Pytest coverage for the core systems.
  worldgen/       Overland map and settlement generation.
```

## Runtime and Tooling Files

- `pyproject.toml`: The canonical Python packaging and tool-configuration file. Targets Python 3.11+, configures pytest, and handles core project metadata.
- `environment.yml`: Defines a Conda/mamba environment named `simple_rl`. Installs core dependencies like Polars, NumPy, Numba, PySide6, and Pytest.

## Quickstart

1. Clone and enter the directory.
2. Initialize and activate the environment:
   ```bash
   mamba env create -f environment.yml
   mamba activate simple_rl
   ```
3. Run the main game:
   ```bash
   sdc
   # or
   python -m lights_dev
   ```

## Tests

The project maintains a comprehensive test suite (currently 270+ passing tests) covering everything from FOV caching and walkability checks to GOAP AI behavior and full expedition loops.

```bash
mamba run -n simple_rl pytest
```

## Development Principles

### 1. Build the playable game first
The project may support ambitious simulation over time, but every major system should serve a playable expedition roguelike. Technical ambition is valuable only when it strengthens command, consequence, discovery, survival, exploration, or practical magic.

### 2. Separate True Targets from Moonshots
True Targets are the real commitments. They must be achievable, testable, and capable of producing an excellent game without speculative infrastructure.
Moonshots may influence architecture and long-term direction, but they must not block playable milestones. Every moonshot should have a simpler fallback: a narrative version, an approximate deterministic simulation version, or a full simulation version only when justified by performance and development cost.

### 3. Preserve determinism
All stochastic systems should use the project’s canonical deterministic RNG path. Procedural generation, AI behavior, simulation events, tests, and debugging tools should remain reproducible from explicit state.

### 4. Prefer data-driven systems
Game state, procedural generation, fixtures, exports, balancing data, and analysis paths should be represented in structured, inspectable data wherever practical. Use Polars, NumPy, arrays, typed records, or configuration files according to the access pattern and performance requirements.

### 5. Keep hot paths fast and explicit
Performance-sensitive systems should avoid accidental Python overhead. Use store-oriented access, spatial indexes, vectorized operations, Numba, caching, or compiled-style data layouts where profiling shows they matter. Do not optimize blindly; measure first, then optimize the actual bottleneck.

### 6. Maintain clear system boundaries
Major systems should have explicit ownership and entrypoints. Experimental systems may live in R&D areas, but production systems should have stable interfaces and clear integration paths. Avoid hidden cross-system coupling.

### 7. Make simulation player-facing
A simulation is valuable when the player can perceive, reason about, and act on it. Consequences should surface through visible state, tactical choices, companion behavior, environmental change, expedition reports, or meaningful UI feedback.

### 8. Treat knowledge as a first-class resource
Discovery should not be cosmetic. Evidence, inscriptions, maps, artifacts, route knowledge, ecological observations, and historical clues should feed back into survival, planning, research, safer travel, better assignments, and new options in the world.

### 9. Preserve responsibility as the central pressure
The player is not merely an adventurer. He is responsible for the expedition. Systems should reinforce tradeoffs between safety, labor, morale, knowledge, time, tools, and human capability.

### 10. Prefer boring correctness over clever fragility
Use straightforward, typed, testable code. Clever abstractions are acceptable only when they reduce repeated complexity without obscuring control flow, data ownership, or failure modes.

### 11. Document systems where they live
Each major component should explain its purpose, canonical entrypoints, data flow, dependencies, test commands, known limitations, and relationship to the overall game. Documentation should help future work continue from the current architecture rather than rediscover it.

### 12. Keep legacy paths retired
Old entrypoints and deprecated architecture should not be revived casually. New work should build through the documented canonical systems unless there is an explicit migration reason.
