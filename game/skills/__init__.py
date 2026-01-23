"""Compatibility shim for migrating from `game.skills` -> top-level `skills`.

Older code may import `game.skills.*`; this module forwards those names
to the new, vectorized `skills` package while preserving the historical
call signatures where necessary.

This file is temporary during migration and can be removed once the rest
of the codebase imports `skills` directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# Models & types ---------------------------------------------------------
from skills.models import (
    Skill,
    SkillCategory,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)

# Progression (map old names to the new progression API)
from skills.progression import (
    calculate_level_from_xp,
    calculate_xp_for_level,
    calculate_xp_to_next_level,
    get_aptitude_multiplier,
)

# System / high-level operations
from skills.system import (
    award_xp,
    batch_award_xp,
    record_skill_usage,
    set_skill_training,
    set_training_mode,
)

# Effects (wrap the new return types into the old dicts/dataclasses expected)
from skills.effects import (
    get_combat_bonuses_dict as _get_combat_bonuses_dict,
    get_magic_bonuses_dict as _get_magic_bonuses_dict,
)

# Registry integration helpers (for initializing entity skills)
from skills.registry_integration import SkillSystemMixin

if TYPE_CHECKING:
    from typing import Any


# Compatibility wrappers -------------------------------------------------


def get_xp_for_level(level: int) -> int:
    """Compatibility: old name -> new calculate_xp_for_level."""
    return int(calculate_xp_for_level(level, 0))


def get_level_from_xp(xp: int) -> int:
    """Compatibility: old name -> new calculate_level_from_xp.

    Note: old API did not take aptitude; this returns the level assuming aptitude
    0. For aptitude-aware queries use calculate_level_from_xp from skills.progression.
    """
    return int(calculate_level_from_xp(int(xp), 0))  # Explicitly cast to int


def get_xp_to_next_level(current_level: int, current_xp: int) -> int:
    """Compatibility wrapper that calls calculate_xp_to_next_level."""
    # Note: old signature passed (current_level, current_xp). The new function
    # expects (xp, aptitude). We take a best-effort approach assuming aptitude 0.
    return int(calculate_xp_to_next_level(int(current_xp), 0))  # Explicitly cast to int


def initialize_entity_skills(
    entity_registry: Any,
    entity_id: int,
    initial_skills: dict[Skill, tuple[int, int]] | None = None,
    training_mode: TrainingMode = TrainingMode.MANUAL,
) -> None:
    """
    Compatibility initializer. Old signature:
        initialize_entity_skills(entity_registry, entity_id, initial_skills, training_mode)

    New preferred flow is to call registry.initialize_entity_skills(...) (method added by
    skills.registry_integration). This wrapper:
      - accepts the legacy `initial_skills` mapping Skill -> (level, aptitude)
      - converts it to the new `aptitudes` and `initial_levels` shape
      - calls registry.initialize_entity_skills(...) if present, otherwise calls the
        unbound SkillSystemMixin implementation so older registries can be initialized.
    """
    aptitudes: dict[Skill, int] = {}
    initial_levels: dict[Skill, int] = {}

    if initial_skills:
        for skill, (level, aptitude) in initial_skills.items():
            initial_levels[skill] = int(level)
            aptitudes[skill] = int(aptitude)

    # If registry already supplies an initialize_entity_skills method, use it.
    if hasattr(entity_registry, "initialize_entity_skills"):
        # Signature from registry_integration:
        # initialize_entity_skills(self, entity_id, aptitudes=None, initial_levels=None, use_species_aptitudes=True)
        entity_registry.initialize_entity_skills(
            entity_id=entity_id,
            aptitudes=aptitudes,
            initial_levels=initial_levels,
            use_species_aptitudes=True,
        )
        return

    # Otherwise, call the mixin's unbound implementation directly.
    SkillSystemMixin.initialize_entity_skills(
        entity_registry,
        entity_id,
        aptitudes=aptitudes,
        initial_levels=initial_levels,
        use_species_aptitudes=True,
    )


def get_entity_skill_level(entity_registry: Any, entity_id: int, skill: Skill) -> int:
    """Compatibility: returns skill level (0 if not present)."""
    # Prefer registry.get_skills()
    skills: dict[Skill, SkillProgress] | None = None
    if hasattr(entity_registry, "get_skills"):
        skills = entity_registry.get_skills(entity_id)
    else:
        # fallback to component-based access if implemented
        try:
            skills = entity_registry.get_entity_component(entity_id, "skills")
        except (AttributeError, KeyError): # Catch specific exceptions
            skills = None

    if not skills:
        return 0

    prog: SkillProgress | None = skills.get(skill)
    return int(prog.level) if prog else 0


def calculate_total_combat_bonuses(
    skills_map: dict[Skill, SkillProgress],
    weapon_skill: Skill | None = None,
    base_armor: int = 0,
) -> dict[str, int | float]:
    """Compatibility wrapper returning the old dict shape."""
    fighting: SkillProgress | None = skills_map.get(Skill.FIGHTING)
    fighting_lvl: int = int(fighting.level) if fighting else 0

    weapon_lvl: int = 0
    if weapon_skill and weapon_skill in skills_map:
        weapon_lvl = int(skills_map[weapon_skill].level)

    armour: SkillProgress | None = skills_map.get(Skill.ARMOUR)
    armour_lvl: int = int(armour.level) if armour else 0

    dodging: SkillProgress | None = skills_map.get(Skill.DODGING)
    dodging_lvl: int = int(dodging.level) if dodging else 0

    shields: SkillProgress | None = skills_map.get(Skill.SHIELDS)
    shields_lvl: int = int(shields.level) if shields else 0

    cb = _get_combat_bonuses_dict(
        fighting=fighting_lvl,
        weapon=weapon_lvl,
        armour=armour_lvl,
        dodging=dodging_lvl,
        shields=shields_lvl,
        base_armor=base_armor,
    )

    return {
        "hp_bonus": cb.hp_bonus,
        "damage_multiplier": cb.damage_multiplier,
        "accuracy_bonus": cb.accuracy_bonus,
        "defense_bonus": cb.shield_defense,
        "armor_bonus": cb.armor_bonus,
        "evasion_bonus": cb.evasion_bonus,
    }


def calculate_total_magic_bonuses(
    skills_map: dict[Skill, SkillProgress],
    magic_school: Skill | None = None,
) -> dict[str, int | float]:
    """Compatibility wrapper returning old dict shape for magic bonuses."""
    spellcasting: SkillProgress | None = skills_map.get(Skill.SPELLCASTING)
    spellcasting_lvl: int = int(spellcasting.level) if spellcasting else 0

    invocations: SkillProgress | None = skills_map.get(Skill.INVOCATIONS)
    invocations_lvl: int = int(invocations.level) if invocations else 0

    school_lvl: int = 0
    if magic_school and magic_school in skills_map:
        school_lvl = int(skills_map[magic_school].level)

    mb = _get_magic_bonuses_dict(
        spellcasting=spellcasting_lvl,
        school=school_lvl,
        invocations=invocations_lvl,
        xl_multiplier=1.0,  # default species-xl multiplier; callers who need species should call into the new API
        school_weight=2.0,  # default weight (old API used simple multipliers)
    )

    return {
        "mp_bonus": mb.mp_bonus,
        "spell_power_multiplier": mb.spell_power,
    }


# Public API exposed by old game.skills.__init__.py --------------------------------
__all__ = [
    # Models
    "Skill",
    "SkillCategory",
    "TrainingMode",
    "TrainingState",
    "SkillProgress",
    "SkillTrainingConfig",
    # Progression
    "calculate_xp_for_level",
    "calculate_level_from_xp",
    "get_aptitude_multiplier",
    "calculate_xp_to_next_level",
    "get_xp_for_level",
    "get_level_from_xp",
    "get_xp_to_next_level",
    # System
    "initialize_entity_skills",
    "award_xp",
    "batch_award_xp",
    "set_skill_training",
    "set_training_mode",
    "record_skill_usage",
    "get_entity_skill_level",
    # Effects
    "calculate_total_combat_bonuses",
    "calculate_total_magic_bonuses",
]
