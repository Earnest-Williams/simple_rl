from __future__ import annotations

import hashlib
import json

import polars as pl

from common.constants import Material
from tools.generate_overland import generate_region
from worldgen.overland import (
    Biome,
    HydroRole,
    HydroState,
    TransitionType,
    apply_hydrology_state,
    generate_overland_region,
    generate_transition_requests,
    load_worldgen_bundle,
    overland_to_game_map,
    render_overland_ascii,
    write_overland_bundle,
)


def test_generate_karst_to_volcanic_overland_region_is_stable(tmp_path) -> None:
    bundle = generate_overland_region(
        seed=20260604,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    paths = write_overland_bundle(bundle, tmp_path)
    loaded = load_worldgen_bundle(tmp_path)
    metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))

    assert paths["tiles_df"].exists()
    assert paths["hydrology_df"].exists()
    assert paths["features_df"].exists()
    assert paths["affordances_df"].exists()
    assert metadata["seed"] == 20260604
    assert metadata["profile"] == "KARST_TO_VOLCANIC_MOUNTAIN"
    assert metadata["schema_version"] == "overland-1"
    assert loaded["tiles_df"].height == 96 * 72

    tiles = bundle.tiles_df
    hydrology = bundle.hydrology_df
    assert _count(tiles, "biome", Biome.KARST_WET_FOREST) > 0
    assert _count(tiles, "biome", Biome.SINKING_LAKE_BASIN) > 0
    assert _count(hydrology, "hydro_role", HydroRole.SPRING) > 0
    assert _count(hydrology, "hydro_role", HydroRole.PONOR) > 0
    assert _count(hydrology, "hydro_role", HydroRole.ESTAVELLE) > 0
    assert _count(tiles, "biome", Biome.LIMESTONE_GORGE) > 0
    assert _count(tiles, "biome", Biome.VOLCANIC_CLOUD_FOREST) > 0
    assert _count(tiles, "material", Material.LAVA_TUBE_SKYLIGHT) > 0
    assert _count(tiles, "material", Material.COLLAPSED_LAVA_TUBE) > 0

    dry = apply_hydrology_state(bundle, HydroState.DRY_SEASON)
    mud = apply_hydrology_state(bundle, HydroState.MUD_SEASON)
    assert _checksum(dry.tiles_df) != _checksum(bundle.tiles_df)
    assert _checksum(mud.tiles_df) != _checksum(bundle.tiles_df)
    assert _count(dry.tiles_df, "material", Material.CRACKED_MUD) > 0
    assert _count(mud.tiles_df, "material", Material.MUDFLAT) > 0

    transitions = generate_transition_requests(dry)
    transition_types = {request.transition_type for request in transitions}
    assert TransitionType.CAVE_ENTRANCE in transition_types
    assert TransitionType.PONOR_DESCENT in transition_types
    assert TransitionType.LAVA_TUBE_SKYLIGHT in transition_types
    assert TransitionType.COLLAPSED_LAVA_TUBE in transition_types

    assert bundle.affordances_df.height > 0
    assert "K" in render_overland_ascii(tiles, view="biome")
    assert "v" in render_overland_ascii(tiles, view="hydro")

    game_map = overland_to_game_map(dry.tiles_df)
    assert game_map.width == 96
    assert game_map.height == 72

    same = generate_overland_region(
        seed=20260604,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    assert _checksum(bundle.tiles_df) == _checksum(same.tiles_df)
    assert _checksum(bundle.hydrology_df) == _checksum(same.hydrology_df)
    assert _checksum(bundle.features_df) == _checksum(same.features_df)


def test_headless_overland_generation_writes_inspectable_output(tmp_path) -> None:
    summary = generate_region(
        seed=7,
        width=64,
        height=48,
        out_dir=tmp_path,
        overwrite=False,
    )
    assert summary["tile_rows"] == 64 * 48
    assert pl.read_ipc(summary["artifacts"]["tiles_df"]).height == 64 * 48
    assert tmp_path.joinpath("overland_metadata.json").exists()


def _count(df: pl.DataFrame, column: str, enum_value: object) -> int:
    return df.filter(pl.col(column) == int(enum_value)).height


def _checksum(df: pl.DataFrame) -> str:
    payload = json.dumps(df.to_dict(as_series=False), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
