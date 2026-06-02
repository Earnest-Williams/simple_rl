"""Lightweight perception helpers for AI modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import polars as pl
import structlog
from numpy.typing import NDArray

from common.constants import FeatureType
from game.perception import apply_radius_perception
from game.world.game_map import GameMap
from game.world.los import line_of_sight
from pathfinding.perception_systems import (
    MAX_FLOWS,
    FlowType,
    monster_perception,
    update_noise,
    update_smell,
)

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from polars import series

    from game.game_state import GameState

log = structlog.get_logger()


def _terrain_map_for_game_map(game_map: GameMap) -> NDArray[np.int32]:
    """Return a production ``FeatureType`` terrain map for perception fields."""
    feature_map = getattr(game_map, "feature_map", None)
    if isinstance(feature_map, np.ndarray):
        return feature_map.astype(np.int32, copy=False)

    terrain_map = np.full(
        game_map.transparent.shape, int(FeatureType.WALL), dtype=np.int32
    )
    terrain_map[game_map.transparent] = int(FeatureType.FLOOR)
    return terrain_map


def _perception_arrays(
    game_state: GameState, height: int, width: int
) -> tuple[NDArray[np.int32], NDArray[np.int32], NDArray[np.int32], int]:
    """Return persistent production perception arrays for ``game_state``."""
    expected_cost_shape = (MAX_FLOWS, height, width)
    if game_state.perception_cave_cost.shape != expected_cost_shape:
        infinity = np.iinfo(np.int32).max // 2
        game_state.perception_cave_cost = np.full(
            expected_cost_shape, infinity, dtype=np.int32
        )

    expected_centers_shape = (MAX_FLOWS, 2)
    if game_state.perception_flow_centers.shape != expected_centers_shape:
        game_state.perception_flow_centers = np.zeros(
            expected_centers_shape, dtype=np.int32
        )

    expected_scent_shape = (height, width)
    if game_state.perception_cave_when.shape != expected_scent_shape:
        game_state.perception_cave_when = np.zeros(expected_scent_shape, dtype=np.int32)

    return (
        game_state.perception_cave_cost,
        game_state.perception_flow_centers,
        game_state.perception_cave_when,
        game_state.perception_global_scent_when,
    )


def _alerted_monster_ids(
    game_state: GameState,
    cave_cost: NDArray[np.int32],
    flow_centers: NDArray[np.int32],
) -> list[int]:
    """Run production monster perception when registry rows expose positions."""
    entities_df = getattr(game_state.entity_registry, "entities_df", None)
    if not isinstance(entities_df, pl.DataFrame) or entities_df.is_empty():
        return []

    required_columns = {"entity_id", "x", "y", "is_active"}
    if not required_columns.issubset(set(entities_df.columns)):
        return []

    player_pos = game_state.player_position
    if player_pos is None:
        return []
    player_x, player_y = player_pos

    monster_df = entities_df.filter(
        (pl.col("entity_id") != game_state.player_id) & pl.col("is_active")
    )
    if monster_df.is_empty():
        return []

    perception_stat = (
        pl.col("perception_stat")
        if "perception_stat" in monster_df.columns
        else pl.lit(10)
    )
    is_dead = (
        (~pl.col("is_active")) | (pl.col("hp") <= 0)
        if "hp" in monster_df.columns
        else ~pl.col("is_active")
    )
    adapted_df = monster_df.select(
        pl.col("entity_id").alias("id"),
        pl.col("y").cast(pl.Int64).alias("fy"),
        pl.col("x").cast(pl.Int64).alias("fx"),
        is_dead.alias("is_dead"),
        perception_stat.cast(pl.Int64).alias("perception_stat"),
    )
    return monster_perception(
        adapted_df,
        cave_cost=cave_cost,
        flow_centers=flow_centers,
        player_y=int(player_y),
        player_x=int(player_x),
        player_stealth_skill=0,
        rng=game_state.rng_instance,
        deterministic=True,
    )


def _update_production_perception_fields(game_state: GameState) -> None:
    """Mirror queued events into production pathfinding perception fields."""
    game_map = game_state.game_map
    terrain_map = _terrain_map_for_game_map(game_map)
    cave_cost, flow_centers, cave_when, global_scent_when = _perception_arrays(
        game_state, game_map.height, game_map.width
    )

    for x, y, _intensity in getattr(game_state, "noise_events", []):
        update_noise(
            cave_cost, flow_centers, terrain_map, y, x, FlowType.REAL_NOISE, {}
        )

    for x, y, _intensity in getattr(game_state, "scent_events", []):
        global_scent_when = update_smell(
            cave_when, terrain_map, y, x, global_scent_when
        )

    game_state.perception_global_scent_when = global_scent_when
    game_state.perception_alerted_monster_ids = _alerted_monster_ids(
        game_state, cave_cost, flow_centers
    )


def gather_perception(
    game_state: GameState,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate perception maps used by AI systems.

    Noise and scent layers are stored on ``GameMap`` and decayed every call
    before new events are applied. Queued game-facing events are also mirrored
    into the production pathfinding perception fields owned by
    ``pathfinding.perception_systems``; audio playback remains owned by
    ``game.systems.sound``.
    """

    game_map = game_state.game_map

    # Decay existing perception layers.
    game_map.noise_map *= 0.6  # noise fades quickly
    game_map.scent_map *= 0.9  # scent lingers longer

    # Apply queued noise events to the AI-facing radius layer.
    for x, y, intensity in getattr(game_state, "noise_events", []):
        apply_radius_perception(
            map_arr=game_map.noise_map,
            x=x,
            y=y,
            r=2,
            base_intensity=intensity,
            game_map=game_map,
        )

    # Apply queued scent events to the AI-facing radius layer.
    for x, y, intensity in getattr(game_state, "scent_events", []):
        apply_radius_perception(
            map_arr=game_map.scent_map,
            x=x,
            y=y,
            r=4,
            base_intensity=intensity,
            game_map=game_map,
        )

    _update_production_perception_fields(game_state)

    # Clear processed events.
    if hasattr(game_state, "noise_events"):
        game_state.noise_events.clear()
    if hasattr(game_state, "scent_events"):
        game_state.scent_events.clear()

    noise_map = game_map.noise_map.copy()
    scent_map = game_map.scent_map.copy()
    # LOS uses the latest visibility grid populated by GameState.update_fov.
    los_map = game_map.visible.copy()
    log.debug("Perception maps generated", shape=noise_map.shape)
    return noise_map, scent_map, los_map


