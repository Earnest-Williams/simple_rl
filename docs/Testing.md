# Testing, linting, and CI status

This document records the repository's expected local checks, what each check
covers, and current CI coverage gaps.

## Setup

Use Python 3.11 or newer and install the development extra before running the
full check suite:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Required local checks

| Check | Command | Purpose |
| --- | --- | --- |
| Black formatting | `black .` | Applies the repository's 88-column formatting policy. |
| Ruff linting | `ruff check .` | Runs pycodestyle, pyflakes, isort, pyupgrade, bugbear, and simplify rules configured in `pyproject.toml`. |
| Strict typing | `mypy .` | Enforces the repository's strict typing configuration for non-quarantined modules and verifies the documented historical backlog remains isolated. |
| Deterministic randomness | `python scripts/check_deterministic_random.py` | Fails on direct nondeterministic randomness in game logic. |
| Unit tests | `pytest -q` | Runs the Python test suite. |
| Syntax smoke test | `python -m compileall -q .` | Catches parser/import-syntax blockers across Python files. |
| LLM policy sync | `python scripts/sync_llm_policy.py --check` | Confirms generated agent-policy copies match the source policy. |

The deterministic-randomness checker intentionally treats `settlegen/` as an
approved subproject boundary. `settlegen` owns a seed-based deterministic NumPy
API; Simple RL integration code must derive that seed from `GameRNG` before
calling into it.

## CI coverage

The repository currently has workflows for LLM policy synchronization,
deterministic-randomness checking, and the modernization pipeline. Local
contributors should still run the required local checks above because not every
local quality gate is represented by CI yet.

Known CI follow-up items:

1. Ensure CI runs the same pinned `black`, `ruff`, and `mypy` versions declared
   in `pyproject.toml`.
2. Add a test job that installs `.[dev]` and runs `pytest -q`.
3. Keep any modernization job aligned with `pyupgrade --py311-plus`, Ruff fixes,
   and Black formatting.

## Verification snapshot and current caution

The 2026-06-01 final audit follow-up recorded these local results in a fully
provisioned editable `.[dev]` environment:

- `black --check .` passed.
- `ruff format --check .` passed.
- `ruff check .` passed.
- `python -m compileall -q .` passed.
- `python scripts/sync_llm_policy.py --check` passed.
- `python scripts/check_deterministic_random.py` passed.
- `pytest -q` passed with 16 tests.
- `mypy .` passed in that snapshot. Historical typing debt was intentionally
  quarantined with an explicit module list in `pyproject.toml` so future cleanup
  PRs could remove those overrides one module at a time.

Do not treat that snapshot as proof that repository-wide checks still pass
today. Re-run current checks before relying on it; later lighting-tool and
lighting-backend PRs have observed pre-existing strict mypy/stub issues in
lighting and glyph modules such as `engine/glyphs.py` and
`game/world/light_fov.py`. When a narrower command such as
`python -m mypy --strict tools/lighting_fov_tool/tool_window.py` reports errors
outside the edited file, record the exact upstream modules and keep the new code
strict-clean.

## Troubleshooting

- If a check fails because dependencies are missing, reinstall with
  `pip install -e ".[dev]"` from the repository root.
- If GUI demos fail in a headless environment, treat that as an environment
  limitation and verify non-GUI checks instead.
- If deterministic-random checks fail, replace direct `random`, NumPy RNG,
  `os.urandom`, or `uuid.uuid4` use in game logic with `GameRNG` or move the
  code behind an explicitly approved non-game-logic boundary.
