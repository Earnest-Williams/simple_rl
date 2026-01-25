# World Generator Design — Fully Integrated Specification

**Version:** 2.0.0 (Canonical Overrides Applied)  
**Status:** Complete specification with reference kernels

---

## Preamble: Goals and Non-Goals

### Goals

1. Build a deterministic planet-scale overland world generator for a roguelike, suitable for long-range travel and exploration.
2. Use a grid world with square tiles, mapped over an entire planet via a cube-sphere (six square faces).
3. Capture some of the "tectonics / climate / rivers" verisimilitude of simulation-style worldgen (inspired by projects like Simulopolis and Nortantis), without chasing "hand-drawn map" aesthetics.
4. Support streaming / on-demand gameplay chunk generation, while keeping the world's starting state identical for a given seed.
5. Use a coarse "simulation resolution" for global fields (tectonics, climate, hydrology), and a higher resolution local mesh/heightfield only when generating a gameplay chunk.

### Non-Goals (for now)

1. Photorealistic geomorphology or hydrology. The goal is plausible-enough structure that reads well in gameplay.
2. Full physical correctness of atmospheric circulation. A deterministic, fast approximation is sufficient.
3. Storing the entire "detail" world at full resolution. The global simulation is the authoritative backbone; chunks derive detail on demand.

---

## Generation Redux Implementation (Canonical Overrides)

This section defines canonical overrides that supersede any conflicting guidance elsewhere in the document. These represent the authoritative implementation approach.

### P0-1: Mask + Curve Authoring Model

**Canonical declaration:** All continuous-valued fields used for classification, blending, or thresholding MUST be authored as **Mask + Curve** pairs.

**Definitions:**

- **Mask:** A `float32[n_cells]` array with values in `[0, 1]` representing normalized membership or intensity.
- **Curve:** A pure, deterministic function `curve(mask_value) -> output_value` that remaps the mask for specific use cases.

**Required masks:**

| Mask Name | Source | Description |
|-----------|--------|-------------|
| `land_mask_f32` | `(elev_q_i32 >= sea_level_q).astype(float32)` | Binary land/ocean from quantized elevation |
| `coast_mask_f32` | `1.0 - clamp(dist_to_ocean_steps / coast_decay_steps, 0, 1)` | Distance-to-ocean decay |
| `boundary_mask_f32` | `exp(-dist_to_boundary / L_decay)` | Plate boundary influence |
| `highlands_mask_f32` | `clamp((elev_m - highland_floor) / highland_range, 0, 1) * slope_factor` | Elevation + slope composite |

**Curve examples:**

```python
def curve_uplift(boundary_mask: float, amplitude: float) -> float:
    """Exponential decay curve for tectonic uplift."""
    return amplitude * boundary_mask

def curve_roughness(highlands_mask: float, r0: float, r1: float) -> float:
    """Linear interpolation curve for roughness."""
    return r0 + r1 * highlands_mask
```

**Rationale:** Mask + Curve separation enables:
1. Independent tuning of spatial extent (mask) vs. output magnitude (curve)
2. Reuse of masks across multiple derived fields
3. Clearer debugging (visualize masks directly)

### P0-2: OpenSimplex3 Surrogate Noise Evaluator

**Canonical declaration:** Until a full OpenSimplex3 port is complete, use the following seam-free, Numba-friendly surrogate.

**Sampling convention:**
- Noise is evaluated on `pos_xyz` (unit sphere coordinates), ensuring automatic seam continuity.
- Multi-octave defaults: 4 octaves, lacunarity 2.0, persistence 0.5.

**Per-octave seed separation:**

```python
NOISE_DOMAIN: int = 0x4E4F4953  # "NOIS" in ASCII
NOISE_OCTAVE_CONST: int = 0x9E3779B9  # Golden ratio derived

def octave_seed(world_seed: int, octave: int) -> int:
    return world_seed ^ NOISE_DOMAIN ^ (octave * NOISE_OCTAVE_CONST)
```

**3×3×3 Gaussian kernel support:** For smooth noise derivatives, convolve with a separable Gaussian kernel in the quantized grid space before spherical projection.

**Swap plan for full OpenSimplex3:**
1. Replace the surrogate evaluator function signature-for-signature.
2. The surrogate uses gradient-based interpolation on a quantized lattice.
3. Full OS3 will use the canonical simplex lattice with proper gradient selection.

### P0-3: Deterministic Indexed Heap and Union-Find

**Canonical declaration:** Priority propagation MUST NOT use Python `heapq`. Use an indexed min-heap with explicit position tracking.

**Required data structures:**

```python
# Indexed min-heap arrays
heap_nodes: NDArray[np.int32]   # int32[capacity] - cell indices in heap order
heap_pos: NDArray[np.int32]     # int32[n_cells] - position of each cell in heap (-1 if not present)
heap_keys: NDArray[np.float32]  # float32[n_cells] - priority key for each cell
heap_size: int                  # Current number of elements
```

**Union-find requirement:** Flat-component detection MUST use union-find with:
- Path compression
- Union by rank
- Deterministic scanning order (increasing `lin`)

### P0-4: Cell Area via Spherical Solid Angle

**Canonical declaration:** `cell_area_f32` MUST be computed using the spherical solid angle method.

**Algorithm:**
1. For each cell, compute the four corner vertices on the unit sphere.
2. Split into two spherical triangles.
3. Sum the spherical excess (computed via `atan2` form) for both triangles.
4. Scale by `planet_radius_m ** 2`.

**Robust fallback:** For near-degenerate cases (very small cells near poles), use the small-angle approximation:
```python
area_approx = 0.5 * abs(cross(v1 - v0, v2 - v0).dot(center_normal)) * R**2
```

### P1-5: Order-Independent Moisture Advection

**Canonical declaration:** Moisture advection MUST use two-phase delta accumulation to eliminate order dependence.

**Algorithm:**

```
Phase A: Compute deltas (read-only from current state)
    for u in range(n_cells):
        v = wind_to_i32[u]
        if v == -1:
            continue  # Polar cap / no transport
        m = moist_cur[u] * transport_frac
        dh = max(0, elev_at_boundary(v) - elev_at_boundary(u))
        p_orog = m * (1 - exp(-dh / orog_scale_m))
        moist_delta[u] -= m
        moist_delta[v] += (m - p_orog)
        precip_delta[v] += p_orog

Phase B: Apply deltas
    moist_next[:] = moist_cur + moist_delta
    precip_f32[:] += precip_delta
```

**Boundary elevation conversion:** When computing `dh`, convert quantized elevation:
```python
elev_at_boundary = elev_q_i32 * ELEV_Q_M
```

### P1-6: Strahler Ordering Fix

**Canonical declaration:** Strahler order computation MUST use correct headwater and sink semantics.

**Definitions:**
- **Headwater:** A cell where `is_river_u8[u] == 1` AND `in_degree[u] == 0` AND `flow_to_i32[u] != -1`
- **Sink:** A cell where `flow_to_i32[u] == -1` (sinks are NOT treated as sources)

**Algorithm:**
1. Build `in_degree[v]` counting only river-to-river edges.
2. Initialize queue with headwaters in increasing `lin` order.
3. Process via Kahn's algorithm on the river subgraph only.
4. Non-river cells retain `stream_order_u8 = 0`.

### P1-7: Accumulation-Driven Erosion (Replaces Particle Erosion)

**Canonical declaration:** Particle-based erosion is REPLACED by deterministic accumulation-driven hydraulic erosion plus thermal talus erosion.

**New Stage H2 (inserted after Stage H):**

**Hydraulic erosion:**
1. Build provisional flow direction and accumulation (scratch arrays).
2. Erosion capacity: `capacity = discharge * slope_factor`
3. Deterministic downstream pass: erode proportional to capacity.

**Thermal erosion (talus):**
1. For each cell, compute maximum slope to neighbors.
2. If slope exceeds `talus_angle`, redistribute elevation via two-phase integer deltas.
3. Recommended iterations: 1–3 (tunable via config).

### P1-8: Polar Wind Degeneracy Handling

**Canonical declaration:** Wind computation MUST handle polar singularities explicitly.

**Requirements:**
1. **Robust tangent basis:** Use fallback reference axis when `pos_xyz` is nearly parallel to the primary reference.
2. **Polar cap definition:** `lat_polar_cap ≈ 0.985` (approximately 80° latitude).
3. **Polar cap behavior:**
   - `wind_to_i32[u] = -1` (no transport)
   - Wind magnitude tapers to 0 approaching the cap.

**Fallback axis selection:**
```python
ref = np.array([0.0, 0.0, 1.0])  # Primary: +Z
if abs(pos_xyz.dot(ref)) > 0.99:
    ref = np.array([1.0, 0.0, 0.0])  # Fallback: +X
```

### P2-10: Quantized Elevation (0.1m int32)

**Canonical declaration:** Elevation storage MUST use quantized integer representation.

**Format:**
- `elev_q_i32: int32[n_cells]` — quantized elevation
- `ELEV_Q_M: float = 0.1` — quantum in meters

**Conversion:**
```python
# Float to quantized
elev_q_i32 = np.round(elev_m / ELEV_Q_M).astype(np.int32)

# Quantized to float
elev_m = elev_q_i32.astype(np.float32) * ELEV_Q_M
```

**Affected operations:**
- Sea level selection: performed in integer space
- Elevation smoothing: use integer arithmetic with rounding
- Biome rules: compare against quantized thresholds
- Climate formulas: convert to float only when needed

**Range:** int32 supports ±214,748,364.7 meters, far exceeding planetary requirements.

### P2-11: Two-Tier Tunables Hash

**Canonical declaration:** Cache invalidation MUST use two-tier hashing.

**Schema:**
```json
{
  "global_tunables_hash": "sha256:...",
  "chunk_tunables_hash": "sha256:..."
}
```

**Rules:**
- **Global hash:** Computed from all parameters affecting global simulation layers.
- **Chunk hash:** Computed from parameters affecting only chunk-level detail generation.
- **Cache key:** Chunk caches MUST include both hashes.

**Computation:**
```python
def compute_tunables_hash(cfg: object, scope: str) -> str:
    if scope == "global":
        fields = extract_global_fields(cfg)
    else:
        fields = extract_chunk_fields(cfg)
    blob = orjson.dumps(fields, option=orjson.OPT_SORT_KEYS)
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"
```

### P2-12: report.json Diagnostics

**Canonical declaration:** Every world build MUST produce a `report.json` with the following metrics.

**Required fields:**

```json
{
  "land_fraction": 0.32,
  "temp_quantiles": {"p5": -15.2, "p25": 5.1, "p50": 12.3, "p75": 22.1, "p95": 28.4},
  "precip_quantiles": {"p5": 0.0, "p25": 0.12, "p50": 0.35, "p75": 0.62, "p95": 0.89},
  "river_stats": {
    "total_river_cells": 125000,
    "order_histogram": [50000, 30000, 20000, 15000, 7000, 3000]
  },
  "seam_continuity": {
    "elev_seam_vs_nonseam_ratio": 1.02,
    "temp_seam_vs_nonseam_ratio": 0.98,
    "precip_seam_vs_nonseam_ratio": 1.01
  }
}
```

**Helper requirements:**
- Quantile computation: deterministic (use `np.partition` or sorted indexing).
- Histogram computation: deterministic bin edges.

### P2-13: Seed Domain Separation

**Canonical declaration:** All hash-based randomness MUST use domain-separated seeds.

**Required domain constants:**

