# Entity Store Migration

## Problem

`GameState.advance_turn()` is currently dominated by live entity mutation through
Polars DataFrames. This is the wrong storage model for the hot simulation loop.

Polars remains valuable for bulk inspection, debugging, exports, fixtures, tests,
and analytics, but it should not be the authoritative mutable entity store during
turn processing.

Current hot-path problems:

- `EntityRegistry.entities_df` is the live entity table.
- `set_entity_component()` checks entity existence through a lazy Polars query
  and `.collect()`.
- `set_entity_component()` updates one component by rebuilding a DataFrame column
  with `with_columns(...)`.
- `set_position()` calls `set_entity_component()` twice, once for `x` and once
  for `y`.
- `try_move()` calls `get_position()` and then `set_position()`, so every move
  performs DataFrame reads and two scalar DataFrame writes.
- Collision queries such as `get_blocking_entity_at()` scan/filter the entity
  DataFrame instead of using an occupancy grid.

This creates catastrophic scaling under AI load. The benchmark harness
`bench/bench_advance_turn.py` exists to measure this.

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
