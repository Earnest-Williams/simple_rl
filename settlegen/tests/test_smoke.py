from settlegen import (
    Facility,
    MagicMode,
    SettlementConfig,
    SettlementGenerator,
    SettlementKind,
    SettlementState,
    TerrainFeature,
)


def test_generate_farming_village():
    cfg = SettlementConfig(
        kind=SettlementKind.FARMING_VILLAGE,
        width=96,
        height=72,
        terrain=(TerrainFeature.PLAIN, TerrainFeature.STREAM),
        facilities=(Facility.CEMETERY, Facility.WINDMILL),
    )
    s = SettlementGenerator(seed=1).generate(cfg)
    assert s.width == 96
    assert s.height == 72
    assert len(s.buildings) > 10
    counts = s.facility_counts()
    assert counts.get("field", 0) >= 1
    assert counts.get("house", 0) + counts.get("hovel", 0) + counts.get("tenement", 0) > 0


def test_generate_port_city_magic_no_crash():
    cfg = SettlementConfig(
        kind=SettlementKind.PORT_CITY,
        width=128,
        height=90,
        magic=MagicMode.RUNIC_MAGIC,
        terrain=(TerrainFeature.BAY, TerrainFeature.RIVER),
        facilities=(Facility.DOCKS, Facility.LIGHTHOUSE, Facility.STONE_WALL, Facility.RUNESTONE_CIRCLE),
    )
    s = SettlementGenerator(seed=2).generate(cfg)
    assert s.population > 0
    assert len(s.docks) >= 1
    assert len(s.magic_sites) >= 1


def test_ghost_town_population_zero():
    cfg = SettlementConfig(
        kind=SettlementKind.TOWN,
        width=96,
        height=72,
        state=SettlementState.GHOST_TOWN,
        terrain=(TerrainFeature.PLAIN,),
    )
    s = SettlementGenerator(seed=3).generate(cfg)
    assert s.population == 0
    assert all(b.occupants == 0 for b in s.buildings)


def test_deterministic_summary():
    cfg = SettlementConfig(kind=SettlementKind.VILLAGE, width=80, height=64, terrain=(TerrainFeature.RIVER,))
    a = SettlementGenerator(seed=99).generate(cfg)
    b = SettlementGenerator(seed=99).generate(cfg)
    assert a.facility_counts() == b.facility_counts()
    assert a.tile_summary() == b.tile_summary()
