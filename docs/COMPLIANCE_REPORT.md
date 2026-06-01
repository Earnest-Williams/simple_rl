# Compliance Report

Date: 2026-05-31

This report records the current repository state against `AGENTS.md`. It
supersedes earlier compliance notes that referenced a missing `.github/workflows/`
directory, a root-level `game_rng.py`, or a missing `dungeon_generator.py`.

## Current infrastructure status

| Area | Status | Current evidence |
| --- | --- | --- |
| Python target | Pass | `pyproject.toml` requires Python 3.11+. |
| Tool pinning | Pass | `pyproject.toml` pins `mypy==1.8.0`, `black==24.1.0`, and `ruff==0.1.14` in the `dev` extra. |
| Formatter config | Pass | `tool.black` and `tool.ruff` both use an 88-character line length and Python 3.11 target. |
| Strict typing config | Pass | `tool.mypy` enables strict mode and related strictness checks. |
| CI/workflows | Pass | `.github/workflows/llm_policy_sync_check.yml` and `.github/workflows/modernize.yml` exist. |
| Canonical RNG | Pass | `utils/game_rng.py` is the implementation and `worldgen/game_rng.py` re-exports it for worldgen compatibility. |
| Legacy dungeon-generator reference | Pass | No root-level `dungeon_generator.py` or `legacy/` tree exists in the current repository. |

## Deterministic-random status

The canonical rule remains: game logic must import `GameRNG` from
`utils.game_rng`. The current implementation file does not import Python's
`random` module. `scripts/check_deterministic_random.py` now parses Python AST
structure, skips its own source file, and ignores comments, docstrings, and
ordinary string literals. Alias expansion now preserves non-aliased root module
names for submodule imports, avoiding false positives from unrelated
`numpy.*` attribute calls, and checker/test locals are explicitly typed per the
repository style guide.

## Remaining compliance risks

- Whole-repository `mypy .` strict compliance still needs to be maintained as
  code changes land.
- Regex-based parsing remains present in a few utility/parser paths and should be
  reviewed case-by-case before broad rewrites.
- The deterministic-random checker is now reliable enough for local use, but it
  still needs CI wiring before it becomes a merge-blocking signal.

## Recommended follow-up

1. Run the repository-standard checks before PRs: `black .`, `ruff format .`,
   `ruff check .`, and `mypy .`.
2. Wire `scripts/check_deterministic_random.py` into CI now that it parses
   Python syntax instead of scanning raw text.
3. Keep this report regenerated when tool versions, workflows, checker behavior,
   or canonical RNG
   locations change.
