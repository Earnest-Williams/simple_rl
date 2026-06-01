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
| Ruff formatting | `ruff format .` | Keeps Ruff's formatter output synchronized with local edits. |
| Ruff linting | `ruff check .` | Runs pycodestyle, pyflakes, isort, pyupgrade, bugbear, and simplify rules configured in `pyproject.toml`. |
| Strict typing | `mypy .` | Enforces the repository's strict typing configuration. |
| Deterministic randomness | `python scripts/check_deterministic_random.py` | Fails on direct nondeterministic randomness in game logic. |
| Unit tests | `pytest -q` | Runs the Python test suite. |
| Syntax smoke test | `python -m compileall -q .` | Catches parser/import-syntax blockers across Python files. |
| LLM policy sync | `python scripts/sync_llm_policy.py --check` | Confirms generated agent-policy copies match the source policy. |

## CI coverage

The repository currently has workflows for LLM policy synchronization and the
modernization pipeline. Local contributors should still run the required local
checks above because not every local quality gate is represented by CI yet.

Known CI follow-up items:

1. Wire `python scripts/check_deterministic_random.py` into CI now that it parses
   Python AST and has focused regression tests.
2. Ensure CI runs the same pinned `black`, `ruff`, and `mypy` versions declared
   in `pyproject.toml`.
3. Add a test job that installs `.[dev]` and runs `pytest -q`.
4. Keep any modernization job aligned with `pyupgrade --py311-plus`, Ruff fixes,
   and Black formatting.

## Current verification notes

The 2026-06-01 documentation follow-up recorded these local results in a
fully provisioned editable `.[dev]` environment:

- Markdown relative-link validation passed.
- `python -m compileall -q .` passed.
- `python scripts/sync_llm_policy.py --check` passed.
- `python scripts/check_deterministic_random.py` passed.
- `pytest -q` passed with 8 tests.
- `black --check .` and `ruff format --check .` still report pre-existing
  formatting drift outside these documentation changes.
- `ruff check .` still reports pre-existing lint issues, including undefined
  typing names and unused imports in R&D modules.
- `mypy .` still stops on a pre-existing duplicate-module mapping for
  `lights_dev/fov.py` before checking the rest of the tree.

## Troubleshooting

- If a check fails because dependencies are missing, reinstall with
  `pip install -e ".[dev]"` from the repository root.
- If GUI demos fail in a headless environment, treat that as an environment
  limitation and verify non-GUI checks instead.
- If deterministic-random checks fail, replace direct `random`, NumPy RNG,
  `os.urandom`, or `uuid.uuid4` use in game logic with `GameRNG` or move the
  code behind an explicitly non-game-logic boundary.
