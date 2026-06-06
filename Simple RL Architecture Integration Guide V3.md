# simple_rl: Comprehensive Systems Architecture & Integration Guide (v3.0)

**Status:** Updated consolidated architecture guide  
**Basis:** Comparison of uploaded v2.0 and v2.1 drafts against current repository documentation and discoverable repository paths  
**Last updated:** 2026-06-04

---

## 0. Comparison and Reconciliation Summary

This version replaces the uploaded v2.0 and v2.1 architecture drafts with a grounded, repository-aligned guide.

### What was retained from v2.0

The v2.0 draft provided the stronger structure and better Markdown formatting. Its core framing remains broadly useful:

- The project is a simulation-heavy roguelike/RPG engine.
- `main.py` and `orchestrator.py` are the main entrypoints.
- `engine/`, `game/`, `Dungeon/`, `pathfinding/`, `magic/`, `utils/`, `skills/`, `game/skills/`, `auto/`, and `ai/` are distinct architectural areas.
- Rendering, FOV/lighting, AI, perception, deterministic RNG, skills, and procedural generation are first-class systems.
- The repository uses ADRs and status documents to prevent duplicate or experimental systems from being mistaken for production paths.

### What was retained from v2.1

The v2.1 draft attempted to expand the architecture with overland, research, morale, infrastructure, and gradient-driven magic systems. Only claims that are supported by current repository documentation or discoverable paths are retained:

- The existence of `worldgen/` as a cube-sphere procedural world-generation area.
- The importance of `magic/` and Brainfuck/tape-style backends.
- The importance of deterministic RNG internals and save/load support.
- The split between top-level `skills/` and game-facing `game/skills/`.

### What was removed or qualified

The following v2.1 claims were not supported by the current repository evidence checked during this update and should not be presented as current architecture:

- `infrastructure_system.py`
- `morale_system.py`
- `research_system.py`
- `wildness_gradient.py`
- `overland_core.py`
- Ancient Road networks, Waystations, road blockage mechanics, `TravelModifier` mutations
- `KnowledgeFragment` / Archive / recipe-array research integration
- SocialBond-driven labor halting and morale reweighting
- Doom Engine gradient mechanics that hybridize magic execution based on coordinates

These ideas may be valid future design concepts, but this guide treats them as **not current production architecture** unless they are later added to code, ADRs, status docs, or accepted design documents.

---

## 1. Executive Summary

`simple_rl` is a simulation-heavy roguelike/RPG research project focused on deterministic, high-performance, modular Python systems. Its production architecture combines:

- 3D cave generation with 2D raster output and preserved depth/height data.
- A main game engine with entity/component-style storage, turn processing, combat, equipment, movement, AI dispatch, effects, items, and world state.
- A rendering stack with tile rendering, entity rendering, lighting, FOV, memory/fog behavior, and SDL/PySide-adjacent tooling.
- AI systems that combine production GOAP, strategy/FSM-style behavior, species behavior modules, and perception facts.
- Sound and scent propagation concepts that feed AI perception and routing.
- A DCSS-inspired skill system with both reusable rule/data helpers and game-facing integration.
- A programmable magic/effects layer, currently in development, using Brainfuck/tape-style execution backends.
- A deterministic `GameRNG` abstraction used for gameplay, procedural generation, AI, combat, items, skills, effects, and simulation randomness.

The repository has evolved from multiple merged prototypes and now relies on documentation boundaries to distinguish production systems from R&D, historical notes, compatibility shims, and generated artifacts.

---

## 2. Repository-Level Architecture

### 2.1 Production and Integrated Areas

