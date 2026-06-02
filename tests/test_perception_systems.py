"""Tests for pathfinding perception flow, scent, and detection helpers."""

import numpy as np
import polars as pl
from numpy.typing import NDArray

from common.constants import FeatureType
from pathfinding.perception_systems import (
    BASE_FLOW_CENTER,
    MAX_FLOWS,
    NOISE_MAX_DIST,
    SCENT_RESET_AGE,
    SMELL_STRENGTH,
    FlowType,
    choose_step_by_flow,
    get_noise_dist,
    get_scent,
    monster_perception,
    update_noise,
    update_smell,
)
from utils.game_rng import GameRNG


def _floor_map(height: int, width: int) -> NDArray[np.int32]:
    return np.full((height, width), int(FeatureType.FLOOR), dtype=np.int32)


def _flow_arrays(
    height: int, width: int
) -> tuple[NDArray[np.int32], NDArray[np.int32]]:
    infinity = np.iinfo(np.int32).max // 2
    cave_cost = np.full((MAX_FLOWS, height, width), infinity, dtype=np.int32)
    flow_centers = np.zeros((MAX_FLOWS, 2), dtype=np.int32)
    return cave_cost, flow_centers


def test_update_noise_resets_one_slice_and_wall_source_blocks() -> None:
    terrain_map = _floor_map(5, 5)
    terrain_map[2, 2] = int(FeatureType.WALL)
    cave_cost = np.full((MAX_FLOWS, 5, 5), 42, dtype=np.int32)
    flow_centers = np.zeros((MAX_FLOWS, 2), dtype=np.int32)

    update_noise(cave_cost, flow_centers, terrain_map, 2, 2, FlowType.REAL_NOISE, {})

    infinity = np.iinfo(np.int32).max // 2
    flow_idx = int(FlowType.REAL_NOISE)
    assert np.all(cave_cost[flow_idx] == infinity)
    assert np.all(cave_cost[int(FlowType.PASS_DOORS)] == 42)
    assert tuple(flow_centers[flow_idx]) == (2, 2)


def test_flow_type_door_semantics() -> None:
    terrain_map = np.full((3, 5), int(FeatureType.WALL), dtype=np.int32)
    terrain_map[1, 1:4] = int(FeatureType.FLOOR)
    terrain_map[1, 2] = int(FeatureType.CLOSED_DOOR)
    penalties = {"pass": 3, "real": 5}
    cave_cost, flow_centers = _flow_arrays(3, 5)

    update_noise(
        cave_cost, flow_centers, terrain_map, 1, 1, FlowType.NO_DOORS, penalties
    )
    update_noise(
        cave_cost, flow_centers, terrain_map, 1, 1, FlowType.PASS_DOORS, penalties
    )
    update_noise(
        cave_cost, flow_centers, terrain_map, 1, 1, FlowType.REAL_NOISE, penalties
    )

    assert (
        get_noise_dist(cave_cost, flow_centers, FlowType.NO_DOORS, 1, 3)
        == NOISE_MAX_DIST
    )
    assert cave_cost[int(FlowType.PASS_DOORS), 1, 2] == BASE_FLOW_CENTER + 4
    assert cave_cost[int(FlowType.REAL_NOISE), 1, 2] == BASE_FLOW_CENTER + 6


def test_noise_distance_uses_sil_geometric_adjustment() -> None:
    terrain_map = _floor_map(5, 5)
    cave_cost, flow_centers = _flow_arrays(5, 5)

    update_noise(cave_cost, flow_centers, terrain_map, 2, 2, FlowType.REAL_NOISE, {})

    assert get_noise_dist(cave_cost, flow_centers, FlowType.REAL_NOISE, 2, 3) == 2
    assert get_noise_dist(cave_cost, flow_centers, FlowType.REAL_NOISE, 3, 3) == 2
    cave_cost[int(FlowType.REAL_NOISE), 2, 2] = BASE_FLOW_CENTER - 1
    assert (
        get_noise_dist(cave_cost, flow_centers, FlowType.REAL_NOISE, 2, 2)
        == NOISE_MAX_DIST
    )


