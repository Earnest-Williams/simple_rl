# Overland Next Steps

This document is the tactical implementation queue beneath
[Overland Roadmap](./Overland%20Roadmap.md). It tracks concrete engineering
slices for the current `worldgen/overland` implementation; the roadmap owns the
longer-term generator direction and start-of-game contract.

## Current State

The overland generator now has a stable first-pass terrain contract:

- semantic overland tile schema
- karst-to-volcanic region generation
- seasonal hydrology transforms
- movement/traversal derivation
- actor-specific traversal helpers
- actor-specific overland pathfinding
- feature and tile query helpers
- transition request generation
- transition Arrow artifact output
- selected route Arrow artifact output
- wildlife affordance output
- settlement-to-overland merge path
- headless generation and actor-aware ASCII inspection

The system can generate a dynamic overland region, merge a starting port into
that region, write inspectable Arrow artifacts, and derive traversal behavior
for different actor profiles.

## Near-Term Goal

Turn overland data into playable movement and routing.

The immediate milestone is:

```text
A seeded overland region can generate actor-specific movement grids and route
between meaningful surface features, with seasonal hydrology changing the route.
```

## Completed: Add Overland Pathfinding

Implemented helper:

```python
find_overland_path(bundle, start, goal, profile)
```

Current behavior:

- A* on 8-way movement
- uses `build_actor_cost_grid(...)`
- infinite cost means blocked
- diagonal movement uses a simple square-root-of-two multiplier
- returns an `OverlandRoute` with path, total cost, and failure reason

Tests:

- human wet-season route is blocked through flooded sinking lake
- human dry-season route can cross cracked mud
- boat wet-season route can use flooded basin
- boat dry-season route is blocked when the lake drains
- amphibious route can use wet corridors more cheaply
- route output is stable for a repeated seed

## Completed: Add Feature Selection Helpers

Implemented helpers:

```python
find_feature(bundle, feature_type)
find_nearest_feature(bundle, origin, feature_type)
find_tiles_by_material(bundle, material)
find_tiles_by_hydro_role(bundle, hydro_role)
first_tile_by_material(bundle, material)
first_tile_by_hydro_role(bundle, hydro_role)
```

These helpers work on in-memory bundles and loaded Arrow-backed bundles because
they operate on the bundle DataFrames directly.

## Step 1: Add Route Artifacts

Completed. Bundle writing now emits selected route output:

```text
overland_routes.arrow
```

Suggested columns:

- `route_id`
- `profile`
- `source_x`
- `source_y`
- `target_x`
- `target_y`
- `step_index`
- `x`
- `y`
- `cost_so_far`
- `tags`

The route writer does not write every possible route. It starts with selected
debug/regression routes:

- coast to spring garden
- starting port to limestone gorge
- starting port to lava-tube skylight
- sinking lake edge to ponor

Use the completed feature helpers to choose endpoints:

- spring garden
- limestone gorge
- ponor
- lava-tube skylight
- starting port

Implemented helpers:

```python
generate_debug_routes(bundle)
overland_routes_to_df(routes)
```

`write_overland_bundle(...)` writes `overland_routes.arrow`, and
`load_worldgen_bundle(...)` loads it as `routes_df` when present.

## Completed: Improve Hydrology Continuity

The current regional hydrology model now emits a connected first-pass karst
drainage system instead of only representative features. It also emits an
ordinary perennial pond/lake system with normal surface inflow and outflow, so
not every waterbody is treated as karst-special.

Implemented behavior:

- ensure surface channels connect spring gardens, sinking basins, ponors, and
  estavelles
- separate visible surface channels from underground channels
- assign stable `flow_group` IDs to connected hydrology systems
- make `connected_to_underground` meaningful for ponor, estavelle,
  karst-window, and underground-channel records
- keep ordinary perennial ponds/lakes stable and surface-only

Tests:

- each ponor belongs to a flow group
- at least one spring and ponor share a system
- spring, sinking lake, ponor, and estavelle records share flow group `1`
- the emitted hydrology rows form a contiguous graph for that flow group
- underground-connected rows include ponors, estavelles, and underground
  channels
- ordinary perennial surface water uses `PERMANENT_POOL`, has surface-channel
  inflow and outflow, and is not underground-connected

## Step 3: Make Settlement Placement More Regional

Partially completed. The starting port now passes regional spatial constraints
into `settlegen` and uses deterministic placement contracts for coastline,
river mouth, road endpoints, and nearby cave entrances.

Inputs to use:

- coastline edge
- river/surface-channel mouth
- nearby cave mouth or karst window
- nearby trail exit
- available buildable lowland
- hydrology risk