| Directory / File | Role | Current Architectural Meaning |
| --- | --- | --- |
| `main.py` | Primary command entrypoint | Forwards into the canonical orchestrated game/simulation flow. |
| `orchestrator.py` | Canonical orchestrator | Runs the shared dungeon/simulation pipeline and can emit `generated_dungeon.arrow`. |
| `Dungeon/` | Production cave generation | Canonical cave generator: graph generation, geometry processing, raster shaping, Arrow/Polars output. |
| `game/` | Main game engine | Owns production gameplay state, entities, combat, movement, AI dispatch, effects, items, and world behavior. |
| `engine/` | Presentation/runtime engine | Owns rendering, lighting accumulation, window management, input handling, and main-loop support. |
| `game/world/` | World-facing runtime logic | Owns `GameMap`, FOV, LOS, light-aware FOV, map memory, visibility, and terrain/world layers. |
| `pathfinding/` | Perception flow concepts | Owns canonical sound/scent flow concepts and helpers, despite the broad directory name. |
| `game/systems/pathfinding/` | Runtime movement/path helpers | Owns production flow-field pathfinding used by game systems. |
| `magic/` | Magic execution experiments | Hosts programmable spell/effect backends and executor logic. |
| `simulation/` | Zone scheduler | Integrated zone-based simulation support used by the game and harnesses. |
| `utils/` | Shared infrastructure | Owns canonical `GameRNG`, save/load helpers, shaped-map conversion, logging, and utilities. |
| `common/` | Shared constants and types | Centralized tuning, constants, material/feature enums, and grid aliases. |
| `config/` | Runtime configuration | YAML/TOML configuration for game systems, keybindings, effects, audio, etc. |
| `data/` | Runtime data | Lexica, templates, items, monsters, and other game data. |
| `worldgen/` | Macro world generation | Cube-sphere world-generation utilities and kernels. |
| `fonts/` | Asset outputs | Font/glyph assets and generated metadata governed by the asset pipeline. |
| `scripts/` | CLI and maintenance tools | Deterministic-random checker, glyph generator, regression helpers, policy sync, audits. |
| `tools/` | Development tools | Lighting/FOV visual tool, Arrow playback, style tooling, and local utilities. |
| `tests/` | Test suite | Unit and integration tests for production and migration boundaries. |
| `docs/` | Governance and architecture docs | Runbook, architecture map, ADRs, status pages, engineering rules, testing, deprecation policy. |

### 2.2 R&D and Harness Areas

| Directory | Role | Important Boundary |
| --- | --- | --- |
| `auto/` | GOAP simulation and tuning harness | Core GOAP has been promoted into `game/ai/`; `auto/` remains a development/testbed environment. |
| `ai/` | Community NPC AI R&D | `ai/v9.py` is retained as source material and should not be imported directly by production gameplay. |
| top-level `skills/` | Reusable skill rules and research helpers | Provides rule/data helpers; runtime hooks belong under `game/skills/` or documented game callers. |
| `notes/` | Historical scratch material | Not current implementation authority; useful content should migrate into curated docs, ADRs, or issues. |

---

## 3. Entrypoints and Runtime Flow

### 3.1 Main Entrypoints

The primary user-facing execution path is:

```bash
python main.py
```

`main.py` forwards to the canonical orchestrated game/simulation flow. For direct control over generation, dimensions, seed, and simulation flags:

```bash
python orchestrator.py
python orchestrator.py --help
```

The orchestrator's default generated output is `generated_dungeon.arrow`. This should normally be treated as a local generated artifact, not committed as a canonical fixture unless a specific change documents why the output belongs in version control.

### 3.2 High-Level Runtime Pipeline

```text
main.py
  -> orchestrator.py
      -> create/load GameRNG
      -> run Dungeon generation
      -> emit shaped dungeon Arrow / Polars data
      -> build or load GameMap
      -> initialize GameState
      -> start engine/main_loop.py
          -> input/action handling
          -> game systems update
          -> perception/FOV/lighting updates
          -> rendering
          -> audio/sound dispatch
          -> persistence/checkpoint hooks where applicable
```

### 3.3 Development Harnesses

| Task | Command |
| --- | --- |
| Main game | `python main.py` |
| Orchestrator | `python orchestrator.py` |
| Orchestrator help | `python orchestrator.py --help` |
| Dungeon pipeline | `cd Dungeon && ./run.sh` |
| GOAP headless harness | `cd auto && ./run.sh --mode headless` |
| GOAP GUI harness | `cd auto && ./run.sh --mode gui` |
| GOAP regression helper | `python scripts/run_auto_regression.py` |
| Lighting/FOV regression tests | `python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py` |
| Lighting/FOV visual tool | `python -m tools.lighting_fov_tool.main` |
| Arrow playback | `python tools/play_from_arrow.py generated_dungeon.arrow` |
| Glyph metadata generation | `python scripts/generate_glyphs.py` |

