"""Comprehensive test suite for skill system.

Property-based tests using Hypothesis.
Performance benchmarks included.
All tests fully type-annotated.
"""

from __future__ import annotations

import timeit

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from skills.cross_training import (
    calculate_cross_training_xp,
    get_cross_trained_skills,
)
from skills.effects import (
    calculate_combat_bonuses,
    calculate_total_damage_multiplier,
    get_combat_bonuses_dict,
)
from skills.models import (
    MAX_APTITUDE,
    MAX_SKILL_LEVEL,
    MIN_APTITUDE,
    ManualBonus,
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    UsageWindow,
)
from skills.progression import (
    calculate_level_from_xp,
    calculate_xp_for_level,
    calculate_xp_to_next_level,
)


class TestProgression:
    """Test XP progression formulas."""

    @given(
        level=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL),
        aptitude=st.integers(min_value=MIN_APTITUDE, max_value=MAX_APTITUDE),
    )
    def test_xp_formula_roundtrip(self, level: int, aptitude: int) -> None:
        """XP -> Level -> XP should be consistent."""
        xp_required: int = calculate_xp_for_level(level, aptitude)
        recovered_level: int = calculate_level_from_xp(xp_required, aptitude)

        assert recovered_level == level

    @given(
        level1=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL - 1),
        level2=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL - 1),
        aptitude=st.integers(min_value=MIN_APTITUDE, max_value=MAX_APTITUDE),
    )
    def test_xp_monotonic(self, level1: int, level2: int, aptitude: int) -> None:
        """Higher levels require more XP."""
        xp1: int = calculate_xp_for_level(level1, aptitude)
        xp2: int = calculate_xp_for_level(level2, aptitude)

        if level1 < level2:
            assert xp1 < xp2
        elif level1 > level2:
            assert xp1 > xp2
        else:
            assert xp1 == xp2

    @given(
        level=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL),
        apt1=st.integers(min_value=MIN_APTITUDE, max_value=MAX_APTITUDE),
        apt2=st.integers(min_value=MIN_APTITUDE, max_value=MAX_APTITUDE),
    )
    def test_aptitude_effects(self, level: int, apt1: int, apt2: int) -> None:
        """Higher aptitude = lower XP cost."""
        xp1: int = calculate_xp_for_level(level, apt1)
        xp2: int = calculate_xp_for_level(level, apt2)

        if apt1 > apt2:
            assert xp1 < xp2  # Higher aptitude = less XP needed
        elif apt1 < apt2:
            assert xp1 > xp2
        else:
            assert xp1 == xp2

    def test_xp_to_next_level_edge_cases(self) -> None:
        """Test XP to next level at boundaries."""
        # At max level
        xp_at_max: int = calculate_xp_for_level(MAX_SKILL_LEVEL, 0)
        remaining: int = calculate_xp_to_next_level(xp_at_max, 0)
        assert remaining == 0

        # At level 0
        remaining_from_zero: int = calculate_xp_to_next_level(0, 0)
        expected: int = calculate_xp_for_level(1, 0)
        assert remaining_from_zero == expected

    @pytest.mark.parametrize(
        "level,aptitude,expected_range",
        [
            (0, 0, (0, 0)),
            (1, 0, (50, 50)),
            (10, 0, (2750, 2750)),
            (27, 0, (18900, 18900)),
            (10, 4, (0, 1500)),  # +4 aptitude halves cost
            (10, -4, (5000, 6000)),  # -4 aptitude doubles cost
        ],
    )
    def test_known_xp_values(
        self, level: int, aptitude: int, expected_range: tuple[int, int]
    ) -> None:
        """Test against known DCSS XP values."""
        xp: int = calculate_xp_for_level(level, aptitude)
        min_expected, max_expected = expected_range
        assert min_expected <= xp <= max_expected