Behavior:

- port docks should align with water/shore
- roads should point toward inland route candidates
- explicit rural facilities should reliably place on available lowland/farmable
  terrain
- avoid placing dense town blocks on deep water or cliffs

Tests:

- merged port always has dock material adjacent to water material
- road or trail exits point inland
- merged port exports road, dock, building-floor, and rural field/orchard/pasture
  surface materials
- settlement merge preserves critical hydrology and transition features

## Step 4: Add Overland-Aware GameMap Metadata

Current `GameMap` conversion still reduces overland to floor/wall tiles. Keep
that simple visual map, but add a sidecar metadata structure for gameplay.

Options:

- return `(GameMap, OverlandMapMetadata)`
- attach read-only overland arrays to `GameMap`
- expose a separate `OverlandRuntimeMap`

Required runtime data:

- material grid
- biome grid
- wetness grid
- hydro role grid
- movement cost grid
- traversal class grid
- transition lookup
- affordance lookup

Do not flatten overland semantics into dungeon-style tiles permanently.

## Step 5: Add Actor-Aware Debug Views

Completed. ASCII inspection supports actor traversal modes:

```bash
python tools/inspect_overland.py out_dir --view actor --profile HUMAN_ON_FOOT
python tools/inspect_overland.py out_dir --view actor --profile BOAT
```

Glyph goals:

- blocked: `#`
- normal: `.`
- slow: `,`
- wade: `w`
- swim/boat: `~`
- transition: `*`
- hazardous: `!`

This gives CI-friendly visibility into gameplay interpretation.

## Completed: Add Pathfinding Regression Tests

Implemented high-level test:

```text
test_seasonal_overland_routes_are_profile_specific()
```

Assertions:

- generated bundle is stable by seed
- human wet-season flooded lake route is blocked
- human dry-season cracked mud route exists
- boat route exists in wet season but fails in dry season
- amphibious route is cheaper than human on a wet route
- routes are stable by checksum

## Step 6: Keep Settlements Secondary To Overland

Settlement generation should continue, but as one producer of overland-compatible
surface layers.

Next settlement work should focus on:

- making roads/trails connect to overland routes
- preserving hydrology and transition features during merge
- tagging settlement facilities as route/encounter/economy anchors
- eventually generating villages along overland route networks

Avoid making a settlement-only gameplay path that bypasses the overland schema.

## Completed: Add Starting-Region Contract

The current regional profile now emits a first-pass start-of-game contract in
`overland_metadata.json` and matching `overland_features.arrow` rows.

Implemented behavior:

- ruined harbor / dead port feature and surface tiles
- local survey zone metadata centered on the harbor
- fresh-water and resource-site feature rows
- ancient road feature and road tiles leading inland
- clearable blockage feature and route metadata
- first waystation candidate
- first inland site candidate
- ordinary cave reference with a cave-mouth transition tile
- route segment state, endpoint references, blockage reference, and
  actor-profile cost hints

Tests:

- required starting-region feature types are emitted
- road, dock, ruin, blockage, and cave-mouth surfaces exist
- contract metadata includes survey, resources, route, blockage, waystation,
  inland site, and cave references
- ordinary cave reference produces a `CAVE_ENTRANCE` transition

## Completed: Add Cave Transition Payloads

Transition artifacts now include first-pass handoff payloads for cave-like
surface transitions.

Implemented behavior:

- cave type for ordinary caves, ponor descents, karst windows, spring sources,
  lava-tube skylights, and collapsed lava tubes
- hydrology `flow_group`, seasonal state, and underground-connectivity context
- substrate and elevation-band context
- nearby affordance summary
- compact handoff tags combining target kind, cave type, terrain context, and
  feature tags

Tests:

- `overland_transitions.arrow` includes the additive handoff columns
- ordinary starting-region cave is classified as `ordinary_cave`
- ponor descents carry karst flow-group and underground-connectivity context
- lava-tube skylights carry lava-tube target and basalt context

## Recommended Next PR

The previous recommendation is implemented. The next best slice is the Phase 4
site-history and evidence-tag work from [Overland Roadmap](./Overland%20Roadmap.md).

Implement:

1. compact historical and archaeological metadata for ruins and route remnants
2. prior expedition trace tags
3. repair, collapse, abandonment, and reuse evidence tags
4. evidence tags on starting-region harbor, road, blockage, waystation, inland
   site, and cave references
5. tests proving evidence metadata is emitted without runtime knowledge logic

Keep this next slice scoped to generator outputs and metadata. Do not broaden it
into runtime expedition gameplay, full survey/knowledge systems, or dungeon
generation internals yet.
