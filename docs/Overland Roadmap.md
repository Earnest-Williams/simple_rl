# Overland Roadmap

## Purpose

This is the canonical planning document for `worldgen/overland`. It bridges the
planet-scale intent in [World Generator Design Proposal](./World%20Generator%20Design%20Proposal.md)
to the current overland implementation described in
[Overland Generation](./Overland%20Generation.md).

This document is aspirational unless it explicitly says a behavior is current.
[Overland Generation](./Overland%20Generation.md) is the authoritative reference
for implemented artifacts, schemas, commands, and tests.

The roadmap is generator-owned. It defines planned terrain, hydrology, route,
site, settlement, cave-transition, resource, and metadata outputs. Runtime
expedition gameplay, base assignments, threats, map knowledge, and local
simulation systems are downstream consumers, not part of this generator scope.

## Current Vs Planned

| Area | Current status | Roadmap status |
| --- | --- | --- |
| Overland artifacts | `overland_tiles.arrow`, `overland_hydrology.arrow`, `overland_features.arrow`, `overland_affordances.arrow`, `overland_transitions.arrow`, `overland_routes.arrow`, and `overland_metadata.json` are the current implemented contract. | Extend these artifacts narrowly or add sidecars only when a phase requires it. |
| `flow_group` | The current regional profile emits a stable connected karst `flow_group` covering springs, sinking lakes, ponors, estavelles, channels, and karst windows. | Future profiles should preserve connected-system semantics as hydrology grows beyond the first regional profile. |
| Connected hydrology | The current regional profile emits karst water systems with visible surface channels, hidden underground channels, and underground-connected ponor/estavelle/karst-window endpoints; it also emits ordinary perennial pond/lake water with stable surface inflow and outflow. | Later work can add richer drainage ranking, discharge, and seasonal network variation. |
| Route segment state | Selected debug routes are emitted in `overland_routes.arrow`; `overland_metadata.json` now includes first-pass starting-region route segment state, endpoints, blockage reference, and actor-profile cost hints. **Option A and Option B complete**: road connection pathfinding merges settlement endpoints to routes, and runtime `OverlandMapMetadata` sidecar drives `movement_cost_for_actor`/`build_actor_cost_grid` (REPAIRED *= 0.75, BLOCKED=inf). `simulate_route_repair` + tests verified. |
| Cave payloads | Transition records now include cave type, hydrology context, seasonal state, flow group, underground connectivity, substrate, elevation band, nearby affordances, and handoff tags for cave-like transitions. | Future work can add richer evidence hooks and dungeon-specific tuning fields as needed. |
| Evidence hooks | Terrain features and transitions can carry tags. | Historical, archaeological, ruin, repair, and prior-expedition evidence hooks are planned. |
| Runtime sidecar | Integrated: `GameMap` conversion attaches the `OverlandMapMetadata` sidecar at runtime, driving movement profiles and **Option C (seasonal hydrology/traversability transitions)** dynamically. | Runtime-facing overland metadata is integrated. |

## Design Target

The long-term target is an Alaska- or Greenland-scale lost continent with
playable regional slices generated first. The map should read as a hydrological,
ecological, and archaeological simulation substrate, not as generic terrain with
decorative points of interest.

The generator should eventually produce:

- large-scale coastal, lowland, karst, foothill, volcanic, and highland structure
- seasonal water behavior that changes traversal, routes, entrances, and
  affordances
- ancient and recent human traces with enough metadata for later gameplay
  systems to reason about them
- cave and dungeon handoff payloads that preserve the surface context of each
  entrance
- regional contracts that can be converted into the first playable expedition
  map without collapsing overland semantics into dungeon-style floor/wall tiles

## Long-Term Generator Direction

### Macro Continent Structure

Generation should scale from the current regional
`KARST_TO_VOLCANIC_MOUNTAIN` profile toward larger continent structure:

- coastlines, dead ports, drowned lowlands, and river mouths
- karst wet forest, limestone benches, sink fields, gorges, and cave windows
- foothills, passes, upland basins, and defensible ridges
- volcanic cloud forest, lava-tube terrain, basalt barrens, and old flow fields
- highland peat, moor, ice-edge analogues, and sparse route corridors

The near-term implementation can stay regional, but each regional slice should
be shaped so it can later sit inside a wider continent model.

### Seasonal Karst Hydrology

Hydrology is the next major semantic layer. Future generation should model
connected seasonal systems rather than isolated representative features:

- springs, spring gardens, and source pools
- ponors, estavelles, swallow holes, and karst windows
- sinking lakes, draining basins, mud states, and cracked dry-season floors
- visible surface channels and separate underground links
- stable `flow_group` IDs for connected hydrology systems
- ordinary perennial ponds and lakes with normal surface inflow and outflow
- meaningful `connected_to_underground` values for transition and route logic

Hydrology should affect traversal, resource affordances, cave entrances, route
viability, and later runtime metadata.

### Ancient Infrastructure

The lost continent should preserve infrastructure as terrain evidence:

- ancient roads, causeways, boardwalks, trail cuts, and switchbacks
- waystations, watch posts, signal points, shrines, and bridge footings
- repaired, blocked, drowned, collapsed, overgrown, or buried route segments
- route endpoints and segment state suitable for future repair and clearing
  systems

These outputs should remain generator artifacts. Runtime systems can later turn
them into actions, jobs, discoveries, hazards, or encounters.

### Settlements And Ruins

Settlements should be placed from regional context, not as standalone maps.
Placement should account for:

