# Overland Generation

## Purpose

Overland generation is the primary terrain contract for the game world. It
describes the surface as semantic terrain first, then derives gameplay
interpretation from that terrain.

This document is the authoritative reference for what is currently implemented:
artifact files, schema columns, generation commands, and test coverage. Planned
or aspirational overland work belongs in
[Overland Roadmap](./Overland%20Roadmap.md) until it is implemented and this
contract is updated.

The core design rule is:

```text
material + wetness + surface_flags -> traversal and gameplay behavior
```

Settlements, roads, docks, caves, ponors, springs, lava tubes, fish trails, and
seasonal wetlands are all overland surface producers.

## Roadmap

[Overland Roadmap](./Overland%20Roadmap.md) is the canonical planning document
for long-term overland generator direction and the near-term start-of-game
contract. Treat roadmap phases as planned work, not current guarantees, unless
the implemented contract below says otherwise.

## Tile Schema

`overland_tiles.arrow` contains one row per tile:

- `x`
- `y`
- `material`
- `biome`
- `elevation_band`
- `hydro_role`
- `wetness`
- `substrate`
- `walkable`
- `blocks_sight`
- `movement_cost`
- `traversal_class`
- `surface_flags`

`walkable`, `blocks_sight`, `movement_cost`, and `traversal_class` are derived
gameplay columns. They are not the source of terrain meaning.

## Traversal

Traversal classes are defined in `worldgen.overland.schema.TraversalClass`:

- `NORMAL`
- `SLOW`
- `WADE`
- `SWIM_OR_BOAT`
- `BLOCKED`
- `HAZARDOUS`
- `TRANSITION`

Examples:

- road: normal movement
- mudflat/reedbed/peat bog: slow movement
- shallow flooded tile: wading
- deep flooded tile: swim or boat
- wall/cliff/deep blocked water: blocked
- ponor or skylight hazard: hazardous or transition

Movement costs are currently first-pass values:

- normal: `1.0`
- slow: `2.5`
- wade: `3.0`
- hazardous: `4.0`
- swim or boat: `6.0`
- blocked: infinity
- transition: `1.0`

These values are intentionally simple and can later become actor-specific.

## Actor Traversal Profiles

Actor-specific traversal is handled by query helpers rather than by writing
large per-actor cost artifacts.

Profiles are defined in `worldgen.overland.actor_traversal`:

- `HUMAN_ON_FOOT`
- `PACK_ANIMAL`
- `SMALL_AMPHIBIOUS`
- `SWIMMER`
- `BOAT`

Helpers:

```python
can_actor_enter(tile_row, profile)
movement_cost_for_actor(tile_row, profile)
build_actor_cost_grid(tiles_df, profile)
```

Examples:

- humans cannot enter deep flooded sinking-lake tiles
- boats prefer flooded water and cannot move over dry cracked mud
- small amphibious actors move efficiently through wet corridors and shallow
  flooded fish trails
- pack animals are more constrained by deep mud, ponors, cave mouths, and deep
  flooding
- swimmers can use flooded routes but are less efficient on dry land

The generic `movement_cost` and `traversal_class` columns remain useful for
inspection and fallback behavior. Actor profiles apply a second interpretation
layer for gameplay.

## Hydrology

Hydrology is split across tile columns and `overland_hydrology.arrow`.

Tile columns:

- `hydro_role`
- `wetness`

Hydrology artifact columns:

- `x`
- `y`
- `hydro_role`
- `flow_group`
- `seasonal_state`
- `connected_to_underground`

Hydrology states are:

- `WET_SEASON`
- `DRAINING`
- `MUD_SEASON`
- `DRY_SEASON`

`apply_hydrology_state(bundle, state)` transforms material and wetness for
seasonal karst behavior, then recomputes:

- `walkable`
- `blocks_sight`
- `movement_cost`
- `traversal_class`
- affordances

This keeps seasonal terrain changes visible to gameplay.

## Transitions

`overland_transitions.arrow` is generated from the bundle and contains:

- `source_x`
- `source_y`
- `transition_type`
- `target_kind`
- `hydro_role`
- `biome`
- `material`
- `seed`
- `tags`

Transition request types include:

- cave entrance
- ponor descent
- karst window
- spring source
- lava-tube skylight
- collapsed lava tube
- settlement entrance
- dock route
- trail exit

The transition artifact is derived at write time from overland tiles and
features. Merged settlements add settlement feature rows, so generated
transition requests include settlement entrances as well as terrain transitions.

## Route Artifacts

`overland_routes.arrow` is generated from a small selected set of debug routes.
It is not a complete all-pairs route cache.

Columns:

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

Route helpers:

```python
generate_debug_routes(bundle)
overland_routes_to_df(routes)
```

Current debug routes include feature-to-feature and starting-port routes when
their endpoints exist:

- coast to spring garden
- starting port to limestone gorge
- starting port to lava-tube skylight
- sinking lake edge to ponor

The route artifact is written by `write_overland_bundle(...)` and loaded by
`load_worldgen_bundle(out_dir)` as `routes_df`.

## Artifacts

The overland bundle writes:

- `overland_tiles.arrow`
- `overland_hydrology.arrow`
- `overland_features.arrow`
- `overland_affordances.arrow`
- `overland_transitions.arrow`
- `overland_routes.arrow`
- `overland_metadata.json`

The loader `load_worldgen_bundle(out_dir)` reads any present overland and
settlement artifacts. This keeps the loader bundle-agnostic.

## Starting Port Merge

Settlements are overland producers.

The starting port is derived from an overland bundle with:

```python
starting_port_from_overland(overland)
```

It is generated with `settlegen`, translated into overland-compatible tile
columns, then merged with:

```python
merge_settlement_into_overland(overland, settlement, origin=origin)
```

Merged settlement surfaces include roads, docks, buildings, walls, bridges,
fields, orchards, and pastures.

## Headless Generation

Generate a plain overland region:

```bash
python tools/generate_overland.py \
  --seed 20260604 \
  --width 96 \
  --height 72 \
  --out-dir tmp/overland/karst_volcanic \
  --overwrite
```

Generate overland with the starting port merged into the tile layer:

```bash
python tools/generate_overland.py \
  --seed 20260604 \
  --width 128 \
  --height 96 \
  --out-dir tmp/overland/merged_starting_port \
  --with-starting-port \
  --overwrite
```

Inspect output:

```bash
python tools/inspect_overland.py tmp/overland/merged_starting_port --view material
python tools/inspect_overland.py tmp/overland/merged_starting_port --view biome
python tools/inspect_overland.py tmp/overland/merged_starting_port --view hydro
python tools/inspect_overland.py tmp/overland/merged_starting_port --view wetness
python tools/inspect_overland.py tmp/overland/merged_starting_port --view traversal
python tools/inspect_overland.py tmp/overland/merged_starting_port --view actor --profile HUMAN_ON_FOOT
python tools/inspect_overland.py tmp/overland/merged_starting_port --view actor --profile BOAT
```

## Test Coverage

Primary tests live in `tests/test_overland_integration.py`.

They cover:

- stable seeded overland generation
- required karst, volcanic, hydrology, and transition features
- hydrology state transforms
- derived movement and traversal columns
- transition artifact output
- route artifact output
- affordance output
- headless generation
- merged starting-port generation
- actor-specific ASCII inspection
- `GameMap` conversion

The current tests intentionally validate relationships, not visual beauty.
The goal is to keep the terrain contract stable while generation quality
improves.