def find_visible_enemies(
    entity_row: series,
    game_state: GameState,
    los_map: np.ndarray,
) -> list[series]:
    """Return a list of enemies visible to ``entity_row``.

    Entities are considered enemies if they belong to a different faction.
    Visibility is determined using both the provided ``los_map`` and a
    line-of-sight check against the game map's transparency grid.
    """

    ex, ey = entity_row.get("x"), entity_row.get("y")
    faction = entity_row.get("faction")
    game_map = game_state.game_map
    enemies: list[series] = []

    if ex is None or ey is None:
        return enemies

    filter_expr = pl.col("is_active") is True
    if faction is not None:
        filter_expr &= pl.col("faction") != faction
    enemy_df = game_state.entity_registry.entities_df.filter(filter_expr)
    enemy_rows = {int(row["entity_id"]): row for row in enemy_df.iter_rows(named=True)}

    vision_range = int(entity_row.get("vision_range") or game_state.fov_radius)
    spatial_index = getattr(game_state, "spatial_index", None)
    nearby = None
    if spatial_index is not None and hasattr(spatial_index, "query_radius"):
        nearby = spatial_index.query_radius((int(ex), int(ey)), vision_range)

    candidates = nearby if nearby is not None else enemy_rows.values()
    for other in candidates:
        if isinstance(other, dict):
            other_row = other
            ox, oy = other_row.get("x"), other_row.get("y")
            other_id = other_row.get("entity_id")
        else:
            other_id, ox, oy = other
            other_row = enemy_rows.get(int(other_id))
            if other_row is None:
                continue
        if other_id == entity_row.get("entity_id"):
            continue
        if ox is None or oy is None:
            continue
        if not game_map.in_bounds(int(ox), int(oy)):
            continue
        if not los_map[int(oy), int(ox)]:
            continue
        if line_of_sight(int(ex), int(ey), int(ox), int(oy), game_map.transparent):
            enemies.append(other_row)

    log.debug(
        "Visible enemies located",
        entity_id=entity_row.get("entity_id"),
        count=len(enemies),
    )
    return enemies


__all__ = ["gather_perception", "find_visible_enemies"]
