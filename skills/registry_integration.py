"""EntityRegistry integration for vectorized skill system.

Adds skills_df DataFrame alongside existing entities_df.skills for backward compatibility.
Implements dual-mode operation during migration.

Thread safety: All mutation methods acquire self._skills_lock when present.
"""

from __future__ import annotations

import logging
from contextlib import nullcontext
from threading import Lock
from typing import Any, Final, Protocol

import polars as pl

from skills.models import (
    MAX_SKILL_LEVEL,
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)

# Sentinel value for nullable UInt8 columns
# Since Polars UInt8 cannot represent null natively, we use 255 as a sentinel
# to represent "no target level set" in the target_level column.
NULL_U8_SENTINEL: Final[int] = 255


def normalize_target_level_to_python(value: int | None) -> int | None:
    """Convert target_level from Polars representation to Python.

    Args:
        value: Target level from Polars row (may be None or NULL_U8_SENTINEL)

    Returns:
        Python int if valid target, None if no target set
    """
    if value is None:
        return None
    # Convert to int and check for sentinel
    int_val: int = int(value)
    if int_val == NULL_U8_SENTINEL:
        return None
    return int_val


def normalize_target_level_to_polars(value: int | None) -> int | None:
    """Convert target_level from Python to Polars representation.

    Args:
        value: Python int or None

    Returns:
        None (Polars will use NULL_U8_SENTINEL when schema enforces UInt8)
    """
    # When writing None to a UInt8 column with NULL_U8_SENTINEL as null representation,
    # Polars handles the conversion automatically in the schema
    return value


# Skill table schema for EntityRegistry.skills_df
SKILL_TABLE_SCHEMA: Final[dict[str, type[pl.DataType]]] = {
    "entity_id": pl.UInt32,
    "skill": pl.UInt8,  # Store Skill.value for memory efficiency
    "level": pl.UInt8,
    "xp": pl.UInt32,
    "aptitude": pl.Int8,
    "weight": pl.Float32,
    "training_state": pl.UInt8,  # Store TrainingState.value
    "target_level": pl.UInt8,  # Nullable (use NULL_U8_SENTINEL=255 for null)
    "usage_count": pl.UInt32,
}


class SkillRegistryHost(Protocol):
    """Protocol defining the interface a registry must implement to host the skill system.

    This makes the dependency between SkillSystemMixin and EntityRegistry explicit
    and type-safe, avoiding the need for hasattr checks and type: ignore comments.
    """

    skills_df: pl.DataFrame
    use_vectorized_skills: bool
    _skills_lock: Lock

    def get_entity_component(self, entity_id: int, component: str) -> Any:
        """Retrieve a component value for an entity."""
        ...

    def set_entity_component(self, entity_id: int, component: str, value: Any) -> None:
        """Set a component value for an entity."""
        ...

    def get_skill_training(self, entity_id: int) -> SkillTrainingConfig | None:
        """Get entity's training configuration."""
        ...