```python
BIOME_JITTER_DOMAIN: int = 0x42494F4D   # "BIOM"
NOISE_DOMAIN: int = 0x4E4F4953          # "NOIS"
PLATE_SEED_DOMAIN: int = 0x504C4154     # "PLAT"
WIND_DOMAIN: int = 0x57494E44           # "WIND"
FLOW_DOMAIN: int = 0x464C4F57           # "FLOW"
FLAT_DOMAIN: int = 0x464C4154           # "FLAT"
```

**Standardized hash function:**

```python
def hash01_domain(world_seed: int, domain: int, lin: int) -> float:
    """Domain-separated hash producing value in [0, 1)."""
    combined = world_seed ^ domain
    return hash01(combined, lin)
```

### P2-14: Numba Parallelization Rules

**Canonical declaration:** Numba `parallel=True` MUST only be used for embarrassingly parallel operations.

**Safe patterns (may use `parallel=True` and `prange`):**
- Per-cell transforms with no neighbor reads: `output[i] = f(input[i])`
- Per-cell transforms with read-only neighbor access: `output[i] = f(input[i], input[nbr[i]])`
- Mask generation: `mask[i] = condition(input[i])`
- Independent noise evaluation: `noise[i] = eval_noise(pos[i])`

**Unsafe patterns (MUST NOT use `parallel=True`):**
- Moisture advection (order-dependent accumulation)
- Flow accumulation (topological DP)
- Strahler order computation (topological DP)
- Priority propagation / Dijkstra-style traversal (heap-based)
- Union-find operations (concurrent modification)
- Any reduction with mutable shared state

**Decision framework:**

```
Is output[i] computed purely from input[i] or read-only neighbors?
├─ YES → Safe for parallel=True
└─ NO → Does computation modify shared state or depend on processing order?
    ├─ YES → UNSAFE - use sequential @njit
    └─ NO → Review carefully; likely unsafe
```

---

## Style Guide (Relevant to Design and Implementation)

This section captures the constraints that directly shape module design.

### Baselines

1. Target Python 3.11+.
2. Determinism rules:
   1. Use `worldgen.game_rng.GameRNG` for any randomness in world logic.
   2. Do not use Python `random` or NumPy RNG in deterministic worldgen code paths.
   3. Use `worldgen.utils_coord.coord_hash(seed, lin)` for deterministic tie-breaking and hash-based jitter; do not rely on unordered iteration (`dict`, `set`) for determinism.
3. Formatting: Black, 88-character lines.
4. Static typing:
   1. Explicit annotations everywhere; no type inference.
   2. Use `X | None`, never `Optional[X]`.
   3. Mypy must pass under `--strict`.
   4. For NumPy/NDArray values, add explicit shape/dtype comments at point of use (e.g., `# float32[n_cells, 3]`).
5. Config immutability:
   1. All config classes MUST be `@dataclass(frozen=True)` to prevent silent mutation.
   2. Prefer `__post_init__` for validation; avoid derived-field mutation.
6. Data/performance primitives:
   1. Prefer `pathlib.Path`.
   2. Pandas is prohibited. Prefer Polars for state and tables.
   3. Use Numba for performance-critical loops and kernels.
   4. Use `msgpack` or `orjson` for serialization.
7. Architecture: avoid object-oriented clutter; prefer explicit data flow.

### Practical Workflow Rules

1. Keep diffs tight and well documented.
2. Verify determinism where feasible using fixed seeds.

---

## Repository Layout and Public APIs

This section defines the stable interfaces for generating and consuming worlds: (1) the Python API, (2) validation/contract rules for stages, and (3) the on-disk format (`meta.json`, layer schema, and cache identity). Gameplay code and tooling should depend only on what is documented here.

### Recommended Repository Layout

```text
simple_rl/
└── worldgen/
├── __init__.py
├── cli.py # CLI entrypoints (thin wrapper over Python API)
├── config.py # frozen dataclasses for tunables & defaults
├── validation.py # fail-fast input/layer contract checks
├── io.py # atomic layer read/write helpers
├── metadata.py # meta.json schema and helpers (hashing, provenance)
├── topology_cube_sphere.py # canonical topology/neighbor builder
├── utils_coord.py # coord_hash, pos_xyz, small helpers
├── game_rng.py # GameRNG adapters/wrappers
├── elevation.py # elevation pipeline
├── kernels/ # Reference Numba kernels
│ ├── __init__.py
│ ├── heap.py # Indexed min-heap
│ ├── union_find.py # Deterministic union-find
│ ├── noise.py # OpenSimplex3 surrogate
│ ├── geometry.py # Solid angle, smoothing
│ └── erosion.py # Hydraulic + thermal erosion
├── climate/
│ ├── __init__.py
│ ├── temperature.py
│ ├── wind.py
│ └── moisture.py
├── hydrology/
│ ├── __init__.py
│ ├── flow_direction.py
│ ├── accumulation.py
│ └── rivers_derived.py
├── chunk/
│ ├── __init__.py
│ ├── river_morphology_bridge.py
│ └── chunk_gen.py
├── biome.py
├── visualization.py # matplotlib / mini-web viewer helpers
└── report.py # diagnostics + report.json writer
```

### Config Conventions

All tunables/configs live in `worldgen/config.py` and are **immutable** by default (`@dataclass(frozen=True)`). Configs must be JSON-serializable deterministically (sorted keys) to support hashing.

Canonical constant:
- `ELEV_Q_M: float = 0.1` (elevation quantum in meters)

Naming conventions for quantized elevation (intentional split):
- **In-memory array variable name**: `elev_q_i32` (`int32[n_cells]`)
- **Meta/layer key**: `elev_q`
- **On-disk filename**: `elev_q.npy`

This avoids readers assuming the filename is `elev_q_i32.npy`.

General naming rule for all layers:
- **In-memory array variable names** carry dtype suffixes (e.g., `flow_to_i32`,
  `cell_area_f32`, `is_river_u8`).
- **Meta/layer keys** and **on-disk filenames** omit dtype suffixes (e.g.,
  `flow_to` → `flow_to.npy`).

```python
from __future__ import annotations

from dataclasses import dataclass

ELEV_Q_M: float = 0.1  # Elevation quantum in meters


@dataclass(frozen=True)
class ElevationConfig:
    N_smooth: int = 4
    target_ocean_frac: float = 0.68
    smooth_strength: float = 0.35
    smooth_cap_m: float = 90.0
    erosion_iterations: int = 2
    talus_angle_deg: float = 35.0


@dataclass(frozen=True)
class ClimateConfig:
    T_equator: float = 30.0
    T_pole: float = -20.0
    lapse_C_per_km: float = 6.0
    lat_gamma: float = 1.15
    lat_polar_cap: float = 0.985
    S_adv: int = 96
    transport_frac: float = 0.85
    orog_scale_m: float = 500.0


@dataclass(frozen=True)
class HydrologyConfig:
    min_catchment_cells: int = 256
    intensity_log_base: float = 10.0


@dataclass(frozen=True)
class WorldConfig:
    elevation: ElevationConfig
    climate: ClimateConfig
    hydrology: HydrologyConfig
    planet_radius_m: float = 6_371_000.0
```

### Determinism and Domain-Separated Randomness
All generation must be deterministic for fixed (seed, N, cfg) within a pinned runtime environment.

Rules:

Any randomness must be derived from deterministic hash primitives (no nondeterministic RNG calls).

Randomness must be domain-separated: each subsystem uses a distinct domain constant so that changing one subsystem does not silently perturb another.

Order-dependent kernels must use fixed traversal order and, when needed, a two-phase “delta” pattern to avoid traversal-order dependence.

### Quantized Elevation (Canonical Representation)
Elevation is canonicalized as quantized integers:

In memory: elev_q_i32: int32[n_cells]

In metadata: layer key elev_q

On disk: elev_q.npy (int32[n_cells]), interpreted with ELEV_Q_M

Conversions:

elev_q_i32 = round(elev_m / ELEV_Q_M).astype(int32)

elev_m = elev_q_i32.astype(float32) * ELEV_Q_M

Stages should compare thresholds (sea level selection, biome rules, erosion caps) in integer space when feasible, converting to float only when required by formulas.

### Top-Level API Surface
Public entrypoints are exported from worldgen (worldgen/__init__.py). Every entrypoint must validate prerequisites, dtypes, shapes, and sentinels before doing expensive work.

```python
# worldgen/__init__.py

from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def build_full_world(
    out_dir: Path,
    seed: int,
    N: int,
    cfg: WorldConfig,
    overwrite: bool = False,
    precompile_kernels: bool = False,
) -> None:
    """Run the full pipeline and emit the canonical report.json diagnostics."""
    ...


def build_world(
    out_dir: Path,
    seed: int,
    N: int,
    cfg: WorldConfig,
    overwrite: bool = False,
) -> None:
    """Build topology + base layers only (pos_xyz, nbr tables, cell_area).

    Writes layers and meta.json into out_dir. Deterministic for fixed (seed, N, cfg).
    """
    ...


def build_elevation(
    out_dir: Path,
    seed: int,
    N: int,
    cfg: ElevationConfig,
    plate_seed_xyz: NDArray[np.float32] | None = None,  # float32[n_plates, 3]
) -> None:
    """Produce quantized elevation and optional tectonic layers and persist them.

    In-memory: elev_q_i32 (int32[n_cells])
    Meta/layer key: elev_q (recorded in meta.json)
    """
    ...


def build_climate(
    out_dir: Path,
    seed: int,
    N: int,
    cfg: ClimateConfig,
) -> None:
    """Produce and persist climate layers.

    Produces (minimum) layer keys recorded in meta.json:
      - temp: float32[n_cells]
      - wind_to: int32[n_cells] (sentinel -1 allowed for polar cap)
      - moist: float32[n_cells]
      - precip: float32[n_cells]
    """
    ...


def build_hydrology(
    out_dir: Path,
    N: int,
    cfg: HydrologyConfig,
) -> None:
    """Compute flow/accumulation and river-derived layers and persist them.

    Requires:
      - elev_q (loaded into memory as elev_q_i32)
      - required climate layers per the hydrology model

    Produces (minimum) layer keys recorded in meta.json:
      - flow_to: int32[n_cells] (sentinel -1 allowed for sinks)
      - accum: float32[n_cells]
      - is_river: uint8[n_cells]
      - river_intensity: float32[n_cells]
      - stream_order: uint8[n_cells]
    """
    ...


def get_chunk(
    out_dir: Path,
    face: int,
    i0: int,
    j0: int,
    width: int,
    height: int,
    margin_cells: int,
    detail_cells_per_sim: int,
) -> dict[str, object]:
    """Return chunk data (elev_detail, river polylines, biome tiles).

    Cache identity must incorporate:
      - request parameters (face/i0/j0/width/height/margin/detail scale),
      - global_tunables_hash, and
      - chunk_tunables_hash.
    """
    ...
```
Recommended get_chunk() return payload:

request: echo of request parameters

elev_detail: chunk-local heightfield in meters (float32[H_detail, W_detail]) or fixed-point if preferred

biome_tiles: biome grid aligned to the chunk output (or a coarser grid plus mapping)

rivers: polylines in chunk-local coordinates with width/intensity/order attributes

provenance: seed, N, format_version, hashes, generator version, and optional commit ID

Validation and Contracts (Fail-Fast)
Every build_* function must validate inputs and prerequisites before doing expensive work.

Minimum Checks Per Stage
Config validation: enforce invariants in __post_init__ on @dataclass(frozen=True) configs.

