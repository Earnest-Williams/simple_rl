from __future__ import annotations

from dataclasses import replace
from typing import Any

import polars as pl

from common.constants import Material
from utils.game_rng import GameRNG
from worldgen.overland.actor_traversal import ActorTraversalProfile
from worldgen.overland.pathfinding import OverlandRoute, find_overland_path
from worldgen.overland.schema import (
    Biome,
    EvidenceTag,
    FeatureType,
    HydroRole,
    OverlandBundle,
    RouteSegmentState,
)


def generate_debug_routes(bundle: OverlandBundle) -> list[OverlandRoute]:
    """Generate a small set of inspectable routes for regression/debug output.

    Routes now carry RouteSegmentState from the starting contract for repair
    simulation.
    """

    routes: list[OverlandRoute] = []

    coast = _first_tile_by_biome(bundle, Biome.COASTAL_RAIN_FOREST)
    spring = _feature_point(bundle, FeatureType.SPRING)
    if coast and spring:
        routes.append(
            _route_with_evidence(
                bundle,
                find_overland_path(
                    bundle,
                    coast,
                    spring,
                    ActorTraversalProfile.HUMAN_ON_FOOT,
                ),
            )
        )

    starting_port = _starting_port_point(bundle)
    gorge = _first_tile_by_biome(bundle, Biome.LIMESTONE_GORGE)
    if starting_port and gorge:
        routes.append(
            _route_with_evidence(
                bundle,
                find_overland_path(
                    bundle,
                    starting_port,
                    gorge,
                    ActorTraversalProfile.HUMAN_ON_FOOT,
                ),
            )
        )

    lava_skylight = _feature_point(bundle, FeatureType.LAVA_TUBE_SKYLIGHT)
    if starting_port and lava_skylight:
        routes.append(
            _route_with_evidence(
                bundle,
                find_overland_path(
                    bundle,
                    starting_port,
                    lava_skylight,
                    ActorTraversalProfile.HUMAN_ON_FOOT,
                ),
            )
        )

    sinking_lake = _first_tile_by_hydro_role(bundle, HydroRole.SINKING_LAKE)
    ponor = _feature_point(bundle, FeatureType.PONOR)
    if sinking_lake and ponor:
        routes.append(
            _route_with_evidence(
                bundle,
                find_overland_path(
                    bundle,
                    sinking_lake,
                    ponor,
                    ActorTraversalProfile.SMALL_AMPHIBIOUS,
                ),
            )
        )

    return routes


def simulate_route_repair(bundle: OverlandBundle, rng: GameRNG) -> OverlandBundle:
    """Deterministic simulation of route repair/clearing using GameRNG.

    Mutates a copy of the bundle's metadata route_segments. BLOCKED segments
    have a chance to become REPAIRED based on repair_cost and RNG roll.
    Advances settlement roads toward CLEAR/REPAIRED states. Returns new bundle
    (immutable pattern).
    """
    metadata = dict(bundle.metadata)  # shallow copy for new bundle
    contract = metadata.get("starting_region_contract", {})
    if "route_segments" not in contract:
        return bundle  # type: ignore[return-value]

    segments: list[dict[str, Any]] = []
    for seg in contract.get("route_segments", []):
        seg = dict(seg)  # copy
        state = RouteSegmentState(seg.get("state", 0))
        if state == RouteSegmentState.BLOCKED:
            # Deterministic roll: lower repair_cost = higher success chance (0-100)
            roll = rng.get_int(0, 100)
            if roll < (100 - seg.get("repair_cost", 50)):
                seg["state"] = int(RouteSegmentState.REPAIRED)
                seg["evidence_tags"] = seg.get("evidence_tags", []) + [
                    int(EvidenceTag.PARTIAL_REPAIR)
                ]
                seg["last_modified"] = 1  # simulation tick
        segments.append(seg)

    contract = dict(contract)
    contract["route_segments"] = segments
    metadata["starting_region_contract"] = contract
    # Also update top-level route_segments if present for sidecar
    if "route_segments" in metadata:
        metadata["route_segments"] = segments

    return OverlandBundle(
        tiles_df=bundle.tiles_df,
        hydrology_df=bundle.hydrology_df,
        features_df=bundle.features_df,
        affordances_df=bundle.affordances_df,
        metadata=metadata,
    )


def _update_route_state_in_features(
    features_df: pl.DataFrame, route_id: str, new_state: int
) -> pl.DataFrame:
    """Helper to propagate route state changes to features_df (for settlement roads)."""
    if features_df.is_empty():
        return features_df
    return features_df.with_columns(
        pl.when(pl.col("tags").str.contains(route_id))
        .then(new_state)
        .otherwise(pl.col("feature_type"))
        .alias("feature_type")  # reuse for state hint in runtime
    )


def overland_routes_to_df(routes: list[OverlandRoute]) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for index, route in enumerate(routes):
        if not route.found:
            continue
        route_id = _route_id(route, index)
        rows.extend(_route_rows(route_id, route))
    return pl.DataFrame(
        rows,
        schema={
            "route_id": pl.String,
            "profile": pl.String,
            "source_x": pl.Int64,
            "source_y": pl.Int64,
            "target_x": pl.Int64,
            "target_y": pl.Int64,
            "step_index": pl.Int64,
            "x": pl.Int64,
            "y": pl.Int64,
            "cost_so_far": pl.Float64,
            "tags": pl.String,
            "evidence_tags": pl.List(pl.Int64),
        },
    )


