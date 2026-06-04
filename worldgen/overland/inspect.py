from __future__ import annotations

from typing import Literal

import polars as pl

from common.constants import Material
from worldgen.overland.schema import Biome, HydroRole, Wetness

OverlandInspectView = Literal["material", "biome", "hydro", "wetness", "traversal"]


def render_overland_ascii(
    tiles_df: pl.DataFrame,
    *,
    view: OverlandInspectView = "material",
) -> str:
    width = int(tiles_df.get_column("x").max()) + 1
    height = int(tiles_df.get_column("y").max()) + 1
    grid = [[" " for _ in range(width)] for _ in range(height)]
    for row in tiles_df.iter_rows(named=True):
        x = int(row["x"])
        y = int(row["y"])
        grid[y][x] = _glyph(row, view)
    return "\n".join("".join(row) for row in grid)


def _glyph(row: dict[str, object], view: OverlandInspectView) -> str:
    if view == "biome":
        return _biome_glyph(Biome(int(row["biome"])))
    if view == "hydro":
        return _hydro_glyph(HydroRole(int(row["hydro_role"])))
    if view == "wetness":
        return _wetness_glyph(Wetness(int(row["wetness"])))
    if view == "traversal":
        if not bool(row["walkable"]):
            return "#"
        if bool(row["blocks_sight"]):
            return "%"
        return "."
    return _material_glyph(Material(int(row["material"])))


def _biome_glyph(biome: Biome) -> str:
    return {
        Biome.COASTAL_RAIN_FOREST: "~",
        Biome.KARST_WET_FOREST: "K",
        Biome.SINKING_LAKE_BASIN: "S",
        Biome.ESTAVELLE_MARSH: "E",
        Biome.SPRING_GARDEN: "G",
        Biome.LIMESTONE_GORGE: "L",
        Biome.FOOTHILL_HARDWOOD_FOREST: "F",
        Biome.VOLCANIC_CLOUD_FOREST: "V",
        Biome.LAVA_TUBE_FOREST: "T",
        Biome.BASALT_BARRENS: "B",
        Biome.HIGHLAND_PEAT_MOOR: "P",
        Biome.SUBALPINE_HEATH: "H",
    }[biome]


def _hydro_glyph(role: HydroRole) -> str:
    return {
        HydroRole.NONE: ".",
        HydroRole.SURFACE_CHANNEL: "=",
        HydroRole.UNDERGROUND_CHANNEL: "_",
        HydroRole.SPRING: "^",
        HydroRole.SEEP: ",",
        HydroRole.PONOR: "v",
        HydroRole.ESTAVELLE: "e",
        HydroRole.TEMPORARY_POOL: "o",
        HydroRole.PERMANENT_POOL: "O",
        HydroRole.SINKING_LAKE: "s",
        HydroRole.KARST_WINDOW: "k",
    }[role]


def _wetness_glyph(wetness: Wetness) -> str:
    return {
        Wetness.DRY: ".",
        Wetness.DAMP: ",",
        Wetness.WET: ";",
        Wetness.SATURATED: "s",
        Wetness.SHALLOW_FLOODED: "w",
        Wetness.DEEP_FLOODED: "W",
    }[wetness]


def _material_glyph(material: Material) -> str:
    if material in {Material.SHALLOW_WATER, Material.DEEP_WATER, Material.SPRING_WATER}:
        return "~"
    if material in {Material.MUDFLAT, Material.MUD, Material.DEEP_MUD, Material.CRACKED_MUD}:
        return "m"
    if material in {Material.LIMESTONE_CLIFF, Material.BASALT_CLIFF}:
        return "#"
    if material in {Material.CAVE_MOUTH, Material.PONOR}:
        return "v"
    if material in {Material.LAVA_TUBE_SKYLIGHT, Material.COLLAPSED_LAVA_TUBE}:
        return "*"
    if material in {Material.BASALT, Material.BASALT_PAVEMENT}:
        return "b"
    if material in {Material.PEAT_BOG, Material.BOG_POOL, Material.SPHAGNUM}:
        return "p"
    if material in {Material.FISH_TRAIL, Material.TRAIL, Material.TRACK}:
        return ":"
    if material in {Material.FOREST_FLOOR, Material.FERN_UNDERSTORY, Material.MOSS}:
        return "f"
    return "."
