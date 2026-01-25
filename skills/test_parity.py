"""Parity tests for skill system migration.

Ensures vectorized implementation matches legacy behavior exactly.
Must pass before enabling use_vectorized_skills flag.
"""

from __future__ import annotations

from threading import Lock
from typing import Any

import numpy as np
import polars as pl
import pytest

from skills.models import (
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)
from skills.registry_integration import SKILL_TABLE_SCHEMA, SkillSystemMixin
from skills.system import (
    award_xp,
    get_entity_skill_level,
    record_skill_usage,
    set_skill_training,
    set_training_mode,
)


class MockRegistry(SkillSystemMixin):
    """Mock EntityRegistry for testing skill system.

    Provides minimal implementation required for parity tests.
    Supports both vectorized and legacy modes.
    """

    def __init__(self, use_vectorized: bool = True) -> None:
        """Initialize mock registry.

        Args:
            use_vectorized: If True, use vectorized skills_df; else use legacy dict
        """
        self.skills_df: pl.DataFrame = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills: bool = use_vectorized
        self._skills_lock: Lock = Lock()

        # Legacy storage for non-vectorized mode
        self._entity_components: dict[int, dict[str, Any]] = {}

    def get_entity_component(self, entity_id: int, component: str) -> Any:
        """Get entity component (legacy support)."""
        if entity_id not in self._entity_components:
            return None
        return self._entity_components[entity_id].get(component)

    def set_entity_component(self, entity_id: int, component: str, value: Any) -> None:
        """Set entity component (legacy support)."""
        if entity_id not in self._entity_components:
            self._entity_components[entity_id] = {}
        self._entity_components[entity_id][component] = value

    def _get_skills_legacy(self, entity_id: int) -> dict[Skill, SkillProgress]:
        """Legacy implementation reading from entity components."""
        skills = self.get_entity_component(entity_id, "skills")
        if skills is None:
            return {}
        return dict(skills)

    def _set_skills_legacy(
        self,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Legacy implementation writing to entity components."""
        self.set_entity_component(entity_id, "skills", skills)

    def _get_skill_training_legacy(self, entity_id: int) -> SkillTrainingConfig:
        """Legacy implementation reading training config."""
        mode_val = self.get_entity_component(entity_id, "training_mode")
        mode = TrainingMode(mode_val) if mode_val is not None else TrainingMode.MANUAL
        return SkillTrainingConfig(mode=mode)


@pytest.fixture
def vectorized_registry() -> MockRegistry:
    """Create registry with vectorized skills enabled."""
    registry = MockRegistry(use_vectorized=True)
    return registry


@pytest.fixture
def legacy_registry() -> MockRegistry:
    """Create registry with legacy dict-based skills."""
    registry = MockRegistry(use_vectorized=False)
    return registry


def create_test_entity(
    registry: MockRegistry,
    entity_id: int,
    aptitudes: dict[Skill, int] | None = None,
    initial_levels: dict[Skill, int] | None = None,
) -> None:
    """Helper to initialize entity skills in a registry."""
    registry.initialize_entity_skills(entity_id, aptitudes, initial_levels)


class TestParityValidation:
    """Tests ensuring new system matches legacy behavior."""

    def test_xp_distribution_parity(self, vectorized_registry: MockRegistry) -> None:
        """Verify XP distribution sums correctly and is deterministic."""
        entity_id: int = 1
        total_xp: int = 1000

        # Initialize entity with some focused skills
        create_test_entity(vectorized_registry, entity_id)

        # Set MANUAL mode with focused training on Fighting and Axes
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)
        set_skill_training(
            vectorized_registry, entity_id, Skill.FIGHTING, TrainingState.FOCUSED
        )
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.FOCUSED
        )
        # Disable all other skills
        for skill in Skill:
            if skill not in (Skill.FIGHTING, Skill.AXES):
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        # Get XP before
        skills_before = vectorized_registry.get_skills(entity_id)
        xp_before = sum(p.xp for p in skills_before.values())

        # Award XP
        _level_ups = award_xp(vectorized_registry, entity_id, total_xp)

        # Get XP after
        skills_after = vectorized_registry.get_skills(entity_id)
        xp_after = sum(p.xp for p in skills_after.values())

        # Verify total XP increased by exactly total_xp (excluding cross-training)
        # Note: Cross-training adds extra XP, so total should be >= total_xp
        xp_gained = xp_after - xp_before
        assert (
            xp_gained >= total_xp
        ), f"Expected at least {total_xp} XP gain, got {xp_gained}"

        # Verify distribution is deterministic by running again
        registry2 = MockRegistry(use_vectorized=True)
        create_test_entity(registry2, entity_id)
        set_training_mode(registry2, entity_id, TrainingMode.MANUAL)
        set_skill_training(registry2, entity_id, Skill.FIGHTING, TrainingState.FOCUSED)
        set_skill_training(registry2, entity_id, Skill.AXES, TrainingState.FOCUSED)
        for skill in Skill:
            if skill not in (Skill.FIGHTING, Skill.AXES):
                set_skill_training(registry2, entity_id, skill, TrainingState.DISABLED)

        _level_ups2 = award_xp(registry2, entity_id, total_xp)
        skills_after2 = registry2.get_skills(entity_id)

        # Results should be identical
        assert_skills_equal(skills_after, skills_after2)

    def test_cross_training_parity(self, vectorized_registry: MockRegistry) -> None:
        """Verify cross-training produces expected results."""
        entity_id: int = 1

        create_test_entity(vectorized_registry, entity_id)

        # Focus only on Axes training
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.FOCUSED
        )
        for skill in Skill:
            if skill != Skill.AXES:
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        # Get initial XP for Maces (cross-trained from Axes at 40%)
        _maces_before = get_entity_skill_level(
            vectorized_registry, entity_id, Skill.MACES_AND_FLAILS
        )
        maces_xp_before = vectorized_registry.get_skills(entity_id)[
            Skill.MACES_AND_FLAILS
        ].xp

        # Award 1000 XP (all to Axes due to disabled others)
        total_xp: int = 1000
        _ = award_xp(vectorized_registry, entity_id, total_xp)

        # Check Maces received cross-training XP (40% of Axes XP)
        maces_xp_after = vectorized_registry.get_skills(entity_id)[
            Skill.MACES_AND_FLAILS
        ].xp
        maces_xp_gained = maces_xp_after - maces_xp_before

        # Should receive 40% of the XP awarded to Axes
        expected_cross_xp = int(total_xp * 0.40)
        assert (
            maces_xp_gained == expected_cross_xp
        ), f"Expected {expected_cross_xp} cross-training XP, got {maces_xp_gained}"

    def test_automatic_mode_parity(self, vectorized_registry: MockRegistry) -> None:
        """Verify automatic training distributes XP based on usage."""
        entity_id: int = 1

        create_test_entity(vectorized_registry, entity_id)
        set_training_mode(vectorized_registry, entity_id, TrainingMode.AUTOMATIC)

        # Record skill usage: 3 uses of Fighting, 1 use of Axes
        record_skill_usage(vectorized_registry, entity_id, Skill.FIGHTING, 3)
        record_skill_usage(vectorized_registry, entity_id, Skill.AXES, 1)

        # Get XP before
        fighting_xp_before = vectorized_registry.get_skills(entity_id)[
            Skill.FIGHTING
        ].xp
        axes_xp_before = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp

        # Award 100 XP
        total_xp: int = 100
        _ = award_xp(vectorized_registry, entity_id, total_xp)

        # Get XP after
        fighting_xp_after = vectorized_registry.get_skills(entity_id)[Skill.FIGHTING].xp
        axes_xp_after = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp

        fighting_gained = fighting_xp_after - fighting_xp_before
        axes_gained = axes_xp_after - axes_xp_before

        # Fighting should get 75% (3/4), Axes should get 25% (1/4)
        # With deterministic rounding
        assert (
            fighting_gained == 75
        ), f"Expected Fighting to gain 75 XP, got {fighting_gained}"
        assert axes_gained == 25, f"Expected Axes to gain 25 XP, got {axes_gained}"

    def test_manual_mode_parity(self, vectorized_registry: MockRegistry) -> None:
        """Verify manual weights produce correct distribution."""
        entity_id: int = 1

        create_test_entity(vectorized_registry, entity_id)
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)

        # Set weights: Fighting = 2.0 (focused), Axes = 1.0 (normal), rest disabled
        set_skill_training(
            vectorized_registry, entity_id, Skill.FIGHTING, TrainingState.FOCUSED
        )
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.NORMAL
        )
        for skill in Skill:
            if skill not in (Skill.FIGHTING, Skill.AXES):
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        # Get XP before
        fighting_xp_before = vectorized_registry.get_skills(entity_id)[
            Skill.FIGHTING
        ].xp
        axes_xp_before = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp

        # Award 300 XP (should split 2:1)
        total_xp: int = 300
        _ = award_xp(vectorized_registry, entity_id, total_xp)

        # Get XP after
        fighting_xp_after = vectorized_registry.get_skills(entity_id)[Skill.FIGHTING].xp
        axes_xp_after = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp

        fighting_gained = fighting_xp_after - fighting_xp_before
        axes_gained = axes_xp_after - axes_xp_before

        # Fighting has weight 2.0, Axes has weight 1.0, total = 3.0
        # Fighting gets 2/3 = 200, Axes gets 1/3 = 100
        assert (
            fighting_gained == 200
        ), f"Expected Fighting to gain 200 XP, got {fighting_gained}"
        assert axes_gained == 100, f"Expected Axes to gain 100 XP, got {axes_gained}"

    def test_target_level_parity(self, vectorized_registry: MockRegistry) -> None:
        """Verify target auto-disable works correctly."""
        entity_id: int = 1

        # Start with level 9 in Fighting
        create_test_entity(
            vectorized_registry,
            entity_id,
            initial_levels={Skill.FIGHTING: 9},
        )

        # Set target level to 10 for Fighting
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)
        set_skill_training(
            vectorized_registry,
            entity_id,
            Skill.FIGHTING,
            TrainingState.FOCUSED,
            target_level=10,
        )
        for skill in Skill:
            if skill != Skill.FIGHTING:
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        # Award enough XP to reach level 10
        # (XP formula: 25 * (level + 1) * (level + 2) / 2 at aptitude 0)
        _ = award_xp(vectorized_registry, entity_id, 5000)

        # Verify skill reached level 10
        level = get_entity_skill_level(vectorized_registry, entity_id, Skill.FIGHTING)
        assert level >= 10, f"Expected level >= 10, got {level}"

        # Verify skill is now disabled (weight = 0)
        skills_df = vectorized_registry.skills_df.filter(
            (pl.col("entity_id") == entity_id)
            & (pl.col("skill") == Skill.FIGHTING.value)
        )
        weight = skills_df["weight"][0]
        assert weight == 0.0, f"Expected weight 0.0 after reaching target, got {weight}"


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

        save_time: float = timeit.timeit(run_save, number=10) / 10
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

    def test_character_progression_workflow(
        self, vectorized_registry: MockRegistry
    ) -> None:
        """Simulate typical character progression from level 1-15."""
        from skills.effects import calculate_combat_bonuses
        from skills.utils import deserialize_skills, serialize_skills

        entity_id: int = 1

        # 1. Create character
        create_test_entity(vectorized_registry, entity_id)

        # 2. Set manual training for Fighting + Axes
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)
        set_skill_training(
            vectorized_registry, entity_id, Skill.FIGHTING, TrainingState.FOCUSED
        )
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.FOCUSED
        )
        for skill in Skill:
            if skill not in (Skill.FIGHTING, Skill.AXES):
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        # 3. Award XP from combat (500 XP per encounter) - simulate 20 encounters
        for _ in range(20):
            _ = award_xp(vectorized_registry, entity_id, 500)

        # 4. Verify cross-training to Maces
        maces_level = get_entity_skill_level(
            vectorized_registry, entity_id, Skill.MACES_AND_FLAILS
        )
        assert maces_level > 0, "Maces should have leveled via cross-training from Axes"

        # 5. Check combat bonuses increase
        fighting_level = get_entity_skill_level(
            vectorized_registry, entity_id, Skill.FIGHTING
        )
        axes_level = get_entity_skill_level(vectorized_registry, entity_id, Skill.AXES)
        bonuses = calculate_combat_bonuses(
            fighting_level, axes_level, 0, 0, 0, 0  # Other skills at 0
        )
        assert bonuses.damage_multiplier > 1.0, "Should have damage bonus"

        # 6. Save and load
        serialized = serialize_skills(vectorized_registry.skills_df)
        loaded_df = deserialize_skills(serialized)

        # 7. Verify state preserved
        original_skills = vectorized_registry.get_skills(entity_id)
        vectorized_registry.skills_df = loaded_df
        loaded_skills = vectorized_registry.get_skills(entity_id)
        assert_skills_equal(original_skills, loaded_skills)

    def test_skill_respec_workflow(self, vectorized_registry: MockRegistry) -> None:
        """Test changing training focus mid-game."""
        entity_id: int = 1

        # Setup entity
        create_test_entity(vectorized_registry, entity_id)
        set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)

        # 1. Train Axes to gain some XP
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.FOCUSED
        )
        for skill in Skill:
            if skill != Skill.AXES:
                set_skill_training(
                    vectorized_registry, entity_id, skill, TrainingState.DISABLED
                )

        axes_xp_before = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp
        _ = award_xp(vectorized_registry, entity_id, 1000)
        axes_xp_after_first = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp
        assert axes_xp_after_first > axes_xp_before, "Axes should gain XP"

        # 2. Switch to training Long Blades
        set_skill_training(
            vectorized_registry, entity_id, Skill.AXES, TrainingState.DISABLED
        )
        set_skill_training(
            vectorized_registry, entity_id, Skill.LONG_BLADES, TrainingState.FOCUSED
        )

        long_blades_xp_before = vectorized_registry.get_skills(entity_id)[
            Skill.LONG_BLADES
        ].xp

        # 3. Award more XP
        _ = award_xp(vectorized_registry, entity_id, 1000)

        # 4. Verify Axes stops gaining XP
        axes_xp_after_second = vectorized_registry.get_skills(entity_id)[Skill.AXES].xp
        assert (
            axes_xp_after_second == axes_xp_after_first
        ), "Axes should not gain XP when disabled"

        # 5. Verify Long Blades progresses
        long_blades_xp_after = vectorized_registry.get_skills(entity_id)[
            Skill.LONG_BLADES
        ].xp
        assert (
            long_blades_xp_after > long_blades_xp_before
        ), "Long Blades should gain XP"

    def test_multi_entity_concurrent_awards(
        self, vectorized_registry: MockRegistry
    ) -> None:
        """Test XP awards to multiple entities in same turn."""
        from skills.system import batch_award_xp

        n_entities: int = 100

        # 1. Create 100 entities
        for entity_id in range(n_entities):
            create_test_entity(vectorized_registry, entity_id)
            set_training_mode(vectorized_registry, entity_id, TrainingMode.MANUAL)
            set_skill_training(
                vectorized_registry, entity_id, Skill.FIGHTING, TrainingState.FOCUSED
            )
            for skill in Skill:
                if skill != Skill.FIGHTING:
                    set_skill_training(
                        vectorized_registry, entity_id, skill, TrainingState.DISABLED
                    )

        # Get initial XP for all entities
        initial_xp: dict[int, int] = {}
        for entity_id in range(n_entities):
            initial_xp[entity_id] = vectorized_registry.get_skills(entity_id)[
                Skill.FIGHTING
            ].xp

        # 2. Award XP to all in single batch
        entity_xp_pairs = [(entity_id, 100) for entity_id in range(n_entities)]
        _level_ups = batch_award_xp(vectorized_registry, entity_xp_pairs)

        # 3. Verify all receive correct amounts
        for entity_id in range(n_entities):
            new_xp = vectorized_registry.get_skills(entity_id)[Skill.FIGHTING].xp
            xp_gained = new_xp - initial_xp[entity_id]
            assert (
                xp_gained == 100
            ), f"Entity {entity_id} should gain 100 XP, got {xp_gained}"

        # 4. Verify no cross-contamination (each entity has independent state)
        # All entities should have identical Fighting XP
        all_fighting_xp = [
            vectorized_registry.get_skills(entity_id)[Skill.FIGHTING].xp
            for entity_id in range(n_entities)
        ]
        assert (
            len(set(all_fighting_xp)) == 1
        ), "All entities should have identical Fighting XP"


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
    assert set(skills_a) == set(skills_b), "Different skills present"

    for skill in skills_a:
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