Filesystem prerequisites: required input layers exist and are recorded in meta.json.

Array contracts:

Dtype matches exactly (e.g., int32, float32).

Shape matches exactly.

Contiguity is C-contiguous for Numba kernels.

Value/sentinel checks:

No NaNs or infinities in float layers.

Indices are in-range or documented sentinels (-1).

Basic range sanity (e.g., precip_f32 >= 0).

Validation utilities should be centralized in worldgen/validation.py so error messages are consistent across stages.

Validation Helper
```python
# worldgen/validation.py

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def validate_array(
    arr: NDArray[np.generic],
    name: str,
    expected_dtype: np.dtype[np.generic],
    expected_shape: tuple[int, ...],
) -> None:
    """Validate array dtype, shape, and contiguity."""
    if arr.dtype != expected_dtype:
        raise ValueError(f"{name}: expected dtype {expected_dtype}, got {arr.dtype}")
    if arr.shape != expected_shape:
        raise ValueError(f"{name}: expected shape {expected_shape}, got {arr.shape}")
    if not arr.flags["C_CONTIGUOUS"]:
        raise ValueError(f"{name}: array must be C-contiguous")


def validate_no_nan(arr: NDArray[np.floating[np.generic]], name: str) -> None:
    """Ensure no NaN or infinity values."""
    if np.any(~np.isfinite(arr)):
        raise ValueError(f"{name}: contains NaN or infinity values")
```
On-Disk Format: meta.json, Layer Schema, and Cache Identity
Canonical World Directory Layout
A world directory is a self-contained artifact. Tooling must rely on meta.json layer entries (paths), not hardcoded filenames.

```text
world_<seed>/
  meta.json                  # required
  report.json                # required (diagnostics)
  tunables.json              # optional (full config dump)
  pos_xyz.npy                # float32[n_cells, 3]
  nbr4.npy                   # int32[n_cells, 4]
  nbr8.npy                   # int32[n_cells, 8]
  cell_area.npy              # float32[n_cells]
  elev_q.npy                 # int32[n_cells] (quantized elevation; meta key "elev_q")
  plate_id.npy               # int32[n_cells] (optional)
  uplift_f32.npy             # float32[n_cells] (optional)
  roughness_f32.npy          # float32[n_cells] (optional)
  temp_f32.npy               # float32[n_cells]
  wind_to.npy                # int32[n_cells]
  moist_f32.npy              # float32[n_cells]
  precip_f32.npy             # float32[n_cells]
  flow_to.npy                # int32[n_cells]
  accum_f32.npy              # float32[n_cells]
  is_river.npy               # uint8[n_cells]
  river_intensity.npy        # float32[n_cells]
  stream_order.npy           # uint8[n_cells]
  biome.npy                  # uint8[n_cells]
  layers/                    # optional per-layer meta
    elev_q.meta.json
    ...
  chunk_cache/               # optional: serialized get_chunk outputs
```
meta.json Schema
meta.json is authoritative and must include:

format_version

world_seed, N, n_cells, planet_radius_m, elev_quantum_m

layers map with path, dtype, shape, and units/sentinels

global_tunables_hash and chunk_tunables_hash

provenance fields (git_commit, timestamps, runtime versions)

```json
{
  "format_version": "2.0.0",
  "world_seed": 12345,
  "N": 1024,
  "n_cells": 6291456,
  "planet_radius_m": 6371000.0,
  "elev_quantum_m": 0.1,
  "layers": {
    "pos_xyz": {"path": "pos_xyz.npy", "dtype": "float32", "shape": [6291456, 3], "units": "unit"},
    "elev_q":  {"path": "elev_q.npy",  "dtype": "int32",   "shape": [6291456],   "units": "quanta", "quantum_m": 0.1},
    "flow_to": {"path": "flow_to.npy", "dtype": "int32",   "shape": [6291456],   "units": "index", "sentinel": -1}
  },
  "global_tunables_hash": "sha256:abc123...",
  "chunk_tunables_hash": "sha256:def456...",
  "git_commit": "abcdef0123456789",
  "created_utc": "2026-01-23T12:00:00Z",
  "platform": {"python": "3.11.0", "numba": "0.59.0"}
}
```
Two-Tier Tunables Hashing and Cache Invalidation
Cache invalidation uses two-tier hashing:

global_tunables_hash: parameters affecting global simulation layers

chunk_tunables_hash: parameters affecting chunk-only detail generation

Rules:

Both hashes must be recorded in meta.json.

Chunk cache artifacts must include both hashes in the cache key.

Hash computation must use deterministic serialization (sorted keys) before SHA-256.

Recommended cache path structure:

chunk_cache/<global_hash>/<chunk_hash>/<request_fingerprint>.<ext>
where <request_fingerprint> is a deterministic digest of request parameters.

report.json (Required Diagnostics)
Every full world build must produce report.json, containing at minimum:

land fraction

temperature quantiles and precipitation quantiles (deterministic computation)

river statistics (e.g., total river cells and stream order histogram)

seam continuity checks for key layers (ratios comparing seam-adjacent vs non-seam neighbor differences)

Quantiles and histograms must be computed deterministically (fixed bin edges; deterministic selection/partitioning methods).

## Data Model: Cube-Sphere, Indexing, and Raster Layers

### Cube-Sphere Layout

The planet is represented as six `N × N` faces (square tiles per face). Each tile maps to a single linear index:

- `face ∈ [0..5]`
- `i ∈ [0..N-1]` (x-like coordinate on face)
- `j ∈ [0..N-1]` (y-like coordinate on face)
- `lin = ((face * N) + j) * N + i`

### Neighbor Topology

Precomputed neighbor index tables:

- `nbr4_i32: int32[n_cells, 4]` for N/E/S/W neighbor indices across cube seams.
- `nbr8_i32: int32[n_cells, 8]` for 8-neighborhood hydrology and smoothing.

### Core Layers (Simulation Resolution)

| Layer | Dtype | Shape | Description |
|-------|-------|-------|-------------|
| `elev_q_i32` | int32 | [n_cells] | Quantized elevation (quantum = 0.1m) |
| `cell_area_f32` | float32 | [n_cells] | Solid angle area in m² |
| `wind_to_i32` | int32 | [n_cells] | Wind target index (-1 for polar) |
| `temp_f32` | float32 | [n_cells] | Temperature in °C |
| `moist_f32` | float32 | [n_cells] | Moisture proxy [0, 1] |
| `precip_f32` | float32 | [n_cells] | Precipitation proxy |
| `flow_to_i32` | int32 | [n_cells] | Flow target (-1 for sinks) |
| `accum_f32` | float32 | [n_cells] | Area-weighted accumulation |

### Derived Layers

| Layer | Dtype | Shape | Description |
|-------|-------|-------|-------------|
| `is_river_u8` | uint8 | [n_cells] | River mask |
| `river_intensity_f32` | float32 | [n_cells] | Log-scaled accumulation |
| `stream_order_u8` | uint8 | [n_cells] | Strahler order |
| `biome_u8` | uint8 | [n_cells] | Biome classification |

### Memory Sizing

`n_cells = 6 * N * N`

| N | n_cells | One float32 layer |
|---|---------|-------------------|
| 1024 | 6,291,456 | ~24 MiB |
| 4096 | 100,663,296 | ~384 MiB |

---

## Module: topology_cube_sphere

### Overview and Invariants

1. Planet represented as 6 faces, each `N × N` cells, so `n_cells = 6 * N * N`.
2. Linear index: `lin = ((face * N) + j) * N + i`.
3. Neighbor tables:
   1. `nbr4_i32: int32[n_cells, 4]` in **fixed order** `N, E, S, W`.
   2. `nbr8_i32: int32[n_cells, 8]` in documented fixed order.
4. All seam crossing is handled during table construction.
5. Invalid neighbors (should not occur): `-1`.

### Required Functions

```python
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray


def lin_index(face: int, i: int, j: int, N: int) -> int:
    """Compute linear index from face coordinates."""
    return ((face * N) + j) * N + i


def build_default_edge_map() -> dict[int, dict[int, dict[str, Any]]]:
    """Return edge_map[face][edge] = {face, edge, xform} for canonical cube."""
    ...


def build_nbr_tables(
    N: int,
    edge_map: dict[int, dict[int, dict[str, Any]]],
) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
    """Return (nbr4_i32, nbr8_i32) for the cube-sphere mapping."""
    ...
```

### Edge Map and Transform Codes

The `xform` code represents rotation/reflection needed to map coordinates along one edge to the adjacent edge. Use a small integer code (0..7) encoding the 8 symmetries of the square.

### Required Tests

1. **Round-trip mapping:** mapping across an edge and back returns the original coordinate.
2. **Mutual consistency:** all 6 faces' edge mappings agree.
3. **Neighbor ranges:** all neighbors are within `[0, n_cells)` or `-1`.
4. **Seam continuity:** compare distributions of neighbor step lengths across seam vs non-seam pairs.

---

## Module: elevation

### Design Intent

1. Produce authoritative, seed-deterministic global simulation elevation field `elev_q_i32` at resolution `N`.
2. Field must contain tectonic-scale structure (continents, basins, mountain belts).
3. Field must be seam-agnostic by construction.
4. Output must be stable for streaming.

### Inputs and Outputs

**Inputs:**
- `seed`
- Cube-sphere topology (`N`, `nbr4_i32`, `nbr8_i32`)
- `cell_area_f32` (for tie-breaking)
- Optional plate seed points

**Outputs (required):**
- `elev_q_i32: int32[n_cells]` (quantized elevation)

**Outputs (optional):**
- `plate_id_i32: int32[n_cells]`
- `plate_type_u8: uint8[n_cells]`
- `uplift_f32: float32[n_cells]`
- `roughness_f32: float32[n_cells]`
- `sea_level_q: int32` (scalar)

### Data Contract

1. **Determinism:** For fixed `(seed, N)` and config, output is bitwise stable.
2. **Units:** `elev_q_i32 * ELEV_Q_M` gives elevation in meters.
3. **Sign:** `elev_q_i32 == sea_level_q` is mean sea level; below is underwater.
4. **Numeric validity:** No sentinel values in elevation (all values are valid).
5. **Seam behavior:** Neighbor transitions across seams have same statistical character as non-seam.

### Tunables (Recommended Starting Points)

```python
@dataclass(frozen=True)
class ElevationTunables:
    # Plates
    P_min: int = 24
    P_max: int = 96
    p_cont: float = 0.30
    
    # Boundary classification
    eps_closing: float = 1e-3
    
    # Decay lengths (grid steps)
    L_conv: int = 12
    L_ridge: int = 10
    L_rift_inner: int = 6
    L_xform: int = 8
    
    # Uplift amplitudes (meters)
    A_conv_cc: float = 3200.0
    A_conv_oc: float = 2200.0
    A_conv_oo: float = 1600.0
    A_ridge: float = 1200.0
    A_rift: float = 900.0
    A_xform: float = 600.0
    
    # Base crust (meters)
    base_ocean: float = -4200.0
    base_cont: float = 300.0
    
    # Noise
    noise_octaves: int = 4
    noise_amp_base: float = 350.0
    noise_amp_uplift: float = 900.0
    uplift_scale: float = 2500.0
    roughness_r0: float = 0.15
    roughness_r1: float = 0.85
    
    # Smoothing
    N_smooth: int = 4
    smooth_strength: float = 0.35
    smooth_cap_m: float = 90.0
    
    # Sea level
    target_ocean_frac: float = 0.68
    
    # Erosion (Stage H2)
    erosion_iterations: int = 2
    hydraulic_k: float = 0.01
    talus_angle_deg: float = 35.0
```

