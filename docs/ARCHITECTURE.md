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
| `lights_dev/` | R&D for lighting, FOV, memory fade (Numba) | [`lights_dev/README.md`](../lights_dev/README.md) |
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
  │    ├─ render_lighting.py (FOV, memory fade)
  │    ├─ render_entities.py (items, NPCs)
  │    └─ renderer.py (compositing)
  ├─ game/ (turn processing)
  │    ├─ game_state.py (central state)
  │    ├─ systems/ (combat, movement, sound, AI)
  │    └─ ai/ (GOAP, strategy, species behaviors)
  └─ simulation/ (zone scheduler)
```

## Shared infrastructure

- **`common/tuning.py`** — Cross-cutting numeric constants (see
  [`docs/ENGINEERING.md`](./ENGINEERING.md))
- **`common/constants.py`** — Material and feature-type enums
- **`common/types.py`** — Grid type aliases
- **`utils/game_rng.py`** — Deterministic RNG (used everywhere)
- **`skills/constants.py`** — Skill-balance tuning parameters

## Documentation index

| Document | Location |
|----------|----------|
| Engineering rules | [`docs/ENGINEERING.md`](./ENGINEERING.md) |
| LLM critical rules | [`docs/LLM_CRITICAL_RULES.md`](./LLM_CRITICAL_RULES.md) |
| Architecture (this file) | [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) |
| Changelog | [`docs/CHANGELOG.md`](./CHANGELOG.md) |
| Systems inventory | [`docs/SYSTEMS_INVENTORY.md`](./SYSTEMS_INVENTORY.md) |
| Performance analysis | [`docs/PERFORMANCE_ANALYSIS.md`](./PERFORMANCE_ANALYSIS.md) |
| Compliance report | [`docs/COMPLIANCE_REPORT.md`](./COMPLIANCE_REPORT.md) |
| Rendering | [`docs/rendering.md`](./rendering.md) |
| Sound system | [`docs/sound_system.md`](./sound_system.md) |
| Modding guide | [`docs/modding.md`](./modding.md) |
| World gen design | [`docs/World_generator_design_proposal.md`](./World_generator_design_proposal.md) |
| Skill system docs | [`docs/SKILL_SYSTEM_EVALUATION.md`](./SKILL_SYSTEM_EVALUATION.md) |
