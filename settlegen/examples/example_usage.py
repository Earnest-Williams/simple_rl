from settlegen import (
    BuildingMaterial,
    DefenseStyle,
    Facility,
    LayoutStyle,
    MagicMode,
    PopulationMode,
    SettlementConfig,
    SettlementGenerator,
    SettlementKind,
    SettlementState,
    TerrainFeature,
    Wealth,
)
from settlegen.export import write_bundle
from settlegen.renderers.ascii import render_ascii

config = SettlementConfig(
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

settlement = SettlementGenerator(seed=77123).generate(config)
print(settlement.name)
print(settlement.population, "people")
print(settlement.facility_counts())
print(render_ascii(settlement, crop=(20, 10, 80, 40)))
write_bundle(settlement, "example_out")
