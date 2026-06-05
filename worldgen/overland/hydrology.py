from __future__ import annotations

import polars as pl

from common.constants import Material
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.rules import (
    derive_blocks_sight,
    derive_movement_cost,
    derive_traversal_class,
    derive_walkable,
)
from worldgen.overland.schema import HydroRole, HydroState, OverlandBundle, Wetness


def apply_hydrology_state(bundle: OverlandBundle, state: HydroState) -> OverlandBundle:
    tiles = bundle.tiles_df
    hydro = bundle.hydrology_df.with_columns(
        pl.lit(state.name.lower()).alias("seasonal_state")
    )

    role = pl.col("hydro_role")
    material = pl.col("material")
    is_sinking_lake = role == int(HydroRole.SINKING_LAKE)
    is_estavelle = role == int(HydroRole.ESTAVELLE)
    is_ponor = role == int(HydroRole.PONOR)
    is_fish_trail = material == int(Material.FISH_TRAIL)

    tiles = tiles.with_columns(
        _material_expr(
            state, is_sinking_lake, is_estavelle, is_ponor, is_fish_trail
        ).alias("material"),
        _wetness_expr(
            state, is_sinking_lake, is_estavelle, is_ponor, is_fish_trail
        ).alias("wetness"),
    )
    tiles = _recompute_gameplay_columns(tiles)
    transformed = OverlandBundle(
        tiles_df=tiles,
        hydrology_df=hydro,
        features_df=bundle.features_df,
        affordances_df=pl.DataFrame(),
        metadata={**bundle.metadata, "hydro_state": state.name.lower()},
    )
    return OverlandBundle(
        tiles_df=tiles,
        hydrology_df=hydro,
        features_df=bundle.features_df,
        affordances_df=generate_affordances(transformed),
        metadata=transformed.metadata,
    )


def _material_expr(
    state: HydroState,
    is_sinking_lake: pl.Expr,
    is_estavelle: pl.Expr,
    is_ponor: pl.Expr,
    is_fish_trail: pl.Expr,
) -> pl.Expr:
    if state == HydroState.WET_SEASON:
        return (
            pl.when(is_sinking_lake)
            .then(int(Material.SHALLOW_WATER))
            .when(is_estavelle)
            .then(int(Material.SPRING_WATER))
            .when(is_ponor)
            .then(int(Material.SINKING_WATER))
            .when(is_fish_trail)
            .then(int(Material.SHALLOW_WATER))
            .otherwise(pl.col("material"))
        )
    if state == HydroState.DRAINING:
        return (
            pl.when(is_sinking_lake | is_ponor)
            .then(int(Material.SINKING_WATER))
            .when(is_estavelle)
            .then(int(Material.ESTAVELLE_WATER))
            .when(is_fish_trail)
            .then(int(Material.MUDFLAT))
            .otherwise(pl.col("material"))
        )
    if state == HydroState.MUD_SEASON:
        return (
            pl.when(is_sinking_lake)
            .then(int(Material.MUDFLAT))
            .when(is_estavelle)
            .then(int(Material.MUD))
            .when(is_ponor)
            .then(int(Material.PONOR))
            .when(is_fish_trail)
            .then(int(Material.FISH_TRAIL))
            .otherwise(pl.col("material"))
        )
    return (
        pl.when(is_sinking_lake)
        .then(int(Material.CRACKED_MUD))
        .when(is_estavelle | is_ponor)
        .then(int(Material.CAVE_MOUTH))
        .when(is_fish_trail)
        .then(int(Material.FISH_TRAIL))
        .otherwise(pl.col("material"))
    )


def _wetness_expr(
    state: HydroState,
    is_sinking_lake: pl.Expr,
    is_estavelle: pl.Expr,
    is_ponor: pl.Expr,
    is_fish_trail: pl.Expr,
) -> pl.Expr:
    if state == HydroState.WET_SEASON:
        return (
            pl.when(is_sinking_lake)
            .then(int(Wetness.DEEP_FLOODED))
            .when(is_estavelle | is_ponor | is_fish_trail)
            .then(int(Wetness.SHALLOW_FLOODED))
            .otherwise(pl.col("wetness"))
        )
    if state == HydroState.DRAINING:
        return (
            pl.when(is_sinking_lake | is_estavelle | is_ponor)
            .then(int(Wetness.WET))
            .when(is_fish_trail)
            .then(int(Wetness.SATURATED))
            .otherwise(pl.col("wetness"))
        )
    if state == HydroState.MUD_SEASON:
        return (
            pl.when(is_sinking_lake | is_estavelle | is_ponor | is_fish_trail)
            .then(int(Wetness.WET))
            .otherwise(pl.col("wetness"))
        )
    return (
        pl.when(is_sinking_lake | is_estavelle | is_ponor | is_fish_trail)
        .then(int(Wetness.DRY))
        .otherwise(pl.col("wetness"))
    )


def _recompute_gameplay_columns(tiles: pl.DataFrame) -> pl.DataFrame:
    rows = tiles.to_dicts()
    for row in rows:
        material = Material(int(row["material"]))
        wetness = Wetness(int(row["wetness"]))
        flags = int(row["surface_flags"])
        row["walkable"] = derive_walkable(material, wetness, flags)
        row["blocks_sight"] = derive_blocks_sight(material, flags)
        row["movement_cost"] = derive_movement_cost(material, wetness, flags)
        row["traversal_class"] = int(derive_traversal_class(material, wetness, flags))
    return pl.DataFrame(rows, schema=tiles.schema)
