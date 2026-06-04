from __future__ import annotations

import polars as pl

from common.constants import Material
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.schema import HydroRole, HydroState, OverlandBundle, Wetness


def apply_hydrology_state(bundle: OverlandBundle, state: HydroState) -> OverlandBundle:
    tiles = bundle.tiles_df
    hydro = bundle.hydrology_df.with_columns(pl.lit(state.name.lower()).alias("seasonal_state"))

    role = pl.col("hydro_role")
    material = pl.col("material")
    is_sinking_lake = role == int(HydroRole.SINKING_LAKE)
    is_estavelle = role == int(HydroRole.ESTAVELLE)
    is_ponor = role == int(HydroRole.PONOR)
    is_fish_trail = material == int(Material.FISH_TRAIL)

    tiles = tiles.with_columns(
        _material_expr(state, is_sinking_lake, is_estavelle, is_ponor, is_fish_trail).alias(
            "material"
        ),
        _wetness_expr(state, is_sinking_lake, is_estavelle, is_ponor, is_fish_trail).alias(
            "wetness"
        ),
    ).with_columns(
        (pl.col("material").is_not_null() & pl.col("wetness").is_not_null()).alias(
            "walkable"
        )
    )
    # Keep gameplay truth conservative after the state transform.
    tiles = tiles.with_columns(
        pl.when(pl.col("wetness") == int(Wetness.DEEP_FLOODED))
        .then(False)
        .when(pl.col("material").is_in([int(Material.DEEP_WATER), int(Material.LIMESTONE_CLIFF)]))
        .then(False)
        .otherwise(True)
        .alias("walkable")
    )
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
