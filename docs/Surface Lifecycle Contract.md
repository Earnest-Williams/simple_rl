# Surface population, identity and hydration contract

This note describes the **runtime boundary** implemented on PR #262. It is
not an assertion that the surface modules are already wired into the game loop.

## Identity is not an array slot

An actor has three separate identifiers:

- **Canonical birth key**: stable world/versions/chunk/anchor-ordinal
  identity, stored as `birth_key` with the actor.
- **Numerical entity ID**: a UInt32 surrogate reserved in a *world-wide*
  `SurfaceIdentityLedger`; high-bit values identify generated actors.
- **EntityStore array index**: transient, reusable when the actor leaves
  active ECS storage.

World save directories must retain **both** the compact checkpoint
`surface_actor_ids.json` and its append-only batch log
`surface_actor_ids.log`, alongside all chunk journals. Worlds saved by
older versions with only the JSON checkpoint continue to load without
migration steps: newly reserved IDs are appended to the log and older
checkpoint bytes remain intact until explicit compaction. Do not create a
new ledger on every chunk load; that would discard reservations held by
dehydrated actors.

The default hash can collide in the 31-bit surface namespace. The ledger
probes a second salted candidate and checks all other world reservations.
The planner stages the placements and reserves all IDs with one
`reserve_many(...)` transaction, appending **one checksummed log record
per populated chunk** and fsyncing that record *before* spawning actors.
The number of previous actors does not affect the amount of ledger data
written during a new chunk's reservation. Numeric
surrogates remain stable in a saved world. **If two colliding birth keys
are first discovered in different orders in two brand-new worlds, their
surrogate IDs may differ**. The canonical birth keys remain the same.
Strictly order-independent surrogate allocation under collisions requires
a wider identity representation or a globally preallocated manifest.

### Append recovery and checkpoint compaction

Every append-only record is an orjson-encoded, newline-terminated batch with
a SHA-256 checksum. At load time, the ledger reads the JSON checkpoint,
replays every complete validated log record, and recognizes identical
assignments replayed twice. A final truncated record (interrupted append) is
discarded and truncated before new appends; a **complete** corrupt record or
a conflicting numeric assignment fails closed instead of overwriting history.
An I/O error during append prevents the current in-memory ledger from
reserving more IDs until it has been reloaded.

Call `ledger.compact()` at a **save checkpoint outside the gameplay
loop**, e.g. after a group of loaded chunks has been unloaded, rather than on
every chunk population. Compaction fsyncs and atomically replaces the complete
JSON checkpoint **before** truncating the replay log; a crash between the
two actions safely replays duplicate records. It is an explicit maintenance
operation, not a source of frame-time spikes.

## First visit / revisit

1. Load one shared ledger with
   `SurfaceIdentityLedger.load_or_create(save_directory)`.
2. Load each chunk's `SaveDiffJournal` and materialize its generated
   base. Apply the journal's tile overlay.
3. On *first visit only*, construct `SurfacePopulationPlanner` with
   `identity_ledger=ledger`, then call
   `planner.populate_chunk(chunk, journal)`. This records birth-key
   assignments and permanently marks the chunk as initialized.
4. Write the journal via `journal.write_atomic(save_directory)`.
5. On revisit, **do not repopulate**: the journal's
   `population_initialized` bit prevents duplicates. Hydrate the
   existing actor snapshots with `ChunkHydrationManager`.
6. The durable ledger batch commit must succeed before any generated actor
   spawns; a disk-write error rolls back newly staged in-memory IDs.
7. On permanent death, record the birth-key tombstone with
   `journal.mark_population_death(birth_key)` in the actor's birth
   journal and remove its active ECS entity. Deaths do not cause
   regenerated births.

A caller must arrange persistence of actor deaths and migration state.
A populated journal is stateful world data, not a disposable generator
cache. Losing a journal can lose mutation and life/death history.

## Immediate Bubble and hydration

Use `EntityRegistryActorStore` over a real `EntityRegistry`; initialize
the occupancy grid before spawning blocking actors. The occupancy grid
uses signed Int64 values to hold every UInt32 actor ID; `-1` denotes
an empty cell.

`ChunkHydrationManager` requires a `SurfaceContext` or explicit
`can_occupy` callback when given the production adapter. Its relocation
logic respects the chunk boundary, occupancy and the actor's traversal
profile. Only generated surface actors with a supported behavior and a
template ID qualify for automatic dehydration. Player and unrelated
entities cannot be evicted by this pathway.

For dehydration, `active_actor_ids_in_rect(x0, y0, x1, y1)` selects
candidate residents before taking snapshots. The production implementation
uses the registry's NumPy position arrays and applies viewport-origin
translation. Eviction locks and eligibility checks are evaluated before
snapshot serialization; the cost of serializing detailed actor components
therefore depends on the actors **inside** the departing chunk, not the
entire active population.

The adapter captures the serializable ECS components and the separate
vectorized skill table. Object values without an explicit JSON serializer
raise `TypeError` rather than silently degrading into strings. Actors whose
state cannot be serialized remain active and emit a warning recording their
identity and chunk. Add approved encoders/decoders before allowing new opaque
actor state to dehydrate.

Reconstruct `SurfaceContext` and `EntityRegistryActorStore` when
the viewport origin changes; both hold an origin fixed at construction.

## Two-sided terrain mutations

`SaveDiffJournal.record_tile_mutation(x, y, tile_id)` by itself changes
**only base tile geometry**. It does not rewrite underlying water, mud,
hydrology, traversal costs or materials. This preserves semantic
generated terrain across a floor-to-floor replay, temporary obstruction
or re-materialization.

When an action truly changes surface semantics, callers supply
`material=`, `traversal=`, `movement_cost=`, `wetness=` and/or
`hydro=` as appropriate. The journal stores that explicit semantic
overlay. Re-recording a tile without semantic keywords **preserves** existing
overrides; supplying a keyword updates only that semantic field. Use
`clear_semantics=True` to explicitly reset all prior overrides when restoring
generated defaults. For example, breaching a solid generated wall requires an
explicit walkable traversal override; merely changing its tile glyph
does not magically establish a traversable passage.

A reloaded chunk begins from immutable generated terrain, then receives
the explicit journal overlay. Avoid treating the current mutable
viewport as the immutable baseline.

## Regression and quality gates

The PR's surface suite includes real-registry high-bit occupancy,
multichunk load/dehydrate/reload, player exclusion, negative/translated
viewports, skill-row recovery, spring ownership and lossless tile replay.

The dedicated workflow runs the broader repository suite (excluding the
independently broken window-manager height-toggle test), with Qt configured
offscreen and EGL libraries installed. Ruff gates modified Python files.
Black gates all new/formatted files and checks **changed line ranges only**
in legacy `registry.py`, `store.py`, and `surface_materializer.py`, so
pre-existing formatting outside the patch does not inflate its diff.
Strict mypy gates the changed surface modules **and**
`game/entities/registry.py`; the old mypy error-suppression exemption for
that registry module has been removed. The separate repository-wide mypy
audit remains informational due to unrelated legacy errors.

The ledger and chunk journal both use `orjson` for deterministic JSON
encoding and decoding. Their existing `.json` on-disk formats remain
readable (the append-only identity log is additional), and the journal's
`to_json()` method still returns text for callers that need that API.
