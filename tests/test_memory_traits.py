"""Tests for MemoryTraits and resolve_memory_decay_parameters.

Conforms to Phase 3 requirements of the retire lights_dev plan.
"""

from __future__ import annotations

import numpy as np

from game.world.memory import (
    MemoryTraits,
    resolve_memory_decay_parameters,
    update_memory_fade,
)


def test_default_traits() -> None:
    """Default traits return base behavior."""
    traits = MemoryTraits()
    mod = traits.compute_decay_modifier()
    assert abs(mod - 1.0) < 1e-6

    steepness, midpoint = resolve_memory_decay_parameters(
        traits, base_steepness=0.1, base_midpoint=30.0
    )
    assert abs(steepness - 0.1) < 1e-6
    assert abs(midpoint - 30.0) < 1e-6


def test_intelligence_modifiers() -> None:
    """Intelligence above base slows decay, below speeds it."""
    # High intelligence (better memory -> slower decay)
    traits_high = MemoryTraits(intelligence=20)
    assert traits_high.compute_decay_modifier() < 1.0

    # Low intelligence (worse memory -> faster decay)
    traits_low = MemoryTraits(intelligence=5)
    assert traits_low.compute_decay_modifier() > 1.0


def test_confusion_speeds_decay() -> None:
    """Confusion speeds decay."""
    traits = MemoryTraits(has_confusion=True)
    assert traits.compute_decay_modifier() > 1.0


def test_illness_speeds_decay() -> None:
    """Illness speeds decay."""
    traits = MemoryTraits(has_illness=True)
    assert traits.compute_decay_modifier() > 1.0


def test_fatigue_scales_decay() -> None:
    """Fatigue scales decay."""
    traits = MemoryTraits(fatigue_level=0.8)
    assert traits.compute_decay_modifier() > 1.0


def test_magic_bonus_slows_decay() -> None:
    """Magic memory bonus slows decay."""
    traits = MemoryTraits(magic_memory_bonus=2.0)
    assert traits.compute_decay_modifier() < 1.0


def test_familiarity_slows_decay() -> None:
    """Location familiarity slows decay."""
    traits = MemoryTraits(location_familiarity=0.5)
    assert traits.compute_decay_modifier() < 1.0


def test_clamp_behavior() -> None:
    """Trait values clamp to valid bounds."""
    traits = MemoryTraits(
        intelligence=50,
        fatigue_level=2.5,
        magic_memory_bonus=-1.0,
        location_familiarity=1.5,
    )
    assert traits.intelligence == 30
    assert traits.fatigue_level == 1.0
    assert traits.magic_memory_bonus == 0.0
    assert traits.location_familiarity == 1.0


def test_update_memory_fade_with_traits() -> None:
    """Trait-derived parameters affect update_memory_fade()."""
    # Low intelligence (decay multiplier = 2.0 -> decays twice as fast)
    traits = MemoryTraits(intelligence=5)
    base_steepness = 0.1
    base_midpoint = 10.0

    steepness, midpoint = resolve_memory_decay_parameters(
        traits, base_steepness=base_steepness, base_midpoint=base_midpoint
    )

    # Low INT -> decay_modifier = 2.0
    # steepness = 0.2, midpoint = 5.0
    assert abs(steepness - 0.2) < 1e-6
    assert abs(midpoint - 5.0) < 1e-6

    # Setup maps
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.zeros((1, 1), dtype=bool)
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.zeros((1, 1), dtype=bool)
    memory_strength = np.zeros((1, 1), dtype=np.float32)
    tile_modifiers = np.ones((1, 1), dtype=np.float32)

    update_memory_fade(
        current_time=8,  # elapsed = 8
        last_seen_time=last_seen_time,
        memory_intensity=memory_intensity,
        visible=visible,
        needs_update_mask=needs_update_mask,
        prev_visible=prev_visible,
        memory_strength=memory_strength,
        tile_modifiers=tile_modifiers,
        steepness=steepness,
        midpoint=midpoint,
    )
    # exponent = steepness / (1+strength)*tile_mod * (elapsed - midpoint*(1+strength)*tile_mod)
    # strength=0, tile_mod=1 -> scale = 1.0.
    # exponent = 0.2 * (8 - 5) = 0.6
    # expected intensity = 1 / (1 + exp(0.6)) = 1 / (1 + 1.822) = ~0.354
    assert abs(memory_intensity[0, 0] - 1.0 / (1.0 + np.exp(0.6))) < 1e-5
