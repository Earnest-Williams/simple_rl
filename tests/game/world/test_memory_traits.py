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
    """Default traits return base behavior (decay modifier = 1.0)."""
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
    # High intelligence (better memory -> slower decay modifier < 1.0)
    traits_high = MemoryTraits(intelligence=20)
    assert traits_high.compute_decay_modifier() < 1.0

    # Low intelligence (worse memory -> faster decay modifier > 1.0)
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


def test_combined_modifiers_composition() -> None:
    """Combined modifiers compose deterministically."""
    # Low intelligence (modifier = 2.0) + confusion (modifier = 2.0)
    # Expected combined modifier = 4.0
    traits = MemoryTraits(intelligence=5, has_confusion=True)
    assert abs(traits.compute_decay_modifier() - 4.0) < 1e-6


def test_update_memory_fade_with_traits() -> None:
    """Trait-derived parameters affect update_memory_fade()."""
    traits = MemoryTraits(intelligence=5)
    base_steepness = 0.1
    base_midpoint = 10.0

    steepness, midpoint = resolve_memory_decay_parameters(
        traits, base_steepness=base_steepness, base_midpoint=base_midpoint
    )

    # Setup maps
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.zeros((1, 1), dtype=bool)
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.zeros((1, 1), dtype=bool)
    memory_strength = np.zeros((1, 1), dtype=np.float32)
    tile_modifiers = np.ones((1, 1), dtype=np.float32)

    update_memory_fade(
        current_time=8,
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
    expected_intensity = 1.0 / (1.0 + np.exp(0.2 * (8 - 5)))
    assert abs(memory_intensity[0, 0] - expected_intensity) < 1e-5


def test_traits_compose_with_memory_strength() -> None:
    """Decay modifier composes with memory_strength (higher strength slows decay)."""
    MemoryTraits()  # default mod = 1.0
    steepness = 0.1
    midpoint = 10.0

    # Strength = 1.0 -> scale = (1 + 1) * 1 = 2.0
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.zeros((1, 1), dtype=bool)
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.zeros((1, 1), dtype=bool)
    memory_strength = np.ones((1, 1), dtype=np.float32)  # strength = 1.0
    tile_modifiers = np.ones((1, 1), dtype=np.float32)

    update_memory_fade(
        current_time=8,
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

    # decay_rate = steepness / scale = 0.1 / 2 = 0.05
    # midpoint_scaled = midpoint * scale = 10 * 2 = 20
    # exponent = 0.05 * (8 - 20) = -0.6
    # expected = 1 / (1 + exp(-0.6))
    expected = 1.0 / (1.0 + np.exp(-0.6))
    assert abs(memory_intensity[0, 0] - expected) < 1e-5


def test_traits_compose_with_tile_modifiers() -> None:
    """Decay modifier composes with tile modifiers."""
    MemoryTraits()  # default mod = 1.0
    steepness = 0.1
    midpoint = 10.0

    # tile_modifier = 2.0 -> scale = (1 + 0) * 2 = 2.0
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.zeros((1, 1), dtype=bool)
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.zeros((1, 1), dtype=bool)
    memory_strength = np.zeros((1, 1), dtype=np.float32)
    tile_modifiers = np.full((1, 1), 2.0, dtype=np.float32)  # modifier = 2.0

    update_memory_fade(
        current_time=8,
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

    # scale = 2.0 -> same exponent as above
    expected = 1.0 / (1.0 + np.exp(-0.6))
    assert abs(memory_intensity[0, 0] - expected) < 1e-5


def test_visible_tiles_refresh_to_full_memory() -> None:
    """Visible tiles are skipped by update_memory_fade and keep/refresh their memory."""
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.ones((1, 1), dtype=bool)  # currently visible
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.ones((1, 1), dtype=bool)
    memory_strength = np.zeros((1, 1), dtype=np.float32)
    tile_modifiers = np.ones((1, 1), dtype=np.float32)

    update_memory_fade(
        current_time=8,
        last_seen_time=last_seen_time,
        memory_intensity=memory_intensity,
        visible=visible,
        needs_update_mask=needs_update_mask,
        prev_visible=prev_visible,
        memory_strength=memory_strength,
        tile_modifiers=tile_modifiers,
        steepness=0.1,
        midpoint=10.0,
    )

    # Visible tiles should be pruned from needs_update_mask
    assert not needs_update_mask[0, 0]
    # memory_intensity should not be decayed (remains 1.0)
    assert memory_intensity[0, 0] == 1.0


def test_forgotten_tiles_are_pruned_from_needs_update_mask() -> None:
    """Tiles that fade to zero are removed from the update mask."""
    last_seen_time = np.zeros((1, 1), dtype=np.int32)
    memory_intensity = np.ones((1, 1), dtype=np.float32)
    visible = np.zeros((1, 1), dtype=bool)
    needs_update_mask = np.ones((1, 1), dtype=bool)
    prev_visible = np.zeros((1, 1), dtype=bool)
    memory_strength = np.zeros((1, 1), dtype=np.float32)
    tile_modifiers = np.ones((1, 1), dtype=np.float32)

    update_memory_fade(
        current_time=10_000,
        last_seen_time=last_seen_time,
        memory_intensity=memory_intensity,
        visible=visible,
        needs_update_mask=needs_update_mask,
        prev_visible=prev_visible,
        memory_strength=memory_strength,
        tile_modifiers=tile_modifiers,
        steepness=1.0,
        midpoint=1.0,
    )

    assert memory_intensity[0, 0] == 0.0
    assert not needs_update_mask[0, 0]
