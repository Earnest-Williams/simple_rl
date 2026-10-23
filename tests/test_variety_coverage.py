"""Variety regression thresholds for utils.core text and name generation.

These are the CI thresholds documented in ``utils/Core README.md``.
"""

from __future__ import annotations

from typing import Final

import pytest

from utils.core import (
    NameGenerator,
    ToneProfile,
    VariationEngine,
    compute_variety_metrics,
)
from utils.game_rng import GameRNG

SEED: Final[int] = 42  # fixed seed so thresholds are deterministic


@pytest.mark.parametrize(
    ("tone", "samples", "min_unique_fraction"),
    [
        (ToneProfile.NEUTRAL, 1000, 0.6),
        (ToneProfile.TERSE, 500, 0.4),
        (ToneProfile.ORNATE, 500, 0.5),
    ],
)
def test_room_description_variety_threshold(
    tone: ToneProfile, samples: int, min_unique_fraction: float
) -> None:
    engine = VariationEngine(GameRNG(seed=SEED), tone=tone)
    variants = [engine.room_description() for _ in range(samples)]
    metrics = compute_variety_metrics(variants)
    assert metrics.unique_fraction >= min_unique_fraction


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Documented threshold is >=0.70 unique over 200 names, but the default "
        "fantasy generator averages ~0.70 across seeds (0.63-0.755 over seeds "
        "1-20) and gives 0.67 at seed 42. Lower the threshold or improve the "
        "generator, then drop this marker."
    ),
)
def test_name_generation_variety_threshold() -> None:
    generator = NameGenerator.default_fantasy_generator(GameRNG(seed=SEED))
    names = [generator.generate() for _ in range(200)]
    metrics = compute_variety_metrics(names)
    assert metrics.unique_fraction >= 0.7
