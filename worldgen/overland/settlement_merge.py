from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from common.constants import Material
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.rules import surface_flag_mask
from worldgen.overland.schema import (
    EvidenceTag,
    HydroRole,
    OverlandBundle,
    RouteSegmentState,
    Substrate,
    SurfaceFlag,
    TraversalClass,
    Wetness,
)

if TYPE_CHECKING:
    from worldgen.settlements.export import SettlementBundle

_OVERLAND_COLUMNS: tuple[str, ...] = (
    "x",
    "y",
    "material",
    "biome",
    "elevation_band",
    "hydro_role",
    "wetness",
    "substrate",
    "walkable",
    "blocks_sight",
    "movement_cost",
    "traversal_class",
    "surface_flags",
)

TRANSITION_MATERIALS = {
    int(Material.PONOR),
    int(Material.CAVE_MOUTH),
    int(Material.LAVA_TUBE_SKYLIGHT),
    int(Material.COLLAPSED_LAVA_TUBE),
}

WATER_HYDRO_MATERIALS = {
    int(Material.SHALLOW_WATER),
    int(Material.DEEP_WATER),
    int(Material.FLOWING_WATER),
    int(Material.SPRING_WATER),
    int(Material.SINKING_WATER),
    int(Material.ESTAVELLE_WATER),
    int(Material.STAGNANT_WATER),
    int(Material.BOG_WATER),
    int(Material.UNDERGROUND_WATER),
    int(Material.BOG_POOL),
    int(Material.TARN),
}

ROAD_BRIDGE_MATERIALS = {
    int(Material.ROAD),
    int(Material.TRACK),
    int(Material.TRAIL),
    int(Material.ANIMAL_TRAIL),
    int(Material.BOARDWALK),
    int(Material.BRIDGE),
    int(Material.DOCK),
}


def merge_settlement_into_overland(
    overland: OverlandBundle,
    settlement: SettlementBundle,
    *,
    origin: tuple[int, int],
) -> OverlandBundle:
    """Overlay settlement-produced surfaces into an overland bundle."""

    ox, oy = origin
    settlement_tiles = _settlement_overland_tiles(settlement, ox=ox, oy=oy)

    # 1. Replace tiles applying preservation rules (hydrology/transitions)
    merged_tiles = _replace_tiles(
        base=overland.tiles_df,
        overlay=settlement_tiles,
    )

    # 2. Connect settlement-generated roads/trails to the overland route network
    road_endpoints = settlement.metadata.get("region", {}).get("road_endpoints", [])
    absolute_endpoints = [(int(rx) + ox, int(ry) + oy) for rx, ry in road_endpoints]

    s_width = int(settlement.metadata.get("width", 0))
    s_height = int(settlement.metadata.get("height", 0))

    # Find base road tiles outside the settlement area
    outside_roads = overland.tiles_df.filter(
        pl.col("material").is_in(
            [int(Material.ROAD), int(Material.TRACK), int(Material.TRAIL)]
        )
        & ~(
            (pl.col("x") >= ox)
            & (pl.col("x") < ox + s_width)
            & (pl.col("y") >= oy)
            & (pl.col("y") < oy + s_height)
        )
    )
    if outside_roads.is_empty():
        # Fallback to any base road tiles
        outside_roads = overland.tiles_df.filter(
            pl.col("material").is_in(
                [int(Material.ROAD), int(Material.TRACK), int(Material.TRAIL)]
            )
        )

    world_width = int(overland.metadata.get("width", 0))
    world_height = int(overland.metadata.get("height", 0))
    if world_width == 0 or world_height == 0:
        world_width = int(overland.tiles_df.get_column("x").max() + 1)
        world_height = int(overland.tiles_df.get_column("y").max() + 1)

    updates = []
    # Dictionary for O(1) coordinate lookups during updates
    merged_lookup = {
        (int(row["x"]), int(row["y"])): dict(row)
        for row in merged_tiles.iter_rows(named=True)
    }

    for ex, ey in absolute_endpoints:
        if not outside_roads.is_empty():
            min_dist = float("inf")
            nearest = None
            for r_row in outside_roads.iter_rows(named=True):
                rx, ry = int(r_row["x"]), int(r_row["y"])
                dist = (rx - ex) ** 2 + (ry - ey) ** 2
                if dist < min_dist:
                    min_dist = dist
                    nearest = (rx, ry)

            if nearest is not None:
                path = _connect_points_with_road(
                    merged_tiles,
                    (ex, ey),
                    nearest,
                    world_width,
                    world_height,
                )

                for px, py in path:
                    tile = merged_lookup.get((px, py))
                    if tile is None:
                        continue

                    mat = int(tile["material"])
                    wetness = int(tile["wetness"])
                    hydro_role = int(tile["hydro_role"])
                    surface_flags = int(tile["surface_flags"])

                    if mat in WATER_HYDRO_MATERIALS:
                        new_mat = int(Material.BRIDGE)
                        substrate = int(Substrate.WOOD)
                        walkable = True
                        blocks_sight = False
                        from worldgen.overland.rules import (
                            derive_movement_cost,
                            derive_traversal_class,
                        )

                        movement_cost = float(
                            derive_movement_cost(
                                Material.BRIDGE, Wetness(wetness), surface_flags
                            )
                        )
                        traversal_class = int(
                            derive_traversal_class(
                                Material.BRIDGE, Wetness(wetness), surface_flags
                            )
                        )
                        surface_flags |= surface_flag_mask(SurfaceFlag.BUILT)
                    else:
                        new_mat = int(Material.ROAD)
                        substrate = int(Substrate.BUILT_STONE)
                        walkable = True
                        blocks_sight = False
                        movement_cost = 1.0
                        traversal_class = int(TraversalClass.NORMAL)
                        hydro_role = int(HydroRole.NONE)
                        wetness = int(Wetness.DAMP)
                        surface_flags = surface_flag_mask(SurfaceFlag.BUILT)

                    updated_row = {
                        "x": tile["x"],
                        "y": tile["y"],
                        "material": new_mat,
                        "biome": int(tile["biome"]),
                        "elevation_band": int(tile["elevation_band"]),
                        "hydro_role": hydro_role,
                        "wetness": wetness,
                        "substrate": substrate,
                        "walkable": walkable,
                        "blocks_sight": blocks_sight,
                        "movement_cost": movement_cost,
                        "traversal_class": traversal_class,
                        "surface_flags": surface_flags,
                    }
                    updates.append(updated_row)
                    merged_lookup[(px, py)] = updated_row

    if updates:
        updates_df = pl.DataFrame(updates, schema=overland.tiles_df.schema)
        merged_tiles = _replace_tiles(base=merged_tiles, overlay=updates_df)

    merged_features = _merge_settlement_features(
        overland.features_df,
        settlement,
        ox=ox,
        oy=oy,
    )
    metadata: dict[str, Any] = {
        **overland.metadata,
        "settlements": [
            *overland.metadata.get("settlements", []),
            {
                "name": settlement.metadata["name"],
                "kind": settlement.metadata["kind"],
                "origin": [ox, oy],
                "width": settlement.metadata["width"],
                "height": settlement.metadata["height"],
                "road_state": int(
                    RouteSegmentState.CLEAR
                ),  # settlement roads start repaired/cleared
            },
        ],
    }
    without_affordances = OverlandBundle(
        tiles_df=merged_tiles,
        hydrology_df=overland.hydrology_df,
        features_df=merged_features,
        affordances_df=pl.DataFrame(),
        metadata=metadata,
    )
    return OverlandBundle(
        tiles_df=merged_tiles,
        hydrology_df=overland.hydrology_df,
        features_df=merged_features,
        affordances_df=generate_affordances(without_affordances),
        metadata=metadata,
    )


