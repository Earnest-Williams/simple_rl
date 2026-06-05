# settlegen

A drop-in procedural medieval/fantasy settlement generator for games. It creates data, not UI: terrain grids, overlay grids, districts, roads, buildings, gates, docks, magic sites, population metadata, economy tags, hazards, and plot hooks.

The generator is designed for towns, cities, villages, farming villages, fishing villages, port cities, forts, monasteries, mining camps, ruined cities, ghost towns, ancient settlements, and nomad camps.

## Stable API Boundary

The procedural generator exposes a stable API contract. The components forming this boundary are:
- `SettlementConfig`: Configures all generation switches, constraints, and dimensions.
- `SpatialConstraints`: Optional regional placement hints for coastline, river mouth, road endpoints, and cave entrances.
- `Settlement`: The final generated container containing districts, roads, buildings, gates, docks, magic sites, final population, and a typed generation report.
- `GenerationReport`: A stable report of requested, placed, and failed facilities, including reason codes for failures.
- `TerrainCode`: The canonical enum representing all generated terrain types on the grid.
- [worldgen/settlements/translate.py](file:///home/earnest/code_projects/simple_rl/worldgen/settlements/translate.py): The translator converting settlement grids and properties into Simple RL native datatypes (overland tiles, etc.).

## Design goals

- **Game integration first:** import `SettlementGenerator` and consume arrays/dataclasses directly.
- **Interface separated:** ASCII preview and CLI live outside the generator.
- **Optional speed/analytics:** NumPy is required; Numba is used for hot grid kernels when installed; Polars is used only for analytics/export tables when installed.
- **Deterministic:** same seed plus same config produces the same generated settlement.
- **Switch-heavy:** terrain, magic, state, material, wealth, defense, layout, population, explicit facilities, and forbidden facilities all affect generation.

## Install locally

```bash
pip install -e .
# Optional acceleration and analytics:
pip install -e '.[fast,analytics]'
```

## Minimal use

```python
from settlegen import SettlementConfig, SettlementGenerator, SettlementKind, TerrainFeature

cfg = SettlementConfig(
    kind=SettlementKind.FARMING_VILLAGE,
    width=96,
    height=72,
    terrain=(TerrainFeature.PLAIN, TerrainFeature.STREAM),
)
settlement = SettlementGenerator(seed=42).generate(cfg)

combined_grid = settlement.combined_grid()  # np.ndarray[int16]
buildings = settlement.buildings          # list[Building]
districts = settlement.districts          # list[District]
report = settlement.generation_report    # GenerationReport
```

## Feature-rich use

```python
from settlegen import *
from settlegen.export import write_bundle

cfg = SettlementConfig(
    kind=SettlementKind.PORT_CITY,
    width=140,
    height=96,
    population_target=8500,
    population_mode=PopulationMode.CROWDED,
    state=SettlementState.THRIVING,
    magic=MagicMode.RUNIC_MAGIC,
    material=BuildingMaterial.MIXED,
    layout=LayoutStyle.COASTAL,
    defense=DefenseStyle.STONE_WALL,
    wealth=Wealth.PROSPEROUS,
    terrain=(TerrainFeature.BAY, TerrainFeature.RIVER, TerrainFeature.HILL),
    facilities=(
        Facility.CEMETERY,
        Facility.CITY_HALL,
        Facility.COURTHOUSE,
        Facility.KEEP,
        Facility.STONE_WALL,
        Facility.DYKE,
        Facility.TOWER,
        Facility.DOCKS,
        Facility.LIGHTHOUSE,
        Facility.RUNESTONE_CIRCLE,
    ),
)
settlement = SettlementGenerator(seed=77123).generate(cfg)
write_bundle(settlement, "out/port_city")
```

## Placement reporting

Requested facilities are either placed or reported as failed. Use the typed
field for new integrations:

```python
report = settlement.generation_report
requested = report.requested_facilities
placed = report.placed_facilities
failed = {item.facility: item.reason for item in report.failed_facilities}
```

Failure reasons currently include:

- `no_water`: waterfront facilities could not find suitable water or shore.
- `no_hill`: hill-dependent facilities could not find hill terrain.
- `no_clear_site`: no valid clear rectangle was available.
- `forbidden`: the facility was forbidden by config or incompatible with a
  generation switch, such as magic facilities in `no_magic` mode.

For backward compatibility, `settlement.metadata["generation_report"]` contains
the same information as a JSON-friendly dictionary.

## Regional placement

Overland integration can pass `SpatialConstraints` through `SettlementConfig`.
The generator uses these hints to align coastlines, river mouths, external road
exits, and nearby cave entrances with regional worldgen. Explicit rural
facilities such as fields, orchards, and pastures are placed before random rural
filler so merged starting ports reliably export farmable surface materials into
overland maps.

## Available switches

### Settlement kind

`hamlet`, `village`, `farming_village`, `fishing_village`, `mining_camp`, `monastery`, `fort`, `market_town`, `town`, `walled_town`, `port_town`, `port_city`, `city`, `capital`, `ancient_city`, `ruined_city`, `nomad_camp`.

### Terrain features

`plain`, `forest`, `dense_forest`, `hill`, `mountain_pass`, `river`, `stream`, `lakeside`, `bay`, `coast`, `island`, `swamp`, `marsh`, `delta`, `cliff`, `desert_edge`, `oasis`, `fertile_valley`, `volcanic`.

### Magic modes

`no_magic`, `low_magic`, `high_magic`, `runic_magic`, `divine_magic`, `necromantic`, `wild_magic`, `techno_arcane`.

### Settlement state

`new`, `thriving`, `ordinary`, `declining`, `scarcely_populated`, `ghost_town`, `ruined`, `ancient`, `occupied`, `plague_struck`, `war_torn`, `flooded`.

### Materials

`mostly_wood`, `mostly_stone`, `mostly_adobe`, `mostly_thatch`, `mostly_brick`, `mixed`, `ruined_stone`, `canvas_and_hide`, `ice_and_bone`.

### Facilities

Includes civic buildings, walls, towers, palisades, dykes, market squares, city halls, courthouses, keeps, castles, docks, wharves, fisheries, cemeteries, shrines, temples, churches, cathedrals, monasteries, mage towers, runestone circles, arcane academies, wells, bridges, mills, farms, fields, orchards, pastures, blacksmiths, guildhalls, libraries, prisons, warehouses, mines, quarries, and more.

## Files emitted by `write_bundle`

- `settlement.json`: metadata, buildings, districts, roads, hooks, summary.
- `grids.npz`: compressed NumPy arrays: `terrain`, `overlay`, and `combined`.
- `buildings.csv`: building table. Uses Polars when installed; otherwise the Python standard library.
- `tile_legend.csv`: numeric tile-code legend.

## CLI demo

```bash
settlegen-demo --seed 7 --kind port_city --terrain bay --terrain river --magic runic_magic --facility keep --facility cemetery --ascii --out demo_out
```
