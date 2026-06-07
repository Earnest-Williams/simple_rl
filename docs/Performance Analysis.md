# Performance Analysis Historical Audit

**Original audit date:** 2026-01-18
**Status refresh:** 2026-06
**Codebase:** simple_rl (Python Roguelike Game Engine)
**Scope:** Performance anti-patterns, N+1 queries, unnecessary re-renders, inefficient algorithms

---

## Current reading guidance

This document is now a historical audit with resolved/open status annotations. It
should not be read as a current P0 incident list. The canonical entity-store
migration status lives in
[`docs/Entity Store Migration.md`](./Entity%20Store%20Migration.md), and current
day-to-day verification guidance lives in [`docs/Testing.md`](./Testing.md) and
[`docs/Runbook.md`](./Runbook.md).

The biggest stale assumptions from the original report have changed:

- **Combat component lookups:** Resolved for the melee hot path. Current
  `game/systems/combat_system.py` bulk-fetches attacker/defender combat
  components through `EntityRegistry.get_combat_components_bulk()`, skills
  through `EntityRegistry.get_skills_bulk()`, and equipment through
  `ItemRegistry.get_equipped_items_bulk()` instead of issuing the old sequence
  of scalar component lookups per attack.
- **Perception enemy detection:** Substantially resolved for the production
  visible-enemy paths. Current `game/ai/perception.py` uses registry/store
  accessors and the spatial-index path instead of materializing
  `entities_df.iter_rows(...)` in the hot visible-enemy search.
- **Entity store migration:** No longer purely future work. The project has moved
  important combat, perception, monster-perception, sound-context, AOE, and AI
  adapter paths toward entity IDs, store/index accessors, and compatibility
  snapshots.

The remaining useful backlog is to profile the next dominant turn-processing
bottleneck after those migrations, verify remaining non-combat item/equipment
DataFrame paths, and keep rendering/lighting checks tied to the production
lighting/FOV tests.

---

## Status summary

| Area from original audit | Current 2026-06 status | Notes / next action |
| --- | --- | --- |
| Combat component N+1 queries | **Resolved for melee hot path** | Keep regression tests around `EntityRegistry.get_combat_components_bulk()`, `EntityRegistry.get_skills_bulk()`, and `ItemRegistry.get_equipped_items_bulk()` usage. |
| Perception visible-enemy O(N²) scan | **Substantially resolved** | Current production paths use store accessors and the spatial index; retain fallback coverage for compatibility paths. |
| Entity position double query / scalar mutation | **Mostly resolved by store-oriented registry paths** | Continue checking movement and non-combat callers for accidental DataFrame mutation. |
| `GameState.process_turn()` entity iteration | **Partially migrated** | Review remaining compatibility row-dict construction and any direct `entities_df` materialization. |
| Equipment/item template lookups outside combat | **Open / needs profiling** | Verify non-combat equipment, inventory, and item-template paths after combat fixes. |
| UI frame conversion, dirty rects, frame pacing | **Open unless a later profiling PR proves otherwise** | Treat as rendering backlog, not entity-store migration work. |
| Lighting/FOV nested-loop concerns | **Superseded by production lighting/FOV cache work** | Use production lighting tests and the visual tool instead of the removed legacy diagnostic. |
| GOAP nearest-entity scans | **Partially migrated** | Production adapters prefer spatial-index access where available; keep cold/test compatibility paths isolated. |
| Flow-field / pathfinding cache work | **Open** | Re-profile after entity-store and perception work to confirm priority. |

---

## Current performance backlog

### P0: Re-profile turn processing after entity-store migration

The original report assumed combat and perception DataFrame scans were still the
primary hot spots. Those paths have been changed, so the next optimization should
start with fresh `advance_turn()` or `process_turn()` profiling rather than
re-implementing old recommendations.

Recommended benchmark commands:

```bash
python bench/bench_advance_turn.py --entities 50 --width 50 --height 50 --turns 1 --warmup-turns 0
python bench/bench_advance_turn.py --entities 100 --width 60 --height 60 --turns 1 --warmup-turns 0
```

