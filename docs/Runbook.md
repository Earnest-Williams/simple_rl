# Simple RL Runbook

This runbook is the canonical quick-start guide for running the repository's
main entrypoints and development harnesses. Use it with the component READMEs
when you need deeper subsystem-specific context.

## Environment setup

Simple RL targets Python 3.11 or newer. Create an isolated environment before
running tools or demos:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

The editable install pulls runtime dependencies from `pyproject.toml` and the
pinned development tools used by the repository checks.

## Main game and orchestration

| Task | Command | Notes |
| --- | --- | --- |
| Run the main entrypoint | `python main.py` | `main.py` forwards to the canonical orchestrator. |
| Run the orchestrator directly | `python orchestrator.py` | Generates a shaped dungeon Arrow file and optional simulation output. |
| Inspect orchestrator flags | `python orchestrator.py --help` | Use before changing defaults such as seed, dimensions, or simulation mode. |

The default orchestrator output is `generated_dungeon.arrow`. Treat generated
Arrow outputs as local artifacts unless a change explicitly documents why a
sample output should be checked in.

## Dungeon generation pipeline

| Task | Command | Notes |
| --- | --- | --- |
| Run the scripted dungeon pipeline | `cd Dungeon && ./run.sh` | Runs the root dungeon generation workflow from the component script. |
| Compile the dungeon package | `python -m compileall -q Dungeon` | Fast syntax check for generation code. |

Use `Dungeon/README.md` for algorithm details and generated debug-output notes.

## GOAP combat/survival testbed

| Task | Command | Notes |
| --- | --- | --- |
| Run headless auto harness | `cd auto && ./run.sh --mode headless` | Uses `python -m auto.main` from the repo root. |
| Run GUI auto harness | `cd auto && ./run.sh --mode gui` | Requires GUI-capable PySide6 environment. |
| Run regression helper | `python scripts/run_auto_regression.py` | Batch helper for repeatable auto simulations. |

The core GOAP planner is integrated under `game/ai/goap.py`; `auto/` remains a
tuning and simulation harness.

## Lighting, FOV, and memory

| Task | Command | Notes |
| --- | --- | --- |
| Run production light-leak diagnostics | `python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py` | Uses production `GameMap`, `LightContributionCache`, and `game.world.light_fov`. |
| Run targeted production lighting/FOV/memory tests | `python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/game/world/test_memory_traits.py tests/test_world_memory.py` | Covers migration parity checks. |
| Run lighting/FOV visual tool | `python -m tools.lighting_fov_tool.main` | Requires GUI support. |

Production rendering, light-aware FOV, and memory behavior live under
`engine/` and `game/world/`.

## Arrow playback and visual tools

| Task | Command | Notes |
| --- | --- | --- |
| Play a generated Arrow map | `python tools/play_from_arrow.py generated_dungeon.arrow` | Uses `config/config.yaml` and `config/keybindings.toml`. |
| Run lighting/FOV visual tool | `python -m tools.lighting_fov_tool.main` | Requires GUI support. |

## Asset generation

| Task | Command | Notes |
| --- | --- | --- |
| Regenerate glyph metadata | `python scripts/generate_glyphs.py` | Updates `fonts/glyphs.yaml` and `fonts/glyphs_report.txt`. |
| Check asset policy | Read `docs/Asset Pipeline.md` | Source of truth for generated font assets. |

## Standard repository checks

Run these before submitting code changes:

Use Black as the formatter and Ruff for linting checks.

```bash
black .
ruff format .
ruff check .
mypy .
python scripts/check_deterministic_random.py
pytest -q
```

For current check ownership and troubleshooting notes, see `docs/Testing.md`.