def _settlement_overland_tiles(
    settlement: SettlementBundle,
    *,
    ox: int,
    oy: int,
) -> pl.DataFrame:
    missing = set(_OVERLAND_COLUMNS) - set(settlement.map_df.columns)
    if missing:
        raise ValueError(
            f"Settlement map is missing overland columns: {sorted(missing)}"
        )
    return (
        settlement.map_df.select(_OVERLAND_COLUMNS)
        .with_columns(
            (pl.col("x").cast(pl.Int32) + ox).alias("x"),
            (pl.col("y").cast(pl.Int32) + oy).alias("y"),
        )
        .filter(pl.col("material") != 0)
    )


def _replace_tiles(*, base: pl.DataFrame, overlay: pl.DataFrame) -> pl.DataFrame:
    if overlay.is_empty():
        return base

    overlapping_base = base.join(
        overlay.select("x", "y"),
        on=["x", "y"],
        how="semi",
    )

    if overlapping_base.is_empty():
        untouched = base.join(
            overlay.select("x", "y"),
            on=["x", "y"],
            how="anti",
        )
        columns = list(base.columns)
        return pl.concat([untouched.select(columns), overlay.select(columns)]).sort(
            ["y", "x"]
        )

    joined = overlay.join(
        overlapping_base,
        on=["x", "y"],
        how="left",
        suffix="_base",
    )

    transition_mask = 1 << (int(SurfaceFlag.TRANSITION) - 1)
    is_transition = pl.col("material_base").is_not_null() & (
        (pl.col("material_base").is_in(list(TRANSITION_MATERIALS)))
        | ((pl.col("surface_flags_base") & transition_mask) != 0)
    )

    is_hydrology = pl.col("material_base").is_not_null() & (
        (pl.col("hydro_role_base") != int(HydroRole.NONE))
        | (pl.col("material_base").is_in(list(WATER_HYDRO_MATERIALS)))
    )

    is_overlay_road_bridge = pl.col("material").is_in(list(ROAD_BRIDGE_MATERIALS))

    merged_cols = []
    for col in _OVERLAND_COLUMNS:
        if col in ("x", "y"):
            merged_cols.append(pl.col(col))
        elif col == "material":
            merged_cols.append(
                pl.when(is_transition)
                .then(pl.col("material_base"))
                .when(is_hydrology)
                .then(
                    pl.when(is_overlay_road_bridge)
                    .then(pl.col("material"))
                    .otherwise(pl.col("material_base"))
                )
                .otherwise(pl.col("material"))
                .alias("material")
            )
        elif col in ("hydro_role", "wetness"):
            merged_cols.append(
                pl.when(is_transition)
                .then(pl.col(f"{col}_base"))
                .when(is_hydrology)
                .then(pl.col(f"{col}_base"))
                .otherwise(pl.col(col))
                .alias(col)
            )
        elif col == "surface_flags":
            seasonal_mask = 1 << (int(SurfaceFlag.SEASONAL) - 1)
            merged_cols.append(
                pl.when(is_transition)
                .then(pl.col("surface_flags_base"))
                .when(is_hydrology)
                .then(
                    pl.when(is_overlay_road_bridge)
                    .then(
                        pl.col("surface_flags")
                        | (pl.col("surface_flags_base") & seasonal_mask)
                    )
                    .otherwise(pl.col("surface_flags_base"))
                )
                .otherwise(pl.col("surface_flags"))
                .alias("surface_flags")
            )
        elif col in ("biome", "elevation_band"):
            merged_cols.append(
                pl.when(is_transition)
                .then(pl.col(f"{col}_base"))
                .when(is_hydrology & ~is_overlay_road_bridge)
                .then(pl.col(f"{col}_base"))
                .otherwise(pl.col(col))
                .alias(col)
            )
        else:
            merged_cols.append(
                pl.when(is_transition)
                .then(pl.col(f"{col}_base"))
                .when(is_hydrology)
                .then(
                    pl.when(is_overlay_road_bridge)
                    .then(pl.col(col))
                    .otherwise(pl.col(f"{col}_base"))
                )
                .otherwise(pl.col(col))
                .alias(col)
            )

    resolved_overlay = joined.select(merged_cols)

    untouched = base.join(
        overlay.select("x", "y"),
        on=["x", "y"],
        how="anti",
    )
    columns = list(base.columns)
    return pl.concat(
        [untouched.select(columns), resolved_overlay.select(columns)]
    ).sort(["y", "x"])


