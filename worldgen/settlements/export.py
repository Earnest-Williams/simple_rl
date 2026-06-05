from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import polars as pl

from settlegen import Settlement
from worldgen.settlements.config import RegionConstraints
from worldgen.settlements.entrances import extract_entrances
from worldgen.settlements.translate import (
    terrain_to_overland_columns,
    terrain_to_shaped_columns,
)


@dataclass(frozen=True, slots=True)
class SettlementBundle:
    settlement: Settlement
    map_df: pl.DataFrame
    buildings_df: pl.DataFrame
    districts_df: pl.DataFrame
    roads_df: pl.DataFrame
    entrances_df: pl.DataFrame
    metadata: dict[str, object]


_BUNDLE_FILES: dict[str, str] = {
    "map_df": "settlement_map.arrow",
    "buildings_df": "settlement_buildings.arrow",
    "districts_df": "settlement_districts.arrow",
    "roads_df": "settlement_roads.arrow",
    "entrances_df": "settlement_entrances.arrow",
}


def to_simple_rl_bundle(
    settlement: Settlement,
    *,
    region: RegionConstraints | None = None,
    origin: tuple[int, int] = (0, 0),
) -> SettlementBundle:
    combined = settlement.combined_grid()
    shaped = terrain_to_shaped_columns(combined)
    overland = terrain_to_overland_columns(combined)
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
            "material": overland["material"].reshape(-1),
            "biome": overland["biome"].reshape(-1),
            "elevation_band": overland["elevation_band"].reshape(-1),
            "hydro_role": overland["hydro_role"].reshape(-1),
            "wetness": overland["wetness"].reshape(-1),
            "substrate": overland["substrate"].reshape(-1),
            "blocks_sight": overland["blocks_sight"].reshape(-1),
            "movement_cost": overland["movement_cost"].reshape(-1),
            "traversal_class": overland["traversal_class"].reshape(-1),
            "surface_flags": overland["surface_flags"].reshape(-1),
        }
    )

    entrances = extract_entrances(settlement)
    entrance_rows: list[dict[str, object]] = [
        asdict(entrance) for entrance in entrances
    ]
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
    metadata: dict[str, object] = {
        "name": settlement.name,
        "seed": settlement.seed,
        "kind": (
            settlement.config.kind.value
            if hasattr(settlement.config.kind, "value")
            else str(settlement.config.kind)
        ),
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


def write_settlement_bundle(
    bundle: SettlementBundle,
    out_dir: Path,
    *,
    overwrite: bool = False,
) -> dict[str, Path]:
    """Write a generated settlement bundle as headless inspectable artifacts."""

    if out_dir.exists() and not out_dir.is_dir():
        raise NotADirectoryError(f"{out_dir} is not a directory")
    out_dir.mkdir(parents=True, exist_ok=True)

    paths: dict[str, Path] = {}
    for attr_name, filename in _BUNDLE_FILES.items():
        path = out_dir / filename
        _check_writable(path, overwrite=overwrite)
        df = getattr(bundle, attr_name)
        df.write_ipc(path)
        paths[attr_name] = path

    metadata_path = out_dir / "settlement_metadata.json"
    _check_writable(metadata_path, overwrite=overwrite)
    payload = {
        **bundle.metadata,
        "artifacts": {name: path.name for name, path in paths.items()},
    }
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
    paths["metadata"] = metadata_path
    return paths


def _buildings_df(settlement: Settlement) -> pl.DataFrame:
    rows = list(settlement.iter_building_records())
    if not rows:
        return pl.DataFrame()
    return pl.DataFrame(rows).with_columns(
        pl.lit(settlement.name).alias("settlement_name")
    )


def _districts_df(settlement: Settlement) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
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
    rows: list[dict[str, object]] = []
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


def _entrances_df(rows: list[dict[str, object]]) -> pl.DataFrame:
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


def _region_payload(region: RegionConstraints | None) -> dict[str, object]:
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


def _check_writable(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"Refusing to overwrite existing artifact: {path}")