GUI tools require a GUI-capable environment.

---

## 4. Dungeon Generation System

### 4.1 Purpose

`Dungeon/` is the canonical production cave-generation pipeline. It generates complex cave networks, preserves 3D properties, and outputs data consumable by the game world.

### 4.2 Pipeline

```text
Dungeon/core.py
  -> raw cave backbone graph
Dungeon/processor.py
  -> augmented geometry and segment data
Dungeon/shaper.py
  -> rasterized grid, depth/height data, feature types, chamber IDs
  -> Polars DataFrame
  -> Arrow output
```

### 4.3 Core Generator: `Dungeon/core.py`

Responsibilities:

- Generates a branching cave backbone graph.
- Uses deterministic `GameRNG`.
- Uses probability-based growth with contextual triggers.
- Supports structural feature flags such as large rooms, cliff edges, and shaft openings.
- Uses spatial indexing, including KDTree-style convergence detection.
- Produces raw node graph data for downstream processing.

### 4.4 Processor: `Dungeon/processor.py`

Responsibilities:

- Consumes the raw graph.
- Computes segment geometry such as XY length, incline rate, and depth delta.
- Preserves feature flags.
- Acts as an intermediate layer for future geological or flow-analysis processing.

### 4.5 Shaper: `Dungeon/shaper.py`

Responsibilities:

- Rasterizes processed cave data into a 2D grid.
- Preserves 3D information such as floor depth, height, and ceiling depth.
- Applies cellular automata smoothing.
- Uses SciPy and Numba-oriented acceleration paths where appropriate.
- Assigns chamber IDs.
- Outputs a Polars DataFrame and Arrow file.

### 4.6 Output Contract

The shaped dungeon output is represented as map-like tabular data with fields such as:

- `x`, `y`
- `floor_depth`
- `height`
- `ceiling_depth`
- `material_id`
- `walkable`
- `chamber_id`
- `open_above`

This output bridges procedural generation and `GameMap` construction.

---

## 5. World Generation and Macro Topology

### 5.1 `worldgen/`

`worldgen/` owns macro-scale world-generation utilities, including cube-sphere topology and kernel-style numerical processing. It is distinct from `Dungeon/`, which owns localized cave/dungeon generation.

Representative areas include:

- `topology_cube_sphere.py`
- hydrology
- metadata/reporting
- validation
- coordinate utilities
- numerical kernels for advection, erosion, geometry, heap operations, noise, smoothing, and union-find

### 5.2 Boundary with `Dungeon/`

`worldgen/` should be treated as macro world-generation infrastructure. `Dungeon/` is the production local cave-generation pipeline.

Do not attribute unsupported overland gameplay systems to `worldgen/` unless those systems exist in the current code, status docs, or ADRs.

---

## 6. Game State, Entity Model, and Core Mechanics

### 6.1 `game/game_state.py`

`GameState` is the central production orchestration object for runtime gameplay. It coordinates:

- map state
- player and entity state
- items
- turns
- perception fields
- FOV and visibility
- AI scheduling
- system updates
- generated events and side effects

### 6.2 Entity Registry

`game/entities/registry.py` owns creation, destruction, and querying of entities. The architecture is ECS-like and data-oriented, using structured component and registry patterns rather than heavyweight inheritance.

Important supporting files include:

- `game/entities/components.py`
- `game/entities/template_registry.py`
- YAML-backed templates in `data/` or related configuration locations

### 6.3 Core Systems

`game/systems/` owns core gameplay mechanics. Important systems include:

| System | Responsibility |
| --- | --- |
| `combat_system.py` | Melee, weapons, hit calculations, damage, combat events. |
| `movement_system.py` | Collision, displacement, walkability checks, position updates. |
| `equipment_system.py` | Equipment slots, bonuses, encumbrance, item interactions. |
| `death_system.py` | Death handling, corpse/loot dropping, entity lifecycle effects. |
| `ai_system.py` | AI scheduling and action execution coordination. |
| `sound.py` | Runtime audio event dispatch and sound playback integration. |
| `magic_system_skill_integration.py` | Skill/magic system integration where applicable. |
| `pathfinding/flowfield.py` | Production flow-field pathfinding support. |

