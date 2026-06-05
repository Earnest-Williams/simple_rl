from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from worldgen.overland.affordances import generate_affordances
from worldgen.overland.schema import OverlandBundle, RouteSegmentState

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


def merge_settlement_into_overland(
    overland: OverlandBundle,
    settlement: SettlementBundle,
    *,
    origin: tuple[int, int],
) -> OverlandBundle:
    """Overlay settlement-produced surfaces into an overland bundle."""

    ox, oy = origin
    settlement_tiles = _settlement_overland_tiles(settlement, ox=ox, oy=oy)
    merged_tiles = _replace_tiles(
        base=overland.tiles_df,
        overlay=settlement_tiles,
    )
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
    untouched = base.join(
        overlay.select("x", "y"),
        on=["x", "y"],
        how="anti",
    )
    columns = list(base.columns)
    return pl.concat([untouched.select(columns), overlay.select(columns)]).sort(
        ["y", "x"]
    )


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
            }
        )
    if not rows:
        return base_features
    return pl.concat([base_features, pl.DataFrame(rows)], how="vertical")
