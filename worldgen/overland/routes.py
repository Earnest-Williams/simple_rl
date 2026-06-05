from __future__ import annotations

import polars as pl

from common.constants import Material
from worldgen.overland.actor_traversal import ActorTraversalProfile
from worldgen.overland.pathfinding import OverlandRoute, find_overland_path
from worldgen.overland.schema import Biome, FeatureType, HydroRole, OverlandBundle


def generate_debug_routes(bundle: OverlandBundle) -> list[OverlandRoute]:
    """Generate a small set of inspectable routes for regression/debug output."""

    routes: list[OverlandRoute] = []

    coast = _first_tile_by_biome(bundle, Biome.COASTAL_RAIN_FOREST)
    spring = _feature_point(bundle, FeatureType.SPRING)
    if coast and spring:
        routes.append(
            find_overland_path(
                bundle,
                coast,
                spring,
                ActorTraversalProfile.HUMAN_ON_FOOT,
            )
        )

    starting_port = _starting_port_point(bundle)
    gorge = _first_tile_by_biome(bundle, Biome.LIMESTONE_GORGE)
    if starting_port and gorge:
        routes.append(
            find_overland_path(
                bundle,
                starting_port,
                gorge,
                ActorTraversalProfile.HUMAN_ON_FOOT,
            )
        )

    lava_skylight = _feature_point(bundle, FeatureType.LAVA_TUBE_SKYLIGHT)
    if starting_port and lava_skylight:
        routes.append(
            find_overland_path(
                bundle,
                starting_port,
                lava_skylight,
                ActorTraversalProfile.HUMAN_ON_FOOT,
            )
        )

    sinking_lake = _first_tile_by_hydro_role(bundle, HydroRole.SINKING_LAKE)
    ponor = _feature_point(bundle, FeatureType.PONOR)
    if sinking_lake and ponor:
        routes.append(
            find_overland_path(
                bundle,
                sinking_lake,
                ponor,
                ActorTraversalProfile.SMALL_AMPHIBIOUS,
            )
        )

    return routes


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
            }
        )
    return rows


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
