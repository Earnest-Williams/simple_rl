"""Tests for the skill system."""

import pytest

from game.skills.models import (
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)
from game.skills.progression import (
    get_xp_for_level,
    get_level_from_xp,
    get_aptitude_multiplier,
    apply_xp_to_skill,
    get_xp_to_next_level,
)
from game.skills.training import distribute_xp
from game.skills.effects import (
    get_fighting_bonus_hp,
    get_fighting_bonus_damage,
    calculate_total_combat_bonuses,
    calculate_total_magic_bonuses,
)


class TestSkillProgression:
    """Test XP tables and progression formulas."""

    def test_xp_for_level_returns_correct_values(self) -> None:
        """Verify XP table matches DCSS formula."""
        assert get_xp_for_level(0) == 0
        assert get_xp_for_level(1) == 50
        assert get_xp_for_level(5) == 750
        assert get_xp_for_level(10) == 2750
        assert get_xp_for_level(15) == 6000
        assert get_xp_for_level(20) == 10500
        assert get_xp_for_level(27) == 18900

    def test_get_level_from_xp(self) -> None:
        """Test level calculation from XP."""
        assert get_level_from_xp(0) == 0
        assert get_level_from_xp(50) == 1
        assert get_level_from_xp(749) == 4
        assert get_level_from_xp(750) == 5
        assert get_level_from_xp(10425) == 20
        assert get_level_from_xp(100000) == 27  # Caps at 27

    def test_aptitude_multiplier(self) -> None:
        """Test aptitude multiplier formula."""
        # Aptitude 0 = no change
        assert get_aptitude_multiplier(0) == 1.0

        # Aptitude +4 halves cost
        assert abs(get_aptitude_multiplier(4) - 0.5) < 0.001

        # Aptitude -4 doubles cost
        assert abs(get_aptitude_multiplier(-4) - 2.0) < 0.001

        # Aptitude +8 quarters cost
        assert abs(get_aptitude_multiplier(8) - 0.25) < 0.001

    def test_apply_xp_to_skill_basic(self) -> None:
        """Test applying XP to a skill."""
        # Start at 0 XP, add 750 XP (should reach level 5)
        new_xp, old_level, new_level = apply_xp_to_skill(0, 750, aptitude=0)
        assert new_level == 5
        assert old_level == 0
        assert new_xp == 750.0

    def test_apply_xp_to_skill_with_aptitude(self) -> None:
        """Test XP application with aptitude modifier."""
        # With +4 aptitude, 750 raw XP becomes 1500 effective XP
        # (multiplier = 0.5, so XP / 0.5 = XP * 2)
        new_xp, old_level, new_level = apply_xp_to_skill(0, 750, aptitude=4)
        # 1500 XP gets to level 8 (1800 needed for 8, 1400 for 7)
        assert new_level == 7
        assert new_xp == 1500.0

    def test_apply_xp_caps_at_max_level(self) -> None:
        """Test that XP doesn't exceed max level."""
        # Start at level 27, try to add more XP
        current_xp = get_xp_for_level(27)
        new_xp, old_level, new_level = apply_xp_to_skill(
            current_xp, 10000, aptitude=0
        )
        assert new_level == 27
        assert old_level == 27

    def test_get_xp_to_next_level(self) -> None:
        """Test XP needed to reach next level."""
        # At level 0 with 0 XP, need 50 to reach level 1
        assert get_xp_to_next_level(0, 0.0) == 50.0

        # At level 5 with 750 XP, need 300 to reach level 6
        assert get_xp_to_next_level(5, 750.0) == 300.0

        # At max level, need 0 XP
        assert get_xp_to_next_level(27, get_xp_for_level(27)) == 0.0


