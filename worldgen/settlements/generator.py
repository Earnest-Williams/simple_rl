from __future__ import annotations

from settlegen import Settlement, SettlementConfig, SettlementGenerator
from utils.game_rng import GameRNG
from worldgen.settlements.config import RegionConstraints
from worldgen.settlements.export import SettlementBundle, to_simple_rl_bundle


def generate_settlement(
    config: SettlementConfig,
    *,
    rng: GameRNG,
    region: RegionConstraints | None = None,
    origin: tuple[int, int] = (0, 0),
) -> SettlementBundle:
    """Generate a settlement through GameRNG and return simple_rl-native outputs."""

    seed = rng.get_int(0, (2**31) - 1)
    settlement: Settlement = SettlementGenerator(seed=seed).generate(
        _apply_region_constraints(config, region)
    )
    return to_simple_rl_bundle(settlement, region=region, origin=origin)


def _apply_region_constraints(
    config: SettlementConfig,
    region: RegionConstraints | None,
) -> SettlementConfig:
    if region is None:
        return config
    tags = tuple(dict.fromkeys((*config.tags, *(_region_tags(region)))))
    return SettlementConfig(
        kind=config.kind,
        width=config.width,
        height=config.height,
        population_target=config.population_target,
        population=config.population,
        population_mode=config.population_mode,
        state=config.state,
        condition=config.condition,
        magic=config.magic,
        material=config.material,
        layout=config.layout,
        road_style=config.road_style,
        defense=config.defense,
        wealth=config.wealth,
        terrain=config.terrain,
        terrain_features=config.terrain_features,
        facilities=config.facilities,
        required_facilities=config.required_facilities,
        forbidden_facilities=config.forbidden_facilities,
        banned_facilities=config.banned_facilities,
        district_count=config.district_count,
        building_density=config.building_density,
        farmland_density=config.farmland_density,
        water_level=config.water_level,
        forest_density=config.forest_density,
        ruin_rate=config.ruin_rate,
        ghost_rate=config.ghost_rate,
        road_width=config.road_width,
        wall_margin=config.wall_margin,
        allow_bridges=config.allow_bridges,
        allow_subterranean=config.allow_subterranean
        or bool(region.cave_entrances),
        allow_secret_features=config.allow_secret_features,
        name=config.name,
        tags=tags,
        walls=config.walls,
        palisade=config.palisade,
        moat=config.moat,
        dyke=config.dyke,
    )


def _region_tags(region: RegionConstraints) -> tuple[str, ...]:
    tags: list[str] = []
    if region.coastline:
        tags.append(f"coastline:{region.coastline}")
    if region.biome:
        tags.append(f"biome:{region.biome}")
    if region.faction:
        tags.append(f"faction:{region.faction}")
    if region.trade_route_importance > 0:
        tags.append("trade_route")
    if region.distance_from_starting_port > 0:
        tags.append(f"distance_from_starting_port:{region.distance_from_starting_port}")
    return tuple(tags)
