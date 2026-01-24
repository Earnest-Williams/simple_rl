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
