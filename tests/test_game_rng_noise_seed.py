from __future__ import annotations

from typing import List, Tuple

from utils.game_rng import GameRNG


def _sample_noise(
    rng: GameRNG, points: List[Tuple[int, int]]
) -> List[float]:
    return [rng.noise_2d(x, y, scale=1.0, seed_offset=0) for x, y in points]


def test_noise_seed_reset_is_deterministic() -> None:
    seed = 123456
    points = [(x, y) for x in range(0, 20, 2) for y in range(0, 20, 2)]

    rng = GameRNG(seed=seed, metrics=False)
    rng.reset(seed)
    first = _sample_noise(rng, points)
    assert rng.noise_seed == seed

    rng.reset(seed)
    second = _sample_noise(rng, points)
    assert rng.noise_seed == seed

    assert first == second
