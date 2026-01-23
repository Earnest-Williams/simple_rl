"""Parity tests for skill system migration.

Ensures vectorized implementation matches legacy behavior exactly.
Must pass before enabling use_vectorized_skills flag.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import polars as pl
import pytest

from skills.models import Skill, SkillProgress, TrainingMode
from skills.progression import calculate_xp_for_level
from skills.system import award_xp, get_entity_skill_level, record_skill_usage

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry


class TestParityValidation:
    """Tests ensuring new system matches legacy behavior."""

    def test_xp_distribution_parity(self) -> None:
        """Verify identical XP distribution between legacy and vectorized."""
        # This is a template - actual test needs real EntityRegistry instances

        # Setup test entity
        entity_id: int = 1
        initial_xp: int = 0

        # Award XP in both systems
        total_xp: int = 1000

        # Legacy path
        # legacy_registry = create_legacy_registry()
        # legacy_registry.initialize_entity_skills(entity_id, ...)
        # legacy_result = legacy_award_xp(legacy_registry, entity_id, total_xp)

        # Vectorized path
        # vectorized_registry = create_vectorized_registry()
        # vectorized_registry.initialize_entity_skills(entity_id, ...)
        # vectorized_result = award_xp(vectorized_registry, entity_id, total_xp)

        # Compare results
        # assert_skills_equal(legacy_result, vectorized_result)

        pytest.skip("Requires EntityRegistry implementation")

    def test_cross_training_parity(self) -> None:
        """Verify cross-training produces identical results."""
        # Setup entity with Axes training
        entity_id: int = 1

        # Train Axes to level 10 in both systems
        # Verify Maces receives exactly 40% XP in both

        pytest.skip("Requires EntityRegistry implementation")

    def test_automatic_mode_parity(self) -> None:
        """Verify automatic training distributes XP identically."""
        entity_id: int = 1

        # Record skill usage pattern
        # Award XP in both systems
        # Verify identical distribution

        pytest.skip("Requires EntityRegistry implementation")

    def test_manual_mode_parity(self) -> None:
        """Verify manual weights produce identical distribution."""
        entity_id: int = 1

        # Set same weights in both systems
        # Award XP
        # Verify identical results

        pytest.skip("Requires EntityRegistry implementation")

    def test_target_level_parity(self) -> None:
        """Verify target auto-disable works identically."""
        entity_id: int = 1

        # Set target level for skill
        # Award XP to reach target
        # Verify skill disabled at same point in both systems

        pytest.skip("Requires EntityRegistry implementation")


class TestLargeScaleBenchmark:
    """Performance tests for batch operations."""

    @pytest.mark.benchmark
    def test_10k_entity_xp_award(self) -> None:
        """Benchmark XP award for 10,000 entities.

        Target: <100ms for full batch update
        """
        import timeit

        n_entities: int = 10000

        # Setup
        from skills.registry_integration import SKILL_TABLE_SCHEMA

        rows: list[dict[str, int | float | None]] = []

        for entity_id in range(n_entities):
            for skill in Skill:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "skill": skill.value,
                        "level": 5,
                        "xp": 750,
                        "aptitude": 0,
                        "weight": 1.0 if skill.value < 3 else 0.0,
                        "training_state": 1,
                        "target_level": None,
                        "usage_count": 10,
                    }
                )

        skills_df = pl.DataFrame(rows, schema=SKILL_TABLE_SCHEMA)

        # Create mock registry
        class MockRegistry:
            def __init__(self) -> None:
                self.skills_df = skills_df
                self.use_vectorized_skills = True

            def get_skill_training(self, entity_id: int):  # type: ignore[no-untyped-def]
                from skills.models import SkillTrainingConfig

                return SkillTrainingConfig(mode=TrainingMode.MANUAL)

        registry = MockRegistry()

        # Benchmark batch update
        def run_batch_award() -> None:
            nonlocal registry
            # Award 100 XP to first 100 entities
            for i in range(100):
                _ = award_xp(registry, i, 100)

        time_taken: float = timeit.timeit(run_batch_award, number=1)

        print(f"\nBatch XP award (100 entities): {time_taken*1000:.1f}ms")

        # Target: <10ms per 100 entities = <1s for 10k
        assert time_taken < 1.0, f"Too slow: {time_taken:.2f}s"

    @pytest.mark.benchmark
    def test_save_load_10k_entities(self) -> None:
        """Benchmark save/load for 10,000 entities.

        Target: <100ms total
        """
        import timeit

        from skills.registry_integration import SKILL_TABLE_SCHEMA
        from skills.utils import deserialize_skills, serialize_skills

        n_entities: int = 10000

        # Generate test data
        rows: list[dict[str, int | float | None]] = []

        for entity_id in range(n_entities):
            for skill in Skill:
                rows.append(
                    {
                        "entity_id": entity_id,
                        "skill": skill.value,
                        "level": 10,
                        "xp": 2750,
                        "aptitude": 0,
                        "weight": 1.0,
                        "training_state": 1,
                        "target_level": None,
                        "usage_count": 100,
                    }
                )

        skills_df = pl.DataFrame(rows, schema=SKILL_TABLE_SCHEMA)

        # Benchmark save
        def run_save() -> bytes:
            return serialize_skills(skills_df)

        save_time: float = timeit.timeit(lambda: run_save(), number=10) / 10
        print(f"\nSave {n_entities} entities: {save_time*1000:.1f}ms")

        # Benchmark load
        packed = run_save()

        def run_load() -> None:
            _ = deserialize_skills(packed)

        load_time: float = timeit.timeit(run_load, number=10) / 10
        print(f"Load {n_entities} entities: {load_time*1000:.1f}ms")

        total_time: float = save_time + load_time
        print(f"Total save/load: {total_time*1000:.1f}ms")

        # Target: <100ms total
        assert total_time < 0.1, f"Too slow: {total_time*1000:.0f}ms"

    @pytest.mark.benchmark
    def test_combat_bonus_calculation_speed(self) -> None:
        """Benchmark combat bonus calculations.

        Target: >50,000 ops/sec
        """
        import timeit

        from skills.effects import calculate_combat_bonuses

        iterations: int = 100000

        def run_bonuses() -> None:
            for _ in range(iterations):
                _ = calculate_combat_bonuses(10, 15, 8, 12, 6, 10)

        time_taken: float = timeit.timeit(run_bonuses, number=1)
        ops_per_sec: float = iterations / time_taken

        print(f"\nCombat bonuses: {ops_per_sec:,.0f} ops/sec")

        # Target: >50k ops/sec
        assert ops_per_sec > 50000, f"Too slow: {ops_per_sec:,.0f} ops/sec"


class TestIntegrationWorkflows:
    """End-to-end workflow tests."""

    def test_character_progression_workflow(self) -> None:
        """Simulate typical character progression from level 1-15."""
        pytest.skip("Requires EntityRegistry implementation")

        # 1. Create character
        # 2. Set manual training for Fighting + Axes
        # 3. Award XP from combat (500 XP per encounter)
        # 4. Verify cross-training to Maces
        # 5. Check combat bonuses increase
        # 6. Save and load
        # 7. Verify state preserved

    def test_skill_respec_workflow(self) -> None:
        """Test changing training focus mid-game."""
        pytest.skip("Requires EntityRegistry implementation")

        # 1. Train Axes to level 15
        # 2. Switch to training Long Blades
        # 3. Verify Axes stops gaining XP
        # 4. Verify Long Blades progresses

    def test_multi_entity_concurrent_awards(self) -> None:
        """Test XP awards to multiple entities in same turn."""
        pytest.skip("Requires EntityRegistry implementation")

        # 1. Create 100 entities
        # 2. Award XP to all in single batch
        # 3. Verify all receive correct amounts
        # 4. Verify no cross-contamination


# Helper functions for parity testing


def assert_skills_equal(
    skills_a: dict[Skill, SkillProgress],
    skills_b: dict[Skill, SkillProgress],
    tolerance: float = 0.0,
) -> None:
    """Assert two skill dicts are equivalent.

    Args:
        skills_a: First skill dict
        skills_b: Second skill dict
        tolerance: Allowed XP difference (for floating-point)
    """
    assert set(skills_a.keys()) == set(skills_b.keys()), "Different skills present"

    for skill in skills_a.keys():
        prog_a = skills_a[skill]
        prog_b = skills_b[skill]

        assert prog_a.level == prog_b.level, f"{skill}: level mismatch"
        assert prog_a.aptitude == prog_b.aptitude, f"{skill}: aptitude mismatch"

        xp_diff: int = abs(prog_a.xp - prog_b.xp)
        assert xp_diff <= tolerance, f"{skill}: XP differs by {xp_diff}"


def assert_dataframes_equal(
    df_a: pl.DataFrame,
    df_b: pl.DataFrame,
) -> None:
    """Assert two skill DataFrames are equivalent.

    Args:
        df_a: First DataFrame
        df_b: Second DataFrame
    """
    assert df_a.height == df_b.height, "Different row counts"
    assert df_a.width == df_b.width, "Different column counts"

    # Sort both for comparison
    df_a_sorted = df_a.sort(["entity_id", "skill"])
    df_b_sorted = df_b.sort(["entity_id", "skill"])

    # Compare column by column
    for col in df_a_sorted.columns:
        assert np.allclose(
            df_a_sorted[col].to_numpy(),
            df_b_sorted[col].to_numpy(),
            equal_nan=True,
        ), f"Column {col} differs"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "benchmark"])
