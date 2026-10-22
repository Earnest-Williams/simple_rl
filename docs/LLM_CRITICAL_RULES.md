# Simple RL — LLM / Agent Engineering Instructions

## Status and scope

This is the canonical instruction set for all LLMs, Codex agents, automated code assistants, and human contributors working in this repository.

These instructions apply repo-wide unless a more specific `AGENTS.md` exists in a subdirectory. If multiple instruction files apply, follow the most restrictive rule.

All generated agent instruction files must be synchronized from this source. Do not maintain conflicting copies.

## Priority levels

* **Critical:** Must not be violated.
* **Strong:** Expected for almost all code. Deviations require an explicit reason.
* **Guideline:** Preferred default.

## 1. Critical engineering rules

### 1.1 Python target

Target Python 3.11+ across the repository.

Use Python 3.11-compatible syntax and typing features, including PEP 604 and PEP 585.

### 1.2 Static typing

Static typing is mandatory.

All new or modified Python code must satisfy the following rules:

* Fully annotate every function and method signature.
* Include `-> None` for functions and methods that do not return a value.
* Use PEP 604 unions, for example `str | None`.
* Do not use `Optional[T]`.
* Use built-in generic types:

  * `list[str]`, not `typing.List[str]`
  * `dict[str, int]`, not `typing.Dict[str, int]`
  * `tuple[int, ...]`, not `typing.Tuple[int, ...]`
  * `set[str]`, not `typing.Set[str]`
* Do not import `List`, `Dict`, `Tuple`, `Set`, or `Optional` from `typing`.
* Import from `typing` only for names without built-in equivalents, such as:

  * `Final`
  * `TypeVar`
  * `Callable`
  * `Protocol`
  * `Literal`
  * `TypedDict`
  * `cast`
  * `TYPE_CHECKING`
* Avoid `Any`.
* If `Any` is unavoidable, isolate it to the smallest possible scope and add a short comment explaining why.
* Annotate module-level variables.
* Annotate constants.
* Annotate class attributes.
* Annotate empty collections, because their element types are otherwise ambiguous.

Local variable inference is allowed only when the inferred type is obvious from the right-hand side and `mypy --strict` accepts it.

Good:

```python
def load_names(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text().splitlines():
        names.append(line)
    return names
```

Good:

```python
count = len(items)
```

Bad:

```python
def load_names(path):
    names = []
    return names
```

Bad:

```python
from typing import Optional, List

def find_name(names: List[str]) -> Optional[str]:
    ...
```

Good:

```python
def find_name(names: list[str]) -> str | None:
    ...
```

### 1.3 Mypy enforcement

The repository is intended to pass strict mypy checking.

Run mypy before completing code changes.

Use:

```bash
python -m mypy .
```

However, some legacy modules may temporarily appear in a mypy `ignore_errors = true` override list.

Do not use that override list as permission to write weakly typed code.

For every Python file you create or modify:

* Ensure the file itself is fully typed.
* Do not add new files to an `ignore_errors = true` override.
* Do not expand existing `ignore_errors = true` overrides.
* If the edited file is already covered by `ignore_errors = true`, still make your changes strict-typed.
* When practical, remove the edited module from the override list and fix its mypy errors.
* If removing the override is too large for the current task, keep the diff focused and explicitly state that the pre-existing override remains.

A successful repository-wide `mypy .` run is not sufficient if the changed code is hidden behind `ignore_errors = true`.

### 1.4 Formatting and linting

Format Python code with Black using an 88-character line length.

Use Ruff for linting and import ordering.

Before completing a code task, run:

```bash
python -m black .
python -m ruff check .
python -m mypy .
```

If the repository uses a narrower command in CI, use the CI-equivalent command as well.

Do not claim the work is complete if formatting, linting, or type checking fails.

If a failure is caused by unrelated pre-existing code, say so clearly and include the failing command and relevant error summary.

### 1.5 Determinism

Use the repository deterministic RNG abstraction for all game-logic randomness:

```python
from utils.game_rng import GameRNG
```

Do not use Python’s `random` module directly in game logic.

Do not use NumPy RNGs directly in game logic.

### 1.6 Data and performance primitives

Prefer `pathlib.Path` over string paths for filesystem work.

Pandas is prohibited.

Use Polars for dataframe-style data manipulation and state.

Use Numba for performance-critical loops and hot paths when appropriate.

For scale-sensitive code, prefer one of:

* NumPy vectorization
* Polars expressions
* memory mapping
* compiled kernels
* other throughput-oriented designs

Avoid slow Python loops over large datasets.

### 1.7 Parsing and validation

Regex is a last resort for structured parsing.

Prefer `pyparsing` or `pydantic` for structured parsing, validation, and schema-like inputs.

Simple string operations are fine for simple string problems.

### 1.8 Strings and f-strings

Keep f-string expressions readable.