Unsupported v2.1 systems such as `infrastructure_system.py` and `morale_system.py` are not listed as current architecture.

---

## 7. Rendering, Lighting, FOV, and Memory

### 7.1 Rendering Ownership

The rendering stack is split between `engine/` and `game/world/`.

| Area | Responsibility |
| --- | --- |
| `engine/renderer.py` | Main composition and renderer-facing orchestration. |
| `engine/render_base_layers.py` | Terrain/base layer rendering. |
| `engine/render_entities.py` | Actor, item, and entity visual rendering. |
| `engine/render_lighting.py` | Production lighting accumulation and contribution caching. |
| `engine/window_manager.py` | SDL/PyGame-style window management and presentation. |
| `engine/window_manager_modules/` | Input handling, tileset management, UI overlays. |
| `game/world/fov.py` | Production gameplay FOV. |
| `game/world/los.py` | Line-of-sight checks. |
| `game/world/light_fov.py` | Advanced light-aware FOV. |
| `game/world/memory.py` | Map memory and memory-fade behavior. |

### 7.2 Render Pipeline

```text
GameState / GameMap / Entity Registry
  -> base terrain layers
  -> ground items
  -> entity sprites
  -> FOV / visibility masks
  -> lighting contribution buffers
  -> memory/fog treatment
  -> viewport composition
  -> window manager presentation
```

### 7.3 Lighting

`engine/render_lighting.py` owns production advanced lighting. Current architecture includes:

- side-aware light buffers
- per-light contribution caching
- deterministic additive blending
- invalidation using scene geometry versioning
- directional cones and channel masks where configured
- integration with FOV and memory behavior

### 7.4 FOV and LOS

Production world visibility is owned under `game/world/`.

New gameplay calls should use:

- `game/world/fov.py` for core gameplay FOV
- `game/world/los.py` for LOS checks
- `game/world/light_fov.py` for advanced light-aware FOV
- `engine/render_lighting.py` for advanced rendering/light accumulation

The `pathfinding/` package should not be used as a general visibility owner; it owns perception flow concepts.

---

## 8. Perception, Sound, Scent, and Pathfinding

### 8.1 Top-Level `pathfinding/`

Despite its broad name, top-level `pathfinding/` is primarily a perception simulation area. Its central module is:

```text
pathfinding/perception_systems.py
```

It owns sound/scent flow mechanics and helpers such as:

- `update_noise`
- `update_smell`
- `monster_perception`
- `choose_step_by_flow`

### 8.2 Production Flow Types

Production noise fields are stored by flow type. Current flow concepts include:

- `PASS_DOORS`
- `NO_DOORS`
- `REAL_NOISE`
- `MONSTER_NOISE`

These fields distinguish door-capable movement, door-blocked movement, real/player/world noise, and monster-originated noise.

### 8.3 Noise Semantics

Production noise semantics are loudest-event-wins for the authoritative pathfinding flow slice:

- All queued noise events may contribute to debug/legacy maps.
- Only the loudest queued noise event rebuilds the production pathfinding flow slice.
- If no noise events are queued, production noise costs reset to infinity.

The current production contract does not model arbitrary simultaneous per-source sound attribution.

### 8.4 Scent Semantics

Production scent uses Sil-style freshness stamps rather than a generic additive scent-intensity field.

Normal production turns append player scent through the `GameState` lifecycle. Explicit scent events remain supported for tests, legacy callers, scripted events, and future non-player scent mechanics.

### 8.5 Runtime Flow-Field Pathfinding

`game/systems/pathfinding/flowfield.py` owns production flow-field movement support. It uses Dijkstra-like integration fields and vector fields for multi-entity routing. This is separate from top-level `pathfinding/`, which owns perception fields.

---

## 9. AI Architecture

### 9.1 Production AI

Production gameplay AI belongs under:

```text
game/ai/
```

Important areas include:

