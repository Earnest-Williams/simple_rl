from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import polars as pl

from settlegen import Settlement
from worldgen.settlements.config import RegionConstraints
from worldgen.settlements.entrances import extract_entrances
from worldgen.settlements.translate import terrain_to_shaped_columns


@dataclass(frozen=True, slots=True)
class SettlementBundle:
    settlement: Settlement
    map_df: pl.DataFrame
    buildings_df: pl.DataFrame
    districts_df: pl.DataFrame
    roads_df: pl.DataFrame
    entrances_df: pl.DataFrame
    metadata: dict[str, Any]


def to_simple_rl_bundle(
    settlement: Settlement,
    *,
    region: RegionConstraints | None = None,
    origin: tuple[int, int] = (0, 0),
) -> SettlementBundle:
    combined = settlement.combined_grid()
    shaped = terrain_to_shaped_columns(combined)
    yy, xx = np.indices(combined.shape)
    ox, oy = origin

    map_df = pl.DataFrame(
        {
            "x": (xx.reshape(-1) + ox).astype(np.float32),
            "y": (yy.reshape(-1) + oy).astype(np.float32),
            "floor_depth": np.zeros(combined.size, dtype=np.float32),
            "height": np.ones(combined.size, dtype=np.float32),
            "ceiling_depth": -np.ones(combined.size, dtype=np.float32),
            "material_id": shaped["material_id"].reshape(-1),
            "walkable": shaped["walkable"].reshape(-1),
            "chamber_id": np.ones(combined.size, dtype=np.int32),
            "open_above": np.ones(combined.size, dtype=bool),
            "features": np.zeros(combined.size, dtype=np.uint32),
            "tags": np.zeros(combined.size, dtype=np.uint32),
            "stratum_index": np.zeros(combined.size, dtype=np.uint8),
            "settlement_tile": shaped["settlement_tile"].reshape(-1),
            "terrain_code": settlement.terrain.reshape(-1).astype(np.uint16),
            "overlay_code": settlement.overlay.reshape(-1).astype(np.uint16),
            "transparent": shaped["transparent"].reshape(-1),
        }
    )

    entrances = extract_entrances(settlement)
    entrance_rows = [asdict(entrance) for entrance in entrances]
    if region is not None:
        for x, y in region.cave_entrances:
            entrance_rows.append(
                {
                    "id": len(entrance_rows) + 1,
                    "x": int(x),
                    "y": int(y),
                    "kind": "cave",
                    "source_building_id": None,
                    "target": "Dungeon",
                }
            )
    metadata: dict[str, Any] = {
        "name": settlement.name,
        "seed": settlement.seed,
        "kind": settlement.config.kind.value,
        "population": settlement.population,
        "width": settlement.width,
        "height": settlement.height,
        "tile_summary": settlement.tile_summary(),
        "facility_counts": settlement.facility_counts(),
        "region": _region_payload(region),
    }

    return SettlementBundle(
        settlement=settlement,
        map_df=map_df,
        buildings_df=_buildings_df(settlement),
        districts_df=_districts_df(settlement),
        roads_df=_roads_df(settlement),
        entrances_df=_entrances_df(entrance_rows),
        metadata=metadata,
    )


def _buildings_df(settlement: Settlement) -> pl.DataFrame:
    rows = list(settlement.iter_building_records())
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).with_columns(
        pl.lit(settlement.name).alias("settlement_name")
    )


def _districts_df(settlement: Settlement) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for district in settlement.districts:
        rows.append(
            {
                "id": district.id,
                "kind": district.kind,
                "center_x": district.center[0],
                "center_y": district.center[1],
                "radius": district.radius,
                "wealth": district.wealth,
                "tags": ";".join(district.tags),
            }
        )
    return pl.DataFrame(rows)


def _roads_df(settlement: Settlement) -> pl.DataFrame:
    rows: list[dict[str, Any]] = []
    for road in settlement.roads:
        rows.append(
            {
                "id": road.id,
                "kind": road.kind,
                "point_count": len(road.points),
                "points": ";".join(f"{x},{y}" for x, y in road.points),
                "tags": ";".join(road.tags),
            }
        )
    return pl.DataFrame(rows)


def _entrances_df(rows: list[dict[str, Any]]) -> pl.DataFrame:
    schema = {
        "id": pl.Int64,
        "x": pl.Int64,
        "y": pl.Int64,
        "kind": pl.Utf8,
        "source_building_id": pl.Int64,
        "target": pl.Utf8,
    }
    if not rows:
        return pl.DataFrame(schema=schema)
    return pl.DataFrame(rows, schema=schema)


def _region_payload(region: RegionConstraints | None) -> dict[str, Any]:
    if region is None:
        return {}
    return {
        "coastline": region.coastline,
        "river_mouth": region.river_mouth,
        "road_endpoints": region.road_endpoints,
        "cave_entrances": region.cave_entrances,
        "biome": region.biome,
        "faction": region.faction,
        "trade_route_importance": region.trade_route_importance,
        "distance_from_starting_port": region.distance_from_starting_port,
    }
