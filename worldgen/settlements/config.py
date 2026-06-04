from __future__ import annotations

from dataclasses import dataclass

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
        ),
        name=name,
        tags=("starting_port",),
        allow_subterranean=True,
    )