| Module | Role |
| --- | --- |
| `goap.py` | Production GOAP planner. |
| `goap_adapter.py` | Adapts game state/perception to GOAP planning and execution. |
| `strategy.py` | Strategy/FSM-style behavior dispatch. |
| `perception.py` | AI-facing perception gathering and snapshots. |
| `ml_policy.py` | ML-policy-oriented decision support. |
| `bird.py`, `mammal.py`, `insect.py`, `plant.py`, `reptile.py` | Species or behavior-family modules. |
| `community.py`, `community_adapter.py` | Production-facing community-related integration points where present. |

### 9.2 GOAP Flow

```text
GameState
  -> gather perception facts
  -> AI system selects entities requiring decisions
  -> strategy or GOAP adapter maps state into AI facts
  -> GOAP planner builds or reuses a plan
  -> selected action is translated into game system calls
  -> movement/combat/effects/sound/perception updates follow
```

### 9.3 `auto/` Boundary

`auto/` is a GOAP simulation and tuning environment. It contains a standalone simulation runner, GUI, and development tools. It is not the production game loop.

Use `auto/` for:

- behavior tuning
- parallel simulations
- action-weight experimentation
- GUI visualization of AI plans
- profiling isolated AI behavior

Promote behavior into production by changing `game/ai/` or documented game-system callers, adding tests or harness coverage, and updating status docs when maturity changes.

### 9.4 `ai/` Boundary

The top-level `ai/` directory is retained R&D for community NPC AI concepts, particularly `ai/v9.py`.

It includes concepts such as:

- trait profiles
- needs
- fatigue and illness
- habit learning
- self-concept and cognitive dissonance
- experience memory
- daily planning

It should not be imported directly by production gameplay unless a specific module is promoted through a focused, tested integration.

---

## 10. Skills and Progression

### 10.1 Current Status

The skill system is integrated in dual-mode form. Vectorized skill storage and legacy compatibility shims coexist while callers migrate to the integrated model.

`docs/SKILL_SYSTEM_STATUS.md` is the source of truth for integration status.

### 10.2 Ownership Boundary

| Area | Ownership |
| --- | --- |
| `game/skills/` | Game-facing skill execution, integration points, XP distribution, entity state mutation, public game API. |
| top-level `skills/` | Reusable models, rule data, progression helpers, manuals, prerequisites, synergies, research/support code that does not own live game state. |

### 10.3 Game-Facing Skill System

`game/skills/` provides a DCSS-inspired classless progression system:

- 29 skills
- levels 0 through 27
- quadratic XP costs
- aptitudes
- manual and automatic training modes
- cross-training
- combat and magic effects
- target levels
- focused/disabled/enabled training states

Representative modules:

```text
game/skills/
  __init__.py
  models.py
  progression.py
  training.py
  effects.py
  system.py
  README.md
```

### 10.4 Top-Level Skill Helpers

Top-level `skills/` supports reusable and research-oriented mechanics, including:

- progression formulas
- cross-training matrices
- effects
- milestones
- prerequisites
- registry integration
- shapeshifting helpers
- reusable models and constants

Do not treat top-level `skills/` as the primary owner of live gameplay state.

---

## 11. Magic, Scripting, and Effects

### 11.1 `magic/`

The magic system is an in-development spell/effect framework with Brainfuck/tape-style execution backends.

Representative modules include:

- `magic/bf_backend.py`
- `magic/brainfuck_numba.py`
- `magic/executor.py`
- `magic/models.py`

### 11.2 `scripting_engine.py`

`scripting_engine.py` implements macro expansion and a Brainfuck interpreter foundation for spell-system experiments. The basic effect system is functional, but the full spell system remains planned/in development.

### 11.3 `game/effects/`

`game/effects/` owns game-facing effect execution and status management. It includes:

- context-based targeting
- cost checking
- status application
- effect handler registry
- passive effects
- cooldown support

### 11.4 Removed v2.1 Claim: Gradient-Modified Magic

No current evidence supports a production `wildness_gradient.py` or Doom Engine gradient that modifies Brainfuck execution based on spatial proximity. This guide therefore omits that as current architecture.

---

## 12. Audio and Sound

### 12.1 Runtime Sound

`game/systems/sound.py` owns runtime sound playback integration. It maps game events to sound behavior and handles interaction with the audio backend.

