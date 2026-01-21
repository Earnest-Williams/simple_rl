"""CI tests for variety coverage metrics.

These tests ensure that text generation maintains minimum variety thresholds,
preventing accidental collapse to repetitive output. Run in CI to catch
regressions in output diversity.
"""

import pytest

from utils.game_rng import GameRNG
from utils.core import (
    ToneProfile,
    Lexicon,
    VariationEngine,
    NameGenerator,
    compute_variety_metrics,
)


class TestVarietyCoverageThresholds:
    """Tests to ensure minimum variety thresholds are met."""

    def test_room_description_variety_threshold(self) -> None:
        """Ensure room descriptions meet minimum variety threshold."""
        rng = GameRNG(seed=42)
        engine = VariationEngine(rng)

        # Generate 1000 samples
        variants = [engine.room_description() for _ in range(1000)]

        # Compute metrics
        metrics = compute_variety_metrics(variants)

        # Should have at least 60% unique descriptions
        assert metrics.unique_fraction >= 0.6, (
            "Room descriptions failed variety threshold: "
            f"{metrics.unique_fraction:.3f} < 0.6"
        )

        # Should have reasonable entropy
        assert metrics.entropy >= 5.0, (
            f"Room descriptions have low entropy: {metrics.entropy:.3f}"
        )

    def test_terse_tone_variety_threshold(self) -> None:
        """Ensure terse tone maintains variety."""
        rng = GameRNG(seed=100)
        engine = VariationEngine(rng, tone=ToneProfile.TERSE)

        variants = [engine.room_description() for _ in range(500)]
        metrics = compute_variety_metrics(variants)

        # Terse has fewer templates, so slightly lower threshold
        assert metrics.unique_fraction >= 0.4, (
            "Terse tone failed variety threshold: "
            f"{metrics.unique_fraction:.3f} < 0.4"
        )

    def test_ornate_tone_variety_threshold(self) -> None:
        """Ensure ornate tone maintains variety."""
        rng = GameRNG(seed=200)
        engine = VariationEngine(rng, tone=ToneProfile.ORNATE)

        variants = [engine.room_description() for _ in range(500)]
        metrics = compute_variety_metrics(variants)

        # Ornate should have good variety
        assert metrics.unique_fraction >= 0.5, (
            "Ornate tone failed variety threshold: "
            f"{metrics.unique_fraction:.3f} < 0.5"
        )

    def test_name_generation_variety_threshold(self) -> None:
        """Ensure name generation produces diverse names."""
        rng = GameRNG(seed=300)
        gen = NameGenerator.default_fantasy_generator(rng)

        # Generate 200 names
        names = [gen.generate() for _ in range(200)]
        metrics = compute_variety_metrics(names)

        # Should have at least 70% unique names (Markov chains produce some duplicates)
        assert metrics.unique_fraction >= 0.70, (
            "Name generation failed variety threshold: "
            f"{metrics.unique_fraction:.3f} < 0.70"
        )

    def test_custom_lexicon_variety(self) -> None:
        """Test variety with custom lexicon."""
        rng = GameRNG(seed=400)

        # Small lexicon to test edge case - need to include all fields
        lex = Lexicon(
            adjectives=["dark", "light", "dim", "bright", "shadowy"],
            nouns=["room", "hall", "chamber"],
            features=[
                "a torch",
                "a statue",
                "a pool",
                "moss",
                "carvings"
            ],
            verbs=["enter", "find", "discover"],
            adverbs=["slowly", "quickly", "cautiously"]
        )

        engine = VariationEngine(rng, lexicon=lex)
        variants = [engine.room_description() for _ in range(200)]
        metrics = compute_variety_metrics(variants)

        # Even with small lexicon, should get reasonable variety
        assert metrics.unique_fraction >= 0.3, (
            "Small lexicon failed minimum variety: "
            f"{metrics.unique_fraction:.3f} < 0.3"
        )

    def test_anti_repeat_effectiveness(self) -> None:
        """Test that anti-repeat biasing reduces consecutive duplicates."""
        rng = GameRNG(seed=500)

        # Larger lexicon for more realistic testing
        lex = Lexicon(
            adjectives=["dark", "light", "dim", "bright", "shadowy", "glowing", "murky", "clear"]
        )

        engine = VariationEngine(rng, lexicon=lex, anti_repeat_size=20)

        # Generate many selections
        selections = [engine.adjective() for _ in range(100)]

        # Count consecutive duplicates
        consecutive_dupes = sum(
            1 for i in range(len(selections) - 1)
            if selections[i] == selections[i + 1]
        )

        # With 8 options, expect very few consecutive duplicates
        # (random would be ~12.5%, anti-repeat should be much lower)
        # Allow some statistical variation but should be significantly better than random
        assert consecutive_dupes < 10, (
            f"Too many consecutive duplicates: {consecutive_dupes} >= 10"
        )

    def test_no_empty_outputs(self) -> None:
        """Ensure generation never produces empty strings."""
        rng = GameRNG(seed=600)
        engine = VariationEngine(rng)

        variants = [engine.room_description() for _ in range(100)]

        # No variant should be empty
        assert all(len(v) > 0 for v in variants), (
            "Found empty output in variants"
        )

        # All variants should have reasonable minimum length
        assert all(len(v) >= 10 for v in variants), (
            "Found suspiciously short output"
        )

    def test_deterministic_variety(self) -> None:
        """Ensure variety metrics are deterministic for same seed."""
        # Run 1
        rng1 = GameRNG(seed=700)
        engine1 = VariationEngine(rng1)
        variants1 = [engine1.room_description() for _ in range(100)]
        metrics1 = compute_variety_metrics(variants1)

        # Run 2 with same seed
        rng2 = GameRNG(seed=700)
        engine2 = VariationEngine(rng2)
        variants2 = [engine2.room_description() for _ in range(100)]
        metrics2 = compute_variety_metrics(variants2)

        # Should produce identical metrics
        assert metrics1.unique_fraction == metrics2.unique_fraction
        assert metrics1.entropy == metrics2.entropy
        assert variants1 == variants2


