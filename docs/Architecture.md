# Architecture Overview

High-level map of the Simple RL codebase.  Each module has its own
`README.md` with detailed documentation; this file provides cross-references.

## Module map

| Directory | Purpose | README |
|-----------|---------|--------|
| `Dungeon/` | Procedural cave generation (Core → Processor → Shaper) | [`Dungeon/README.md`](../Dungeon/README.md) |
| `ai/` | Community NPC AI with traits, habits, needs | [`ai/README.md`](../ai/README.md) |
| `auto/` | GOAP AI test environment & simulation GUI | [`auto/README.md`](../auto/README.md) |
| `common/` | Shared constants, types, and tuning values | — |
| `config/` | YAML/TOML game configuration files | — |
| `data/` | Runtime data (lexica, templates, items, monsters) | — |
| `engine/` | Rendering, lighting, FOV, window management | — |
| `game/` | Main game engine: combat, movement, AI, effects, entities, world | — |
| `game/skills/` | Skill system integration with game engine | [`game/skills/README.md`](../game/skills/README.md) |
| `magic/` | Spell system with Brainfuck interpreter backends | — |
| `pathfinding/` | Perception systems: noise & scent propagation | [`pathfinding/README.md`](../pathfinding/README.md) |
| `scripts/` | CLI tools, validators, linters, sync scripts | — |
| `simulation/` | Zone-based simulation scheduler | — |
| `skills/` | Standalone 29-skill DCSS-style progression system | [`skills/README.md`](../skills/README.md) |
| `tools/` | Development tooling (style scripts, utilities) | — |
| `utils/` | Shared utilities: GameRNG, helpers, savegame, logging | [`utils/README.md`](../utils/README.md) |
| `worldgen/` | Cube-sphere procedural world generation | — |

## Key data flows

```
orchestrator.py
  ├─ Dungeon/ (cave generation) → Polars IPC
  ├─ utils/shaped_map.py → GameMap
  ├─ engine/ (rendering pipeline)
  │    ├─ render_lighting.py (production lighting)
  │    ├─ render_entities.py (items, NPCs)
  │    └─ renderer.py (compositing)
  ├─ game/world/
  │    ├─ light_fov.py (advanced light-aware FOV)
  │    └─ memory.py (map memory fade and traits)
  ├─ game/ (turn processing)
  │    ├─ game_state.py (central state)
  │    ├─ systems/ (combat, movement, sound, AI)
  │    └─ ai/ (GOAP, strategy, species behaviors)
  └─ simulation/ (zone scheduler)
```

## Shared infrastructure

- **`common/tuning.py`** — Cross-cutting numeric constants (see
  [`docs/Engineering.md`](./Engineering.md))
- **`common/constants.py`** — Material and feature-type enums
- **`common/types.py`** — Grid type aliases
- **`utils/game_rng.py`** — Deterministic RNG (used everywhere)
- **`skills/constants.py`** — Skill-balance tuning parameters

## Documentation index

| Document | Location |
|----------|----------|
| Engineering rules | [`docs/Engineering.md`](./Engineering.md) |
| LLM critical rules | [`docs/LLM Critical Rules.md`](./LLM%20Critical%20Rules.md) |
| Architecture (this file) | [`docs/Architecture.md`](./Architecture.md) |
| Changelog | [`docs/Changelog.md`](./Changelog.md) |
| Systems inventory | [`docs/Systems Inventory.md`](./Systems%20Inventory.md) |
| Performance analysis | [`docs/Performance Analysis.md`](./Performance%20Analysis.md) |
| Compliance report | [`docs/Compliance Report.md`](./Compliance%20Report.md) |
| Rendering | [`docs/Rendering.md`](./Rendering.md) |
| Sound system | [`docs/Sound System.md`](./Sound%20System.md) |
| Modding guide | [`docs/Modding.md`](./Modding.md) |
| World gen design | [`docs/World Generator Design Proposal.md`](./World%20Generator%20Design%20Proposal.md) |
| Skill system docs | [`docs/Skill System Evaluation.md`](./Skill%20System%20Evaluation.md) |