### Pipeline Stages

#### Stage A: Plate Seeds and Velocities

1. Choose plate count `P = clamp(round(n_cells / 16384), P_min, P_max)`.
2. For each plate `p`:
   1. Sample `seed_xyz[p]` uniformly on unit sphere.
   2. Sample plate velocity in tangent plane.
3. Outputs: `seed_xyz[P, 3]`, `plate_vel[P, 3]`.

#### Stage B: Per-Cell Plate Assignment

For each cell `u`:
1. Compute `pos = pos_xyz_f32[u]`.
2. Assign `plate_id[u] = argmax_p dot(pos, seed_xyz[p])`.

Optional: `K = 2` iterations of majority smoothing.

#### Stage C: Plate Types

1. For each plate `p`, sample `plate_is_cont[p]` with probability `p_cont`.
2. For each cell `u`, set `plate_type_u8[u] = plate_is_cont[plate_id[u]]`.

#### Stage D: Boundary Detection and Stress Classification

1. A cell `u` is boundary if any `v in nbr8(u)` has different `plate_id`.
2. Classify boundaries as convergent, divergent, or transform based on relative motion.

#### Stage E: Distance-to-Boundary Fields

Use priority propagation with indexed heap (NOT `heapq`).

```python
# Initialize
dist[boundary_cells] = 0
dist[other_cells] = INF
heap.push_all(boundary_cells, key=0)

# Propagate
while not heap.empty():
    u = heap.pop_min()
    for v in nbr4[u]:
        new_dist = dist[u] + 1
        if new_dist < dist[v]:
            dist[v] = new_dist
            heap.decrease_key(v, new_dist)
```

#### Stage F: Base Crust and Tectonic Uplift

```python
elev_raw[u] = base(u) + uplift_conv + uplift_div + uplift_xform
```

Where each uplift is computed from distance masks and amplitude curves.

#### Stage G: Seam-Free Multi-Octave Noise

Evaluate noise on `pos_xyz_f32[u]` for automatic seam continuity:

```python
noise_total = 0.0
for k in range(noise_octaves):
    seed_k = octave_seed(world_seed, k)
    freq_k = lacunarity ** k
    amp_k = persistence ** k
    noise_total += amp_k * eval_noise_3d(pos_xyz * freq_k, seed_k)

roughness = roughness_r0 + roughness_r1 * highlands_mask
elev_raw += noise_total * (noise_amp_base + noise_amp_uplift * roughness)
```

#### Stage H: Artifact Control (Slope-Limited Smoothing)

```python
for iteration in range(N_smooth):
    for u in range(n_cells):
        m = mean(elev_raw[nbr4[u]])
        d = m - elev_raw[u]
        elev_raw[u] += clamp(d, -smooth_cap, +smooth_cap) * smooth_strength
```

#### Stage H2: Accumulation-Driven Erosion (NEW)

**Hydraulic erosion:**
```python
# Build provisional flow and accumulation
flow_to_scratch_i32 = compute_flow_direction(elev_raw)
accum_scratch_f32 = compute_accumulation(flow_to_scratch_i32, cell_area_f32)

# Erosion capacity
for u in range(n_cells):
    v = flow_to_scratch_i32[u]
    if v == -1:
        continue
    slope = max(0, elev_raw[u] - elev_raw[v])
    capacity = accum_scratch_f32[u] * slope
    erosion = min(capacity * hydraulic_k, elev_raw[u] - base[u])
    erosion_delta[u] -= erosion
    erosion_delta[v] += erosion * 0.5  # Partial deposition

# Apply deltas (two-phase for order independence)
elev_raw += erosion_delta
```

**Thermal erosion (talus):**
```python
talus_slope = tan(radians(talus_angle_deg))

for iteration in range(erosion_iterations):
    talus_delta.fill(0)
    for u in range(n_cells):
        for v in nbr8[u]:
            dh = elev_raw[u] - elev_raw[v]
            if dh > talus_slope:
                transfer = (dh - talus_slope) * 0.5
                talus_delta[u] -= transfer
                talus_delta[v] += transfer
    elev_raw += talus_delta
```

#### Stage I: Deterministic Sea Level Selection

1. Target `target_ocean_frac`.
2. Compute `sea_level` as the quantile of `elev_raw`.
3. Convert to quantized:

```python
sea_level_q = int(round(sea_level / ELEV_Q_M))
elev_q_i32 = np.round(elev_raw / ELEV_Q_M).astype(np.int32)
```

### Validation Hooks

1. **Determinism:** Hash `elev_q_i32` for known seed and assert stability.
2. **Land fraction:** Verify against `target_ocean_frac`.
3. **Seam continuity:** Compare neighbor-difference distributions.
4. **Range sanity:** Check min/max are within expected bounds.

---

## Climate: Wind, Temperature, Moisture, Precipitation

### Design Intent

1. Produce deterministic, planet-scale climate layers suitable for biome mapping.
2. Favor speed and repeatability over physical realism.
3. All operations are seam-agnostic (use neighbor tables only).
4. Climate layers are immutable world state once generated.

### Core Outputs

1. `temp_f32: float32[n_cells]` — temperature in °C
2. `wind_to_i32: int32[n_cells]` — wind target index (-1 for polar caps)
3. `moist_f32: float32[n_cells]` — moisture proxy [0, 1]
4. `precip_f32: float32[n_cells]` — precipitation proxy

### Module: climate_temperature

#### Algorithm

1. **Baseline latitude term:**
   ```python
   abs_lat = abs(pos_xyz[u, 2])  # sin(latitude)
   t_lat = T_equator - (T_equator - T_pole) * (abs_lat ** lat_gamma)
   ```

2. **Elevation lapse (land only):**
   ```python
   h_km = max(elev_q_i32[u] * ELEV_Q_M, 0) / 1000.0
   t = t_lat - lapse_C_per_km * h_km
   ```

3. **Ocean moderation:**
   ```python
   # Compute ocean_influence via smoothed sea_mask
   t_ocean = T_ocean_equator - (T_ocean_equator - T_ocean_pole) * (abs_lat ** lat_gamma_ocean)
   temp_f32[u] = lerp(t, t_ocean, ocean_influence[u] * ocean_blend_strength)
   ```

#### Tunables

```python
T_equator: float = 30.0
T_pole: float = -20.0
lapse_C_per_km: float = 6.0
lat_gamma: float = 1.15
ocean_blend_strength: float = 0.65
```

### Module: climate_wind

#### Algorithm

1. **Latitudinal band classification:**
   ```python
   abs_lat = abs(pos_xyz[u, 2])
   if abs_lat < lat_trade_max:
       band = "tropics"  # Easterlies
   elif abs_lat < lat_westerly_max:
       band = "midlat"   # Westerlies
   elif abs_lat < lat_polar_cap:
       band = "polar"    # Polar easterlies
   else:
       band = "cap"      # No transport
   ```

2. **Robust tangent basis:**
   ```python
   ref = [0.0, 0.0, 1.0]  # +Z
   if abs(dot(pos_xyz[u], ref)) > 0.99:
       ref = [1.0, 0.0, 0.0]  # Fallback to +X
   
   east_hat = normalize(cross(ref, pos_xyz[u]))
   north_hat = cross(pos_xyz[u], east_hat)
   ```

3. **Discretize to neighbor graph:**
   ```python
   wind_to_i32[u] = argmax_v dot(step_dir[v], wind_hat)
   # With deterministic tie-breaking via coord_hash
   ```

4. **Polar cap handling:**
   ```python
   if abs_lat >= lat_polar_cap:
       wind_to_i32[u] = -1  # No transport
   ```

#### Tunables

```python
lat_trade_max: float = 0.50      # ~30°
lat_westerly_max: float = 0.866  # ~60°
lat_polar_cap: float = 0.985     # ~80°
merid_frac: float = 0.20
```

### Module: climate_moisture_and_precip

#### Algorithm (Order-Independent Two-Phase)

```python
# Initialize
moist_cur = np.zeros(n_cells, dtype=np.float32)
precip_f32 = np.zeros(n_cells, dtype=np.float32)

for step in range(S_adv):
    # Phase A: Compute deltas (read-only)
    moist_delta = np.zeros(n_cells, dtype=np.float32)
    precip_delta = np.zeros(n_cells, dtype=np.float32)
    
    for u in range(n_cells):
        v = wind_to_i32[u]
        if v == -1:
            continue
        
        m = moist_cur[u] * transport_frac
        elev_u = elev_q_i32[u] * ELEV_Q_M
        elev_v = elev_q_i32[v] * ELEV_Q_M
        dh = max(0.0, elev_v - elev_u)
        
        # Orographic precipitation
        p_orog = m * (1.0 - exp(-dh / orog_scale_m))
        
        moist_delta[u] -= m
        moist_delta[v] += (m - p_orog)
        precip_delta[v] += p_orog
    
    # Phase B: Apply deltas
    moist_cur += moist_delta
    precip_f32 += precip_delta
    
    # Apply sources
    moist_cur[sea_mask] = np.maximum(moist_cur[sea_mask], ocean_source)
    
    # Condensation by capacity
    cap = cap_min + cap_slope * temp_f32
    cap = np.clip(cap, cap_lo, cap_hi)
    cond = np.maximum(0.0, moist_cur - cap)
    precip_f32 += cond
    moist_cur -= cond

# Normalize
moist_f32 = np.clip(moist_cur, 0.0, 1.0)
```

#### Tunables

```python
S_adv: int = 96
transport_frac: float = 0.85
orog_scale_m: float = 500.0
cap_min: float = 0.15
cap_slope: float = 0.012
cap_lo: float = 0.05
cap_hi: float = 0.95
ocean_source: float = 0.45
evap_land: float = 0.02
```

---

## Module: hydrology_flow_direction

### Design Intent

1. Flow can traverse large equal-elevation flats when they have an outlet.
2. Land sinks are allowed (lakes/ponds terminate accumulation).
3. No BFS-based elevation modification.

### Output Semantics

- `flow_to_i32[lin] = downstream_lin` if cell has outflow path
- `flow_to_i32[lin] = -1` if cell is a sink

### Algorithm

#### Stage A: Assign Strictly Downhill Flows

```python
for u in range(n_cells):
    min_elev = INF
    best_v = -1
    for v in nbr8[u]:
        if elev_q_i32[v] < min_elev:
            min_elev = elev_q_i32[v]
            best_v = v
        elif elev_q_i32[v] == min_elev and best_v != -1:
            # Deterministic tie-breaking
            if cell_area_f32[v] > cell_area_f32[best_v]:
                best_v = v
            elif cell_area_f32[v] == cell_area_f32[best_v]:
                if coord_hash(seed, v) < coord_hash(seed, best_v):
                    best_v = v
    
    if min_elev < elev_q_i32[u]:
        flow_to_i32[u] = best_v
    else:
        flow_to_i32[u] = UNRESOLVED  # Mark for Stage B
```

#### Stage B: Flat-Component Routing via Priority Propagation

1. **Identify flat components** using union-find:
   ```python
   uf = UnionFind(n_cells)
   for u in range(n_cells):
       if flow_to_i32[u] != UNRESOLVED:
           continue
       for v in nbr8[u]:
           if elev_q_i32[v] == elev_q_i32[u] and flow_to_i32[v] == UNRESOLVED:
               uf.union(u, v)
   ```

