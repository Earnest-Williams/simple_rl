from __future__ import annotations

from settlegen import Facility, SettlementConfig, SettlementKind, TerrainFeature
from utils.game_rng import GameRNG
from worldgen.settlements import (
    RegionConstraints,
    generate_settlement,
    starting_port_config,
)


def test_starting_port_bundle_shape_and_semantics() -> None:
    bundle = generate_settlement(
        starting_port_config(width=96, height=72),
        rng=GameRNG(seed=123),
        region=RegionConstraints(coastline="south", faction="port_authority"),
    )

    assert bundle.map_df.height == 96 * 72
    assert {
        "x",
        "y",
        "material_id",
        "walkable",
        "settlement_tile",
        "terrain_code",
        "overlay_code",
    }.issubset(set(bundle.map_df.columns))
    assert bundle.metadata["kind"] == "port_town"
    assert bundle.metadata["region"]["faction"] == "port_authority"
    assert bundle.buildings_df.height > 0
    assert bundle.settlement.facility_counts().get("docks", 0) >= 1


def test_generation_is_deterministic_through_game_rng() -> None:
    cfg = SettlementConfig(
        kind=SettlementKind.FARMING_VILLAGE,
        width=80,
        height=64,
        terrain=(TerrainFeature.STREAM,),
        facilities=(Facility.CEMETERY,),
    )

    first = generate_settlement(cfg, rng=GameRNG(seed=88))
    second = generate_settlement(cfg, rng=GameRNG(seed=88))

    assert first.metadata["seed"] == second.metadata["seed"]
    assert first.metadata["tile_summary"] == second.metadata["tile_summary"]
    assert first.buildings_df.to_dicts() == second.buildings_df.to_dicts()


def test_subsurface_entrances_are_exported() -> None:
    cfg = SettlementConfig(
        kind=SettlementKind.MINING_CAMP,
        width=80,
        height=64,
        terrain=(TerrainFeature.HILL,),
        facilities=(Facility.MINE,),
        allow_subterranean=True,
    )

    bundle = generate_settlement(
        cfg,
        rng=GameRNG(seed=44),
        region=RegionConstraints(cave_entrances=((12, 18),)),
    )

    assert bundle.entrances_df.height >= 1
    assert "cave" in set(bundle.entrances_df.get_column("kind").to_list())
