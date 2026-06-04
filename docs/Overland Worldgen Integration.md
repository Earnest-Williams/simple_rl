# Overland Worldgen Integration

## What Changed

The world generator has been pivoted from settlement-first plumbing toward an
overland-first terrain system. `settlegen` is still useful, but it is now treated
as one producer of surface features rather than the driver of the whole world
schema.

The current implementation adds:

- An expanded shared `Material` enum in `common/constants.py` with overland,
  karst, volcanic, wetland, built, and legacy dungeon materials.
- A new `worldgen/overland/` package with terrain schema, generation,
  hydrology transforms, artifact export, artifact loading, ASCII inspection,
  wildlife affordances, transition requests, and `GameMap` conversion.
- A deterministic first-pass `KARST_TO_VOLCANIC_MOUNTAIN` profile.
- Headless generation and inspection tools:
  - `tools/generate_overland.py`
  - `tools/inspect_overland.py`
  - `tools/generate_settlement.py`
- Regression coverage for both the new overland route and the existing
  settlement integration path.

## Why The Pivot Matters

The game world needs dynamic overland terrain, not just static settlements.
Karst hydrology, volcanic/lava-tube terrain, seasonal wetness, cave transitions,
fish trails, spring refuges, estavelles, ponors, and mudflat ecology are core
setting concepts. Encoding those concepts as only `Material.WATER` or
`Material.GRASS` would collapse important world logic into broad display labels.

The new overland tile schema separates terrain meaning into multiple columns:

- `material`
- `biome`
- `elevation_band`
- `hydro_role`
- `wetness`
- `substrate`
- `walkable`
- `blocks_sight`
- `surface_flags`

`walkable` remains the gameplay truth, but it is derived from terrain semantics
rather than being the only thing worldgen knows.

## Current Artifacts

Overland generation writes:

- `overland_tiles.arrow`
- `overland_hydrology.arrow`
- `overland_features.arrow`
- `overland_affordances.arrow`
- `overland_metadata.json`

Settlement generation currently writes:

- `settlement_map.arrow`
- `settlement_buildings.arrow`
- `settlement_districts.arrow`
- `settlement_roads.arrow`
- `settlement_entrances.arrow`
- `settlement_metadata.json`

The overland artifact set is the primary worldgen contract. Settlement artifacts
are compatible side outputs that can later be embedded into overland tiles.

## Overland Profile

The first implemented profile is:

```text
KARST_TO_VOLCANIC_MOUNTAIN
```

It deterministically places:

- coastal/lowland edge
- karst wet forest
- sinking lake basin
- spring garden
- ponor and estavelle field
- limestone gorge
- foothill transition
- volcanic cloud forest
- lava-tube forest
- basalt barrens
- highland peat/moor

The profile is intentionally simple. Its job is to prove that the schema can
represent the right ecological and hydrological relationships before more
beautiful terrain algorithms are added.

## Hydrology State

`apply_hydrology_state(bundle, state)` supports:

- `WET_SEASON`
- `DRAINING`
- `MUD_SEASON`
- `DRY_SEASON`

The transform changes terrain deterministically. Examples:

- sinking lakes become flooded water, sinking water, mudflat, or cracked mud
- estavelles become spring water, estavelle water, mud, or cave mouths
- ponors become submerged drains, exposed throats, or cave entrances
- fish trails move between hidden water, active mud corridors, and dry partial
  corridors

This is the foundation for dynamic karst terrain.

## Transitions

Overland terrain emits `SurfaceTransitionRequest` objects instead of only
dungeon entrances. Supported transition kinds include:

- cave entrance
- ponor descent
- karst window
- spring source
- lava-tube skylight
- collapsed lava tube
- settlement entrance
- dock route
- trail exit

This keeps dungeon generation in scope while making it one target of a broader
surface-transition system.

## Wildlife Affordances

The current system does not simulate wildlife. It does generate an affordance
layer so future wildlife has terrain semantics to consume:

- fish migration
- mudflat sunning
- burrowing mud
- mustelid hunting
- octopus refuge
- spring refuge
- cave refuge
- amphibious corridor

These are derived from material, wetness, and hydrology roles.

## Headless Usage

Generate a representative overland bundle:

```bash
python tools/generate_overland.py \
  --seed 20260604 \
  --width 96 \
  --height 72 \
  --out-dir tmp/overland/karst_volcanic \
  --overwrite
```

Inspect it without UI:

```bash
python tools/inspect_overland.py tmp/overland/karst_volcanic --view biome
python tools/inspect_overland.py tmp/overland/karst_volcanic --view hydro
python tools/inspect_overland.py tmp/overland/karst_volcanic --view wetness
python tools/inspect_overland.py tmp/overland/karst_volcanic --view material
python tools/inspect_overland.py tmp/overland/karst_volcanic --view traversal
```

Generate the current settlement bundle:

```bash
python tools/generate_settlement.py \
  --seed 20260604 \
  --out-dir tmp/settlements/starting_port \
  --width 96 \
  --height 72 \
  --population 1400 \
  --overwrite
```

## Tests

The main overland stability test is:

```text
tests/test_overland_integration.py::test_generate_karst_to_volcanic_overland_region_is_stable
```

It checks:

- required Arrow artifacts exist
- metadata includes seed/profile/schema version
- required biomes exist
- required hydrology roles exist
- lava-tube and karst transition features exist
- hydrology transforms are deterministic and change terrain
- surface transition requests include cave, ponor, and lava-tube transitions
- affordances are generated
- ASCII inspection works
- overland tiles convert to `GameMap`
- same seed produces stable checksums

Settlement integration tests remain in `tests/test_settlement_integration.py`.

## Current Direction

The next architectural move is to make settlements emit overland-compatible
surfaces instead of treating settlement tiles as a separate world. Roads, docks,
boardwalks, walls, buildings, fields, orchards, and pastures should become
settlement-produced overland tiles.

The guiding rule is:

```text
overland schema first, settlements as producers, gameplay interpretation last
```

That keeps the world generator aligned with the actual game premise: a dynamic
karst-to-volcanic landscape with meaningful hydrology, transitions, ecology,
and settlements layered into it.
