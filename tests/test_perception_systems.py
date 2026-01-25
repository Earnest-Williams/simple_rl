import numpy as np
import polars as pl

from common.constants import FeatureType
from pathfinding.perception_systems import (
    BASE_FLOW_CENTER,
    MAX_FLOWS,
    NOISE_MAX_DIST,
    SCENT_ADJUST_TABLE,
    FlowType,
    _lay_scent_kernel,
    _process_monster_perception_chunk,
    cave_closed_door,
    line_of_sight,
    skill_check,
    terrain_transparency_map,
)
from utils.game_rng import GameRNG


def test_skill_check_deterministic():
    seed = 7
    expected_roll = GameRNG(seed).get_int(1, 100)
    rng = GameRNG(seed)
    result = skill_check(actor_skill=30, difficulty=10, target_skill=5, rng=rng)
    threshold = 50 + (3 * (30 - 5)) - 10
    threshold = max(5, min(95, threshold))
    assert result == (expected_roll <= threshold)


def test_cave_closed_door_feature_detection():
    assert cave_closed_door(FeatureType.CLOSED_DOOR)
    assert cave_closed_door(FeatureType.SECRET_DOOR)
    assert not cave_closed_door(FeatureType.OPEN_DOOR)
    assert not cave_closed_door(FeatureType.FLOOR)


def test_process_chunk_perception_outcome():
    rng_seed = 42
    rng = GameRNG(rng_seed)
    cave_cost = np.full(
        (MAX_FLOWS, 5, 5), BASE_FLOW_CENTER + NOISE_MAX_DIST + 1, dtype=np.int32
    )
    flow_centers = np.zeros((MAX_FLOWS, 2), dtype=np.int32)
    cave_cost[FlowType.REAL_NOISE, 1, 1] = BASE_FLOW_CENTER + 5
    cave_cost[FlowType.REAL_NOISE, 1, 2] = BASE_FLOW_CENTER + 50
    monster_df = pl.DataFrame(
        {
            "id": [1, 2],
            "fy": [1, 1],
            "fx": [1, 2],
            "perception_stat": [60, 60],
        }
    )
    result = _process_monster_perception_chunk(
        monster_df, cave_cost, flow_centers, 10, FlowType.REAL_NOISE, rng
    )
    exp_rng = GameRNG(rng_seed)
    roll1 = exp_rng.get_int(1, 100)
    roll2 = exp_rng.get_int(1, 100)
    threshold1 = 50 + (3 * (60 - 10)) - 5
    threshold2 = 50 + (3 * (60 - 10)) - 50
    threshold1 = max(5, min(95, threshold1))
    threshold2 = max(5, min(95, threshold2))
    expected = []
    if roll1 <= threshold1:
        expected.append(1)
    if roll2 <= threshold2:
        expected.append(2)
    assert result == expected


def test_line_of_sight_blocks_walls():
    terrain = np.full((5, 5), FeatureType.FLOOR, dtype=np.int32)
    terrain[2, 2] = FeatureType.WALL
    assert not line_of_sight(2, 0, 2, 4, terrain)
    assert line_of_sight(0, 0, 0, 4, terrain)


def test_scent_respects_line_of_sight():
    terrain = np.full((7, 7), FeatureType.FLOOR, dtype=np.int32)
    terrain[3, 4] = FeatureType.WALL
    cave_when = np.zeros((7, 7), dtype=np.int32)
    transparency = terrain_transparency_map(terrain)
    _lay_scent_kernel(
        cave_when,
        transparency,
        py=3,
        px=3,
        current_scent_when=100,
        scent_adjust=SCENT_ADJUST_TABLE,
    )
    assert cave_when[3, 5] == 0
    assert cave_when[3, 2] > 0
