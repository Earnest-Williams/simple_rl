from __future__ import annotations

from game.world.game_map import GameMap
from game.world.overland_traversal import human_on_foot_can_enter_map
from utils.game_rng import GameRNG
from worldgen.overland.convert import overland_to_game_map
from worldgen.overland.generator import generate_overland_region
from worldgen.overland.hydrology import apply_hydrology_state
from worldgen.overland.schema import HydroState
from worldgen.overland.settlement_merge import merge_settlement_into_overland
from worldgen.settlements import generate_settlement, starting_port_from_overland


def load_starting_overland_game_map(
    *,
    seed: int,
    width: int,
    height: int,
    hydro_state: HydroState | None = None,
) -> tuple[GameMap, tuple[int, int]]:
    overland = generate_overland_region(
        seed=seed,
        width=width,
        height=height,
        profile="KARST_TO_VOLCANIC_MOUNTAIN",
    )

    port_width = min(80, max(56, width - 16))
    port_height = min(56, max(40, height - 16))

    config, region, origin = starting_port_from_overland(
        overland,
        width=port_width,
        height=port_height,
        population_target=1400,
    )

    settlement = generate_settlement(
        config,
        rng=GameRNG(seed=seed),
        region=region,
    )

    merged = merge_settlement_into_overland(
        overland,
        settlement,
        origin=origin,
    )

    if hydro_state is not None:
        merged = apply_hydrology_state(merged, hydro_state)

    converted = overland_to_game_map(merged, with_metadata=True)
    if not isinstance(converted, tuple):
        raise TypeError(
            "Expected overland_to_game_map(..., with_metadata=True) to return metadata"
        )

    game_map, _ = converted
    spawn = choose_starting_overland_spawn(game_map)

    return game_map, spawn


def choose_starting_overland_spawn(game_map: GameMap) -> tuple[int, int]:
    metadata = game_map.overland_metadata
    if metadata is None:
        return _first_walkable_tile(game_map)

    contract = metadata.starting_contract

    explicit_spawn = contract.get("player_spawn")
    if _is_point(explicit_spawn):
        x, y = int(explicit_spawn[0]), int(explicit_spawn[1])
        if human_on_foot_can_enter_map(game_map, x, y):
            return x, y

    harbor = contract.get("harbor")
    if isinstance(harbor, dict):
        point = harbor.get("point")
        if _is_point(point):
            hx, hy = int(point[0]), int(point[1])
            spawn = _nearest_human_walkable_tile(game_map, hx, hy, radius=16)
            if spawn is not None:
                return spawn

    return _first_human_walkable_tile(game_map)


def _is_point(value: object) -> bool:
    return (
        isinstance(value, list | tuple)
        and len(value) == 2
        and isinstance(value[0], int | float)
        and isinstance(value[1], int | float)
    )


def _nearest_human_walkable_tile(
    game_map: GameMap,
    center_x: int,
    center_y: int,
    *,
    radius: int,
) -> tuple[int, int] | None:
    best: tuple[int, int] | None = None
    best_dist2: int | None = None

    for y in range(
        max(0, center_y - radius), min(game_map.height, center_y + radius + 1)
    ):
        for x in range(
            max(0, center_x - radius), min(game_map.width, center_x + radius + 1)
        ):
            if not human_on_foot_can_enter_map(game_map, x, y):
                continue
            dist2 = (x - center_x) * (x - center_x) + (y - center_y) * (y - center_y)
            if best_dist2 is None or dist2 < best_dist2:
                best = (x, y)
                best_dist2 = dist2

    return best


def _first_human_walkable_tile(game_map: GameMap) -> tuple[int, int]:
    for y in range(game_map.height):
        for x in range(game_map.width):
            if human_on_foot_can_enter_map(game_map, x, y):
                return x, y
    raise ValueError("No human-walkable tile found in starting overland map")


def _first_walkable_tile(game_map: GameMap) -> tuple[int, int]:
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.is_walkable(x, y):
                return x, y
    raise ValueError("No walkable tile found in map")