class TestCombatEffects:
    """Test combat bonus calculations."""

    @given(
        fighting=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL),
        weapon=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL),
    )
    def test_damage_multiplier_monotonic(self, fighting: int, weapon: int) -> None:
        """Damage multiplier increases with skill."""
        base_mult: float = calculate_total_damage_multiplier(fighting, weapon)

        # Increasing fighting
        higher_fighting_mult: float = calculate_total_damage_multiplier(
            fighting + 1, weapon
        )
        assert higher_fighting_mult > base_mult

        # Increasing weapon
        higher_weapon_mult: float = calculate_total_damage_multiplier(
            fighting, weapon + 1
        )
        assert higher_weapon_mult > base_mult

    @given(
        fighting=st.integers(min_value=0, max_value=MAX_SKILL_LEVEL),
    )
    def test_hp_bonus_linear(self, fighting: int) -> None:
        """HP bonus is exactly +1 per Fighting level."""
        result: tuple[int, float, int, int, int, int] = calculate_combat_bonuses(
            fighting, 0, 0, 0, 0, 0
        )
        hp_bonus: int = result[0]

        assert hp_bonus == fighting

    def test_armor_skill_effectiveness(self) -> None:
        """Armour skill increases armor effectiveness."""
        base_armor: int = 10

        # No skill
        result_0: tuple[int, float, int, int, int, int] = calculate_combat_bonuses(
            0, 0, 0, 0, 0, base_armor
        )
        armor_bonus_0: int = result_0[3]
        assert armor_bonus_0 == 0

        # Level 10 Armour
        result_10: tuple[int, float, int, int, int, int] = calculate_combat_bonuses(
            0, 0, 10, 0, 0, base_armor
        )
        armor_bonus_10: int = result_10[3]
        assert armor_bonus_10 > 0

        # Level 20 Armour
        result_20: tuple[int, float, int, int, int, int] = calculate_combat_bonuses(
            0, 0, 20, 0, 0, base_armor
        )
        armor_bonus_20: int = result_20[3]
        assert armor_bonus_20 > armor_bonus_10

    def test_combat_bonuses_dataclass(self) -> None:
        """Test Python wrapper returns proper dataclass."""
        bonuses = get_combat_bonuses_dict(
            fighting=10,
            weapon=15,
            armour=8,
            dodging=12,
            shields=6,
            base_armor=10,
        )

        assert bonuses.hp_bonus == 10  # Fighting level
        assert bonuses.damage_multiplier > 1.0
        assert bonuses.accuracy_bonus > 0
        assert bonuses.armor_bonus >= 0
        assert bonuses.evasion_bonus == 12  # Dodging level
        assert bonuses.shield_defense == 2  # Shields // 3


class TestCrossTraining:
    """Test cross-training mechanics."""

    def test_axes_maces_cross_training(self) -> None:
        """Axes and Maces cross-train at 0.40."""
        related: dict[Skill, float] = get_cross_trained_skills(Skill.AXES)

        assert Skill.MACES_AND_FLAILS in related
        assert related[Skill.MACES_AND_FLAILS] == 0.40

    def test_long_short_blades_bidirectional(self) -> None:
        """Long and Short Blades cross-train bidirectionally."""
        long_to_short: dict[Skill, float] = get_cross_trained_skills(Skill.LONG_BLADES)
        short_to_long: dict[Skill, float] = get_cross_trained_skills(Skill.SHORT_BLADES)

        assert Skill.SHORT_BLADES in long_to_short
        assert Skill.LONG_BLADES in short_to_long
        assert long_to_short[Skill.SHORT_BLADES] == 0.40
        assert short_to_long[Skill.LONG_BLADES] == 0.40

    @given(
        xp_amount=st.integers(min_value=1, max_value=10000),
    )
    def test_cross_training_xp_calculation(self, xp_amount: int) -> None:
        """Cross-training XP is correct proportion."""
        cross_xp: dict[Skill, int] = calculate_cross_training_xp(Skill.AXES, xp_amount)

        if Skill.MACES_AND_FLAILS in cross_xp:
            expected: int = int(xp_amount * 0.40)
            assert cross_xp[Skill.MACES_AND_FLAILS] == expected

        if Skill.POLEARMS in cross_xp:
            expected_polearms: int = int(xp_amount * 0.25)
            assert cross_xp[Skill.POLEARMS] == expected_polearms