def test_update_smell_wrap_preserves_recent_scent_and_stamps_center() -> None:
    terrain_map = _floor_map(7, 7)
    cave_when = np.zeros((7, 7), dtype=np.int32)
    cave_when[0, 0] = SMELL_STRENGTH + 1
    cave_when[0, 1] = 1

    global_scent_when = update_smell(cave_when, terrain_map, 4, 4, 1)

    reset_offset = SCENT_RESET_AGE - SMELL_STRENGTH
    assert global_scent_when == reset_offset
    assert cave_when[0, 0] == 0
    assert cave_when[0, 1] == reset_offset + 1
    assert cave_when[4, 4] == reset_offset


def test_scent_stamp_skips_sentinel_corners_and_door_blocked_los() -> None:
    terrain_map = _floor_map(5, 5)
    terrain_map[2, 3] = int(FeatureType.CLOSED_DOOR)
    cave_when = np.zeros((5, 5), dtype=np.int32)

    update_smell(cave_when, terrain_map, 2, 2, SCENT_RESET_AGE)

    assert get_scent(cave_when, 0, 0) == 0
    assert get_scent(cave_when, 2, 4) == 0
    assert get_scent(cave_when, -1, 2) == 0


def test_monster_perception_is_deterministic_and_filters_dead_monsters() -> None:
    terrain_map = _floor_map(5, 5)
    cave_cost, flow_centers = _flow_arrays(5, 5)
    update_noise(cave_cost, flow_centers, terrain_map, 2, 2, FlowType.REAL_NOISE, {})
    monster_df = pl.DataFrame(
        {
            "id": [3, 1, 2],
            "fy": [2, 2, 2],
            "fx": [2, 3, 4],
            "is_dead": [False, False, True],
            "perception_stat": [500, 500, 500],
        }
    )

    first = monster_perception(
        monster_df,
        cave_cost=cave_cost,
        flow_centers=flow_centers,
        player_y=2,
        player_x=2,
        player_stealth_skill=0,
        rng=GameRNG(seed=99),
        deterministic=True,
    )
    second = monster_perception(
        monster_df,
        cave_cost=cave_cost,
        flow_centers=flow_centers,
        player_y=2,
        player_x=2,
        player_stealth_skill=0,
        rng=GameRNG(seed=99),
        deterministic=True,
    )

    assert first == [1, 3]
    assert second == first


def test_monster_perception_seed_is_independent_of_chunking() -> None:
    terrain_map = _floor_map(9, 9)
    cave_cost, flow_centers = _flow_arrays(9, 9)
    update_noise(cave_cost, flow_centers, terrain_map, 4, 4, FlowType.REAL_NOISE, {})
    monster_df = pl.DataFrame(
        {
            "id": list(range(8)),
            "fy": [4, 4, 4, 4, 5, 5, 5, 5],
            "fx": [1, 2, 3, 4, 4, 5, 6, 7],
            "is_dead": [False] * 8,
            "perception_stat": [4] * 8,
        }
    )

    single_job = monster_perception(
        monster_df,
        cave_cost=cave_cost,
        flow_centers=flow_centers,
        player_y=4,
        player_x=4,
        player_stealth_skill=2,
        rng=GameRNG(seed=123),
        num_jobs=1,
        deterministic=True,
    )
    parallel_chunks = monster_perception(
        monster_df,
        cave_cost=cave_cost,
        flow_centers=flow_centers,
        player_y=4,
        player_x=4,
        player_stealth_skill=2,
        rng=GameRNG(seed=123),
        num_jobs=2,
        deterministic=False,
    )

    assert parallel_chunks == single_job


def test_choose_step_by_flow_descends_without_entering_walls() -> None:
    terrain_map = _floor_map(3, 3)
    terrain_map[1, 1] = int(FeatureType.WALL)
    flow_costs = np.array(
        [
            [9, 8, 7],
            [8, 10, 6],
            [7, 6, 5],
        ],
        dtype=np.int32,
    )

    assert choose_step_by_flow(terrain_map, flow_costs, 1, 0) == (2, 1)
    assert choose_step_by_flow(terrain_map, flow_costs, -1, 0) == (-1, 0)
