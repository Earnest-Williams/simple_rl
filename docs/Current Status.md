# Current system status

This status matrix summarizes subsystem ownership, maturity, runnable commands,
integration state, and known blockers. It is intentionally concise; use the
linked component documentation for implementation details.

| System | Primary paths | Maturity | Runnable command | Integration state | Known blockers or follow-ups |
| --- | --- | --- | --- | --- | --- |
| Main orchestrator | `main.py`, `orchestrator.py` | Integrated | `python main.py` or `python orchestrator.py --help` | Canonical entrypoint for shared dungeon/simulation pipeline | Keep generated Arrow outputs local unless promoted as fixtures. |
| Dungeon generation | `Dungeon/` | Integrated | `cd Dungeon && ./run.sh` | Production cave-generation pipeline used by the orchestrator | Continue aligning docs and generated debug artifacts with current pipeline behavior. |
| Main game engine | `game/`, `engine/` | Integrated but evolving | `python main.py`; playback via `python tools/play_from_arrow.py generated_dungeon.arrow` | Owns production rendering, entities, combat, world state, AI dispatch, and effects | Needs stronger end-to-end test coverage and documented CI gates. |
| Deterministic RNG | `utils/game_rng.py`, `docs/ADR/0001-canonical-rng.md` | Integrated | `python scripts/check_deterministic_random.py` | `utils.game_rng.GameRNG` is canonical; legacy RNG re-exports are removed | Keep CI and local checker behavior synchronized. |
| GOAP testbed | `auto/` | R&D plus integrated core planner | `cd auto && ./run.sh --mode headless` | `game/ai/goap.py` is integrated; `auto/` remains a tuning/simulation harness | Clarify long-term GUI and benchmark ownership. |
| Community AI | `ai/`, `game/ai/community*.py`, `docs/ADR/0002-ai-boundaries.md` | R&D | See `ai/README.md` | `ai/v9.py` is retained as source material; production gameplay should use `game/ai/` and integrated GOAP APIs | Promote features into `game/ai/` through focused, tested integration patches, then delete or split the prototype. |
| Lighting/FOV | `game/world/light_fov.py`, `engine/render_lighting.py`, `docs/ADR/0004-perception-fov-boundaries.md` | Integrated | None | Advanced shadowcasting, directional lighting, and height/cone illumination are fully integrated into production rendering | None |
| Perception and pathfinding | `pathfinding/`, `game/world/`, `game/systems/pathfinding/`, `docs/ADR/0004-perception-fov-boundaries.md` | Mixed integrated/R&D | See component READMEs | Sound/scent concepts feed AI; world FOV and LOS live under `game/world/` | Keep production calls on documented canonical APIs. |
| Overland generation | `worldgen/overland/`, `tools/generate_overland.py`, `tools/inspect_overland.py` | Evolving integrated subsystem | `python tools/generate_overland.py --help`; `pytest -q tests/test_overland_integration.py` | Overland-first terrain, connected hydrology, starting-region contract (with RouteSegmentState, evidence_tags, repair_cost), runtime OverlandMapMetadata sidecar attached to `GameMap.overland_metadata`, deterministic repair simulation in routes.py, route segments and transitions with evidence_tags shape exposed in `overland_metadata.json`, CLI inspect subcommand support for evidence views, settlement roads using CLEAR/REPAIRED states, actor_traversal.py now consults metadata for state-based costs; Option A, Option B, and Option C complete. Phase 5+ verified. Planning source is `docs/Overland Roadmap.md`. | Next: richer evidence in runtime survey systems. |
| First playable expedition loop | `game/expedition/`, overland runtime UI, transition handling | Planned / in progress | `python tools/play_game.py --first-playable` | Binds starting port, survey, route, blockage, cave transition, and return condition into one playable loop | Track against [First Playable Expedition Loop.md](First%20Playable%20Expedition%20Loop.md) |
| Skill systems | `skills/`, `game/skills/`, `docs/Skill System Status.md`, `docs/ADR/0003-skill-system-boundaries.md` | Mixed integrated/R&D | See skill-system docs | Current status is centralized in `docs/Skill System Status.md` | Continue reducing duplicate or stale integration claims. |
| Magic and scripting | `magic/`, `scripting_engine.py`, `docs/ADR/0007-magic-work-runtime-boundaries.md` | In development | `pytest -q tests/test_magic_work_parser.py tests/test_magic_runtime_boundary.py` | Parser/model work and executable runtime work have an explicit boundary; executor dispatch and runtime requirement checks have focused tests | Add a small game-facing cast/work command wrapper before broader spell catalogue work. |
| Asset pipeline | `fonts/`, `scripts/generate_glyphs.py`, `docs/Asset Pipeline.md` | Documented pipeline | `python scripts/generate_glyphs.py` | Generated metadata and selected previews are intentionally checked in | Keep generated-file policy synchronized with asset changes. |
| Notes and scratch material | `notes/`, `notes/README.md`, `docs/Deprecation Policy.md` | Historical | None | Not production documentation; the obsolete `notes/code_basicrl.txt` index has been removed | Retain only while useful content is migrated into curated docs or issues. |

## Status update policy

Update this file when a subsystem changes maturity, gains or loses a runnable
entrypoint, moves ownership, or receives a new canonical documentation source.