def _connect_points_with_road(
    tiles_df: pl.DataFrame,
    start: tuple[int, int],
    goal: tuple[int, int],
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    """A* pathfinder connecting a settlement road endpoint to the overland road network."""
    import heapq
    from math import hypot

    weights = np.ones((height, width), dtype=np.float32)

    for row in tiles_df.select("x", "y", "material", "walkable").iter_rows(named=True):
        x, y = int(row["x"]), int(row["y"])
        if not (0 <= x < width and 0 <= y < height):
            continue
        mat = int(row["material"])
        walk = bool(row["walkable"])
        if not walk:
            weights[y, x] = 10.0
        elif mat in WATER_HYDRO_MATERIALS:
            weights[y, x] = 5.0

    frontier = []
    heapq.heappush(
        frontier, (hypot(start[0] - goal[0], start[1] - goal[1]), 0.0, start)
    )
    came_from = {start: None}
    cost_so_far = {start: 0.0}

    while frontier:
        _, current_cost, current = heapq.heappop(frontier)
        if current == goal:
            break
        cx, cy = current
        for dx, dy in [
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        ]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < width and 0 <= ny < height:
                step_mult = 1.414 if (dx != 0 and dy != 0) else 1.0
                new_cost = current_cost + weights[ny, nx] * step_mult
                next_node = (nx, ny)
                if new_cost < cost_so_far.get(next_node, float("inf")):
                    cost_so_far[next_node] = new_cost
                    priority = new_cost + hypot(nx - goal[0], ny - goal[1])
                    came_from[next_node] = current
                    heapq.heappush(frontier, (priority, new_cost, next_node))

    if goal not in came_from:
        return []

    path = []
    current = goal
    while current is not None:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path


def _merge_settlement_features(
    base_features: pl.DataFrame,
    settlement: SettlementBundle,
    *,
    ox: int,
    oy: int,
) -> pl.DataFrame:
    rows: list[dict[str, int | str]] = []
    for row in settlement.entrances_df.iter_rows(named=True):
        rows.append(
            {
                "x": int(row["x"]) + ox,
                "y": int(row["y"]) + oy,
                "feature_type": 0,
                "target_id": int(row["id"]),
                "tags": f"settlement;{row['kind']};{row['target']}",
                "evidence_tags": [int(EvidenceTag.RECENT_LOCAL_OCCUPATION)],
            }
        )
    if not rows:
        return base_features
    return pl.concat([base_features, pl.DataFrame(rows)], how="vertical")