### 12.2 Audio Generation and Playback

`game/audio/` includes audio-related support such as synthesis or music modules where present. Audio remains conceptually distinct from perception noise:

| Concept | Owner | Meaning |
| --- | --- | --- |
| Runtime sound playback | `game/systems/sound.py`, `game/audio/` | What the player hears or what the engine plays. |
| AI noise perception | `pathfinding/perception_systems.py`, `game/ai/perception.py` | Noise fields and perception facts used by AI. |

Do not conflate playback audio with pathfinding/perception noise maps.

---

## 13. Deterministic RNG and Reproducibility

### 13.1 Canonical RNG

`utils/game_rng.py` owns `GameRNG`, the canonical deterministic random-number API.

All gameplay, generation, AI, combat, item, skill, effect, and simulation code that needs randomness must accept or own an explicit `GameRNG` instance.

Disallowed in game logic:

- direct `random`
- direct `numpy.random`
- `secrets`
- `os.urandom`
- direct `uuid.uuid4`

Exceptions belong only in clearly non-game-logic boundaries or inside the canonical RNG implementation.

### 13.2 Desired Properties

`GameRNG` supports:

- seeded reproducibility
- state save/load
- deterministic replay semantics
- weighted choice and sampling helpers
- dice rolling
- noise generation helpers
- metrics and cache behavior
- thread-safe access patterns

### 13.3 Determinism Gate

The repository includes:

```bash
python scripts/check_deterministic_random.py
```

This should be run before completing changes that touch gameplay, simulation, generation, AI, effects, items, skills, or systems likely to use randomness.

---

## 14. Persistence and Generated Artifacts

### 14.1 Save/Load

Persistence support is owned under `utils/` and related game-system save/load paths. Save data should preserve enough state to reproduce gameplay and simulation behavior, including deterministic RNG state where applicable.

### 14.2 Generated Artifacts

Generated files should not be committed unless documented as intentional. Examples of intentionally retained generated outputs may include asset metadata that runtime code reads or review artifacts that are expensive/noisy to regenerate.

Generated dungeon Arrow files are local artifacts by default.

### 14.3 Notes and Historical Material

`notes/` is historical scratch material. It is not current implementation authority. Useful content should move into:

- `docs/`
- ADRs
- component READMEs
- tracked issues
- current status pages

---

## 15. Engineering Standards

### 15.1 Python and Typing

The repository targets Python 3.11+.

Rules for new or modified code:

- Fully annotate every function and method signature.
- Include `-> None` for functions that do not return a value.
- Use PEP 604 unions: `str | None`, not `Optional[str]`.
- Use built-in generics: `list[str]`, `dict[str, int]`, etc.
- Avoid `Any`; isolate and explain unavoidable use.
- Annotate module-level variables, constants, class attributes, and empty collections.
- Prefer explicit, small, focused functions and straightforward data flow.

### 15.2 Data and Performance

Default choices:

- Polars for dataframe-style state and data manipulation.
- NumPy vectorization for dense numerical arrays.
- Numba for hot loops and kernels.
- `pathlib.Path` for filesystem paths.
- `msgpack`/`orjson` where fast serialization is appropriate.
- No Pandas in repository code.

### 15.3 Parsing

Regex is a last resort for structured parsing. Prefer:

- simple string operations for simple string problems
- `pyparsing` for grammar-like parsing
- `pydantic` for structured validation/schema-like inputs

### 15.4 Constants

Constants should:

- appear near the top of the module after imports
- use `ALL_CAPS_WITH_UNDERSCORES`
- use `typing.Final`
- prefer immutable values
- avoid storing secrets or environment-specific values

### 15.5 Architecture Style

The repository favors:

- deterministic explicit state
- data-oriented design
- small modules
- minimal, useful abstraction
- focused diffs
- no drive-by refactors
- no invented APIs, files, classes, or config keys

Before changing code, inspect existing files and follow established patterns.

---

## 16. Quality Gates and Testing

### 16.1 Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 16.2 Standard Local Checks

Run these before submitting code changes:

```bash
black .
ruff format .
ruff check .
mypy .
python scripts/check_deterministic_random.py
pytest -q
python -m compileall -q .
python scripts/sync_llm_policy.py --check
```