def _route_rows(route_id: str, route: OverlandRoute) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    denominator = max(1, len(route.path) - 1)
    for step_index, point in enumerate(route.path):
        cost_so_far = route.total_cost * (step_index / denominator)
        rows.append(
            {
                "route_id": route_id,
                "profile": route.profile.name,
                "source_x": route.start[0],
                "source_y": route.start[1],
                "target_x": route.goal[0],
                "target_y": route.goal[1],
                "step_index": step_index,
                "x": point[0],
                "y": point[1],
                "cost_so_far": cost_so_far,
                "tags": "debug;found",
                "evidence_tags": list(route.evidence_tags),
            }
        )
    return rows


def _route_with_evidence(
    bundle: OverlandBundle,
    route: OverlandRoute,
) -> OverlandRoute:
    return replace(route, evidence_tags=_route_evidence_tags(bundle, route))


def _route_evidence_tags(
    bundle: OverlandBundle,
    route: OverlandRoute,
) -> tuple[int, ...]:
    if not route.path:
        return ()

    feature_evidence_tags: dict[tuple[int, int], set[int]] = {}
    for row in bundle.features_df.iter_rows(named=True):
        key = (int(row["x"]), int(row["y"]))
        evidence = row.get("evidence_tags", [])
        if evidence is None:
            continue
        feature_evidence_tags.setdefault(key, set()).update(
            int(value) for value in evidence
        )

    tile_lookup = {
        (int(row["x"]), int(row["y"])): row
        for row in bundle.tiles_df.iter_rows(named=True)
    }

    values: set[int] = set()
    for point in route.path:
        values.update(feature_evidence_tags.get(point, set()))
        tile = tile_lookup.get(point)
        if tile is None:
            continue
        material = Material(int(tile["material"]))
        if material == Material.ROAD:
            values.update(
                {
                    int(EvidenceTag.EARLY_COLONIAL_OCCUPATION),
                    int(EvidenceTag.ROAD_ENGINEERING),
                    int(EvidenceTag.ABANDONED),
                    int(EvidenceTag.OVERGROWN),
                }
            )
        elif material == Material.DOCK:
            values.update(
                {
                    int(EvidenceTag.RECENT_LOCAL_OCCUPATION),
                    int(EvidenceTag.ROAD_ENGINEERING),
                }
            )
        elif material == Material.COLLAPSED_LAVA_TUBE:
            values.update(
                {
                    int(EvidenceTag.VOLCANIC_BURIAL),
                    int(EvidenceTag.STRUCTURAL_COLLAPSE),
                    int(EvidenceTag.RECENT_COLLAPSE),
                }
            )

    return tuple(sorted(values))


def _route_id(route: OverlandRoute, index: int) -> str:
    return (
        f"{index:02d}_{route.profile.name.lower()}_"
        f"{route.start[0]}_{route.start[1]}_to_{route.goal[0]}_{route.goal[1]}"
    )


def _feature_point(
    bundle: OverlandBundle,
    feature_type: FeatureType,
) -> tuple[int, int] | None:
    rows = (
        bundle.features_df.filter(pl.col("feature_type") == int(feature_type))
        .head(1)
        .to_dicts()
    )
    if not rows:
        return None
    return int(rows[0]["x"]), int(rows[0]["y"])


def _first_tile_by_biome(
    bundle: OverlandBundle,
    biome: Biome,
) -> tuple[int, int] | None:
    return _first_tile_by_column(bundle, "biome", int(biome))


def _first_tile_by_hydro_role(
    bundle: OverlandBundle,
    hydro_role: HydroRole,
) -> tuple[int, int] | None:
    return _first_tile_by_column(bundle, "hydro_role", int(hydro_role))


def _first_tile_by_column(
    bundle: OverlandBundle,
    column: str,
    value: int,
) -> tuple[int, int] | None:
    rows = bundle.tiles_df.filter(pl.col(column) == value).head(1).to_dicts()
    if not rows:
        return None
    return int(rows[0]["x"]), int(rows[0]["y"])


def _starting_port_point(bundle: OverlandBundle) -> tuple[int, int] | None:
    settlements = bundle.metadata.get("settlements")
    if not isinstance(settlements, list) or not settlements:
        return None
    first = settlements[0]
    if not isinstance(first, dict):
        return None
    origin = first.get("origin")
    width = first.get("width")
    height = first.get("height")
    if not isinstance(origin, list | tuple) or len(origin) != 2:
        return None
    if not isinstance(width, int) or not isinstance(height, int):
        return None
    center = (int(origin[0]) + width // 2, int(origin[1]) + height // 2)
    return _nearest_material(bundle, center, Material.ROAD) or center


def _nearest_material(
    bundle: OverlandBundle,
    origin: tuple[int, int],
    material: Material,
) -> tuple[int, int] | None:
    rows = bundle.tiles_df.filter(pl.col("material") == int(material)).to_dicts()
    if not rows:
        return None
    ox, oy = origin
    row = min(
        rows,
        key=lambda item: (int(item["x"]) - ox) ** 2 + (int(item["y"]) - oy) ** 2,
    )
    return int(row["x"]), int(row["y"])
