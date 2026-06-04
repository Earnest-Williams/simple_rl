from __future__ import annotations

import hashlib
import json

import numpy as np
import polars as pl

from common.constants import Material
from tools.generate_overland import generate_region
from utils.game_rng import GameRNG
from worldgen.overland import (
    ActorTraversalProfile,
    Biome,
    HydroRole,
    HydroState,
    TransitionType,
    TraversalClass,
    apply_hydrology_state,
    build_actor_cost_grid,
    can_actor_enter,
    generate_overland_region,
    generate_transition_requests,
    load_worldgen_bundle,
    merge_settlement_into_overland,
    movement_cost_for_actor,
    overland_to_game_map,
    render_overland_ascii,
    write_overland_bundle,
)
from worldgen.settlements import generate_settlement, starting_port_from_overland


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
    assert paths["transitions_df"].exists()
    assert metadata["seed"] == 20260604
    assert metadata["profile"] == "KARST_TO_VOLCANIC_MOUNTAIN"
    assert metadata["schema_version"] == "overland-1"
    assert loaded["tiles_df"].height == 96 * 72
    assert "movement_cost" in loaded["tiles_df"].columns
    assert "traversal_class" in loaded["tiles_df"].columns
    assert loaded["transitions_df"].height > 0

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
    assert _count(dry.tiles_df, "traversal_class", TraversalClass.SLOW) > 0
    assert dry.tiles_df.get_column("movement_cost").max() >= 2.5

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
    assert pl.read_ipc(summary["artifacts"]["transitions_df"]).height > 0
    assert tmp_path.joinpath("overland_metadata.json").exists()


def test_starting_port_merges_as_overland_surface_layer() -> None:
    overland = generate_overland_region(
        seed=991,
        width=128,
        height=96,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    config, region, origin = starting_port_from_overland(
        overland,
        width=80,
        height=56,
        population_target=900,
    )
    settlement = generate_settlement(config, rng=GameRNG(seed=991), region=region)

    merged = merge_settlement_into_overland(overland, settlement, origin=origin)
    material_view = render_overland_ascii(merged.tiles_df, view="material")

    assert _count(merged.tiles_df, "material", Material.ROAD) > 0
    assert _count(merged.tiles_df, "material", Material.DOCK) > 0
    assert _count(merged.tiles_df, "material", Material.BUILDING_FLOOR) > 0
    assert (
        _count(merged.tiles_df, "material", Material.FIELD)
        + _count(merged.tiles_df, "material", Material.ORCHARD)
        + _count(merged.tiles_df, "material", Material.PASTURE)
        > 0
    )
    assert "R" in material_view
    assert "D" in material_view
    assert "B" in material_view
    assert merged.hydrology_df.height == overland.hydrology_df.height
    transition_types = {
        request.transition_type for request in generate_transition_requests(merged)
    }
    assert TransitionType.DOCK_ROUTE in transition_types
    assert TransitionType.SETTLEMENT_ENTRANCE in transition_types
    assert merged.metadata["settlements"][0]["kind"] == "port_town"


def test_headless_overland_generation_can_merge_starting_port(tmp_path) -> None:
    summary = generate_region(
        seed=11,
        width=96,
        height=72,
        out_dir=tmp_path,
        overwrite=False,
        with_starting_port=True,
    )

    assert "starting_port" in summary
    assert summary["tile_rows"] == 96 * 72
    loaded = load_worldgen_bundle(tmp_path)
    assert _count(loaded["tiles_df"], "material", Material.DOCK) > 0
    assert _count(loaded["tiles_df"], "material", Material.BUILDING_FLOOR) > 0
    assert _count(
        loaded["transitions_df"],
        "transition_type",
        TransitionType.SETTLEMENT_ENTRANCE,
    ) > 0


def test_actor_traversal_profiles_respond_to_hydrology_state() -> None:
    bundle = generate_overland_region(
        seed=202,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    wet = apply_hydrology_state(bundle, HydroState.WET_SEASON)
    dry = apply_hydrology_state(bundle, HydroState.DRY_SEASON)

    wet_lake = _first_row(wet.tiles_df, "hydro_role", HydroRole.SINKING_LAKE)
    dry_lake = _first_row(dry.tiles_df, "hydro_role", HydroRole.SINKING_LAKE)
    wet_fish_trail = _first_row(wet.tiles_df, "material", Material.SHALLOW_WATER)
    dry_fish_trail = _first_row(dry.tiles_df, "material", Material.FISH_TRAIL)

    assert not can_actor_enter(wet_lake, ActorTraversalProfile.HUMAN_ON_FOOT)
    assert can_actor_enter(wet_lake, ActorTraversalProfile.BOAT)
    assert can_actor_enter(wet_lake, ActorTraversalProfile.SWIMMER)
    assert can_actor_enter(wet_lake, ActorTraversalProfile.SMALL_AMPHIBIOUS)

    assert can_actor_enter(dry_lake, ActorTraversalProfile.HUMAN_ON_FOOT)
    assert not can_actor_enter(dry_lake, ActorTraversalProfile.BOAT)
    assert movement_cost_for_actor(
        dry_lake, ActorTraversalProfile.HUMAN_ON_FOOT
    ) > 1.0

    assert movement_cost_for_actor(
        wet_fish_trail, ActorTraversalProfile.SMALL_AMPHIBIOUS
    ) < movement_cost_for_actor(wet_fish_trail, ActorTraversalProfile.HUMAN_ON_FOOT)
    assert can_actor_enter(dry_fish_trail, ActorTraversalProfile.HUMAN_ON_FOOT)

    human_costs = build_actor_cost_grid(dry.tiles_df, ActorTraversalProfile.HUMAN_ON_FOOT)
    boat_costs = build_actor_cost_grid(wet.tiles_df, ActorTraversalProfile.BOAT)
    assert human_costs.shape == (72, 96)
    assert boat_costs.shape == (72, 96)
    assert np.isfinite(human_costs).sum() > np.isfinite(boat_costs).sum()


def _count(df: pl.DataFrame, column: str, enum_value: object) -> int:
    return df.filter(pl.col(column) == int(enum_value)).height


def _first_row(df: pl.DataFrame, column: str, enum_value: object) -> dict[str, object]:
    rows = df.filter(pl.col(column) == int(enum_value)).head(1).to_dicts()
    assert rows
    return rows[0]


def _checksum(df: pl.DataFrame) -> str:
    payload = json.dumps(df.to_dict(as_series=False), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
