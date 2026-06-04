# settlegen

A drop-in procedural medieval/fantasy settlement generator for games. It creates data, not UI: terrain grids, overlay grids, districts, roads, buildings, gates, docks, magic sites, population metadata, economy tags, hazards, and plot hooks.

The generator is designed for towns, cities, villages, farming villages, fishing villages, port cities, forts, monasteries, mining camps, ruined cities, ghost towns, ancient settlements, and nomad camps.

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
