## [Unreleased] - Fixes

### Fixed
- Flow-field pathfinding (`game/systems/pathfinding/flowfield.py`): the Dijkstra loop dropped live cells because of a float64/float32 comparison, leaving much of the map unreached; it now runs as a Numba kernel (~74x faster turns in `bench/bench_advance_turn.py`).
- `worldgen/kernels/heap.py`: keyword-only parameters could not be bound by Numba 0.68, which broke `worldgen.hydrology.build_flow_direction`.
- Brainfuck magic (`magic/brainfuck_numba.py`): step-limit results are no longer re-run in pure Python on a dirty tape; sandbox CPU and address-space limits now apply on top of the worker's start-up usage (previously they sat below the post-import footprint, so compiled runs could fail to allocate and silently fell back to pure Python); a worker that dies without replying returns `sandbox_execution_failed` instead of raising `EOFError`.
- Line of sight: the fallback used when `liblos.so` is not built is now a Numba kernel instead of pure Python.
- `scripts/generate_glyphs.py` and `tools/ocr_and_update_glyph_chart.py` pointed at `fonts/glyph_name_chart.md`, which was renamed to `fonts/Glyph Name Chart.md`.
- `bench/bench_fov.py` used the removed `GameRNG.randint`.
- Missing `Any` imports in `game/ai/*` and `game/entities/components.py`.

### Changed
- Dev pins: `ruff==0.5.12` (never published) → `ruff==0.5.7`; `mypy==1.8.0` → `mypy==1.15.0` (1.8 predates the TypeVar-default support NumPy 2.2+ stubs rely on); pre-commit ruff hook `charliermarsh/ruff-pre-commit@0.1.14` (tag does not exist) → `astral-sh/ruff-pre-commit@v0.5.7`.

### Tests
- New: `tests/game/test_flowfield.py`, `tests/test_magic_bf_max_steps.py`, `tests/test_variety_coverage.py`.
- `tests/test_surface_materializer.py::test_surface_materializer_ruin_template` searched only one chunk for features of a ruin that spans several.

## [Unreleased] - Worldgen

### Added
- New `worldgen/` package: cube-sphere topology, elevation, climate, hydrology kernels, metadata and reporting.
- Tests covering kernels, determinism, edge cases and end-to-end pipeline.

### CI
- Added a CI job to run static typing and linting (`mypy`, `ruff`, `black`) on PRs to enforce typing and style.

### Notes / Requirements
- **Numba compilation:** Running `build_full_world(...)` triggers Numba compilation of kernels; expect the first run to be significantly slower while numba/llvmlite JIT caches are created.
- **Native dependencies:** The worldgen pipeline requires native/numpy+compiled deps at runtime:
  - `numba`, `llvmlite` (for numba kernels)
  - `numpy`, `scipy`, `scikit-image`
  - `pydantic` (for metadata validation)
  - `orjson` (for fast report serialization)
- Ensure you install the project with its runtime dependencies (for example, `pip install .` or `pip install -e '.[dev]'` for CI/dev) and have a compatible `llvmlite`/`numba` wheel for your platform.
