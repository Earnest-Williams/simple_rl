from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import polars as pl

from settlegen import (
    BuildingMaterial,
    DefenseStyle,
    Facility,
    LayoutStyle,
    MagicMode,
    SettlementConfig,
    SettlementKind,
    SettlementState,
    TerrainFeature,
    Wealth,
)

if TYPE_CHECKING:
    from worldgen.overland.schema import OverlandBundle


@dataclass(frozen=True, slots=True)
class RegionConstraints:
    """Upstream worldgen context used to keep settlements connected."""

    coastline: str | None = None
    river_mouth: tuple[int, int] | None = None
    road_endpoints: tuple[tuple[int, int], ...] = ()
    cave_entrances: tuple[tuple[int, int], ...] = ()
    biome: str | None = None
    faction: str | None = None
    trade_route_importance: float = 0.0
    distance_from_starting_port: int = 0


def starting_port_config(
    *,
    width: int = 160,
    height: int = 112,
    population_target: int = 2200,
    name: str | None = None,
) -> SettlementConfig:
    """Return the default simple_rl starting port-town settlement config."""

    return SettlementConfig(
        kind=SettlementKind.PORT_TOWN,
        width=width,
        height=height,
        population_target=population_target,
        state=SettlementState.THRIVING,
        magic=MagicMode.LOW_MAGIC,
        material=BuildingMaterial.MIXED,
        layout=LayoutStyle.COASTAL,
        defense=DefenseStyle.PALISADE,
        wealth=Wealth.MODEST,
        terrain=(
            TerrainFeature.BAY,
            TerrainFeature.RIVER,
            TerrainFeature.FERTILE_VALLEY,
        ),
        facilities=(
            Facility.DOCKS,
            Facility.WHARF,
            Facility.FISHERY,
            Facility.CUSTOMS_HOUSE,
            Facility.MARKET,
            Facility.WAREHOUSE,
            Facility.LIGHTHOUSE,
            Facility.INN,
            Facility.BLACKSMITH,
            Facility.CEMETERY,
            Facility.FIELD,
        ),
        name=name,
        tags=("starting_port",),
        allow_subterranean=True,
    )


def starting_port_from_overland(
    overland: OverlandBundle,
    *,
    width: int = 80,
    height: int = 56,
    population_target: int = 1400,
) -> tuple[SettlementConfig, RegionConstraints, tuple[int, int]]:
    """Derive a deterministic starting-port request from an overland region."""

    world_width = int(overland.metadata["width"])
    origin = (
        max(0, min(world_width - width, world_width // 2 - width // 2)),
        1,
    )
    river_mouth = (origin[0] + width // 2, origin[1] + height - 1)
    cave_rows = overland.features_df.filter(pl.col("tags").str.contains("cave"))
    cave_entrances: tuple[tuple[int, int], ...] = ()
    if not cave_rows.is_empty():
        cave_entrances = (
            (
                int(cave_rows.get_column("x")[0]) - origin[0],
                int(cave_rows.get_column("y")[0]) - origin[1],
            ),
        )
    region = RegionConstraints(
        coastline="south",
        river_mouth=(river_mouth[0] - origin[0], river_mouth[1] - origin[1]),
        road_endpoints=((width // 2, -origin[1]),),
        cave_entrances=cave_entrances,
        biome="coastal_rain_forest",
        faction="port_authority",
        trade_route_importance=1.0,
    )
    return (
        starting_port_config(
            width=width,
            height=height,
            population_target=population_target,
        ).normalized(),
        region,
        origin,
    )