Depending on the task, targeted checks may be run first, but final completion should report the full relevant commands or clearly explain any environment limitations or pre-existing failures.

### 16.3 Known CI Caveat

Not every local quality gate is necessarily represented in CI. Local checks remain the standard for confidence.

---

## 17. Documentation Governance

### 17.1 Source-of-Truth Documents

| Topic | Source |
| --- | --- |
| Architecture map | `docs/ARCHITECTURE.md` |
| Engineering rules | `docs/ENGINEERING.md` and `docs/LLM_CRITICAL_RULES.md` |
| Run commands | `docs/RUNBOOK.md` |
| System maturity | `docs/CURRENT_STATUS.md` |
| Testing | `docs/TESTING.md` |
| Deprecation/archive policy | `docs/DEPRECATION_POLICY.md` |
| Skill status | `docs/SKILL_SYSTEM_STATUS.md` |
| ADR index | `docs/ADR/README.md` |

### 17.2 ADRs

Current ADRs establish boundaries for:

- canonical RNG ownership
- production AI vs. R&D AI
- skill-system ownership
- perception/FOV/LOS/lighting ownership

ADRs prevent compatibility shims, prototypes, and historical systems from being mistaken for canonical implementation paths.

### 17.3 Documentation Update Rule

When a subsystem changes maturity, gains or loses a runnable command, changes integration state, or receives a new canonical owner, update `docs/CURRENT_STATUS.md` or the relevant status document in the same focused change.

---

## 18. Component Integration Matrix

| Subsystem | Primary Components | Production Role | Notes |
| --- | --- | --- | --- |
| Main orchestration | `main.py`, `orchestrator.py`, `engine/main_loop.py` | Starts and coordinates runtime flow. | `main.py` forwards into the canonical orchestrated path. |
| Dungeon generation | `Dungeon/core.py`, `Dungeon/processor.py`, `Dungeon/shaper.py` | Produces shaped cave data with preserved depth/height and features. | Canonical local cave pipeline. |
| Macro world generation | `worldgen/` | Cube-sphere and macro world-generation utilities. | Do not attribute unsupported overland gameplay systems without code/docs. |
| Game state | `game/game_state.py` | Central runtime state and update coordination. | Integrates map, entities, systems, perception, AI, and turns. |
| Entity model | `game/entities/` | ECS-like entity registry and template management. | Uses structured components and data-oriented storage. |
| Combat/movement/equipment | `game/systems/combat_system.py`, `movement_system.py`, `equipment_system.py` | Core gameplay rules. | Mutates entity state through documented systems. |
| AI | `game/ai/`, `game/systems/ai_system.py` | Production decisions and action dispatch. | `auto/` informs tuning; production code belongs in `game/ai/`. |
| GOAP harness | `auto/` | R&D/testbed for GOAP training and visualization. | Not the production game loop. |
| Community AI R&D | `ai/` | Prototype source material for future community NPC behavior. | Do not import directly into production without promotion. |
| Perception | `pathfinding/perception_systems.py`, `game/ai/perception.py` | Sound/scent/FOV-derived AI facts. | Top-level `pathfinding/` owns perception flow concepts. |
| Runtime pathfinding | `game/systems/pathfinding/flowfield.py` | Flow-field routing for movement. | Separate from perception flow ownership. |
| FOV/LOS | `game/world/fov.py`, `game/world/los.py`, `game/world/light_fov.py` | Visibility and light-aware FOV. | Production world visibility lives under `game/world/`. |
| Rendering | `engine/renderer.py`, `render_base_layers.py`, `render_entities.py`, `render_lighting.py` | Tile/entity/light composition and viewport output. | Advanced lighting accumulation belongs in `engine/render_lighting.py`. |
| Memory/fog | `game/world/memory.py` | Map memory and memory fade behavior. | Renderer-adjacent but world-owned. |
| Skills | `game/skills/`, top-level `skills/` | Game-facing progression plus reusable skill rules. | Current status is centralized in `docs/SKILL_SYSTEM_STATUS.md`. |
| Magic/effects | `magic/`, `game/effects/`, `scripting_engine.py` | Spell/effect execution and status behavior. | Full spell system remains in development. |
| Audio | `game/audio/`, `game/systems/sound.py` | Playback and synthesized/music/audio cues. | Distinct from AI noise perception. |
| RNG | `utils/game_rng.py` | Canonical deterministic randomness. | Required for game logic randomness. |
| Persistence/utilities | `utils/` | Save/load and shared helpers. | Preserve deterministic replay semantics where applicable. |
| Config/data | `config/`, `data/` | Runtime configuration and game content. | Update when adding systems or entity/effect templates. |
| Tooling | `scripts/`, `tools/` | Maintenance, generation, diagnostics, playback. | Prefer documented scripts and current runbook commands. |
| Governance | `docs/`, `docs/ADR/` | Architecture decisions, status, testing, engineering rules. | Update status docs with maturity changes. |