If an f-string expression becomes complex, precompute intermediate values into named variables.

Bad:

```python
message = f"{entity.name}: {world.tiles[entity.y][entity.x].terrain.name.lower().replace('_', ' ')}"
```

Good:

```python
terrain_name = world.tiles[entity.y][entity.x].terrain.name
display_name = terrain_name.lower().replace("_", " ")
message = f"{entity.name}: {display_name}"
```

### 1.9 Architecture

Avoid unnecessary object-oriented structure.

Prefer:

* explicit data flow
* small focused functions
* simple modules
* structural clarity
* throughput-oriented design

Do not introduce broad abstractions unless they remove real duplication or clarify an existing design problem.

### 1.10 Constants

Declare constants at the top of the module, after the module docstring and imports, before classes and functions.

Name constants with `ALL_CAPS_WITH_UNDERSCORES`.

Use `typing.Final` for constants.

Prefer immutable constant values:

* `tuple` instead of `list`
* `frozenset` instead of `set`
* `MappingProxyType` instead of mutable `dict` where immutability matters

Add a short inline comment for units or non-obvious purpose.

Good:

```python
from typing import Final

MAX_RETRIES: Final[int] = 3  # maximum retry attempts for transient failures
TILE_SIZE_PIXELS: Final[int] = 32  # rendered tile size in pixels
DIRECTIONS: Final[tuple[tuple[int, int], ...]] = (
    (0, -1),
    (1, 0),
    (0, 1),
    (-1, 0),
)
```

Use a dedicated `constants.py` or `constants/` package when:

* a value is shared by two or more modules
* a module would otherwise contain many constants
* constants represent domain-wide configuration rather than local implementation detail

Do not store secrets or environment-specific values as code constants.

Constants must not be mutable runtime state.

### 1.11 API and repository awareness

Do not invent APIs, files, classes, configuration keys, or command names.

Use what exists in the repository.

If you need a new API, file, class, or configuration key, add it explicitly in the same focused change.

Before modifying code, inspect the relevant existing files and patterns.

Prefer minimal diffs.

Avoid drive-by refactors.

Do not rewrite unrelated code.

### 1.12 Dependency changes

Do not add dependencies casually.

Before adding a dependency:

* Check whether the repository already has a suitable dependency.
* Prefer the standard library when it is sufficient.
* Keep dependency changes focused.
* Update project configuration and documentation if a dependency is added.

* Never use fallback patterns (e.g., `try ... except ImportError`) for core dependencies like `numba`, `numpy`, or `polars`. They are guaranteed to be available, and fallbacks only introduce new failure points and complication.

### 1.13 Documentation

When changing behavior, update relevant documentation.

When adding non-trivial algorithms, include clear examples or comments explaining the design.

Do not add noisy comments that merely restate the code.

## 2. Required completion checklist for code changes

Before saying a coding task is complete, verify the following:

* The diff is focused on the requested task.
* No unrelated refactors were introduced.
* All new and modified function signatures are fully typed.
* Void functions use `-> None`.
* No `Optional`, `List`, `Dict`, `Tuple`, or `Set` imports were introduced.
* No avoidable `Any` was introduced.
* Empty collections have explicit element types.
* Constants use `Final` where appropriate.
* Filesystem paths use `Path` where appropriate.
* Pandas was not introduced.
* Randomness in game logic uses `GameRNG`.
* Formatting, linting, and mypy commands were run.
* Any remaining failures are reported accurately and distinguished from the current change.

## 3. Commands

Use these commands unless project documentation or CI specifies a stricter equivalent:

```bash
python -m black .
python -m ruff check .
python -m mypy .
```

For targeted checks during development, prefer checking changed files or packages first, then run the full commands before completion when practical.

## 4. Project context

This is a simulation-heavy roguelike/RPG research project emphasizing:

* deterministic simulation
* modular systems
* high-performance Python
* explicit state
* typed interfaces
* reproducible behavior

Important project conventions:

* Polars for dataframe-style state and data manipulation.
* Numba and NumPy for fast numerical kernels.
* `GameRNG` for deterministic game-logic randomness.
* `pathlib.Path` for filesystem paths.
* Black, Ruff, and mypy for code quality gates.

## 5. Synchronization rule

This instruction set is the canonical source.

If the repository contains generated copies such as:

* `AGENTS.md`
* `.codex/AGENTS.md`
* `.github/copilot-instructions.md`
* `CLAUDE.md`
* `.gemini/styleguide.md`
* other LLM or agent instruction files

they must be generated from this same source or manually kept identical in substance.

Do not allow generated instruction files to drift.

Do not put stricter typing rules in one agent file and weaker typing rules in another.

Do not maintain contradictory command lists.

Do not maintain contradictory mypy expectations.

When updating these instructions, update the canonical source first, then regenerate or synchronize all derived instruction files.