Use the profile to decide whether the next dominant cost is turn iteration,
pathfinding, item/equipment lookups, AI adapter compatibility rows, rendering, or
lighting.

### P1: Verify remaining DataFrame-shaped compatibility paths

The next audit should search for hot callers that still materialize
`entities_df`, use row dictionaries in production AI paths, or mutate runtime
state through Polars. Compatibility snapshots are acceptable for reporting,
fixtures, tests, exports, and cold paths; they should not own the turn loop.

Focus areas:

- `game/game_state.py` compatibility row construction and remaining turn-loop
  materialization.
- Non-combat item/equipment paths that may still chain DataFrame filters.
- AI adapters that still accept row dictionaries instead of entity IDs or typed
  views.
- Any direct Polars mutation in movement, AOE, sound context, or perception.

### P1: Rendering and UI frame work

The original rendering concerns are still plausible until re-profiled:

- PIL/QImage/QPixmap conversion and image-copy overhead.
- Lack of dirty-rectangle rendering.
- Overlay copying and redundant full-frame refreshes.
- Frame pacing or rate limiting under held-key input.

Treat these as independent rendering work after turn-processing bottlenecks are
measured.

### P2: Pathfinding and propagation work

Flow-field caching, early termination, and propagation-map reuse remain valid
ideas, but they should be prioritized only after fresh profiling confirms that
pathfinding/perception propagation is the limiting cost.

---

## Historical findings retained for context

The sections below summarize why the original audit existed. Items marked
**resolved** should not be filed as new bugs unless regression profiling shows the
problem has returned.

### Combat system component access — resolved

The original report described 13 scalar `get_entity_component()` calls per melee
attack and recommended adding a bulk component fetch method. That recommendation
has been implemented in the combat hot path. Current combat code bulk-fetches the
attacker/defender data it needs with `EntityRegistry.get_combat_components_bulk()`,
reads equipped items with `ItemRegistry.get_equipped_items_bulk()`, and
bulk-fetches attacker/defender skills with `EntityRegistry.get_skills_bulk()`.

Regression risk: future combat changes should avoid reintroducing scalar
component lookups inside per-attack loops.

### Perception enemy detection — substantially resolved

The original report described a production visible-enemy loop over
`game_state.entity_registry.entities_df.iter_rows(named=True)` for every actor.
Current production visible-enemy code builds candidates from registry/store
accessors and uses the spatial index when present.

Regression risk: fallback compatibility scans should remain cold, covered by
behavior tests, and easy to identify during profiling.

### Game-state turn iteration — partially migrated

The original report flagged multiple full entity iterations per turn. The store
migration has reduced several hot DataFrame reads, but `game_state.py` should
remain under review because turn processing is the place most likely to rebuild
compatibility dictionaries for legacy AI callers.

Next action: inspect remaining `entities_df` uses and row-dict adapters in
`GameState.process_turn()` whenever process-turn performance changes.

### Equipment and item lookup churn — open

The combat hot path no longer represents the old repeated equipped-item lookup
problem. Non-combat equipment and inventory flows still deserve a targeted audit:
fetch an item/template once per operation, pass structured data through helper
calls, and avoid chained DataFrame filtering in repeated operations.

### Rendering and lighting — open / superseded depending on path

The original report included UI image-copy concerns and old light-iteration
concerns. For lighting/FOV diagnostics, use the production tests and
`python -m tools.lighting_fov_tool.main`; do not rely on removed legacy scripts.
Rendering copy/dirty-rect work remains a separate backlog item until measured.

---

## Validation guidance

Before changing priorities in this document, run or record why you cannot run:

```bash
python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py
python -m pytest tests/test_ai_turn_scenarios.py tests/test_ai_perception_behavior.py tests/test_perception_systems.py tests/test_ai_behavior.py
python bench/bench_advance_turn.py --entities 100 --width 60 --height 60 --turns 1 --warmup-turns 0
```

For GUI-only lighting/FOV inspection, use:

```bash
python -m tools.lighting_fov_tool.main
```