class TestSkillTraining:
    """Test training modes and XP distribution."""

    def test_manual_mode_single_skill(self) -> None:
        """Test manual training with one skill enabled."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.FIGHTING, TrainingState.ENABLED)

        # Award 750 XP, all should go to Fighting
        level_changes = distribute_xp(750.0, skills, config)

        assert Skill.FIGHTING in skills
        assert skills[Skill.FIGHTING].level == 5
        assert level_changes[Skill.FIGHTING] == (0, 5)

    def test_manual_mode_multiple_skills(self) -> None:
        """Test manual training splits XP evenly."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.FIGHTING, TrainingState.ENABLED)
        config.set_training_state(Skill.DODGING, TrainingState.ENABLED)

        # Award 1500 XP, should split 750 each
        level_changes = distribute_xp(1500.0, skills, config)

        assert Skill.FIGHTING in skills
        assert Skill.DODGING in skills
        assert skills[Skill.FIGHTING].level == 5
        assert skills[Skill.DODGING].level == 5

    def test_manual_mode_focused_gets_double(self) -> None:
        """Test focused skill gets 2x share."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.FIGHTING, TrainingState.ENABLED)  # 1x
        config.set_training_state(Skill.DODGING, TrainingState.FOCUSED)  # 2x

        # Total weight = 3 (1 + 2), so Fighting gets 1/3, Dodging gets 2/3
        # Award 1500 XP: Fighting gets 500, Dodging gets 1000
        level_changes = distribute_xp(1500.0, skills, config)

        # 500 XP gets to level 4
        assert skills[Skill.FIGHTING].level == 4
        # 1000 XP gets to level 6
        assert skills[Skill.DODGING].level == 6

    def test_disabled_skill_gets_no_xp(self) -> None:
        """Test disabled skills don't receive XP."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.FIGHTING, TrainingState.ENABLED)
        config.set_training_state(Skill.DODGING, TrainingState.DISABLED)

        distribute_xp(1500.0, skills, config)

        assert Skill.FIGHTING in skills
        assert Skill.DODGING not in skills  # Should not be trained at all

    def test_target_level_disables_training(self) -> None:
        """Test that reaching target level disables training."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.FIGHTING, TrainingState.ENABLED)
        config.set_target_level(Skill.FIGHTING, 5)

        # Award enough XP to reach level 5
        distribute_xp(750.0, skills, config)

        # Should be disabled now
        assert config.get_training_state(Skill.FIGHTING) == TrainingState.DISABLED
        assert config.get_target_level(Skill.FIGHTING) is None

    def test_cross_training_bonus(self) -> None:
        """Test that cross-training works correctly."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.MANUAL)
        config.set_training_state(Skill.MACES_AND_FLAILS, TrainingState.ENABLED)

        # Award XP to Maces & Flails, should also train Axes and Staves
        distribute_xp(1000.0, skills, config)

        assert Skill.MACES_AND_FLAILS in skills
        assert Skill.AXES in skills  # Cross-trained at 25%
        assert Skill.STAVES in skills  # Cross-trained at 25%

        # Maces gets full XP
        maces_level = skills[Skill.MACES_AND_FLAILS].level
        # Axes and Staves get 25% bonus
        axes_level = skills[Skill.AXES].level
        staves_level = skills[Skill.STAVES].level

        # Axes and Staves should have lower levels due to partial XP
        assert axes_level < maces_level
        assert staves_level < maces_level
        assert axes_level > 0  # But still gained some levels
        assert staves_level > 0

    def test_automatic_mode_uses_recent_usage(self) -> None:
        """Test automatic mode distributes based on usage."""
        skills = {}
        config = SkillTrainingConfig(mode=TrainingMode.AUTOMATIC)

        # Record usage: Fighting used 10 times, Dodging used 5 times
        config.record_usage(Skill.FIGHTING, 10)
        config.record_usage(Skill.DODGING, 5)

        # Total usage = 15, so Fighting gets 2/3, Dodging gets 1/3
        # Award 1500 XP: Fighting gets 1000, Dodging gets 500
        distribute_xp(1500.0, skills, config)

        # 1000 XP gets to level 6
        assert skills[Skill.FIGHTING].level == 6
        # 500 XP gets to level 4
        assert skills[Skill.DODGING].level == 4

        # Usage should be cleared after distribution
        assert len(config.recent_usage) == 0


