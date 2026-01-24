# Simple RL LLM Style Guide

## Purpose (LLM-only)

This file is for **LLMs only**. It defines repo-wide engineering constraints and
output expectations. If instructions conflict, follow the **most restrictive**.

## Priority levels

* **Critical**: Must not be violated.
* **Strong**: Expected for almost all code; deviations require a reason.
* **Guideline**: Preferred default.

## 1. Critical engineering rules

### 1.1 Python target

* **Rule:** Target **Python 3.11+** across the repo.

### 1.2 Determinism

* **Rule:** Use `from utils.game_rng import GameRNG` for all randomness.
* **Rule:** Never use Python’s `random` module or NumPy RNG directly in game
  logic.

### 1.3 Formatting

* **Rule:** Format with `black` using an **88-character** line length.

### 1.4 Static typing

* **Rule:** All code must have explicit type annotations. No type inference.
* **Rule:** Use PEP 604 unions (`X | None`), never `Optional[X]`.
* **Rule:** Function signatures must be fully annotated, including `-> None` for
  void functions.
* **Rule:** Code must pass `mypy --strict`.
* **Rule:** Do not introduce `Any` unless there is no practical alternative, and
  isolate it as tightly as possible.

### 1.5 Data + performance primitives

* **Rule:** Prefer `pathlib.Path` over string paths for filesystem work.
* **Rule:** **Pandas is prohibited.** Use **Polars** for data
  manipulation/state.
* **Rule:** Use **Numba** for performance-critical loops/hot paths.
* **Rule:** For anything involving scale, prefer `mmap`, NumPy, Polars
  expressions, or other vectorized approaches. Avoid slow Python loops over
  large data.

### 1.6 Parsing and string rules

* **Rule:** Regex is a last resort. Prefer `pyparsing` or `pydantic` for
  structured parsing/validation.
* **Rule:** If an f-string expression becomes unclear on one line, precompute
  intermediate values into named variables.

### 1.7 Architecture

* **Rule:** Avoid object-oriented clutter. Prefer structural clarity, explicit
  data flow, and throughput-oriented design.

### 1.8 Constants

* **Rule:** Declare constant values at the top of the module (after docstring and
  imports, before any class or function definitions) and name them using
  `ALL_CAPS_WITH_UNDERSCORES`.
* **Rule:** For shared or numerous constants, create a dedicated `constants.py`
  (or `constants/` package) and import from there. Prefer this when:

  * A value is used by two or more modules.
  * A module would otherwise have many constants (roughly >10).
  * Constants represent domain/global configuration rather than module-specific
    settings.

* **Rule:** Use explicit type annotations and `typing.Final` for constants.
* **Rule:** Prefer immutable types for constants (`tuple`, `frozenset`,
  `MappingProxyType`) over mutable `list`/`dict`.
* **Rule:** Add a short inline comment describing purpose and units where
  relevant.
* **Rule:** Group related constants with a one-line header comment.
* **Rule:** If a shared constants module would introduce circular imports, split
  constants by package or keep truly local constants in the original module.
* **Rule:** Do not store secrets or environment-specific values in code
  constants; use environment/config instead.
* **Rule:** Constants must not be mutable runtime state.
* **Rule:** Consider a lightweight lint/CI check to enforce placement and
  `Final` annotations.

Example:

```python
from types import MappingProxyType
from typing import Final

MAX_RETRIES: Final[int] = 3  # max retries for network calls
DEFAULT_TIMEOUT_SECONDS: Final[float] = 5.0  # seconds; default network timeout
AGENT_NAMES: Final[tuple[str, ...]] = ("claude", "gpt", "bard")
AGENT_TIMEOUTS: Final[dict[str, float]] = MappingProxyType({"claude": 1.5})
```

### 1.9 LLM operating rules

* **Rule:** Do not invent APIs, files, classes, or configuration keys. Only use
  what exists in the repo or what you add explicitly.
* **Rule:** Prefer minimal diffs. Avoid drive-by refactors.
* **Rule:** Every code change must satisfy all **Critical** rules in this
  document.
* **Rule:** If you are uncertain about a requirement, stop and request the
  missing information rather than guessing.

## 2. Tooling and CI (Critical)

### 2.1 Tool version pinning

* **Rule:** `pyproject.toml` must pin **mypy**, **black**, and the repository
  linter versions (for example, ruff), and they must be consistent across
  developer machines and CI.
* **Rule:** CI must run the formatter, linter, and type checker in a way that
  matches local expectations.

## 3. Development workflow (Strong)

### 3.1 Keep changes tight

* Keep changes focused and well documented.
* Reuse helper functions and existing patterns where possible.

### 3.2 Tests

* Run `pytest` before submitting changes.
* Add tests for new features when feasible.
* Verify deterministic behavior with fixed RNG seeds where applicable.

### 3.3 Performance work

* For performance-critical changes, profile before and after (e.g. `cProfile`).
* Confirm Numba compilation and correctness.
* Test with realistic dataset sizes (e.g., large maps, 100+ entities).

### 3.4 Documentation

* When adding or changing behavior, update relevant docs in `docs/` and
  component README files.
* Document complex algorithms and design decisions with clear examples.

## 4. Project context (Guideline)

* This is a simulation-heavy roguelike/RPG research project emphasizing
  determinism, modularity, and high-performance Python.
* Key libraries and patterns:

  * Polars for state/dataframes.
  * Numba + NumPy for fast kernels and numerical work.
  * `GameRNG` for deterministic randomness.