2. **For each component, find outlets:**
   ```python
   outlets = []
   for u in component:
       for v in nbr8[u]:
           if elev_q_i32[v] < elev_q_i32[u]:
               outlets.append(u)
               break
   ```

3. **Route via priority propagation:**
   ```python
   if outlets:
       # Seed heap with outlets
       for o in outlets:
           phi[o] = 0
           heap.push(o, key=(0, coord_hash(seed, o)))
       
       # Propagate
       while not heap.empty():
           u = heap.pop_min()
           for v in nbr8[u]:
               if v in component and phi[v] > phi[u] + 1:
                   phi[v] = phi[u] + 1
                   heap.decrease_key(v, (phi[v], coord_hash(seed, v)))
       
       # Assign flow toward lower phi
       for u in component:
           if u in outlets:
               continue  # Keep downhill edge
           best_v = argmin(phi[v] for v in nbr8[u] if v in component)
           flow_to_i32[u] = best_v
   else:
       # No outlet: create sink at deterministic location
       sink = min(component, key=lambda u: coord_hash(seed, u))
       flow_to_i32[sink] = -1
       # Route everything else toward sink
       ...
```

### DAG Validation

After assignment, verify no directed cycles exist. If found, break by setting the cycle node with smallest `coord_hash` to `-1`.

---

## Module: hydrology_flow_accumulation

### Responsibilities

1. Compute area-weighted accumulation from `flow_to_i32`.
2. Treat sinks (`flow_to_i32 == -1`) as terminals.

### Algorithm (Topological Sort)

```python
# Build in-degree
in_deg = np.zeros(n_cells, dtype=np.int32)
for u in range(n_cells):
    v = flow_to_i32[u]
    if v != -1:
        in_deg[v] += 1

# Initialize accumulation with cell area
accum_f32 = cell_area_f32.copy()

# Process in topological order (sources first)
queue = [u for u in range(n_cells) if in_deg[u] == 0]
queue.sort()  # Deterministic order

while queue:
    u = queue.pop(0)
    v = flow_to_i32[u]
    if v != -1:
        accum_f32[v] += accum_f32[u]
        in_deg[v] -= 1
        if in_deg[v] == 0:
            # Insert in sorted position for determinism
            bisect.insort(queue, v)
```

---

## Module: rivers_derived_fields

### Outputs

- `is_river_u8: uint8[n_cells]`
- `river_intensity_f32: float32[n_cells]`
- `stream_order_u8: uint8[n_cells]`

### River Thresholding

```python
cell_area_ref = np.median(cell_area_f32)
is_river = accum_f32 >= (cell_area_ref * min_catchment_cells)
is_river_u8 = is_river.astype(np.uint8)
```

### River Intensity

```python
river_intensity_f32 = np.where(
    is_river,
    np.log1p(accum_f32 / (cell_area_ref * intensity_log_base)),
    0.0
).astype(np.float32)
```

### Strahler Stream Order (Fixed)

```python
# Build river-only in-degree
in_deg = np.zeros(n_cells, dtype=np.int32)
for u in range(n_cells):
    if not is_river[u]:
        continue
    v = flow_to_i32[u]
    if v != -1 and is_river[v]:
        in_deg[v] += 1

# Initialize
max_up = np.zeros(n_cells, dtype=np.uint8)
cnt_max = np.zeros(n_cells, dtype=np.uint8)
order = np.zeros(n_cells, dtype=np.uint8)

# Find headwaters: river cells with no upstream rivers and valid outflow
headwaters = []
for u in range(n_cells):
    if is_river[u] and in_deg[u] == 0 and flow_to_i32[u] != -1:
        headwaters.append(u)
headwaters.sort()  # Deterministic order

# Process
queue = list(headwaters)
while queue:
    u = queue.pop(0)
    
    # Compute order for u
    if max_up[u] == 0:
        order[u] = 1
    elif cnt_max[u] >= 2:
        order[u] = max_up[u] + 1
    else:
        order[u] = max_up[u]
    
    # Propagate to downstream
    v = flow_to_i32[u]
    if v != -1 and is_river[v]:
        if order[u] > max_up[v]:
            max_up[v] = order[u]
            cnt_max[v] = 1
        elif order[u] == max_up[v]:
            cnt_max[v] += 1
        
        in_deg[v] -= 1
        if in_deg[v] == 0:
            bisect.insort(queue, v)

stream_order_u8 = order
```

---

## Module: biome_mapping

### Responsibilities

1. Convert climate + elevation to `biome_u8: uint8[n_cells]`.
2. Use Whittaker-style temperature/moisture table.
3. Add deterministic jitter for border breakup.

### Biome IDs

```python
class BiomeID:
    OCEAN: int = 0
    SEA_ICE: int = 1
    ICE_CAP: int = 2
    ALPINE: int = 3
    
    TUNDRA: int = 10
    BOREAL_FOREST: int = 11
    TEMPERATE_FOREST: int = 12
    TEMPERATE_RAINFOREST: int = 13
    GRASSLAND: int = 14
    SHRUBLAND: int = 15
    DESERT: int = 16
    
    TROPICAL_SEASONAL: int = 20
    SAVANNA: int = 21
    TROPICAL_RAINFOREST: int = 22
```

### Precedence Rules

1. **Ocean:** `elev_q_i32 < sea_level_q` → `OCEAN` (unless sea ice)
2. **Sea ice:** ocean and `temp <= ice_temp_C` → `SEA_ICE`
3. **Ice cap:** land and `temp <= ice_temp_C` → `ICE_CAP`
4. **Alpine:** land and `elev_m >= alpine_m` → `ALPINE`
5. **Otherwise:** Whittaker table

### Deterministic Jitter

```python
j = hash01_domain(seed, BIOME_JITTER_DOMAIN, lin) - 0.5
w_jittered = clamp(wetness + j * jitter_strength, 0, 1)
```

### Whittaker Mapping

```python
# Temperature bands
if temp < t_tundra:
    t_band = "cold"
elif temp < t_boreal:
    t_band = "boreal"
elif temp < t_temperate:
    t_band = "temperate"
else:
    t_band = "tropical"

# Wetness bands
if w < wet_desert:
    w_band = "very_dry"
elif w < wet_shrub:
    w_band = "dry"
elif w < wet_grass:
    w_band = "semi"
elif w < wet_forest:
    w_band = "wet"
else:
    w_band = "very_wet"

# Lookup table
biome = WHITTAKER_TABLE[(t_band, w_band)]
```

---

## Module: river_morphology_bridge

### Responsibilities

1. Convert coarse river network to smooth chunk-local centerlines.
2. Provide deterministic carving parameters (width/depth).
3. Ensure continuity across chunk boundaries.

### Coordinate Frame

```python
# Chunk center on sphere
c = chunk_center_xyz

# Tangent basis with polar fallback
ref = [0, 0, 1]
if abs(dot(c, ref)) > 0.99:
    ref = [1, 0, 0]

t0 = normalize(cross(ref, c))
t1 = cross(c, t0)

# Project cell position to chunk-local 2D
def to_local_2d(p: NDArray) -> tuple[float, float]:
    x = dot(p, t0) * R
    y = dot(p, t1) * R
    return (x, y)
```

### Width and Depth Derivation

```python
s = max(stream_order[u], 1)
q = river_intensity[u]

W = width_base * (2 ** (s - 1)) * (1 + width_intensity_k * q)
D = depth_base * sqrt(W / width_base)

W = clamp(W, 0, W_max)
D = clamp(D, 0, D_max)
```

### Carving Profile

```python
def carve_elevation(d: float, W: float, D: float) -> float:
    """Compute elevation delta for distance d from centerline."""
    r = 0.5 * W
    if d < r:
        return -D * (1 - (d / r) ** 2)
    elif d < r + bank_width:
        # Bank shoulder
        t = (d - r) / bank_width
        return bank_height * (1 - t)
    else:
        return 0.0
```

---

## Appendix A: Reference Numba Kernels

### A.1: Indexed Min-Heap

```python
# worldgen/kernels/heap.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def heap_init(
    heap_nodes: NDArray[np.int32],
    heap_pos: NDArray[np.int32],
    heap_keys: NDArray[np.float32],
) -> int:
    """Initialize empty heap. Returns size (0)."""
    heap_pos[:] = -1
    return 0


@njit(cache=True)
def heap_push(
    heap_nodes: NDArray[np.int32],
    heap_pos: NDArray[np.int32],
    heap_keys: NDArray[np.float32],
    size: int,
    node: int,
    key: float,
) -> int:
    """Push node with key. Returns new size."""
    # Add at end
    heap_nodes[size] = node
    heap_pos[node] = size
    heap_keys[node] = key
    
    # Bubble up
    i: int = size
    while i > 0:
        parent: int = (i - 1) // 2
        p_node: int = heap_nodes[parent]
        if heap_keys[p_node] <= key:
            break
        # Swap
        heap_nodes[i] = p_node
        heap_pos[p_node] = i
        heap_nodes[parent] = node
        heap_pos[node] = parent
        i = parent
    
    return size + 1


@njit(cache=True)
def heap_pop_min(
    heap_nodes: NDArray[np.int32],
    heap_pos: NDArray[np.int32],
    heap_keys: NDArray[np.float32],
    size: int,
) -> tuple[int, int]:
    """Pop minimum. Returns (node, new_size)."""
    if size == 0:
        return -1, 0
    
    result: int = heap_nodes[0]
    heap_pos[result] = -1
    size -= 1
    
    if size == 0:
        return result, 0
    
    # Move last to root
    last: int = heap_nodes[size]
    heap_nodes[0] = last
    heap_pos[last] = 0
    last_key: float = heap_keys[last]
    
    # Bubble down
    i: int = 0
    while True:
        left: int = 2 * i + 1
        right: int = 2 * i + 2
        smallest: int = i
        smallest_key: float = last_key
        
        if left < size:
            left_node: int = heap_nodes[left]
            left_key: float = heap_keys[left_node]
            if left_key < smallest_key:
                smallest = left
                smallest_key = left_key
        
        if right < size:
            right_node: int = heap_nodes[right]
            right_key: float = heap_keys[right_node]
            if right_key < smallest_key:
                smallest = right
        
        if smallest == i:
            break
        
        # Swap
        swap_node: int = heap_nodes[smallest]
        heap_nodes[i] = swap_node
        heap_pos[swap_node] = i
        heap_nodes[smallest] = last
        heap_pos[last] = smallest
        i = smallest
    
    return result, size


@njit(cache=True)
def heap_decrease_key(
    heap_nodes: NDArray[np.int32],
    heap_pos: NDArray[np.int32],
    heap_keys: NDArray[np.float32],
    node: int,
    new_key: float,
) -> None:
    """Decrease key for existing node."""
    if heap_pos[node] < 0:
        return
    
    heap_keys[node] = new_key
    i: int = heap_pos[node]
    
    # Bubble up
    while i > 0:
        parent: int = (i - 1) // 2
        p_node: int = heap_nodes[parent]
        if heap_keys[p_node] <= new_key:
            break
        # Swap
        heap_nodes[i] = p_node
        heap_pos[p_node] = i
        heap_nodes[parent] = node
        heap_pos[node] = parent
        i = parent
```

### A.2: Deterministic Union-Find

