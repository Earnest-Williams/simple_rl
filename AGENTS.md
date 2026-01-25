# Simple RL — AGENTS.md

> For human contributors and automated code-assist agents. If instructions conflict,
> follow the most restrictive rule.

## Purpose
This document defines repository-wide engineering constraints, LLM operating rules,
and contributor ergonomics for *Simple RL* — a high-performance, deterministic,
simulation-heavy roguelike. **Critical** rules are non-negotiable.

## Priority levels
* **Critical** — Must not be violated.
* **Strong** — Expected for most code; deviations require explanation in the PR.
* **Guideline** — Preferred default.

---

## 1. Critical engineering rules

### 1.1 Python target
* **Rule:** Target **Python 3.11+**. Use Python 3.11 language and typing features (PEP 604, PEP 585, etc.). (See `pyproject.toml`.)

### 1.2 Determinism
* **Rule:** Use `from utils.game_rng import GameRNG` for all randomness in game logic and deterministic tests. Do not use `random` or NumPy RNGs directly for game logic.

### 1.3 Formatting
* **Rule:** Format with `black` configured for **88-character** line length. CI and local dev must run the same commands.

### 1.4 Static typing (CRITICAL)
* **Rule:** All code must have explicit type annotations; function signatures must be fully annotated (including `-> None`) and pass `mypy --strict`.

* **Rule (PEP 585 — CRITICAL):** Always use built-in generic types for annotations (e.g., `list[str]`, `dict[str, int]`, `tuple[int, ...]`, `set[str]`). Do **not** use `typing.List`, `typing.Dict`, or `typing.Tuple`. Import from `typing` only for names without builtin equivalents (e.g., `TypeVar`, `Callable`, `Protocol`, `Literal`, `TYPE_CHECKING`).

  **LLM / contributor guidance:**
  1. Replace `List`, `Dict`, `Tuple`, `Set`, etc. with `list`, `dict`, `tuple`, `set`.
  2. Remove these names from `from typing import ...` lines; consolidate `from typing import ...` into a single line per module with only required names.
  3. Use `from __future__ import annotations` when appropriate.
  4. After edits, run `black .`, `ruff format .`, `ruff check .`, `mypy .` and fix failures.

  **Example:**
  ```py
  # Bad
  from typing import List, Dict

  def foo(xs: List[str]) -> Dict[str, int]:
      ...

  # Good
  def foo(xs: list[str]) -> dict[str, int]:
      ...
  ```

### 1.5 Tool version pinning
* **Rule:** Pin `mypy`, `black`, `ruff`, and other tools in `pyproject.toml`. CI must run same pinned versions.

### 1.6 Performance & data primitives
* **Rule:** Use `pathlib.Path`. Pandas is prohibited — use Polars. Use Numba for hot loops. For scale, prefer vectorized, mmap, or NumPy approaches. Avoid Python loops over massive datasets.

### 1.7 Parsing & strings
* **Rule:** Prefer `pyparsing` or `pydantic` for structured parsing. Avoid complex regex as first choice. Precompute complex f-string expressions into named variables.

### 1.8 Architecture & constants
* **Rule:** Favor structural clarity and throughput over unnecessary OOP. Define constants at module top, use `typing.Final`, and prefer immutable types.

### 1.9 LLM operating rules (CRITICAL)
* **Rule:** Do not invent APIs, files, or configuration keys. Use only what exists or what you add via focused changes. Every change must satisfy Critical rules. If uncertain, stop and request clarification.

---

## 2. Tooling & CI (CRITICAL)

### 2.1 Dev dependencies & venv
Use a venv for development:
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\Activate.ps1  # Windows PowerShell
pip install -e ".[dev]"
```
Pinned dev tools are in `pyproject.toml`.

### 2.2 Formatting & lint commands
Local commands:
```bash
black .
ruff format .
ruff check .
mypy .
```
CI must run the same.

### 2.3 Enforce PEP-585 automatically (CRITICAL)
Add `pyupgrade` and a small check script to fail CI on legacy `typing.List`/`typing.Dict`/`typing.Tuple` uses.

Add `pyupgrade --py311-plus -r .` to modernization pipeline and `ruff --fix` + `black` for cleanup.

---

## 3. Development workflow (STRONG)

### 3.1 Repository layout & imports (CRITICAL)
Canonical layout:
```
.
├─ README.md
├─ AGENTS.md
├─ pyproject.toml
├─ game/
├─ Dungeon/
├─ ai/
├─ utils/
├─ tests/
└─ scripts/
```

Tests go in `tests/` and mirror package structure; tests should use absolute imports.

Do not add `__init__.py` under `tests/`.

### 3.2 Tests & determinism
Use `pytest`. Tests must be deterministic — use `GameRNG` with fixed seeds. Treat warnings as errors in CI.

### 3.3 PR checklist
Before PR:
- [ ] `black .` and `ruff format .` run cleanly.
- [ ] `ruff check .` and `mypy .` produce no errors.
- [ ] `pytest` passes.
- [ ] Documentation updated for behavior changes.
- [ ] Diffs focused and small.

---

## 4. LLM edit hygiene (for Codex / Gemini / other agents)

1. Consolidate `from typing import ...` into one line with only required names.
2. Prefer PEP-585 builtins. Remove `List`/`Dict`/`Tuple` imports and uses.
3. Run formatters and typechecker after edits.
4. Avoid drive-by refactors — if you must modernize widely, do a single modernization PR (`pyupgrade` + `ruff` + `black`) and document it.

---

## 5. Appendix: Enforcement snippets & examples

(Place suggested scripts under `scripts/` and CI hooks / pre-commit as shown in repo addenda).

---

## 6. Migration plan

1. Add `pyupgrade` to dev deps.
2. Add `scripts/check_pep585.py` to CI & pre-commit.
3. Create modernization branch and run `pyupgrade --py311-plus -r .`, `python scripts/cleanup_typing_imports.py`, `ruff --fix .`, `black .`, `mypy .`, `pytest`.
4. Commit and open a PR describing the codemod.
