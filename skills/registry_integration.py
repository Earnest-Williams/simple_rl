"""EntityRegistry integration for vectorized skill system.

Adds skills_df DataFrame alongside existing entities_df.skills for backward compatibility.
Implements dual-mode operation during migration.

Thread safety: All mutation methods acquire self._skills_lock when present.
"""

from __future__ import annotations

from threading import Lock
from typing import Final

import polars as pl

from skills.models import (
    MAX_SKILL_LEVEL,
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
    TrainingState,
)

# Skill table schema for EntityRegistry.skills_df
SKILL_TABLE_SCHEMA: Final[dict[str, type[pl.DataType]]] = {
    "entity_id": pl.UInt32,
    "skill": pl.UInt8,  # Store Skill.value for memory efficiency
    "level": pl.UInt8,
    "xp": pl.UInt32,
    "aptitude": pl.Int8,
    "weight": pl.Float32,
    "training_state": pl.UInt8,  # Store TrainingState.value
    "target_level": pl.UInt8,  # Nullable
    "usage_count": pl.UInt32,
}


class SkillSystemMixin:
    """Mixin to add to EntityRegistry for skill system support.

    Add this to EntityRegistry.__init__:
        self.skills_df: pl.DataFrame = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills: bool = False  # Feature flag
        self._skills_lock: Lock = Lock()  # Thread safety for skills_df mutations
    """

    skills_df: pl.DataFrame
    use_vectorized_skills: bool
    _skills_lock: Lock

    def initialize_entity_skills(
        self,
        entity_id: int,
        aptitudes: dict[Skill, int] | None = None,
        initial_levels: dict[Skill, int] | None = None,
    ) -> None:
        """Initialize all 29 skills for an entity.

        Thread-safe: Acquires self._skills_lock if present.

        Args:
            entity_id: Entity to initialize
            aptitudes: Skill aptitude modifiers (default: 0 for all)
            initial_levels: Starting skill levels (default: 0 for all)
        """
        if aptitudes is None:
            aptitudes = {}
        if initial_levels is None:
            initial_levels = {}

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

        # Append to skills_df (with lock if present)
        new_skills = pl.DataFrame(rows, schema=SKILL_TABLE_SCHEMA)

        lock: Lock | None = getattr(self, "_skills_lock", None)
        if lock is not None:
            with lock:
                self._initialize_entity_skills_impl(entity_id, new_skills)
        else:
            self._initialize_entity_skills_impl(entity_id, new_skills)

    def _initialize_entity_skills_impl(
        self,
        entity_id: int,
        new_skills: pl.DataFrame,
    ) -> None:
        """Internal implementation of skill initialization without locking."""
        if self.use_vectorized_skills:
            self.skills_df = pl.concat([self.skills_df, new_skills], how="vertical")
        else:
            # Backward compatibility: also populate entities_df.skills
            self._sync_skills_to_legacy(entity_id, new_skills)

    def get_skills(self, entity_id: int) -> dict[Skill, SkillProgress]:
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
                self.skills_df.lazy()
                .filter(pl.col("entity_id") == entity_id)
                .collect()
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
            return self._get_skills_legacy(entity_id)

    def set_skills(
        self,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Update entity's skills.

        Thread-safe: Acquires self._skills_lock if present.

        Args:
            entity_id: Entity to update
            skills: New skill values
        """
        lock: Lock | None = getattr(self, "_skills_lock", None)
        if lock is not None:
            with lock:
                self._set_skills_impl(entity_id, skills)
        else:
            self._set_skills_impl(entity_id, skills)

    def _set_skills_impl(
        self,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Internal implementation of set_skills without locking."""
        if self.use_vectorized_skills:
            # Update skills_df rows
            updates: list[dict[str, int]] = []

            for skill, progress in skills.items():
                updates.append(
                    {
                        "entity_id": entity_id,
                        "skill": skill.value,
                        "level": progress.level,
                        "xp": progress.xp,
                    }
                )

            update_df = pl.DataFrame(updates)

            # Join and update
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
                    ]
                )
                .drop(["level_new", "xp_new"])
            )

            # Sync to legacy for compatibility
            if not self.use_vectorized_skills:
                self._sync_skills_to_legacy(entity_id, update_df)
        else:
            # Legacy path
            self._set_skills_legacy(entity_id, skills)

    def get_skill_training(self, entity_id: int) -> SkillTrainingConfig:
        """Get entity's training configuration.

        Args:
            entity_id: Entity to query

        Returns:
            Training configuration
        """
        if self.use_vectorized_skills:
            rows = (
                self.skills_df.lazy()
                .filter(pl.col("entity_id") == entity_id)
                .select(["skill", "weight", "target_level", "training_state"])
                .collect()
            )

            # Determine mode from training_state values
            states = rows["training_state"].to_list()
            mode = (
                TrainingMode.MANUAL
                if all(s in (TrainingState.DISABLED.value, TrainingState.FOCUSED.value) for s in states)
                else TrainingMode.AUTOMATIC
            )

            config = SkillTrainingConfig(mode=mode)

            for row in rows.iter_rows(named=True):
                skill = Skill(row["skill"])
                config.weights[skill] = row["weight"]

                if row["target_level"] is not None:
                    config.targets[skill] = row["target_level"]

            return config
        else:
            return self._get_skill_training_legacy(entity_id)

    def _sync_skills_to_legacy(
        self,
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
        # Read current legacy dict (if any) via existing registry method
        legacy: dict[Skill, SkillProgress] = {}
        if hasattr(self, "get_entity_component"):
            existing = self.get_entity_component(entity_id, "skills")  # type: ignore[attr-defined]
            if existing is not None:
                legacy = dict(existing)

        # Build updates from skills_update rows
        for row in skills_update.iter_rows(named=True):
            skill = Skill(int(row["skill"]))
            level: int = int(row.get("level", 0))
            xp: int = int(row.get("xp", 0))
            aptitude: int = int(row.get("aptitude", 0))

            prog = SkillProgress(
                skill=skill,
                level=level,
                xp=xp,
                aptitude=aptitude,
            )
            legacy[skill] = prog

        # Write back into entities_df via existing set_entity_component
        if hasattr(self, "set_entity_component"):
            self.set_entity_component(entity_id, "skills", legacy)  # type: ignore[attr-defined]

    def _get_skills_legacy(self, entity_id: int) -> dict[Skill, SkillProgress]:
        """Legacy implementation reading from entities_df.skills."""
        # Placeholder - delegate to existing registry code
        raise NotImplementedError("Legacy path - delegate to EntityRegistry")

    def _set_skills_legacy(
        self,
        entity_id: int,
        skills: dict[Skill, SkillProgress],
    ) -> None:
        """Legacy implementation writing to entities_df.skills."""
        raise NotImplementedError("Legacy path - delegate to EntityRegistry")

    def _get_skill_training_legacy(self, entity_id: int) -> SkillTrainingConfig:
        """Legacy implementation reading training config."""
        raise NotImplementedError("Legacy path - delegate to EntityRegistry")


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
    # Add skills_df, flag, and lock to __init__
    original_init = registry_class.__init__

    def new_init(self: EntityRegistry, *args, **kwargs) -> None:  # type: ignore[name-defined]
        original_init(self, *args, **kwargs)
        self.skills_df = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills = False
        self._skills_lock = Lock()

    registry_class.__init__ = new_init  # type: ignore[method-assign]

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