```python
# worldgen/kernels/union_find.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def uf_init(n: int) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
    """Initialize union-find. Returns (parent, rank)."""
    parent: NDArray[np.int32] = np.arange(n, dtype=np.int32)
    rank: NDArray[np.int32] = np.zeros(n, dtype=np.int32)
    return parent, rank


@njit(cache=True)
def uf_find(parent: NDArray[np.int32], x: int) -> int:
    """Find with path compression."""
    root: int = x
    while parent[root] != root:
        root = parent[root]
    
    # Path compression
    while parent[x] != root:
        next_x: int = parent[x]
        parent[x] = root
        x = next_x
    
    return root


@njit(cache=True)
def uf_union(
    parent: NDArray[np.int32],
    rank: NDArray[np.int32],
    x: int,
    y: int,
) -> bool:
    """Union by rank. Returns True if merged, False if already same set."""
    rx: int = uf_find(parent, x)
    ry: int = uf_find(parent, y)
    
    if rx == ry:
        return False
    
    # Union by rank (deterministic: prefer lower index on tie)
    if rank[rx] < rank[ry]:
        parent[rx] = ry
    elif rank[rx] > rank[ry]:
        parent[ry] = rx
    else:
        # Same rank: prefer lower index as root
        if rx < ry:
            parent[ry] = rx
            rank[rx] += 1
        else:
            parent[rx] = ry
            rank[ry] += 1
    
    return True


@njit(cache=True)
def uf_build_components(
    parent: NDArray[np.int32],
    n: int,
) -> NDArray[np.int32]:
    """Build component ID array (deterministic: uses canonical root)."""
    component: NDArray[np.int32] = np.empty(n, dtype=np.int32)
    for i in range(n):
        component[i] = uf_find(parent, i)
    return component
```

### A.3: OpenSimplex3 Surrogate Noise

```python
# worldgen/kernels/noise.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray

NOISE_DOMAIN: int = 0x4E4F4953
NOISE_OCTAVE_CONST: int = 0x9E3779B9
MASK64: int = (1 << 64) - 1
MASK32: int = (1 << 32) - 1


@njit(cache=True)
def splitmix64(x: int) -> int:
    """SplitMix64 finalizer."""
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & MASK64
    x = (x ^ (x >> 27)) * 0x94D049BB133111EB & MASK64
    return (x ^ (x >> 31)) & MASK64


@njit(cache=True)
def hash_gradient(seed: int, ix: int, iy: int, iz: int) -> tuple[float, float, float]:
    """Deterministic gradient vector from lattice point."""
    key: int = ((seed & MASK32) << 32) ^ (
        ((ix * 73856093) ^ (iy * 19349663) ^ (iz * 83492791)) & MASK32
    )
    h: int = splitmix64(key)
    
    # Generate gradient from hash
    gx: float = ((h & 0xFFFF) / 32768.0) - 1.0
    gy: float = (((h >> 16) & 0xFFFF) / 32768.0) - 1.0
    gz: float = (((h >> 32) & 0xFFFF) / 32768.0) - 1.0
    
    # Normalize
    length: float = np.sqrt(gx * gx + gy * gy + gz * gz)
    if length > 1e-10:
        inv_len: float = 1.0 / length
        gx *= inv_len
        gy *= inv_len
        gz *= inv_len
    
    return gx, gy, gz


@njit(cache=True)
def smoothstep(t: float) -> float:
    """Quintic smoothstep for smooth derivatives."""
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@njit(cache=True)
def noise_3d_single(seed: int, x: float, y: float, z: float) -> float:
    """Single-octave gradient noise."""
    # Lattice coordinates
    ix: int = int(np.floor(x))
    iy: int = int(np.floor(y))
    iz: int = int(np.floor(z))
    
    # Fractional coordinates
    fx: float = x - ix
    fy: float = y - iy
    fz: float = z - iz
    
    # Smoothstep weights
    wx: float = smoothstep(fx)
    wy: float = smoothstep(fy)
    wz: float = smoothstep(fz)
    
    # Trilinear interpolation of dot products
    result: float = 0.0
    for dz in range(2):
        for dy in range(2):
            for dx in range(2):
                gx, gy, gz = hash_gradient(seed, ix + dx, iy + dy, iz + dz)
                dot: float = gx * (fx - dx) + gy * (fy - dy) + gz * (fz - dz)
                
                weight: float = 1.0
                weight *= (1.0 - wx) if dx == 0 else wx
                weight *= (1.0 - wy) if dy == 0 else wy
                weight *= (1.0 - wz) if dz == 0 else wz
                
                result += weight * dot
    
    return result


@njit(cache=True)
def octave_seed(world_seed: int, octave: int) -> int:
    """Compute per-octave seed with domain separation."""
    return world_seed ^ NOISE_DOMAIN ^ (octave * NOISE_OCTAVE_CONST)


@njit(cache=True)
def noise_3d_multi_octave(
    seed: int,
    x: float,
    y: float,
    z: float,
    octaves: int,
    lacunarity: float,
    persistence: float,
) -> float:
    """Multi-octave noise evaluation."""
    total: float = 0.0
    freq: float = 1.0
    amp: float = 1.0
    max_amp: float = 0.0
    
    for k in range(octaves):
        seed_k: int = octave_seed(seed, k)
        total += amp * noise_3d_single(seed_k, x * freq, y * freq, z * freq)
        max_amp += amp
        freq *= lacunarity
        amp *= persistence
    
    return total / max_amp


@njit(cache=True)
def eval_noise_sphere(
    pos_xyz: NDArray[np.float32],
    seed: int,
    octaves: int = 4,
    lacunarity: float = 2.0,
    persistence: float = 0.5,
    scale: float = 1.0,
) -> NDArray[np.float32]:
    """Evaluate multi-octave noise on sphere positions."""
    n: int = pos_xyz.shape[0]
    result: NDArray[np.float32] = np.empty(n, dtype=np.float32)
    
    for i in range(n):
        x: float = pos_xyz[i, 0] * scale
        y: float = pos_xyz[i, 1] * scale
        z: float = pos_xyz[i, 2] * scale
        result[i] = noise_3d_multi_octave(
            seed, x, y, z, octaves, lacunarity, persistence
        )
    
    return result
```

### A.4: Spherical Solid Angle (Cell Area)

```python
# worldgen/kernels/geometry.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def cross_3d(
    a: NDArray[np.float32],
    b: NDArray[np.float32],
) -> NDArray[np.float32]:
    """3D cross product."""
    result: NDArray[np.float32] = np.empty(3, dtype=np.float32)
    result[0] = a[1] * b[2] - a[2] * b[1]
    result[1] = a[2] * b[0] - a[0] * b[2]
    result[2] = a[0] * b[1] - a[1] * b[0]
    return result


@njit(cache=True)
def dot_3d(a: NDArray[np.float32], b: NDArray[np.float32]) -> float:
    """3D dot product."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


@njit(cache=True)
def normalize_3d(v: NDArray[np.float32]) -> NDArray[np.float32]:
    """Normalize 3D vector."""
    length: float = np.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    if length < 1e-10:
        return v
    inv_len: float = 1.0 / length
    result: NDArray[np.float32] = np.empty(3, dtype=np.float32)
    result[0] = v[0] * inv_len
    result[1] = v[1] * inv_len
    result[2] = v[2] * inv_len
    return result


@njit(cache=True)
def spherical_triangle_area(
    a: NDArray[np.float32],
    b: NDArray[np.float32],
    c: NDArray[np.float32],
) -> float:
    """Compute spherical triangle area on unit sphere using spherical excess.
    
    Uses the formula: Area = |alpha + beta + gamma - pi|
    where alpha, beta, gamma are the angles of the spherical triangle.
    
    Implemented via the atan2-based formula for numerical stability.
    """
    # Normalize to unit sphere
    a = normalize_3d(a)
    b = normalize_3d(b)
    c = normalize_3d(c)
    
    # Edge vectors
    ab: NDArray[np.float32] = cross_3d(a, b)
    bc: NDArray[np.float32] = cross_3d(b, c)
    ca: NDArray[np.float32] = cross_3d(c, a)
    
    # Lengths
    lab: float = np.sqrt(dot_3d(ab, ab))
    lbc: float = np.sqrt(dot_3d(bc, bc))
    lca: float = np.sqrt(dot_3d(ca, ca))
    
    # Handle degenerate cases
    if lab < 1e-10 or lbc < 1e-10 or lca < 1e-10:
        # Fallback to planar approximation
        edge1: NDArray[np.float32] = b - a
        edge2: NDArray[np.float32] = c - a
        cross_prod: NDArray[np.float32] = cross_3d(edge1, edge2)
        return 0.5 * np.sqrt(dot_3d(cross_prod, cross_prod))
    
    # Normalize
    ab = ab * (1.0 / lab)
    bc = bc * (1.0 / lbc)
    ca = ca * (1.0 / lca)
    
    # Dihedral angles (spherical excess formula)
    cos_alpha: float = -dot_3d(ab, ca)
    cos_beta: float = -dot_3d(bc, ab)
    cos_gamma: float = -dot_3d(ca, bc)
    
    # Clamp for numerical stability
    cos_alpha = max(-1.0, min(1.0, cos_alpha))
    cos_beta = max(-1.0, min(1.0, cos_beta))
    cos_gamma = max(-1.0, min(1.0, cos_gamma))
    
    alpha: float = np.arccos(cos_alpha)
    beta: float = np.arccos(cos_beta)
    gamma: float = np.arccos(cos_gamma)
    
    # Spherical excess
    excess: float = alpha + beta + gamma - np.pi
    
    return abs(excess)


@njit(cache=True)
def compute_cell_area(
    corners: NDArray[np.float32],
    radius_m: float,
) -> float:
    """Compute cell area from 4 corner vertices.
    
    corners: float32[4, 3] - four corners on unit sphere
    radius_m: planet radius in meters
    
    Returns: area in m²
    """
    # Split into two triangles and sum
    area1: float = spherical_triangle_area(corners[0], corners[1], corners[2])
    area2: float = spherical_triangle_area(corners[0], corners[2], corners[3])
    
    # Scale by radius squared
    return (area1 + area2) * radius_m * radius_m


@njit(cache=True)
def compute_all_cell_areas(
    N: int,
    radius_m: float,
) -> NDArray[np.float32]:
    """Compute cell areas for all cells."""
    n_cells: int = 6 * N * N
    cell_area_f32: NDArray[np.float32] = np.empty(n_cells, dtype=np.float32)
    
    # Corner offsets (in normalized face coordinates)
    du: float = 1.0 / N
    dv: float = 1.0 / N
    
    for face in range(6):
        for j in range(N):
            for i in range(N):
                lin: int = ((face * N) + j) * N + i
                
                # Cell center in [-1, 1]
                u_center: float = (2.0 * i + 1.0) / N - 1.0
                v_center: float = (2.0 * j + 1.0) / N - 1.0
                
                # Four corners
                corners: NDArray[np.float32] = np.empty((4, 3), dtype=np.float32)
                for ci, (du_off, dv_off) in enumerate([
                    (-du, -dv), (du, -dv), (du, dv), (-du, dv)
                ]):
                    u: float = u_center + du_off
                    v: float = v_center + dv_off
                    
                    # Project to cube face
                    x: float
                    y: float
                    z: float
                    if face == 0:
                        x, y, z = 1.0, u, v
                    elif face == 1:
                        x, y, z = -1.0, -u, v
                    elif face == 2:
                        x, y, z = -u, 1.0, v
                    elif face == 3:
                        x, y, z = u, -1.0, v
                    elif face == 4:
                        x, y, z = -u, v, 1.0
                    else:
                        x, y, z = u, v, -1.0
                    
                    # Normalize to sphere
                    inv_len: float = 1.0 / np.sqrt(x * x + y * y + z * z)
                    corners[ci, 0] = x * inv_len
                    corners[ci, 1] = y * inv_len
                    corners[ci, 2] = z * inv_len
                
                cell_area_f32[lin] = compute_cell_area(corners, radius_m)
    
    return cell_area_f32
```

