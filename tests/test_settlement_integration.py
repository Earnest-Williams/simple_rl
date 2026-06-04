from __future__ import annotations

import json

import polars as pl

from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL
from settlegen import Facility, SettlementConfig, SettlementKind, TerrainFeature
from tools.generate_settlement import generate_starting_port
from utils.game_rng import GameRNG
from utils.shaped_map import shaped_dataframe_to_game_map
from worldgen.settlements import (
    RegionConstraints,
    SettlementTile,
    generate_settlement,
    starting_port_config,
    write_settlement_bundle,
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


def test_bundle_artifacts_round_trip_to_game_map(tmp_path) -> None:
    bundle = generate_settlement(
        starting_port_config(width=96, height=72),
        rng=GameRNG(seed=222),
        region=RegionConstraints(cave_entrances=((20, 20),)),
    )

    paths = write_settlement_bundle(bundle, tmp_path)
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
    loaded_map_df = pl.read_ipc(paths["map_df"])
    game_map, origin = shaped_dataframe_to_game_map(loaded_map_df)

    assert metadata["artifacts"]["map_df"] == "settlement_map.arrow"
    assert loaded_map_df.height == 96 * 72
    assert game_map.width == 96
    assert game_map.height == 72
    assert origin == (0, 0)
    assert int((game_map.tiles == TILE_ID_FLOOR).sum()) > 0


def test_settlement_tiles_drive_walkability() -> None:
    bundle = generate_settlement(
        starting_port_config(width=96, height=72),
        rng=GameRNG(seed=333),
    )
    game_map, _origin = shaped_dataframe_to_game_map(bundle.map_df)
    tile_column = bundle.map_df.get_column("settlement_tile")
    walkable_column = bundle.map_df.get_column("walkable")

    for tile in (
        SettlementTile.ROAD,
        SettlementTile.SHORE,
        SettlementTile.DOCK,
        SettlementTile.GATE,
    ):
        rows = bundle.map_df.filter(tile_column == int(tile))
        if rows.is_empty():
            continue
        assert rows.get_column("walkable").all()
        x = int(rows.get_column("x")[0])
        y = int(rows.get_column("y")[0])
        assert game_map.tiles[y, x] == TILE_ID_FLOOR

    blocker_rows = bundle.map_df.filter(
        (walkable_column == False)  # noqa: E712
        & (tile_column.is_in([int(SettlementTile.WALL), int(SettlementTile.WATER)]))
    )
    assert blocker_rows.height > 0
    x = int(blocker_rows.get_column("x")[0])
    y = int(blocker_rows.get_column("y")[0])
    assert game_map.tiles[y, x] == TILE_ID_WALL


def test_headless_starting_port_generation_writes_inspectable_output(tmp_path) -> None:
    summary = generate_starting_port(
        seed=444,
        out_dir=tmp_path,
        width=80,
        height=64,
        population=1200,
        overwrite=False,
    )

    artifacts = summary["artifacts"]
    assert isinstance(artifacts, dict)
    assert summary["map_rows"] == 80 * 64
    assert pl.read_ipc(artifacts["map_df"]).height == 80 * 64
    assert json.loads(tmp_path.joinpath("settlement_metadata.json").read_text())[
        "kind"
    ] == "port_town"
