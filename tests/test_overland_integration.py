from __future__ import annotations

import hashlib
import json
from collections import deque

import numpy as np
import polars as pl

from common.constants import Material
from game.world.game_map import GameMap
from tools.generate_overland import generate_region
from utils.game_rng import GameRNG
from worldgen.overland import (
    ActorTraversalProfile,
    Biome,
    EvidenceTag,
    FeatureType,
    HydroRole,
    HydroState,
    OverlandMapMetadata,
    RouteSegmentState,
    TransitionType,
    TraversalClass,
    apply_hydrology_state,
    build_actor_cost_grid,
    can_actor_enter,
    find_feature,
    find_nearest_feature,
    find_overland_path,
    generate_debug_routes,
    generate_overland_region,
    generate_transition_requests,
    load_worldgen_bundle,
    merge_settlement_into_overland,
    movement_cost_for_actor,
    overland_routes_to_df,
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
    assert paths["routes_df"].exists()
    assert metadata["seed"] == 20260604
    assert metadata["profile"] == "KARST_TO_VOLCANIC_MOUNTAIN"
    assert metadata["schema_version"] == "overland-1"
    assert loaded["tiles_df"].height == 96 * 72
    assert "movement_cost" in loaded["tiles_df"].columns
    assert "traversal_class" in loaded["tiles_df"].columns
    assert loaded["transitions_df"].height > 0
    assert loaded["routes_df"].height > 0

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
    actor_view = render_overland_ascii(
        tiles,
        view="actor",
        profile=ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    assert "#" in actor_view
    assert "." in actor_view

    game_map = overland_to_game_map(dry.tiles_df)
    assert isinstance(game_map, GameMap)
    assert game_map.width == 96
    assert game_map.height == 72

    # Test new runtime sidecar (with_metadata=True)
    result = overland_to_game_map(dry, with_metadata=True)
    assert isinstance(result, tuple)
    gm, metadata = result
    assert isinstance(gm, GameMap)
    assert isinstance(metadata, OverlandMapMetadata)
    assert gm.overland_metadata is metadata
    assert metadata.material_grid.shape == (
        dry.tiles_df["y"].max() + 1,
        dry.tiles_df["x"].max() + 1,
    )
    assert metadata.biome_grid.shape == metadata.material_grid.shape
    assert metadata.hydro_grid.shape == metadata.material_grid.shape
    assert metadata.wetness_grid.shape == metadata.material_grid.shape
    assert metadata.movement_cost_grid.shape == metadata.material_grid.shape
    assert metadata.traversal_class_grid.shape == metadata.material_grid.shape
    sample = dry.tiles_df.row(0, named=True)
    sample_x = int(sample["x"])
    sample_y = int(sample["y"])
    assert metadata.material_grid[sample_y, sample_x] == int(sample["material"])
    assert metadata.biome_grid[sample_y, sample_x] == int(sample["biome"])
    assert metadata.hydro_grid[sample_y, sample_x] == int(sample["hydro_role"])
    assert metadata.wetness_grid[sample_y, sample_x] == int(sample["wetness"])
    assert metadata.movement_cost_grid[sample_y, sample_x] == float(
        sample["movement_cost"]
    )
    assert metadata.traversal_class_grid[sample_y, sample_x] == int(
        sample["traversal_class"]
    )
    assert metadata.transitions
    assert metadata.affordances
    assert len(metadata.route_segments) >= 1
    assert metadata.route_segments[0]["state"] == int(RouteSegmentState.BLOCKED)
    assert "repair_cost" in metadata.route_segments[0]

    same = generate_overland_region(
        seed=20260604,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    assert _checksum(bundle.tiles_df) == _checksum(same.tiles_df)
    assert _checksum(bundle.hydrology_df) == _checksum(same.hydrology_df)
    assert _checksum(bundle.features_df) == _checksum(same.features_df)


def test_debug_overland_routes_emit_artifact_rows() -> None:
    bundle = generate_overland_region(
        seed=303,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    routes = generate_debug_routes(bundle)
    routes_df = overland_routes_to_df(routes)

    assert routes_df.height > 0
    assert {
        "route_id",
        "profile",
        "source_x",
        "source_y",
        "target_x",
        "target_y",
        "step_index",
        "x",
        "y",
        "cost_so_far",
        "tags",
        "evidence_tags",
    } == set(routes_df.columns)
    assert routes_df.get_column("step_index").min() == 0
    assert routes_df.get_column("cost_so_far").min() == 0.0


def test_transition_artifacts_include_cave_handoff_payloads(tmp_path) -> None:
    bundle = generate_overland_region(
        seed=707,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    paths = write_overland_bundle(bundle, tmp_path)
    transitions_df = pl.read_ipc(paths["transitions_df"])

    assert {
        "cave_type",
        "seasonal_state",
        "flow_group",
        "connected_to_underground",
        "substrate",
        "elevation_band",
        "nearby_affordances",
        "handoff_tags",
        "evidence_tags",
    } <= set(transitions_df.columns)

    ordinary_cave = bundle.metadata["starting_region_contract"]["cave_refs"][0]
    ordinary_point = tuple(ordinary_cave["point"])
    ordinary = _transition_at(transitions_df, ordinary_point)
    assert ordinary["transition_type"] == int(TransitionType.CAVE_ENTRANCE)
    assert ordinary["cave_type"] == "ordinary_cave"
    assert ordinary["flow_group"] == 0
    assert not ordinary["connected_to_underground"]
    assert "ordinary" in ordinary["handoff_tags"]
    assert set(ordinary["evidence_tags"]) == {
        int(EvidenceTag.PRECURSOR_OCCUPATION),
        int(EvidenceTag.PRIOR_EXPEDITION),
    }

    ponor = (
        transitions_df.filter(
            pl.col("transition_type") == int(TransitionType.PONOR_DESCENT)
        )
        .head(1)
        .to_dicts()[0]
    )
    assert ponor["cave_type"] == "ponor_descent"
    assert ponor["flow_group"] == 1
    assert ponor["connected_to_underground"]
    assert ponor["seasonal_state"] != ""
    assert "karst_subsurface" in ponor["handoff_tags"]
    assert set(ponor["evidence_tags"]) >= {
        int(EvidenceTag.SUBSIDENCE_DAMAGE),
        int(EvidenceTag.FLOOD_DAMAGE),
    }

    lava = (
        transitions_df.filter(
            pl.col("transition_type") == int(TransitionType.LAVA_TUBE_SKYLIGHT)
        )
        .head(1)
        .to_dicts()[0]
    )
    assert lava["cave_type"] == "lava_tube_skylight"
    assert lava["target_kind"] == "lava_tube"
    assert "basalt" in lava["handoff_tags"]
    assert set(lava["evidence_tags"]) >= {
        int(EvidenceTag.VOLCANIC_BURIAL),
        int(EvidenceTag.STRUCTURAL_COLLAPSE),
    }

    loaded = load_worldgen_bundle(tmp_path)
    assert loaded["overland_metadata"]["starting_region_contract"]["route_segments"][0][
        "evidence_tags"
    ] == bundle.metadata["starting_region_contract"]["route_segments"][0][
        "evidence_tags"
    ]


def test_karst_hydrology_flow_group_is_connected() -> None:
    bundle = generate_overland_region(
        seed=404,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    hydrology = bundle.hydrology_df

    assert _count(hydrology, "hydro_role", HydroRole.SURFACE_CHANNEL) > 0
    assert _count(hydrology, "hydro_role", HydroRole.UNDERGROUND_CHANNEL) > 0

    expected_roles = {
        HydroRole.SPRING,
        HydroRole.PONOR,
        HydroRole.ESTAVELLE,
        HydroRole.SINKING_LAKE,
    }
    role_groups = {
        role: _flow_groups_for_role(hydrology, role) for role in expected_roles
    }
    assert all(groups == {1} for groups in role_groups.values())

    assert _hydrology_roles_connected(
        hydrology,
        source_role=HydroRole.SPRING,
        target_role=HydroRole.PONOR,
        flow_group=1,
    )
    assert _hydrology_roles_connected(
        hydrology,
        source_role=HydroRole.SINKING_LAKE,
        target_role=HydroRole.PONOR,
        flow_group=1,
    )
    assert _hydrology_roles_connected(
        hydrology,
        source_role=HydroRole.SPRING,
        target_role=HydroRole.ESTAVELLE,
        flow_group=1,
    )
    assert _flow_group_is_connected(hydrology, flow_group=1)

    underground = hydrology.filter(pl.col("connected_to_underground"))
    assert _count(underground, "hydro_role", HydroRole.PONOR) > 0
    assert _count(underground, "hydro_role", HydroRole.ESTAVELLE) > 0
    assert _count(underground, "hydro_role", HydroRole.UNDERGROUND_CHANNEL) > 0


def test_perennial_surface_water_is_not_karst_hydrology() -> None:
    bundle = generate_overland_region(
        seed=505,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    hydrology = bundle.hydrology_df
    perennial = hydrology.filter(pl.col("flow_group") == 2)

    assert perennial.height > 0
    assert _count(perennial, "hydro_role", HydroRole.PERMANENT_POOL) > 0
    assert _count(perennial, "hydro_role", HydroRole.SURFACE_CHANNEL) > 0
    assert _count(perennial, "hydro_role", HydroRole.UNDERGROUND_CHANNEL) == 0
    assert not bool(perennial.get_column("connected_to_underground").any())
    assert set(perennial.get_column("seasonal_state").to_list()) == {"stable"}
    assert _flow_group_is_connected(hydrology, flow_group=2)
    assert _hydrology_roles_connected(
        hydrology,
        source_role=HydroRole.PERMANENT_POOL,
        target_role=HydroRole.SURFACE_CHANNEL,
        flow_group=2,
    )

    pool = perennial.filter(pl.col("hydro_role") == int(HydroRole.PERMANENT_POOL))
    channels = perennial.filter(pl.col("hydro_role") == int(HydroRole.SURFACE_CHANNEL))
    pool_min_x = int(pool.get_column("x").min())
    pool_max_x = int(pool.get_column("x").max())
    assert int(channels.get_column("x").min()) < pool_min_x
    assert int(channels.get_column("x").max()) > pool_max_x


def test_starting_region_contract_emits_required_surface_features() -> None:
    bundle = generate_overland_region(
        seed=606,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    contract = bundle.metadata["starting_region_contract"]

    assert contract["kind"] == "first_expedition_region"
    assert contract["harbor"]["state"] == "ruined_dead_port"
    assert contract["local_survey_zone"]["radius_tiles"] > 0
    assert len(contract["resource_sites"]) >= 4
    assert len(contract["route_segments"]) == 1
    assert len(contract["blockages"]) == 1
    assert len(contract["waystation_candidates"]) == 1
    assert len(contract["inland_sites"]) == 1
    assert len(contract["cave_refs"]) == 1

    # Phase 4 evidence tags (generator outputs only)
    assert "evidence_tags" in contract["harbor"]
    assert set(contract["harbor"]["evidence_tags"]) == {
        int(EvidenceTag.LATE_COLONIAL_OCCUPATION),
        int(EvidenceTag.RUINED),
        int(EvidenceTag.OVERGROWN),
    }
    assert "evidence_tags" in contract["blockages"][0]
    assert set(contract["blockages"][0]["evidence_tags"]) == {
        int(EvidenceTag.RECENT_COLLAPSE),
        int(EvidenceTag.SUBSIDENCE_DAMAGE),
    }
    assert "evidence_tags" in contract["waystation_candidates"][0]
    assert set(contract["waystation_candidates"][0]["evidence_tags"]) == {
        int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
        int(EvidenceTag.WAYSTATION_REMAINS),
        int(EvidenceTag.PARTIAL_REPAIR),
    }
    assert "evidence_tags" in contract["inland_sites"][0]
    assert set(contract["inland_sites"][0]["evidence_tags"]) == {
        int(EvidenceTag.PRECURSOR_OCCUPATION),
        int(EvidenceTag.MAUSOLEUM_COMPLEX),
        int(EvidenceTag.RUINED),
        int(EvidenceTag.OVERGROWN),
    }
    assert "evidence_tags" in contract["cave_refs"][0]
    assert set(contract["cave_refs"][0]["evidence_tags"]) == {
        int(EvidenceTag.PRECURSOR_OCCUPATION),
        int(EvidenceTag.PRIOR_EXPEDITION),
    }

    route = contract["route_segments"][0]
    assert route["route_id"] == "ancient_road_harbor_to_inland_site"
    assert route["state"] == int(RouteSegmentState.BLOCKED)
    assert route["blockage"] == contract["blockages"][0]["blockage_id"]
    assert "repair_cost" in route and route["repair_cost"] > 0
    assert "evidence_tags" in route
    assert set(route["evidence_tags"]) == {
        int(EvidenceTag.EARLY_COLONIAL_OCCUPATION),
        int(EvidenceTag.ROAD_ENGINEERING),
        int(EvidenceTag.RECENT_COLLAPSE),
        int(EvidenceTag.PRIOR_EXPEDITION),
        int(EvidenceTag.PARTIAL_REPAIR),
    }
    assert "last_modified" in route
    assert set(route["profile_costs"]) == {
        "HUMAN_ON_FOOT",
        "PACK_ANIMAL",
        "SMALL_AMPHIBIOUS",
        "SWIMMER",
        "BOAT",
    }
    assert route["profile_costs"]["BOAT"] is None

    required_features = {
        FeatureType.RUINED_HARBOR,
        FeatureType.FRESH_WATER_SITE,
        FeatureType.RESOURCE_SITE,
        FeatureType.ANCIENT_ROAD,
        FeatureType.CLEARABLE_BLOCKAGE,
        FeatureType.WAYSTATION_CANDIDATE,
        FeatureType.INLAND_SITE,
        FeatureType.ORDINARY_CAVE,
    }
    emitted_features = {
        FeatureType(int(row["feature_type"]))
        for row in bundle.features_df.filter(
            pl.col("tags").str.starts_with("starting_region;")
        ).iter_rows(named=True)
    }
    assert required_features <= emitted_features
    assert "evidence_tags" in bundle.features_df.columns

    ruined_harbor = bundle.features_df.filter(
        pl.col("feature_type") == int(FeatureType.RUINED_HARBOR)
    ).to_dicts()[0]
    assert set(ruined_harbor["evidence_tags"]) == {
        int(EvidenceTag.LATE_COLONIAL_OCCUPATION),
        int(EvidenceTag.RUINED),
        int(EvidenceTag.OVERGROWN),
    }

    ancient_road = bundle.features_df.filter(
        pl.col("feature_type") == int(FeatureType.ANCIENT_ROAD)
    ).to_dicts()[0]
    assert set(ancient_road["evidence_tags"]) == {
        int(EvidenceTag.EARLY_COLONIAL_OCCUPATION),
        int(EvidenceTag.ROAD_ENGINEERING),
        int(EvidenceTag.ABANDONED),
        int(EvidenceTag.OVERGROWN),
    }

    stone_site = bundle.features_df.filter(pl.col("target_id") == 104).to_dicts()[0]
    assert stone_site["evidence_tags"] == [int(EvidenceTag.QUARRIED_STONE)]

    assert _count(bundle.tiles_df, "material", Material.ROAD) > 0
    assert _count(bundle.tiles_df, "material", Material.DOCK) > 0
    assert _count(bundle.tiles_df, "material", Material.RUIN_FLOOR) > 0
    assert _count(bundle.tiles_df, "material", Material.SINKHOLE_EDGE) > 0

    cave_point = tuple(contract["cave_refs"][0]["point"])
    cave_tile = _tile_at(bundle.tiles_df, cave_point)
    assert cave_tile["material"] == int(Material.CAVE_MOUTH)
    assert cave_tile["hydro_role"] == int(HydroRole.NONE)

    transitions = generate_transition_requests(bundle)
    assert any(
        request.transition_type == TransitionType.CAVE_ENTRANCE
        and (request.source_x, request.source_y) == cave_point
        for request in transitions
    )
    assert any(request.evidence_tags for request in transitions)


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
    routes_df = overland_routes_to_df(generate_debug_routes(merged))
    assert "evidence_tags" in routes_df.columns
    assert any(
        int(EvidenceTag.RECENT_LOCAL_OCCUPATION) in row["evidence_tags"]
        for row in routes_df.iter_rows(named=True)
    )


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
    assert (
        _count(
            loaded["transitions_df"],
            "transition_type",
            TransitionType.SETTLEMENT_ENTRANCE,
        )
        > 0
    )


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
    assert movement_cost_for_actor(dry_lake, ActorTraversalProfile.HUMAN_ON_FOOT) > 1.0

    assert movement_cost_for_actor(
        wet_fish_trail, ActorTraversalProfile.SMALL_AMPHIBIOUS
    ) < movement_cost_for_actor(wet_fish_trail, ActorTraversalProfile.HUMAN_ON_FOOT)
    assert can_actor_enter(dry_fish_trail, ActorTraversalProfile.HUMAN_ON_FOOT)

    human_costs = build_actor_cost_grid(
        dry.tiles_df, ActorTraversalProfile.HUMAN_ON_FOOT
    )
    boat_costs = build_actor_cost_grid(wet.tiles_df, ActorTraversalProfile.BOAT)
    assert human_costs.shape == (72, 96)
    assert boat_costs.shape == (72, 96)
    assert np.isfinite(human_costs).sum() > np.isfinite(boat_costs).sum()


def test_seasonal_overland_routes_are_profile_specific() -> None:
    bundle = generate_overland_region(
        seed=303,
        width=96,
        height=72,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    wet = apply_hydrology_state(bundle, HydroState.WET_SEASON)
    dry = apply_hydrology_state(bundle, HydroState.DRY_SEASON)

    spring = find_feature(bundle, FeatureType.SPRING)
    assert spring is not None
    ponor = find_nearest_feature(
        bundle,
        (int(spring["x"]), int(spring["y"])),
        FeatureType.PONOR,
    )
    assert ponor is not None
    start = (int(spring["x"]), int(spring["y"]))
    goal = (int(ponor["x"]), int(ponor["y"]))

    wet_human = find_overland_path(
        wet,
        start,
        goal,
        ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    dry_human = find_overland_path(
        dry,
        start,
        goal,
        ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    amphibious = find_overland_path(
        wet,
        start,
        goal,
        ActorTraversalProfile.SMALL_AMPHIBIOUS,
    )

    assert wet_human.found
    assert dry_human.found
    assert amphibious.found
    assert amphibious.total_cost < wet_human.total_cost

    lake_start = (20, 21)
    lake_goal = (33, 21)
    wet_lake_human = find_overland_path(
        wet,
        lake_start,
        lake_goal,
        ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    dry_lake_human = find_overland_path(
        dry,
        lake_start,
        lake_goal,
        ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    wet_boat = find_overland_path(
        wet,
        lake_start,
        lake_goal,
        ActorTraversalProfile.BOAT,
    )
    dry_boat = find_overland_path(
        dry,
        lake_start,
        lake_goal,
        ActorTraversalProfile.BOAT,
    )
    assert not wet_lake_human.found
    assert dry_lake_human.found
    assert wet_boat.found
    assert not dry_boat.found
    assert _route_uses_any_material(dry, dry_lake_human.path, {Material.CRACKED_MUD})

    same_wet = apply_hydrology_state(
        generate_overland_region(
            seed=303,
            width=96,
            height=72,
            profile="KARST_TO_VOLCANIC_MOUNTAIN",
        ),
        HydroState.WET_SEASON,
    )
    same_route = find_overland_path(
        same_wet,
        start,
        goal,
        ActorTraversalProfile.HUMAN_ON_FOOT,
    )
    assert _route_checksum(wet_human.path) == _route_checksum(same_route.path)


def _count(df: pl.DataFrame, column: str, enum_value: object) -> int:
    return df.filter(pl.col(column) == int(enum_value)).height


def _first_row(df: pl.DataFrame, column: str, enum_value: object) -> dict[str, object]:
    rows = df.filter(pl.col(column) == int(enum_value)).head(1).to_dicts()
    assert rows
    return rows[0]


def _tile_at(df: pl.DataFrame, point: tuple[int, int]) -> dict[str, object]:
    x, y = point
    rows = df.filter((pl.col("x") == x) & (pl.col("y") == y)).to_dicts()
    assert len(rows) == 1
    return rows[0]


def _transition_at(df: pl.DataFrame, point: tuple[int, int]) -> dict[str, object]:
    x, y = point
    rows = df.filter((pl.col("source_x") == x) & (pl.col("source_y") == y)).to_dicts()
    assert rows
    return rows[0]


def _flow_groups_for_role(df: pl.DataFrame, hydro_role: HydroRole) -> set[int]:
    return {
        int(row["flow_group"])
        for row in df.filter(pl.col("hydro_role") == int(hydro_role)).iter_rows(
            named=True
        )
    }


def _hydrology_roles_connected(
    df: pl.DataFrame,
    *,
    source_role: HydroRole,
    target_role: HydroRole,
    flow_group: int,
) -> bool:
    cells = _hydrology_cells(df, flow_group=flow_group)
    starts = _hydrology_cells(df, flow_group=flow_group, hydro_role=source_role)
    goals = _hydrology_cells(df, flow_group=flow_group, hydro_role=target_role)
    return _cells_connected(cells, starts, goals)


def _flow_group_is_connected(df: pl.DataFrame, *, flow_group: int) -> bool:
    cells = _hydrology_cells(df, flow_group=flow_group)
    if not cells:
        return False
    first = next(iter(cells))
    return _reachable_cells(cells, {first}) == cells


def _hydrology_cells(
    df: pl.DataFrame,
    *,
    flow_group: int,
    hydro_role: HydroRole | None = None,
) -> set[tuple[int, int]]:
    query = df.filter(pl.col("flow_group") == flow_group)
    if hydro_role is not None:
        query = query.filter(pl.col("hydro_role") == int(hydro_role))
    return {(int(row["x"]), int(row["y"])) for row in query.iter_rows(named=True)}


def _cells_connected(
    cells: set[tuple[int, int]],
    starts: set[tuple[int, int]],
    goals: set[tuple[int, int]],
) -> bool:
    if not cells or not starts or not goals:
        return False
    queue = deque(starts)
    visited = set(starts)
    while queue:
        cell = queue.popleft()
        if cell in goals:
            return True
        x, y = cell
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor = (x + dx, y + dy)
                if neighbor in cells and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    return False


def _reachable_cells(
    cells: set[tuple[int, int]],
    starts: set[tuple[int, int]],
) -> set[tuple[int, int]]:
    queue = deque(starts)
    visited = set(starts)
    while queue:
        x, y = queue.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                neighbor = (x + dx, y + dy)
                if neighbor in cells and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
    return visited


def _checksum(df: pl.DataFrame) -> str:
    payload = json.dumps(df.to_dict(as_series=False), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _route_checksum(path: tuple[tuple[int, int], ...]) -> str:
    payload = json.dumps(path)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _route_uses_any_material(
    bundle: object,
    path: tuple[tuple[int, int], ...],
    materials: set[Material],
) -> bool:
    wanted = {int(material) for material in materials}
    material_lookup = {
        (int(row["x"]), int(row["y"])): int(row["material"])
        for row in bundle.tiles_df.iter_rows(named=True)
    }
    return any(material_lookup.get(coord) in wanted for coord in path)


def test_metadata_contains_route_segments_and_transitions_with_evidence_tags_shape(tmp_path) -> None:
    bundle = generate_overland_region(
        seed=123,
        width=64,
        height=48,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    paths = write_overland_bundle(bundle, tmp_path)
    loaded_metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))

    # Assert top-level keys are present in metadata JSON
    assert "route_segments" in loaded_metadata
    assert "transitions" in loaded_metadata

    # Assert route segments have evidence_tags as list of ints
    route_segs = loaded_metadata["route_segments"]
    assert len(route_segs) > 0
    for seg in route_segs:
        assert "evidence_tags" in seg
        assert isinstance(seg["evidence_tags"], list)
        assert all(isinstance(tag, int) for tag in seg["evidence_tags"])

    # Assert transitions have evidence_tags as list of ints
    transitions = loaded_metadata["transitions"]
    assert len(transitions) > 0
    for trans in transitions:
        assert "evidence_tags" in trans
        assert isinstance(trans["evidence_tags"], list)
        assert all(isinstance(tag, int) for tag in trans["evidence_tags"])

    # Verify that overland_to_game_map loads sidecar with route_segments & transitions correctly
    # when using the loaded metadata (with-metadata path)
    from worldgen.overland.convert import overland_to_game_map
    from worldgen.overland.schema import OverlandMapMetadata
    from game.world.game_map import GameMap

    gm, sidecar = overland_to_game_map(bundle, with_metadata=True)
    assert isinstance(gm, GameMap)
    assert isinstance(sidecar, OverlandMapMetadata)
    assert len(sidecar.route_segments) > 0
    assert len(sidecar.transitions) > 0

    # Test that the sidecar transitions match what was in the metadata
    for trans in transitions:
        coord = (trans["source_x"], trans["source_y"])
        assert coord in sidecar.transitions
        for payload in sidecar.transitions[coord]:
            assert "source_x" not in payload
            assert "source_y" not in payload


def test_inspect_overland_evidence_view_runs(tmp_path) -> None:
    bundle = generate_overland_region(
        seed=124,
        width=32,
        height=32,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )
    write_overland_bundle(bundle, tmp_path)

    # Invoke inspect_overland.py via subprocess
    import subprocess
    import sys

    cmd = [sys.executable, "tools/inspect_overland.py", str(tmp_path), "--view", "evidence"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    assert "=== FEATURES WITH EVIDENCE TAGS ===" in result.stdout
    assert "=== TRANSITIONS WITH EVIDENCE TAGS ===" in result.stdout
    assert "=== ROUTE SEGMENTS WITH EVIDENCE TAGS ===" in result.stdout

