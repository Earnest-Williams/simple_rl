from __future__ import annotations

from math import hypot

import polars as pl

from common.constants import Material
from worldgen.overland.schema import FeatureType, HydroRole, OverlandBundle


def find_feature(
    bundle: OverlandBundle,
    feature_type: FeatureType,
) -> dict[str, object] | None:
    rows = (
        bundle.features_df.filter(pl.col("feature_type") == int(feature_type))
        .head(1)
        .to_dicts()
    )
    return rows[0] if rows else None


def find_nearest_feature(
    bundle: OverlandBundle,
    origin: tuple[int, int],
    feature_type: FeatureType,
) -> dict[str, object] | None:
    rows = bundle.features_df.filter(
        pl.col("feature_type") == int(feature_type)
    ).to_dicts()
    if not rows:
        return None
    ox, oy = origin
    return min(rows, key=lambda row: hypot(int(row["x"]) - ox, int(row["y"]) - oy))


def find_tiles_by_material(bundle: OverlandBundle, material: Material) -> pl.DataFrame:
    return bundle.tiles_df.filter(pl.col("material") == int(material))


def find_tiles_by_hydro_role(
    bundle: OverlandBundle,
    hydro_role: HydroRole,
) -> pl.DataFrame:
    return bundle.tiles_df.filter(pl.col("hydro_role") == int(hydro_role))


def first_tile_by_material(
    bundle: OverlandBundle,
    material: Material,
) -> tuple[int, int] | None:
    rows = find_tiles_by_material(bundle, material).head(1).to_dicts()
    if not rows:
        return None
    return int(rows[0]["x"]), int(rows[0]["y"])


def first_tile_by_hydro_role(
    bundle: OverlandBundle,
    hydro_role: HydroRole,
) -> tuple[int, int] | None:
    rows = find_tiles_by_hydro_role(bundle, hydro_role).head(1).to_dicts()
    if not rows:
        return None
    return int(rows[0]["x"]), int(rows[0]["y"])