- stable fresh water and seasonal flood risk
- route access, harbor access, and road junctions
- defensible ground, buildable lowland, and resource proximity
- historical phase: occupied, abandoned, repaired, destroyed, drowned, or
  overgrown

`settlegen` remains a producer merged into overland-compatible surfaces. It is
not the top-level world schema.

### Cave And Dungeon Handoff

Overland should identify cave and dungeon candidates with enough payload for
the downstream dungeon generator to preserve surface meaning:

- entrance coordinates and transition type
- cave type such as ordinary cave, ponor descent, karst window, spring source,
  lava-tube skylight, or collapsed lava tube
- hydrology role, seasonal state, and `flow_group`
- biome, substrate, elevation band, and nearby affordances
- evidence hooks such as smoke traces, repairs, old shrine markers, fresh
  tracks, prior expedition debris, or collapse scars

The dungeon generator remains a separate consumer of these handoff records.

### Site History And Archaeology

POIs, ruins, routes, and settlements should carry compact history metadata:

- occupation phase
- collapse or abandonment phase
- repair or reuse evidence
- prior expedition traces
- burial, flooding, fire, volcanic, or structural damage
- visible evidence tags that can become survey discoveries later

The generator should produce evidence hooks; gameplay systems decide what the
player knows, remembers, or can act on.

### Downstream Consumers

Future consumers may include:

- runtime overland map metadata
- local survey and generated description systems
- route repair and blockage-clearing systems
- scent, threat, weather, wildlife, and encounter fields
- map knowledge, rumor, and expedition log systems
- wildness or Doom-gradient style progression pressure

These are downstream systems. The generator roadmap only requires that overland
artifacts expose enough structured context for them.

## Near-Term Start-Of-Game Plan

The first playable target is one dense starting region, not the full continent.
The generator should emit a compact contract that can seed the initial
expedition area.

The starting region should contain:

- ruined harbor or dead port
- local survey zone around the landing area
- fresh water and basic resource affordance sites
- ancient road leading inland
- at least one clearable blockage on or near that road
- first waystation candidate
- first inland site, ruin, or settlement
- at least one ordinary cave
- at least one meaningful cave transition tied to hydrology, volcanic terrain,
  or route history

The starting-region contract should include:

- route endpoints and road segment state
- local resource affordance sites
- cave transition payloads
- settlement and ruin evidence hooks
- hydrology `flow_group` records
- route traversal costs by actor profile

The output should be sufficient for later gameplay conversion while preserving
the current rule: overland owns the top-level terrain contract, and `settlegen`
is one producer merged into it.

## Implementation Phases

### Phase 1: Hydrology Continuity

Implemented as a first pass for the current regional profile. The generator now
emits continuous surface drainage and stable `flow_group` semantics for the
karst system, plus a separate ordinary perennial surface-water system. The
scoped PR did not include ruins, roads, runtime metadata, site history, or
richer cave payloads.

Implemented direction:

- connect spring gardens, sinking basins, ponors, and estavelles
- separate visible surface channels from underground links
- represent ordinary ponds/lakes as stable surface-water systems instead of
  treating every waterbody as karst-special
- make `connected_to_underground` meaningful
- add tests proving ponors, springs, and dry-season cave mouths belong to useful
  systems

### Phase 2: Starting-Region Contract

Implemented as a first pass for the current regional profile. The generator now
emits feature rows, surface tiles, and metadata for:

- ruined harbor or dead port
- local resource sites and fresh water
- ancient road leading inland
- first clearable blockage
- first waystation candidate
- first inland site, ruin, or settlement
- route endpoints and traversal costs

This phase extended artifact metadata narrowly rather than inventing a separate
world schema. Runtime expedition gameplay, site-history systems, and richer
dungeon handoff payloads remain out of scope.

### Phase 3: Cave Transition Payloads

Implemented as a first pass. Transition records now distinguish ordinary caves,
karst hydrology transitions, and lava-tube transitions with additive handoff
columns.

Payloads include cave type, hydrology role, seasonal state, flow group,
underground connectivity, biome, substrate, elevation band, nearby affordances,
and compact handoff tags. Full evidence-hook systems remain planned.

### Phase 4: Site-History Evidence Tags

Add compact historical and archaeological metadata for ruins, prior expedition
traces, route repairs, collapses, and occupation phases.

These tags should support future survey and knowledge systems without requiring
those systems to exist yet.

### Phase 5: Runtime-Facing Metadata Sidecar

Create a narrow runtime-facing metadata sidecar for converting generated
overland regions into game maps. The sidecar should preserve overland semantics
after the visual `GameMap` conversion.

Candidate payloads:

- material, biome, wetness, and hydro-role grids
- route, transition, and affordance lookups
- actor traversal cost layers
- cave, settlement, ruin, and resource references
- evidence hooks and regional tags

## Public Interfaces And Artifact Direction

Current artifacts remain authoritative:

- `overland_tiles.arrow`
- `overland_hydrology.arrow`
- `overland_features.arrow`
- `overland_affordances.arrow`
- `overland_transitions.arrow`
- `overland_routes.arrow`
- `overland_metadata.json`

Future roadmap items should extend these contracts or add narrow sidecars for:

- route segment state
- local resource sites
- historical and evidence metadata
- cave handoff payloads
- runtime overland metadata

No code API changes are part of this roadmap document. Implementation PRs should
change schemas only when a phase requires it and should update
[Overland Generation](./Overland%20Generation.md) with the current artifact
contract at that time.