class SkillSystemMixin:
    """Mixin to add to EntityRegistry for skill system support.

    Methods in this mixin expect self to implement SkillRegistryHost Protocol.
    This ensures type-safe access to registry methods without hasattr checks.

    Add this to EntityRegistry.__init__:
        self.skills_df: pl.DataFrame = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills: bool = False  # Feature flag
        self._skills_lock: Lock = Lock()  # Thread safety for skills_df mutations
    """

    def initialize_entity_skills(
        self: SkillRegistryHost,
        entity_id: int,
        aptitudes: dict[Skill, int] | None = None,
        initial_levels: dict[Skill, int] | None = None,
        use_species_aptitudes: bool = True,
    ) -> None:
        """Initialize all 29 skills for an entity.

        Thread-safe: Acquires self._skills_lock if present.

        Args:
            entity_id: Entity to initialize
            aptitudes: Skill aptitude modifiers (overrides species aptitudes)
            initial_levels: Starting skill levels (default: 0 for all)
            use_species_aptitudes: Auto-detect species and apply aptitudes
        """
        if aptitudes is None:
            aptitudes = {}
        if initial_levels is None:
            initial_levels = {}

        # Auto-detect species aptitudes if enabled
        if use_species_aptitudes and not aptitudes:
            species = self.get_entity_component(entity_id, "species")  # type: ignore[attr-defined]
            if species:
                from skills.species_aptitudes import get_species_aptitudes

                species_apts = get_species_aptitudes(species)
                # Use species aptitudes as base, allow overrides
                aptitudes = species_apts

        # Build initial skill rows
        rows: list[dict[str, int | float | None]] = []

        for skill in Skill:
            aptitude: int = aptitudes.get(skill, 0)
            level: int = initial_levels.get(skill, 0)

            # Calculate initial XP for level
            from skills.progression import calculate_xp_for_level

            xp: int = calculate_xp_for_level(level, aptitude)

            rows.append(
                {
                    "entity_id": entity_id,
                    "skill": skill.value,
                    "level": level,
                    "xp": xp,
                    "aptitude": aptitude,
                    "weight": 1.0,  # Normal weight by default
                    "training_state": TrainingState.NORMAL.value,
                    "target_level": None,
                    "usage_count": 0,
                }
            )

        # Append to skills_df (with lock)
        new_skills = pl.DataFrame(rows, schema=SKILL_TABLE_SCHEMA)

        with self._skills_lock:
            self._initialize_entity_skills_impl(entity_id, new_skills)  # type: ignore[attr-defined]

    def _initialize_entity_skills_impl(
        self: SkillRegistryHost,
        entity_id: int,
        new_skills: pl.DataFrame,
    ) -> None:
        """Internal implementation of skill initialization without locking."""
        # Always add to skills_df (dual-mode operation during migration)
        self.skills_df = pl.concat([self.skills_df, new_skills], how="vertical")

        # Also sync to legacy format if not in vectorized-only mode
        if not self.use_vectorized_skills:
            self._sync_skills_to_legacy(entity_id, new_skills)  # type: ignore[attr-defined]

    def get_skills(
        self: SkillRegistryHost, entity_id: int
    ) -> dict[Skill, SkillProgress]:
        """Retrieve entity's skills as dict.

        Maintains backward compatibility with existing code.

        Args:
            entity_id: Entity to query

        Returns:
            Mapping of Skill -> SkillProgress
        """
        if self.use_vectorized_skills:
            # Read from skills_df
            skills_rows = (
                self.skills_df.lazy().filter(pl.col("entity_id") == entity_id).collect()
            )

            result: dict[Skill, SkillProgress] = {}

            for row in skills_rows.iter_rows(named=True):
                skill = Skill(row["skill"])
                result[skill] = SkillProgress(
                    skill=skill,
                    level=row["level"],
                    xp=row["xp"],
                    aptitude=row["aptitude"],
                )

            return result
        else:
            # Legacy path: read from entities_df.skills
            return self._get_skills_legacy(entity_id)  # type: ignore[attr-defined]

    def set_skills(
        self: SkillRegistryHost,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Update entity's skills.

        Thread-safe: Acquires self._skills_lock.

        Args:
            entity_id: Entity to update
            skills: New skill values
        """
        with self._skills_lock:
            self._set_skills_impl(entity_id, skills)  # type: ignore[attr-defined]

    def _set_skills_impl(
        self: SkillRegistryHost,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Internal implementation of set_skills without locking."""
        # Update skills_df rows
        updates: list[dict[str, int]] = []

        for skill, progress in skills.items():
            updates.append(
                {
                    "entity_id": entity_id,
                    "skill": skill.value,
                    "level": progress.level,
                    "xp": progress.xp,
                    "aptitude": progress.aptitude,
                }
            )

        update_df = pl.DataFrame(updates)

        # Join and update skills_df (always maintain vectorized format)
        self.skills_df = (
            self.skills_df.join(
                update_df,
                on=["entity_id", "skill"],
                how="left",
                suffix="_new",
            )
            .with_columns(
                [
                    pl.when(pl.col("level_new").is_not_null())
                    .then(pl.col("level_new"))
                    .otherwise(pl.col("level"))
                    .alias("level"),
                    pl.when(pl.col("xp_new").is_not_null())
                    .then(pl.col("xp_new"))
                    .otherwise(pl.col("xp"))
                    .alias("xp"),
                    pl.when(pl.col("aptitude_new").is_not_null())
                    .then(pl.col("aptitude_new"))
                    .otherwise(pl.col("aptitude"))
                    .alias("aptitude"),
                ]
            )
            .drop(["level_new", "xp_new", "aptitude_new"])
        )

        # Sync to legacy format for backward compatibility during migration
        if not self.use_vectorized_skills:
            self._sync_skills_to_legacy(entity_id, update_df)  # type: ignore[attr-defined]

    def get_skill_training(
        self: SkillRegistryHost, entity_id: int
    ) -> SkillTrainingConfig | None:
        """Get entity's training configuration.

        Args:
            entity_id: Entity to query

        Returns:
            Training configuration, or None if entity not found
        """
        if self.use_vectorized_skills:
            rows = (
                self.skills_df.lazy()
                .filter(pl.col("entity_id") == entity_id)
                .select(["skill", "weight", "target_level", "training_state"])
                .collect()
            )

            if rows.height == 0:
                return None

            # Read training mode from entity component storage
            mode: TrainingMode = TrainingMode.AUTOMATIC  # Default
            stored_mode = self.get_entity_component(entity_id, "training_mode")
            if stored_mode is not None:
                mode = TrainingMode(stored_mode)

            config = SkillTrainingConfig(mode=mode)

            for row in rows.iter_rows(named=True):
                skill = Skill(int(row["skill"]))
                # Defensive cast for weight with fallback
                weight_val = row.get("weight")
                config.weights[skill] = (
                    float(weight_val) if weight_val is not None else 1.0
                )

                # Use normalization helper to handle NULL_U8_SENTINEL
                target_val = normalize_target_level_to_python(row.get("target_level"))
                if target_val is not None:
                    config.targets[skill] = target_val

            return config
        else:
            return self._get_skill_training_legacy(entity_id)  # type: ignore[attr-defined]

    def _sync_skills_to_legacy(
        self: SkillRegistryHost,
        entity_id: int,
        skills_update: pl.DataFrame,
    ) -> None:
        """Sync skills_df changes back to entities_df.skills dict.

        For backward compatibility during migration. Converts vectorized
        skill rows to legacy dict[Skill, SkillProgress] format.

        Args:
            entity_id: Entity being updated
            skills_update: DataFrame with skill updates
        """
        logger = logging.getLogger(__name__)

        # Read current legacy dict (if any) via existing registry method
        legacy: dict[Skill, SkillProgress] = {}
        existing = self.get_entity_component(entity_id, "skills")
        if existing is not None:
            legacy = dict(existing)

        # Build updates from skills_update rows
        for row in skills_update.iter_rows(named=True):
            skill = Skill(int(row["skill"]))
            # Defensive casts with None checks
            level_val = row.get("level")
            xp_val = row.get("xp")
            aptitude_val = row.get("aptitude")

            level: int = int(level_val) if level_val is not None else 0
            xp: int = int(xp_val) if xp_val is not None else 0
            aptitude: int = int(aptitude_val) if aptitude_val is not None else 0

            prog = SkillProgress(
                skill=skill,
                level=level,
                xp=xp,
                aptitude=aptitude,
            )

            # Log changes for debugging parity issues
            if skill in legacy and legacy[skill] != prog:
                logger.debug(
                    f"Entity {entity_id} skill {skill.name}: "
                    f"{legacy[skill].level}/{legacy[skill].xp} -> {level}/{xp}"
                )

            legacy[skill] = prog

        # Write back into entities_df via existing set_entity_component
        self.set_entity_component(entity_id, "skills", legacy)

    def _get_skills_legacy(
        self: SkillRegistryHost, entity_id: int
    ) -> dict[Skill, SkillProgress]:
        """Legacy implementation reading from entities_df.skills.

        Override this method in EntityRegistry to delegate to existing
        skill storage implementation if use_vectorized_skills=False.
        """
        raise NotImplementedError(
            "Legacy skill storage not implemented. "
            "Set use_vectorized_skills=True or override _get_skills_legacy() "
            "in EntityRegistry to delegate to existing skill storage."
        )

    def _set_skills_legacy(
        self: SkillRegistryHost,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Legacy implementation writing to entities_df.skills.

        Override this method in EntityRegistry to delegate to existing
        skill storage implementation if use_vectorized_skills=False.
        """
        raise NotImplementedError(
            "Legacy skill storage not implemented. "
            "Set use_vectorized_skills=True or override _set_skills_legacy() "
            "in EntityRegistry to delegate to existing skill storage."
        )

    def _get_skill_training_legacy(
        self: SkillRegistryHost, entity_id: int
    ) -> SkillTrainingConfig | None:
        """Legacy implementation reading training config.

        Override this method in EntityRegistry to delegate to existing
        training config storage if use_vectorized_skills=False.
        """
        raise NotImplementedError(
            "Legacy training config storage not implemented. "
            "Set use_vectorized_skills=True or override _get_skill_training_legacy() "
            "in EntityRegistry to delegate to existing training config storage."
        )


def patch_entity_registry(registry_class: type) -> type:
    """Class decorator to add skill system to EntityRegistry.

    Adds:
      - skills_df: Polars DataFrame for vectorized skill storage
      - use_vectorized_skills: Feature flag for migration
      - _skills_lock: Threading lock for thread-safe mutations

    Usage:
        @patch_entity_registry
        class EntityRegistry:
            ...
    """
    from typing import Any

    # Add skills_df, flag, and lock to __init__
    original_init = registry_class.__init__  # type: ignore[misc]

    def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.skills_df = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills = False
        self._skills_lock = Lock()

    registry_class.__init__ = new_init  # type: ignore[misc]

    # Mixin methods
    for attr_name in dir(SkillSystemMixin):
        if not attr_name.startswith("_") or attr_name in (
            "_sync_skills_to_legacy",
            "_get_skills_legacy",
            "_set_skills_legacy",
            "_get_skill_training_legacy",
            "_initialize_entity_skills_impl",
            "_set_skills_impl",
        ):
            attr = getattr(SkillSystemMixin, attr_name)
            if callable(attr):
                setattr(registry_class, attr_name, attr)

    return registry_class
