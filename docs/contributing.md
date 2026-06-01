# Contributing

Thank you for your interest in improving Simple RL. This document describes how to set up a development environment and the expectations for testing changes.

## Environment setup

1. Clone the repository and switch into its directory:
   ```bash
   git clone https://github.com/Earnest-Williams/simple_rl.git
   cd simple_rl
   ```

2. Create a Python 3.11+ virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -e .
   # OR for development with additional tools:
   pip install -e ".[dev]"
   ```

   `pyproject.toml` is the canonical pip dependency source. The obsolete
   `requirements.txt` placeholder was removed after downstream setup guidance
   moved to editable installs. An `environment.yml` is also provided for
   Conda/Mamba users:
   ```bash
   conda env create -f environment.yml
   conda activate simple_rl
   ```

## Development workflow

* Keep changes focused and well documented
* When adding code or content, update relevant documentation in `docs/` or component-specific README files
* Follow the existing code style (PEP 8, use `black` formatter with 88-character line limit)
* Add type annotations to all new code (required for `mypy --strict` compliance)
* Use the project's `GameRNG` class for all random number generation (never use Python's `random` module in game logic)
* Prefer Polars over Pandas for data manipulation
* Add Numba JIT compilation for performance-critical loops
* Reuse helper functions and existing patterns where possible

### Code Style Guidelines

* **Type Safety**: All code must have explicit type annotations
* **Determinism**: Use `from utils.game_rng import GameRNG` for random numbers
* **Performance**: Use Polars, Numba, and vectorized operations
* **Paths**: Use `pathlib.Path` for all filesystem interactions
* **Formatting**: Run `black .` before committing

### Before Submitting Changes

1. Format code: `black .`
2. Update documentation if needed
3. Verify type annotations if added new code

## Performance Considerations

For performance-critical changes:

1. Profile code with `cProfile` before and after changes
2. Verify Numba compilation works correctly
3. Test with realistic dataset sizes (100+ entities, large maps)
4. Check memory usage with `memory_profiler` if applicable

## Component-Specific Development

### Working on Dungeon Generation
* Test with: `cd Dungeon && ./run.sh`
* Verify output DataFrames have expected schema
* Ensure 3D depth information is preserved

### Working on AI Systems
* Production AI: Modify `game/ai/` directory
* Test AI behaviors: Use `auto/` test environment for isolated testing
* Community AI: Work in `ai/` directory (not yet integrated)

### Working on Rendering
* Test visual changes by running the main game
* Verify performance with `cProfile` for rendering pipeline
* Check compatibility with lighting and memory fade systems

### Working on Effects
* Update `game/effects/handlers.py` for new effect types
* Add effect definitions to `config/effects.yaml`
* Test with various target contexts

## Documentation Standards

When updating documentation:

* Keep README files in sync with code changes
* Update integration status when connecting new systems
* Document any breaking changes or API modifications
* Include code examples for new features
* Cross-reference related documentation files
* Mark experimental features clearly (⚠️ or 🔄 symbols)
