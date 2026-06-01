# Current system status

This status matrix summarizes subsystem ownership, maturity, runnable commands,
integration state, and known blockers. It is intentionally concise; use the
linked component documentation for implementation details.

| System | Primary paths | Maturity | Runnable command | Integration state | Known blockers or follow-ups |
| --- | --- | --- | --- | --- | --- |
| Main orchestrator | `main.py`, `orchestrator.py` | Integrated | `python main.py` or `python orchestrator.py --help` | Canonical entrypoint for shared dungeon/simulation pipeline | Keep generated Arrow outputs local unless promoted as fixtures. |
| Dungeon generation | `Dungeon/` | Integrated | `cd Dungeon && ./run.sh` | Production cave-generation pipeline used by the orchestrator | Continue aligning docs and generated debug artifacts with current pipeline behavior. |
| Main game engine | `game/`, `engine/` | Integrated but evolving | `python main.py`; playback via `python tools/play_from_arrow.py generated_dungeon.arrow` | Owns production rendering, entities, combat, world state, AI dispatch, and effects | Needs stronger end-to-end test coverage and documented CI gates. |
| Deterministic RNG | `utils/game_rng.py`, `worldgen/game_rng.py` | Integrated | `python scripts/check_deterministic_random.py` | `utils.game_rng.GameRNG` is canonical; `worldgen/game_rng.py` is compatibility re-export | Wire checker into CI. |
| GOAP testbed | `auto/` | R&D plus integrated core planner | `cd auto && ./run.sh --mode headless` | `game/ai/goap.py` is integrated; `auto/` remains a tuning/simulation harness | Clarify long-term GUI and benchmark ownership. |
| Community AI | `ai/`, `game/ai/community*.py` | R&D | See `ai/README.md` | Advanced community behavior is not fully integrated into main gameplay | Needs ADR/status decision for production AI versus R&D AI. |
| Lighting/FOV R&D | `lights_dev/` | R&D | `cd lights_dev && python main_game.py` | Experimental; production rendering lives in `engine/` and `game/world/` | Decide which algorithms graduate into production and which remain archived. |
| Perception and pathfinding | `pathfinding/`, `game/world/`, `game/systems/pathfinding/` | Mixed integrated/R&D | See component READMEs | Sound/scent concepts feed AI; world FOV and LOS live under `game/world/` | Needs ADR for canonical perception/FOV boundaries. |
| Skill systems | `skills/`, `game/skills/`, `docs/SKILL_SYSTEM_STATUS.md` | Mixed integrated/R&D | See skill-system docs | Current status is centralized in `docs/SKILL_SYSTEM_STATUS.md` | Continue reducing duplicate or stale integration claims. |
| Magic and scripting | `magic/`, `scripting_engine.py` | In development | See module docs and tests as added | Foundation for spell/effect experiments | Needs integration plan and test coverage before production claims. |
| Asset pipeline | `fonts/`, `scripts/generate_glyphs.py`, `docs/ASSET_PIPELINE.md` | Documented pipeline | `python scripts/generate_glyphs.py` | Generated metadata and selected previews are intentionally checked in | Keep generated-file policy synchronized with asset changes. |
| Notes and scratch material | `notes/` | Historical | None | Not production documentation | Migrate useful content into curated docs or delete/archive scratch files. |

## Status update policy

Update this file when a subsystem changes maturity, gains or loses a runnable
entrypoint, moves ownership, or receives a new canonical documentation source.