class TestVarietyRegression:
    """Regression tests to catch variety decreases."""

    @pytest.fixture
    def baseline_variety(self):
        """Baseline variety metrics for regression testing."""
        return {
            "room_neutral_1000": 0.60,  # Minimum unique fraction
            "room_terse_500": 0.40,
            "room_ornate_500": 0.50,
            "names_200": 0.70,  # Adjusted for Markov chain behavior
        }

    def test_room_neutral_regression(self, baseline_variety) -> None:
        """Test room descriptions don't regress below baseline."""
        rng = GameRNG(seed=1000)
        engine = VariationEngine(rng, tone=ToneProfile.NEUTRAL)

        variants = [engine.room_description() for _ in range(1000)]
        metrics = compute_variety_metrics(variants)

        baseline = baseline_variety["room_neutral_1000"]
        assert metrics.unique_fraction >= baseline, (
            f"Regression detected: {metrics.unique_fraction:.3f} < {baseline}"
        )

    def test_room_terse_regression(self, baseline_variety) -> None:
        """Test terse descriptions don't regress below baseline."""
        rng = GameRNG(seed=1100)
        engine = VariationEngine(rng, tone=ToneProfile.TERSE)

        variants = [engine.room_description() for _ in range(500)]
        metrics = compute_variety_metrics(variants)

        baseline = baseline_variety["room_terse_500"]
        assert metrics.unique_fraction >= baseline, (
            f"Regression detected: {metrics.unique_fraction:.3f} < {baseline}"
        )

    def test_room_ornate_regression(self, baseline_variety) -> None:
        """Test ornate descriptions don't regress below baseline."""
        rng = GameRNG(seed=1200)
        engine = VariationEngine(rng, tone=ToneProfile.ORNATE)

        variants = [engine.room_description() for _ in range(500)]
        metrics = compute_variety_metrics(variants)

        baseline = baseline_variety["room_ornate_500"]
        assert metrics.unique_fraction >= baseline, (
            f"Regression detected: {metrics.unique_fraction:.3f} < {baseline}"
        )

    def test_names_regression(self, baseline_variety) -> None:
        """Test name generation doesn't regress below baseline."""
        rng = GameRNG(seed=1300)
        gen = NameGenerator.default_fantasy_generator(rng)

        names = [gen.generate() for _ in range(200)]
        metrics = compute_variety_metrics(names)

        baseline = baseline_variety["names_200"]
        assert metrics.unique_fraction >= baseline, (
            f"Regression detected: {metrics.unique_fraction:.3f} < {baseline}"
        )


class TestEdgeCases:
    """Edge case tests for variety metrics."""

    def test_single_template_still_varies(self) -> None:
        """Test that even single template produces some variety."""
        rng = GameRNG(seed=2000)

        # Lexicon with variety but we'll only use one simple pattern
        lex = Lexicon(
            adjectives=["dark", "light", "bright", "shadowy", "glowing"],
            nouns=["room", "hall", "chamber", "vault", "crypt"],
            features=["a torch", "moss", "carvings", "water", "bones"],
            verbs=["enter", "find"],
            adverbs=["slowly", "quickly"]
        )

        engine = VariationEngine(rng, lexicon=lex)

        # Even with template variety, lexicon provides variation
        variants = [engine.room_description() for _ in range(50)]
        metrics = compute_variety_metrics(variants)

        # Should still get some variety from lexicon choices
        assert metrics.unique > 10

    def test_very_small_lexicon_warning(self) -> None:
        """Test behavior with extremely small lexicon."""
        rng = GameRNG(seed=3000)

        # Minimal lexicon
        lex = Lexicon(
            adjectives=["dark"],
            nouns=["room"],
            features=["nothing"]
        )

        engine = VariationEngine(rng, lexicon=lex)
        variants = [engine.room_description() for _ in range(10)]

        # With single options, should get same output
        # (but shouldn't crash or error)
        assert all(isinstance(v, str) for v in variants)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
