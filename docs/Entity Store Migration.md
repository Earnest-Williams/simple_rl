# Entity Store Migration

## Problem

`GameState.advance_turn()` was previously dominated by live entity mutation
through Polars DataFrames. That was the wrong storage model for the hot
simulation loop, and the migration away from DataFrame-owned runtime mutation is
now well underway.

Polars remains valuable for bulk inspection, debugging, exports, fixtures, tests,
and analytics, but it should not be the authoritative mutable entity store during
turn processing.

Historical hot-path problems included:

- `EntityRegistry.entities_df` acting as the live entity table instead of a
  compatibility snapshot.
- `set_entity_component()` checking entity existence through lazy Polars queries
  and `.collect()`.
- Scalar component updates rebuilding DataFrame columns with `with_columns(...)`.
- Position updates writing `x` and `y` through separate scalar component paths.
- Movement and collision checks scanning/filtering DataFrames instead of using
  store fields and occupancy/spatial indexes.

These are no longer all current production blockers. Combat, perception, monster
perception, sound context, AOE, and AI adapter paths have moved substantially
toward registry/store accessors, entity IDs, spatial indexes, and cached Polars
compatibility snapshots. The benchmark harness `bench/bench_advance_turn.py`
exists to measure remaining turn-loop costs.

## Goal

Replace the live entity store with a mutable, row-addressable runtime structure.

The target design is:

- Numeric hot fields live in NumPy arrays.
- Object/string/list fields live in Python lists indexed by entity row.
- `entity_id_to_index: dict[int, int]` maps stable entity IDs to row indices.
- Movement updates `x` and `y` directly in one operation.
- Collision uses an occupancy grid, not a DataFrame filter.
- Polars becomes a cached snapshot/view generated from the live store when needed.

## Non-goals

- Do not remove Polars from the project.
- Do not rewrite every system in one PR.
- Do not optimize FOV first.
- Do not preserve Polars as the live mutable entity source.

## Current status as of 2026-06

- [x] **Phase 1: Introduce `EntityStore` behind `EntityRegistry` — mostly
  complete.** `entities_df` should now be treated as a compatibility/reporting
  snapshot, while hot registry APIs read and write through store-oriented fields.
- [x] **Phase 2: Fast movement and occupancy — mostly complete.** Movement,
  collision, spatial-index population, and common position updates should prefer
  store/index access. Continue watching for legacy callers that still route
  movement through scalar DataFrame-shaped updates.
- [ ] **Phase 3: Rewrite process-turn over indices — partially complete.**
  `game_state.py` has moved important paths to active indices, entity IDs, and
  spatial-index entries, but process-turn remains the highest-risk place for
  compatibility rows and remaining `entities_df` materialization.
- [x] **Phase 4: Remove Polars from perception hot reads — substantially
  complete.** Visible-enemy and perception paths now use registry/store
  accessors and spatial-index candidates in production code; fallback or test
  compatibility paths should remain cold and explicit.
- [x] **Phase 5: Replace AI row dicts with entity IDs or typed views —
  substantially complete for production adapters.** GOAP/strategy adapters and
  perception snapshots have moved toward entity-ID/store access. Remaining
  exceptions should be called out when a production path still requires a
  DataFrame-shaped row dictionary.

Current follow-up work is therefore not "start the migration"; it is to profile
the next dominant turn-processing bottleneck, remove any remaining hot
compatibility-row construction, and keep `entities_df` uses clearly separated
from runtime mutation.

## Runtime storage model

Introduce an internal `EntityStore`, likely in:

```text
game/entities/store.py

The store owns arrays/lists such as:

entity_id: np.ndarray[np.uint32]
is_active: np.ndarray[np.bool_]
x: np.ndarray[np.int16]
y: np.ndarray[np.int16]
glyph: np.ndarray[np.uint16]
hp: np.ndarray[np.int16]
max_hp: np.ndarray[np.int16]
blocks_movement: np.ndarray[np.bool_]
intelligence: np.ndarray[np.int16]

name: list[str | None]
ai_type: list[str | None]
species: list[str | None]
faction: list[str | None]
strategy_state: list[str | None]
status_effects: list[list[dict[str, object]]]
body_plan: list[dict[str, int]]

All arrays/lists use the same row index.
```