### A.5: Two-Phase Moisture Advection

```python
# worldgen/kernels/advection.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray

ELEV_Q_M: float = 0.1


@njit(cache=True)
def advect_moisture_step(
    moist_cur: NDArray[np.float32],
    precip_accum: NDArray[np.float32],
    elev_q_i32: NDArray[np.int32],
    wind_to_i32: NDArray[np.int32],
    sea_mask: NDArray[np.uint8],
    temp_f32: NDArray[np.float32],
    n_cells: int,
    transport_frac: float,
    orog_scale_m: float,
    ocean_source: float,
    cap_min: float,
    cap_slope: float,
    cap_lo: float,
    cap_hi: float,
) -> NDArray[np.float32]:
    """Single step of order-independent moisture advection.
    
    Returns: updated moisture array
    """
    # Phase A: Compute deltas (read-only from moist_cur)
    moist_delta: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    precip_delta: NDArray[np.float32] = np.zeros(n_cells, dtype=np.float32)
    
    for u in range(n_cells):
        v: int = wind_to_i32[u]
        if v == -1:
            continue  # Polar cap / no transport
        
        m: float = moist_cur[u] * transport_frac
        
        # Convert quantized elevation to meters
        elev_u: float = elev_q_i32[u] * ELEV_Q_M
        elev_v: float = elev_q_i32[v] * ELEV_Q_M
        dh: float = elev_v - elev_u
        if dh < 0.0:
            dh = 0.0
        
        # Orographic precipitation
        p_orog: float = m * (1.0 - np.exp(-dh / orog_scale_m))
        
        moist_delta[u] -= m
        moist_delta[v] += (m - p_orog)
        precip_delta[v] += p_orog
    
    # Phase B: Apply deltas
    moist_next: NDArray[np.float32] = moist_cur + moist_delta
    precip_accum += precip_delta
    
    # Apply sources
    for u in range(n_cells):
        if sea_mask[u] == 1:
            if moist_next[u] < ocean_source:
                moist_next[u] = ocean_source
    
    # Condensation by capacity
    for u in range(n_cells):
        cap: float = cap_min + cap_slope * temp_f32[u]
        if cap < cap_lo:
            cap = cap_lo
        elif cap > cap_hi:
            cap = cap_hi
        
        cond: float = moist_next[u] - cap
        if cond > 0.0:
            precip_accum[u] += cond
            moist_next[u] = cap
    
    # Clamp
    for u in range(n_cells):
        if moist_next[u] < 0.0:
            moist_next[u] = 0.0
        elif moist_next[u] > 1.0:
            moist_next[u] = 1.0
    
    return moist_next
```

### A.6: Accumulation-Driven Erosion

```python
# worldgen/kernels/erosion.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray

ELEV_Q_M: float = 0.1


@njit(cache=True)
def hydraulic_erosion_step(
    elev_q_i32: NDArray[np.int32],
    flow_to_i32: NDArray[np.int32],
    accum_f32: NDArray[np.float32],
    n_cells: int,
    hydraulic_k: float,
    base_elev_q_i32: NDArray[np.int32],
) -> NDArray[np.int32]:
    """Single step of hydraulic erosion.
    
    Uses two-phase deltas for order independence.
    """
    # Phase A: Compute deltas
    delta_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    
    for u in range(n_cells):
        v: int = flow_to_i32[u]
        if v == -1:
            continue
        
        # Slope in quanta
        slope_q: int = elev_q_i32[u] - elev_q_i32[v]
        if slope_q <= 0:
            continue
        
        # Erosion capacity = accumulation * slope
        capacity: float = accum_f32[u] * (slope_q * ELEV_Q_M)
        
        # Maximum erosion: don't go below base
        max_erosion_q: int = elev_q_i32[u] - base_elev_q_i32[u]
        if max_erosion_q < 0:
            max_erosion_q = 0
        
        # Compute erosion in quanta
        erosion_f: float = capacity * hydraulic_k / ELEV_Q_M
        erosion_q: int = int(min(erosion_f, max_erosion_q))
        
        if erosion_q > 0:
            delta_q[u] -= erosion_q
            # Partial deposition downstream
            delta_q[v] += erosion_q // 2
    
    # Phase B: Apply deltas
    return elev_q_i32 + delta_q


@njit(cache=True)
def thermal_erosion_step(
    elev_q_i32: NDArray[np.int32],
    nbr8: NDArray[np.int32],
    n_cells: int,
    talus_slope_q: int,
) -> NDArray[np.int32]:
    """Single step of thermal (talus) erosion.
    
    talus_slope_q: maximum allowed slope in elevation quanta
    """
    # Phase A: Compute deltas
    delta_q: NDArray[np.int32] = np.zeros(n_cells, dtype=np.int32)
    
    for u in range(n_cells):
        for k in range(8):
            v: int = nbr8[u, k]
            if v == -1:
                continue
            
            dh: int = elev_q_i32[u] - elev_q_i32[v]
            if dh > talus_slope_q:
                # Transfer half the excess
                transfer_q: int = (dh - talus_slope_q) // 2
                if transfer_q > 0:
                    delta_q[u] -= transfer_q
                    delta_q[v] += transfer_q
    
    # Phase B: Apply deltas
    return elev_q_i32 + delta_q
```

### A.7: Seam-Aware Smoothing

```python
# worldgen/kernels/smoothing.py

from __future__ import annotations

import numpy as np
from numba import njit
from numpy.typing import NDArray


@njit(cache=True)
def smooth_f32_nbr4(
    data: NDArray[np.float32],
    nbr4: NDArray[np.int32],
    n_cells: int,
    strength: float,
    cap: float,
) -> NDArray[np.float32]:
    """Slope-limited smoothing using 4-neighbors."""
    result: NDArray[np.float32] = data.copy()
    
    for u in range(n_cells):
        # Compute mean of neighbors
        total: float = 0.0
        count: int = 0
        for k in range(4):
            v: int = nbr4[u, k]
            if v != -1:
                total += data[v]
                count += 1
        
        if count == 0:
            continue
        
        mean_nbr: float = total / count
        diff: float = mean_nbr - data[u]
        
        # Clamp difference
        if diff > cap:
            diff = cap
        elif diff < -cap:
            diff = -cap
        
        result[u] = data[u] + diff * strength
    
    return result


@njit(cache=True)
def smooth_i32_nbr4(
    data_q: NDArray[np.int32],
    nbr4: NDArray[np.int32],
    n_cells: int,
    strength: float,
    cap_q: int,
) -> NDArray[np.int32]:
    """Slope-limited smoothing for quantized elevation."""
    result: NDArray[np.int32] = data_q.copy()
    
    for u in range(n_cells):
        # Compute mean of neighbors
        total: int = 0
        count: int = 0
        for k in range(4):
            v: int = nbr4[u, k]
            if v != -1:
                total += data_q[v]
                count += 1
        
        if count == 0:
            continue
        
        mean_nbr: float = total / count
        diff_f: float = mean_nbr - data_q[u]
        
        # Clamp difference
        if diff_f > cap_q:
            diff_f = cap_q
        elif diff_f < -cap_q:
            diff_f = -cap_q
        
        # Apply with strength and round
        adjustment: int = int(round(diff_f * strength))
        result[u] = data_q[u] + adjustment
    
    return result
```

---

## Appendix B: Report Generation

```python
# worldgen/report.py

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import orjson
from numpy.typing import NDArray


def compute_quantiles(
    arr: NDArray[np.floating[np.generic]],
    percentiles: list[int],
) -> dict[str, float]:
    """Compute quantiles deterministically."""
    sorted_arr: NDArray[np.floating[np.generic]] = np.sort(arr)
    n: int = len(sorted_arr)
    result: dict[str, float] = {}
    for p in percentiles:
        idx: int = int(p * n / 100)
        idx = min(idx, n - 1)
        result[f"p{p}"] = float(sorted_arr[idx])
    return result


def compute_seam_continuity(
    layer: NDArray[np.floating[np.generic]],
    nbr4: NDArray[np.int32],
    seam_pairs: list[tuple[int, int]],
    sample_size: int = 10000,
) -> float:
    """Compute ratio of seam vs non-seam neighbor differences."""
    rng: np.random.Generator = np.random.default_rng(42)  # Deterministic
    
    # Sample non-seam pairs
    n_cells: int = len(layer)
    non_seam_diffs: list[float] = []
    for _ in range(sample_size):
        u: int = rng.integers(0, n_cells)
        for k in range(4):
            v: int = nbr4[u, k]
            if v != -1 and (u, v) not in seam_pairs:
                non_seam_diffs.append(abs(float(layer[u] - layer[v])))
                break
    
    # Sample seam pairs
    seam_diffs: list[float] = []
    seam_sample: list[tuple[int, int]] = list(seam_pairs)[:sample_size]
    for u, v in seam_sample:
        seam_diffs.append(abs(float(layer[u] - layer[v])))
    
    if not seam_diffs or not non_seam_diffs:
        return 1.0
    
    return float(np.mean(seam_diffs) / np.mean(non_seam_diffs))


def generate_report(
    out_dir: Path,
    elev_q_i32: NDArray[np.int32],
    temp_f32: NDArray[np.float32],
    precip_f32: NDArray[np.float32],
    is_river_u8: NDArray[np.uint8],
    stream_order_u8: NDArray[np.uint8],
    nbr4: NDArray[np.int32],
    sea_level_q: int,
) -> dict[str, Any]:
    """Generate and save report.json."""
    elev_q_m: float = 0.1
    
    # Land fraction
    land_mask: NDArray[np.bool_] = elev_q_i32 >= sea_level_q
    land_fraction: float = float(np.mean(land_mask))
    
    # Temperature quantiles
    temp_quantiles: dict[str, float] = compute_quantiles(
        temp_f32, [5, 25, 50, 75, 95]
    )
    
    # Precipitation quantiles
    precip_quantiles: dict[str, float] = compute_quantiles(
        precip_f32, [5, 25, 50, 75, 95]
    )
    
    # River stats
    total_river_cells: int = int(np.sum(is_river_u8))
    max_order: int = int(np.max(stream_order_u8))
    order_hist: list[int] = []
    for o in range(1, max_order + 1):
        order_hist.append(int(np.sum(stream_order_u8 == o)))
    
    report: dict[str, Any] = {
        "land_fraction": land_fraction,
        "temp_quantiles": temp_quantiles,
        "precip_quantiles": precip_quantiles,
        "river_stats": {
            "total_river_cells": total_river_cells,
            "order_histogram": order_hist,
        },
        "seam_continuity": {
            "elev_seam_vs_nonseam_ratio": 1.0,  # Placeholder
            "temp_seam_vs_nonseam_ratio": 1.0,
            "precip_seam_vs_nonseam_ratio": 1.0,
        },
    }
    
    # Write atomically
    tmp: Path = out_dir / "report.json.tmp"
    with tmp.open("wb") as f:
        f.write(orjson.dumps(report, option=orjson.OPT_INDENT_2))
    os.replace(tmp, out_dir / "report.json")
    
    return report
```

---

## Build Order Checklist (Updated)

