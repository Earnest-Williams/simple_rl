from __future__ import annotations

import polars as pl

from common.constants import Material
from worldgen.overland.schema import Affordance, HydroRole, OverlandBundle, Wetness


def generate_affordances(bundle: OverlandBundle) -> pl.DataFrame:
    rows: list[dict[str, int | float]] = []
    for row in bundle.tiles_df.iter_rows(named=True):
        material = int(row["material"])
        hydro_role = int(row["hydro_role"])
        wetness = int(row["wetness"])
        x = int(row["x"])
        y = int(row["y"])
        rows.extend(_affordances_for_tile(x, y, material, hydro_role, wetness))
    return pl.DataFrame(rows) if rows else pl.DataFrame(_affordance_schema())


def _affordances_for_tile(
    x: int,
    y: int,
    material: int,
    hydro_role: int,
    wetness: int,
) -> list[dict[str, int | float]]:
    rows: list[dict[str, int | float]] = []

    def add(affordance: Affordance, strength: float) -> None:
        rows.append(
            {
                "x": x,
                "y": y,
                "affordance": int(affordance),
                "strength": float(strength),
            }
        )

    if material in {
        int(Material.FISH_TRAIL),
        int(Material.MUDFLAT),
        int(Material.SHALLOW_WATER),
    }:
        add(Affordance.FISH_MIGRATION, 0.8)
    if material in {
        int(Material.MUDFLAT),
        int(Material.MUD),
        int(Material.SHALLOW_WATER),
    }:
        add(Affordance.MUDFLAT_SUNNING, 0.55)
    if material in {int(Material.DEEP_MUD), int(Material.MUDFLAT), int(Material.CLAY)}:
        add(Affordance.BURROWING_MUD, 0.65)
    if hydro_role in {
        int(HydroRole.TEMPORARY_POOL),
        int(HydroRole.PERMANENT_POOL),
        int(HydroRole.SINKING_LAKE),
    }:
        add(Affordance.MUSTELID_HUNTING, 0.45)
    if material in {
        int(Material.SPRING_WATER),
        int(Material.UNDERGROUND_WATER),
        int(Material.CAVE_MOUTH),
    }:
        add(Affordance.OCTOPUS_REFUGE, 0.35)
    if hydro_role == int(HydroRole.SPRING):
        add(Affordance.SPRING_REFUGE, 1.0)
    if material in {int(Material.CAVE_MOUTH), int(Material.UNDERGROUND_WATER)}:
        add(Affordance.CAVE_REFUGE, 0.9)
    if wetness >= int(Wetness.WET) and material != int(Material.DEEP_WATER):
        add(Affordance.AMPHIBIOUS_CORRIDOR, 0.5)
    return rows


def _affordance_schema() -> dict[str, pl.DataType]:
    return {
        "x": pl.Int64,
        "y": pl.Int64,
        "affordance": pl.Int64,
        "strength": pl.Float64,
    }