---

## 19. Practical Guidance for Future Work

### 19.1 Adding Production AI Behavior

1. Inspect `game/ai/` and `game/systems/ai_system.py`.
2. Use `GameRNG` for randomness.
3. Do not import directly from top-level `ai/` unless promoting a module.
4. Add tests or a harness command.
5. Update `docs/CURRENT_STATUS.md` if maturity or ownership changes.

### 19.2 Changing Dungeon Generation

1. Work in `Dungeon/core.py`, `Dungeon/processor.py`, or `Dungeon/shaper.py`.
2. Preserve 3D properties and output schema expectations.
3. Run `cd Dungeon && ./run.sh`.
4. Verify generated DataFrame/Arrow shape and schema.
5. Keep generated outputs local unless intentionally documented.

### 19.3 Changing Rendering or Lighting

1. Use `engine/render_lighting.py` for production lighting changes.
2. Use `game/world/light_fov.py`, `fov.py`, and `los.py` for visibility changes.
3. Run lighting/FOV tests and diagnostics where relevant.
4. Avoid moving visibility behavior into unrelated modules.

### 19.4 Changing Skills

1. Use `game/skills/` for runtime hooks.
2. Use top-level `skills/` for reusable rule helpers not dependent on live game state.
3. Update `docs/SKILL_SYSTEM_STATUS.md` for integration changes.
4. Add or update skill tests.

### 19.5 Adding Randomness

1. Accept or pass a `GameRNG` instance.
2. Do not use direct nondeterministic APIs in game logic.
3. Run `python scripts/check_deterministic_random.py`.

### 19.6 Adding New Documents

1. Prefer `docs/`, a component README, an ADR, or a tracked issue.
2. Avoid adding new scratch notes under `notes/`.
3. Mark experimental/R&D content clearly.
4. Include runnable commands or deletion/promotion conditions for retained prototypes.

---

## 20. Current Architecture in One Sentence

`simple_rl` is a deterministic, high-performance roguelike/RPG simulation engine whose production path is centered on `Dungeon/` generation, `game/` state and systems, `engine/` rendering, `game/world/` visibility, `pathfinding/` perception flows, `game/ai/` production AI, `game/skills/` game-facing progression, `magic/` and `game/effects/` spell/effect execution, and `utils/game_rng.py` as the canonical reproducibility primitive.

---

## Appendix A: Unsupported v2.1 Claims to Track Separately

The following concepts should be tracked as speculative design ideas, not current architecture, unless they are added to code and documentation:

| Claim | Current Treatment |
| --- | --- |
| Ancient Road network | Unsupported as current architecture. |
| Waystations | Unsupported as current architecture. |
| `infrastructure_system.py` | Unsupported as current architecture. |
| `morale_system.py` | Unsupported as current architecture. |
| `research_system.py` | Unsupported as current architecture. |
| `wildness_gradient.py` | Unsupported as current architecture. |
| Doom Engine gradient spell hybridization | Unsupported as current architecture. |
| KnowledgeFragment Archive synthesis | Unsupported as current architecture. |
| SocialBond cascading labor stoppage | Unsupported as current architecture. |
| Overland scent gradients from expedition supply lines | Unsupported as current architecture. |

If these are desired roadmap items, promote them through design proposals, ADRs, issues, or implementation branches with explicit ownership and tests.