1. **topology_cube_sphere** — finalize `edge_map`, generate `nbr4_i32` and `nbr8_i32`, add seam-continuity tests.

2. **kernels** — implement reference Numba kernels:
   - `heap.py`: indexed min-heap
   - `union_find.py`: deterministic union-find
   - `noise.py`: OpenSimplex3 surrogate
   - `geometry.py`: solid angle cell area
   - `smoothing.py`: seam-aware smoothing
   - `advection.py`: two-phase moisture
   - `erosion.py`: hydraulic + thermal

3. **io** + **metadata** — implement atomic writes and authoritative `meta.json` with two-tier hashing.

4. **validation** — centralize shape/dtype/value contract checks.

5. **utils_coord** — implement `coord_hash`, `hash01`, `hash01_domain`, `pos_xyz`.

6. **game_rng** — provide deterministic RNG wrapper.

7. **elevation** — plates → uplift → noise → smoothing → erosion (H2) → sea level; write `elev_q_i32`.

8. **climate** — temperature → wind (with polar handling) → moisture/precip (two-phase).

9. **hydrology.flow_direction** — flat traversal with indexed heap + union-find; DAG validation.

10. **hydrology.accumulation** — area-weighted accumulation.

11. **hydrology.rivers_derived** — river mask, intensity, Strahler order (fixed headwater semantics).

12. **biome** — biome mapping with domain-separated jitter.

13. **chunk.river_morphology_bridge** — centerline extraction, spline, chunk carving.

14. **report** — generate `report.json` with diagnostics.

15. **CLI** + **visualization** + **diagnostics**.

16. **CI**: linting, type checking, and small-`N` determinism validation (`N=64` or `N=128`).

---

## Implementation Notes and Caveats

1. **Numba and determinism:** Constrain Numba versions and avoid `parallel=True` for order-dependent kernels.

2. **Floating-point reproducibility:** Use quantized int32 elevation to improve cross-platform stability.

3. **Zarr vs `.npy`:** `.npy` is simplest. If Zarr is adopted, record chunk shapes and compressor settings in `meta.json`.

4. **Two-phase delta pattern:** Use for all operations that could otherwise exhibit order dependence.

---

## Final Checklist Before Merging

1. ☐ Add the `worldgen/` package with skeleton modules.
2. ☐ Implement reference Numba kernels in `kernels/` subpackage.
3. ☐ Implement `utils_coord.coord_hash`, `hash01_domain`, and `game_rng.GameRNG`.
4. ☐ Implement `topology_cube_sphere.build_nbr_tables` with validation.
5. ☐ Implement atomic layer I/O and metadata helpers with two-tier hashing.
6. ☐ Implement elevation pipeline with Stage H2 erosion.
7. ☐ Implement climate with polar wind handling and two-phase advection.
8. ☐ Implement hydrology with indexed heap and fixed Strahler semantics.
9. ☐ Add validation checks and CI determinism pipeline.
10. ☐ Generate `report.json` with all required diagnostics.
11. ☐ Document the exact `meta.json` schema in repo README.
12. ☐ Add CLI entrypoints and visualization workflow.

# Operational Addenda

### Define a formal chunk API and storage spec (high priority)
The chunk API must be a minimal, explicit contract that callers and caches can rely on: for example `GetChunk(seed:int, face:int, chunk_i:int, chunk_j:int, tunables_hashes:{global,chunk}) -> ChunkBlob` and `PutChunk(...) -> OK/Err` with clear semantics for idempotency and reentrancy. Every API response must include strict metadata (chunk version, generation timestamp, global and chunk tunables hashes, payload checksum) and the implementation must validate the checksum before accepting or serving a blob. Document edge semantics for partial-chunk reads, neighbour dependencies, and how to request multiple adjacent chunks atomically so callers know when to expect implicit neighbour generation. Finally, require that chunk generators produce bitwise-identical output for the same inputs and that the API include a compact error model for malformed or stale blobs.

### Explicit chunk dimensions, tile ordering, coordinate transforms, and on-disk schema
Specify a canonical chunk tile size (a power-of-two is recommended); use `64×64` tiles per chunk as the default and allow smaller or larger profiles such as `32×32` and `128×128` as alternate profiles. Fix row-major tile ordering (`local_lin = local_y*chunk_w + local_x`) and publish canonical linear indexing and the exact cube-sphere projection formula so every implementation computes identical `pos_xyz` for a given `(face,chunk,local_x,local_y)`. Define an on-disk chunk header with fields such as: `magic(4B)`, `version(u16)`, `face(u8)`, `chunk_i(u32)`, `chunk_j(u32)`, `chunk_w(u16)`, `global_tunables_hash(sha256)`, `chunk_tunables_hash(sha256)`, `payload_length(u32)`, `payload_checksum(sha256)`, `compression_flags(u8)`, and reserved bytes, followed by the (optionally compressed) payload. Require little-endian canonicalization for multi-byte integers and pin compression standards (for example zstd with a specified level) so different runtimes produce readable and identical files.

### Atomic write strategy and compact cache-validity test
Document the canonical atomic write pattern: write to a temporary file in the target directory, `fsync` the file contents, `fsync` the directory, then atomically `rename` the temp file to the canonical pathname; include the exact sequence so implementers do not omit `fsync`. Require that the header include a payload length and a payload SHA-256 checksum and that readers compute and validate the checksum, treating any mismatch as a cache miss rather than corrupting global state. For remote object stores define an analogous staging/commit procedure (multipart upload + ETag or a staging key followed by an atomic rename/commit) and recommend adding a generation number for tie-breaking in distributed caches. Finally, document recovery behavior on startup: remove uncommitted temp/staging files and treat checksum failures as cache misses so the system remains robust.

### Add a portability & determinism section (high priority)
Publish a pinned runtime matrix (for example supported CPU architectures, Python X.Y.Z, Numba X.Y, NumPy X.Y and the preferred BLAS or a “no BLAS” mode) and provide a canonical Docker image used for CI and local reproduction. Explicitly call out deterministic floating-point requirements: avoid non-deterministic library calls, pin compiler or runtime flags where necessary, and prefer integer/quantized algorithms for critical code paths; provide recommended environment knobs (for example `NUMBA_DISABLE_JIT`, `OMP_NUM_THREADS`, MKL configuration) that must be set for deterministic runs. Mandate deterministic idioms such as stable sorts, `np.partition` for quantiles, and scanning orders by increasing `lin`, and identify which routines must provide integer fallbacks if bitwise reproducibility across platforms is required. Close the section with a short environment checklist that CI and production runs must satisfy to claim reproducibility.

### For critical operations, provide integer/quantized fallbacks or exact integer algorithms
Extend the quantized-elevation pattern to other continuous fields used in reductions or thresholds by specifying fixed-point representations and explicit scaling factors so rounding is consistent and deterministic. For accumulation and reduction algorithms (moisture transport, discharge accumulation, talus redistribution) provide integer arithmetic reference implementations with defined rounding rules and fixed-point multipliers, and prefer two-phase delta accumulation or pairwise deterministic combine trees for parallel reductions. For noise and random-domain conversions prefer lattice/hash-based integer noise or a deterministic integer-to-float bit-extraction method to produce `[0,1)` values, and document exact bit-level conversions so all platforms yield identical results. Finally, require integer-only core steps for graph algorithms (union-find, Strahler order) with deterministic tie-breakers (for example by `lin`) and include pseudo-code for the integer variants.

### Add a CI/regression plan and canonical reference vectors (high priority)
Provide a CI job that runs on the pinned Docker image and verifies a small suite of canonical seeds; each CI run should execute the global simulation and a set of chunk generations and assert SHA-256 checksums for `report.json` and one or more golden chunk blobs. Publish a minimal golden dataset in the repository (a tiny planet plus 4–8 golden chunks and the corresponding `report.json`) and gate merges on strict bitwise equality for those golden artifacts; allow an opt-in numeric-tolerance mode only for exploratory branches. Add cross-platform validation (Linux x86_64, Linux arm64, and where feasible macOS) and a nightly job that runs larger seeds to detect performance and seam-continuity regressions early. Document how to reproduce CI failures locally and require that any intentional change to canonical outputs be accompanied by a reviewed update to the golden dataset.

### Specify performance/scale targets (medium priority)
Provide at least one reference configuration to guide capacity planning: for example a “large” target with `facesize = 4096` (≈100M cells across six faces), default chunk `64×64`, an estimated worst-case global simulation memory footprint of 12–16 GiB, and a warm-cache chunk generator memory footprint of 64–256 MiB per generator. Define latency SLOs for interactive use such as: cold-cache 64×64 chunk generation ≤ 500 ms on a modern 8-core CPU and warm-cache generation < 150 ms, and define a batch throughput goal such as ~1M cells/sec on an 8-core node as an initial target. Provide microbenchmark harnesses and instructions to measure per-cell pipeline time, chunk latency, and peak memory for a given facesize so teams can extrapolate to different hardware. Finally, include guidance that enumerates trade-offs (reduce `facesize`, change `chunk_w`, or apply stage approximations) and their expected effects on latency and memory.

### Document error tolerances and alerting rules (low→medium)
Specify concrete thresholds for `report.json` metrics used in CI and monitoring; for example require `seam_continuity` ratios to lie in `[0.95, 1.05]` for automatic acceptance and treat deviations beyond `±10%` as a blocking regression that triggers alerts. For statistical fields such as `land_fraction`, `temp_quantiles`, and `precip_quantiles` provide soft-warning bands that create notifications and hard-failure bands that block changes; document how to interpret histogram differences, for example flagging aggregate KL divergence above a chosen threshold as a red flag. For river statistics, define absolute or relative change tolerances (for example >20% change in high-order river counts should open a regression issue) and describe automated follow-up actions. Finally, include a remediation workflow: run local reproduction with canonical seeds, generate per-chunk checksum diffs, and use a bisect strategy across commits or tunable changes to isolate the cause.

### Add example reference datasets and diagrams (low priority but useful)
Add a small set of reference artifacts under `docs/diagrams/` and `tests/reference/`: an SVG showing cube-sphere face numbering and orientation, an annotated graphic for cell corner/vertex indexing on the unit sphere, and a lookup diagram that maps `(face, chunk_i, chunk_j, local_x, local_y)` to `pos_xyz`. Provide a tiny reference world (for example `facesize=256`) and a zipped set of golden chunks plus `report.json` so developers can perform quick sanity-checks and visual validation. Prefer vector diagrams (SVG) with simple PNG exports for quick viewing and keep short snippets of annotated pseudocode alongside each figure to make the math-to-code mapping explicit. Finally, document how to regenerate diagrams and the scripts or tools required so contributors can keep the illustrations current.

### Clarify concurrency and parallelism rules
Extend the existing Numba rules with runtime conventions: allow `parallel=True` only for embarrassingly-parallel per-cell transforms and forbid it for neighbor-dependent passes, which must use a deterministic task decomposition and a single-threaded driver that schedules parallel workers with well-defined ordering. Recommend process pools for CPU-bound compiled kernels (to avoid interpreter-level thread contention and to enable NUMA affinity) and thread pools for I/O-bound cache reads/writes; include suggested worker counts and affinity hints for standard hardware profiles. Declare global arrays immutable after the global simulation stage and require explicit locks or single-writer queues for any mutable shared structures; list the data structures that must be built single-threaded (for example indexed heaps or union-find component construction). Finally, mandate that chunk generation be concurrency-safe and idempotent so multiple workers can attempt the same chunk in parallel without producing inconsistent caches.
