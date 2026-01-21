# LLM + Human Style Guide (Simple RL)

## 0. Scope and priority

This document is the single source of truth for code style and engineering constraints for this repository.

**Severity levels:**

* **Critical**: Must not be violated. Fix before merging.
* **Strong**: Expected for almost all code. Deviations require a clear reason.
* **Guideline**: Preferable defaults.

If two rules conflict, follow the **more restrictive** rule.

## 1. Baselines (Critical)

### 1.1 Python target (Critical)

* **Rule:** Target **Python 3.11+** across the repo.

### 1.2 Determinism (Critical)

* **Rule:** Use `from utils.game_rng import GameRNG` for all randomness.
* **Rule:** Never use Python’s `random` module or NumPy RNG directly in game logic.

### 1.3 Formatting (Critical)

* **Rule:** Format with `black` using an **88-character** line length.

### 1.4 Static typing (Critical)

* **Rule:** All code must have explicit type annotations. No type inference.
* **Rule:** Use PEP 604 unions (`X | None`), never `Optional[X]`.
* **Rule:** Function signatures must be fully annotated, including `-> None` for void functions.
* **Rule:** Code must pass `mypy --strict`.
* **Rule:** Do not introduce `Any` unless there is no practical alternative, and isolate it as tightly as possible.

### 1.5 Data + performance primitives (Critical)

* **Rule:** Prefer `pathlib.Path` over string paths for filesystem work.
* **Rule:** **Pandas is prohibited.** Use **Polars** for data manipulation/state.
* **Rule:** Use **Numba** for performance-critical loops/hot paths.
* **Rule:** For anything involving scale, prefer `mmap`, NumPy, Polars expressions, or other vectorized approaches. Avoid slow Python loops over large data.

### 1.6 Parsing and string rules (Critical)

* **Rule:** Regex is a last resort. Prefer `pyparsing` or `pydantic` for structured parsing/validation.
* **Rule:** If an f-string expression becomes unclear on one line, precompute intermediate values into named variables.

### 1.7 Architecture (Critical)

* **Rule:** Avoid object-oriented clutter. Prefer structural clarity, explicit data flow, and throughput-oriented design.

## 2. Tooling and CI (Critical)

### 2.1 Tool version pinning (Critical)

* **Rule:** `pyproject.toml` must pin **mypy**, **black**, and the repository linter versions (for example, ruff), and they must be consistent across developer machines and CI.
* **Rule:** CI must run the formatter, linter, and type checker in a way that matches local expectations.

## 3. Development workflow (Strong)

### 3.1 Keep changes tight (Strong)

* Keep changes focused and well documented.
* Reuse helper functions and existing patterns where possible.

### 3.2 Tests (Strong)

* Run `pytest` before submitting changes.
* Add tests for new features when feasible.
* Verify deterministic behavior with fixed RNG seeds where applicable.

### 3.3 Performance work (Strong)

* For performance-critical changes, profile before and after (e.g. `cProfile`).
* Confirm Numba compilation and correctness.
* Test with realistic dataset sizes (e.g., large maps, 100+ entities).

### 3.4 Documentation (Strong)

* When adding or changing behavior, update relevant docs in `docs/` and component README files.
* Document complex algorithms and design decisions with clear examples.

## 4. Project context for LLMs (Guideline)

* This is a simulation-heavy roguelike/RPG research project emphasizing determinism, modularity, and high-performance Python.
* Key libraries and patterns:

  * Polars for state/dataframes.
  * Numba + NumPy for fast kernels and numerical work.
  * `GameRNG` for deterministic randomness.

## 5. LLM operating rules (Critical)

These rules exist to prevent incorrect or low-quality automated edits.

* **Rule:** Do not invent APIs, files, classes, or configuration keys. Only use what exists in the repo or what you add explicitly.
* **Rule:** Prefer minimal diffs. Avoid drive-by refactors.
* **Rule:** Every code change must satisfy all **Critical** rules in this document.
* **Rule:** If you are uncertain about a requirement, stop and request the missing information rather than guessing.