### Polars role

Polars becomes a materialized compatibility/reporting view:

```python
to_polars() -> pl.DataFrame
```

`EntityRegistry.entities_df` may remain temporarily as a cached property:

```python
@property
def entities_df(self) -> pl.DataFrame:
    if self._entities_df_dirty:
        self._entities_df_cache = self.to_polars()
        self._entities_df_dirty = False
    return self._entities_df_cache
```

Runtime mutation must mark the snapshot dirty, but must not mutate through Polars.

### Occupancy grid

Add a map-sized occupancy grid for blocking entities:

```python
blocking_entity_at[y, x] = entity_id
```

Use `-1` for empty cells.

Movement must update occupancy when blocking entities move.

`get_blocking_entity_at(x, y)` should become one array lookup.

## Migration phases

### Phase 1: Introduce EntityStore behind EntityRegistry

Keep the public `EntityRegistry` API stable:

- `create_entity`
- `get_entity_component`
- `set_entity_component`
- `get_entity_components`
- `get_position`
- `set_position`
- `get_active_entities`
- `get_blocking_entity_at`
- `delete_entity`
- `compact_registry`

Reimplement those methods against `EntityStore`.

Acceptance criteria:
- Existing tests pass.
- `entities_df` still works as a compatibility snapshot.
- No hot mutation path calls Polars `.collect()`.

### Phase 2: Fast movement and occupancy

Add a direct movement/update path:

```python
move_entity(entity_id: int, dx: int, dy: int, game_map: GameMap) -> bool
```

or:

```python
try_move_entity(entity_id: int, dest_x: int, dest_y: int, game_map: GameMap) -> bool
```

Movement must:
- Read current x/y from arrays.
- Check bounds.
- Check map walkability.
- Check occupancy.
- Update x/y arrays.
- Update occupancy.
- Mark Polars snapshot dirty.
- Emit perception noise from `movement_system.try_move()` after success.

Acceptance criteria:
- `set_position()` no longer performs two component writes.
- `movement_system.try_move()` no longer depends on DataFrame mutation.
- Scenario tests still pass.

### Phase 3: Rewrite process_turn over indices

Change `GameState.process_turn()` to iterate active entity indices from the store, not `entities_df.iter_rows(...)`.

It should build:
- active indices
- AI indices
- spatial index entries
- pending status/resource updates

Acceptance criteria:
- `process_turn()` does not materialize `entities_df`.
- Spatial index population uses array/list fields.
- AI rows may still be compatibility dicts temporarily.

### Phase 4: Remove Polars from perception hot reads

Update `find_visible_enemies()` and related perception code to read from:
- spatial index
- active indices
- x/y arrays
- faction lists
- active flags

Acceptance criteria:
- `gather_perception_snapshot()` avoids DataFrame filtering in the per-entity loop.
- Behavioral perception tests still pass.

### Phase 5: Replace AI row dicts with entity IDs or typed views

Long-term AI adapter signature should move toward:

```python
take_turn(entity_id: int, game_state: GameState, rng: GameRNG, perception: PerceptionSnapshot)
```

instead of passing loose row dictionaries.

Acceptance criteria:
- GOAP and strategy AI no longer require DataFrame-shaped rows.
- Hot AI logic reads from registry arrays/lists directly.
- Compatibility wrappers remain only for cold/test paths.

## Benchmark gate

Use `bench/bench_advance_turn.py` after every phase.

Baseline commands:

```bash
python bench/bench_advance_turn.py --entities 50 --width 50 --height 50 --turns 1 --warmup-turns 0
python bench/bench_advance_turn.py --entities 100 --width 60 --height 60 --turns 1 --warmup-turns 0
```

Target sequence:
1. Remove Polars `.collect()` from mutation paths.
2. Get 100 entities under 5 seconds/turn.
3. Get 100 entities under 1 second/turn.
4. Continue only after profiling confirms the next dominant bottleneck.

## Validation

Run:

```bash
pytest -q tests/test_ai_turn_scenarios.py tests/test_ai_perception_behavior.py tests/test_perception_systems.py tests/test_ai_behavior.py
python -m compileall game tests bench/bench_advance_turn.py
```