class TestModels:
    """Test data model validation."""

    def test_skill_progress_validation(self) -> None:
        """SkillProgress validates ranges."""
        # Valid
        progress = SkillProgress(skill=Skill.FIGHTING, level=10, xp=2750, aptitude=0)
        assert progress.level == 10

        # Invalid level
        with pytest.raises(ValueError):
            SkillProgress(skill=Skill.FIGHTING, level=30, xp=0, aptitude=0)

        # Invalid aptitude
        with pytest.raises(ValueError):
            SkillProgress(skill=Skill.FIGHTING, level=0, xp=0, aptitude=15)

        # Negative XP
        with pytest.raises(ValueError):
            SkillProgress(skill=Skill.FIGHTING, level=0, xp=-100, aptitude=0)

    def test_manual_bonus_consumption(self) -> None:
        """ManualBonus.consume reduces remaining XP."""
        manual = ManualBonus(
            skill=Skill.FIRE_MAGIC, bonus_aptitude=4, remaining_xp=2500
        )

        # Partial consumption
        updated = manual.consume(500)
        assert updated is not None
        assert updated.remaining_xp == 2000

        # Full consumption
        depleted = manual.consume(2500)
        assert depleted is None

        # Over-consumption
        over_depleted = manual.consume(3000)
        assert over_depleted is None

    def test_usage_window_recording(self) -> None:
        """UsageWindow tracks skill usage."""
        window = UsageWindow.create(window_size=100)

        # Record usage
        window.record(Skill.FIGHTING, amount=5)
        window.record(Skill.AXES, amount=3)

        assert window.counts[Skill.FIGHTING.value] == 5
        assert window.counts[Skill.AXES.value] == 3
        assert window.total_usage == 8

    def test_usage_window_weights(self) -> None:
        """UsageWindow.get_weights normalizes to 1.0."""
        window = UsageWindow.create()
        window.record(Skill.FIGHTING, amount=10)
        window.record(Skill.AXES, amount=5)

        weights: np.ndarray = window.get_weights()

        # Check normalization
        total_weight: float = float(weights.sum())
        assert abs(total_weight - 1.0) < 1e-6

        # Check proportions
        fighting_weight: float = float(weights[Skill.FIGHTING.value])
        axes_weight: float = float(weights[Skill.AXES.value])

        assert abs(fighting_weight - 0.6667) < 0.01  # 10/15
        assert abs(axes_weight - 0.3333) < 0.01  # 5/15

    @pytest.mark.parametrize("weight", [0.0, 1.0, 2.0])
    def test_skill_training_config_set_weight_valid(self, weight: float) -> None:
        """SkillTrainingConfig.set_weight accepts valid weights."""
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_weight(Skill.FIGHTING, weight)
        assert config.weights[Skill.FIGHTING] == weight

    def test_skill_training_config_set_weight_invalid(self) -> None:
        """SkillTrainingConfig.set_weight rejects invalid weights."""
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)

        # Negative weights should be rejected
        with pytest.raises(ValueError, match="Invalid weight"):
            config.set_weight(Skill.FIGHTING, -1.0)

        # Arbitrary positive weights should be rejected
        with pytest.raises(ValueError, match="Invalid weight"):
            config.set_weight(Skill.FIGHTING, 0.5)

        with pytest.raises(ValueError, match="Invalid weight"):
            config.set_weight(Skill.FIGHTING, 1.5)

        with pytest.raises(ValueError, match="Invalid weight"):
            config.set_weight(Skill.FIGHTING, 3.0)

        with pytest.raises(ValueError, match="Invalid weight"):
            config.set_weight(Skill.FIGHTING, 100.0)


class TestPerformance:
    """Performance benchmarks."""

    @pytest.mark.benchmark
    def test_xp_calculation_speed(self) -> None:
        """Benchmark XP calculation."""
        iterations: int = 100000

        def run_xp_calcs() -> None:
            for i in range(iterations):
                calculate_xp_for_level(i % 28, 0)

        time_taken: float = timeit.timeit(run_xp_calcs, number=1)
        ops_per_sec: float = iterations / time_taken

        print(f"\nXP calculations: {ops_per_sec:,.0f} ops/sec")
        assert ops_per_sec > 100000  # Should be >100k ops/sec

    @pytest.mark.benchmark
    def test_combat_bonus_speed(self) -> None:
        """Benchmark combat bonus calculations."""
        iterations: int = 100000

        def run_combat_calcs() -> None:
            for _ in range(iterations):
                calculate_combat_bonuses(10, 15, 8, 12, 6, 10)

        time_taken: float = timeit.timeit(run_combat_calcs, number=1)
        ops_per_sec: float = iterations / time_taken

        print(f"\nCombat bonuses: {ops_per_sec:,.0f} ops/sec")
        assert ops_per_sec > 50000  # Should be >50k ops/sec


# Integration tests


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_typical_character_progression(self) -> None:
        """Simulate typical character skill progression."""
        # Start with 0 XP in Fighting
        fighting_xp: int = 0
        aptitude: int = 0

        # Award XP equivalent to reaching level 10
        target_xp: int = calculate_xp_for_level(10, aptitude)
        fighting_xp = target_xp

        # Verify level
        level: int = calculate_level_from_xp(fighting_xp, aptitude)
        assert level == 10

        # Calculate bonuses
        bonuses = get_combat_bonuses_dict(
            fighting=level,
            weapon=0,
            armour=0,
            dodging=0,
            shields=0,
            base_armor=0,
        )

        assert bonuses.hp_bonus == 10
        assert bonuses.damage_multiplier > 1.0

    def test_cross_training_integration(self) -> None:
        """Test cross-training affects related skills."""
        # Train Axes to level 10
        axes_xp: int = calculate_xp_for_level(10, 0)

        # Calculate cross-training bonus for Maces
        cross_xp: dict[Skill, int] = calculate_cross_training_xp(Skill.AXES, axes_xp)

        # Maces should receive 40% of Axes XP
        maces_bonus: int = cross_xp.get(Skill.MACES_AND_FLAILS, 0)
        expected_bonus: int = int(axes_xp * 0.40)

        assert maces_bonus == expected_bonus

        # This bonus should give Maces some levels
        maces_level: int = calculate_level_from_xp(maces_bonus, 0)
        assert maces_level > 0  # Should be around level 6-7


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "not benchmark"])