class TestSkillEffects:
    """Test skill effect calculations."""

    def test_fighting_bonus_hp(self) -> None:
        """Test HP bonus from Fighting skill."""
        assert get_fighting_bonus_hp(0) == 0
        assert get_fighting_bonus_hp(10) == 10
        assert get_fighting_bonus_hp(27) == 27

    def test_fighting_bonus_damage(self) -> None:
        """Test damage multiplier from Fighting skill."""
        assert get_fighting_bonus_damage(0) == 1.0
        assert abs(get_fighting_bonus_damage(10) - 1.1) < 0.001
        assert abs(get_fighting_bonus_damage(27) - 1.27) < 0.001

    def test_calculate_total_combat_bonuses(self) -> None:
        """Test total combat bonus calculation."""
        skills = {
            Skill.FIGHTING: SkillProgress(level=10, xp_invested=2750.0),
            Skill.LONG_BLADES: SkillProgress(level=15, xp_invested=6000.0),
            Skill.DODGING: SkillProgress(level=8, xp_invested=1800.0),
            Skill.SHIELDS: SkillProgress(level=9, xp_invested=2250.0),
            Skill.ARMOUR: SkillProgress(level=12, xp_invested=3900.0),
        }

        # Test with base armor
        bonuses = calculate_total_combat_bonuses(
            skills, weapon_skill=Skill.LONG_BLADES, base_armor=10
        )

        # HP bonus from Fighting level 10
        assert bonuses["hp_bonus"] == 10

        # Damage multiplier from Fighting (1.1x) and Long Blades (1.3x)
        # Total = 1.1 * 1.3 = 1.43
        assert abs(bonuses["damage_multiplier"] - 1.43) < 0.01

        # Accuracy from Fighting (10//2 = 5) and Long Blades (15)
        assert bonuses["accuracy_bonus"] == 20

        # Defense from Shields (9 // 3 = 3)
        assert bonuses["defense_bonus"] == 3

        # Armor from Armour skill (12 * 0.03 * 10 = 3.6, rounded to 3)
        # Formula: int(base_armor * (1 + level * 0.03)) - base_armor
        # = int(10 * 1.36) - 10 = 13 - 10 = 3
        assert bonuses["armor_bonus"] == 3

        # Evasion from Dodging level 8
        assert bonuses["evasion_bonus"] == 8

    def test_calculate_total_magic_bonuses(self) -> None:
        """Test total magic bonus calculation."""
        skills = {
            Skill.SPELLCASTING: SkillProgress(level=10, xp_invested=2775.0),
            Skill.FIRE_MAGIC: SkillProgress(level=12, xp_invested=3925.0),
        }

        bonuses = calculate_total_magic_bonuses(skills, Skill.FIRE_MAGIC)

        # MP bonus from Spellcasting level 10
        assert bonuses["mp_bonus"] == 10.0

        # Spell power from Spellcasting (1.15x) and Fire Magic (1.24x)
        # Total = 1.15 * 1.24 = 1.426
        assert abs(bonuses["spell_power_multiplier"] - 1.426) < 0.01

    def test_invocations_provides_mp_bonus(self) -> None:
        """Test that Invocations provides MP (half of Spellcasting rate)."""
        # Invocations only
        skills = {
            Skill.INVOCATIONS: SkillProgress(level=20, xp_invested=10425.0),
        }
        bonuses = calculate_total_magic_bonuses(skills)
        assert bonuses["mp_bonus"] == 10.0  # 20 / 2

        # Both Spellcasting and Invocations (take max)
        skills[Skill.SPELLCASTING] = SkillProgress(level=12, xp_invested=3925.0)
        bonuses = calculate_total_magic_bonuses(skills)
        assert bonuses["mp_bonus"] == 12.0  # Max of 12 and 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
