# game/entities/registry.py
from __future__ import annotations

from threading import Lock
from typing import TYPE_CHECKING, Any, Self, Callable

import numpy as np
from numpy.typing import NDArray
import polars as pl
import structlog

from game.entities.components import Position
from game.entities.store import EntityStore
from skills.models import Skill, SkillProgress, SkillTrainingConfig, TrainingMode
from skills.registry_integration import SKILL_TABLE_SCHEMA, SkillSystemMixin

if TYPE_CHECKING:
    pass

# Fallback removed
from game.items.registry import BodySlotType, EquipSlot

log = structlog.get_logger()


def _is_list_dtype(dtype: pl.DataType) -> bool:
    """
    Helper function to check if a Polars dtype represents a list type.
    More robust than isinstance checks against polars internals.
    """
    try:
        # Check if it's a List instance
        if isinstance(dtype, pl.List):
            return True
        # Check string representation as fallback
        dtype_str = str(dtype)
        return dtype_str.startswith("List(")
    except Exception:
        return False


# ENTITY_SCHEMA
ENTITY_SCHEMA: dict[str, pl.DataType] = {
    "entity_id": pl.UInt32,
    "is_active": pl.Boolean,
    "x": pl.Int16,
    "y": pl.Int16,
    "glyph": pl.UInt16,
    "color_fg_r": pl.UInt8,
    "color_fg_g": pl.UInt8,
    "color_fg_b": pl.UInt8,
    "name": pl.Utf8,
    "ai_type": pl.Utf8,
    "species": pl.Utf8,
    "intelligence": pl.Int16,
    "blocks_movement": pl.Boolean,
    "faction": pl.Utf8,
    "strategy_state": pl.Utf8,
    "hp": pl.Int16,
    "max_hp": pl.Int16,
    "strength": pl.Int16,
    "defense": pl.Int16,
    "armor": pl.Int16,
    "xp": pl.Int32,
    "xp_reward": pl.Int32,
    "inventory_capacity": pl.UInt16,
    "carried_weight": pl.Float32,
    "weight_capacity": pl.Float32,
    "status_effects": pl.List(
        pl.Struct({"id": pl.Utf8, "duration": pl.Int16, "intensity": pl.Float32})
    ),
    "mana": pl.Float32,
    "max_mana": pl.Float32,
    "fullness": pl.Float32,
    "max_fullness": pl.Float32,
    "fuel": pl.Float32,
    "max_fuel": pl.Float32,
    "equipped_item_ids": pl.List(pl.UInt64),
    "body_plan": pl.Object,
    "resistances": pl.Object,
    "vulnerabilities": pl.Object,
    "drop_table": pl.Object,
    "linked_positions": pl.List(pl.Struct({"x": pl.Int16, "y": pl.Int16})),
    "target_map": pl.Utf8,
    # New resource-tracking components
    "seal_tags": pl.List(pl.Utf8),
    "font_sources": pl.List(pl.Utf8),
    "vent_targets": pl.List(pl.Utf8),
    "community_ai": pl.Object,
    "community_profile": pl.Object,
    # Skill system
    "skills": pl.Object,  # Dict[Skill, SkillProgress]
    "skill_training": pl.Object,  # SkillTrainingConfig
    "active_manuals": pl.Object,  # Dict[int, Dict] - Active skill manuals
    "shapeshifted_form": pl.Utf8,  # Current shapeshifted form (None = normal)
    "training_mode": pl.UInt8,  # TrainingMode value
}


class EntityRegistry:
    @property
    def entities_df(self) -> pl.DataFrame:
        if self._entities_df_cache is None or self._store.dirty_polars_snapshot:
            self._entities_df_cache = self._store.to_polars()
            self._store.dirty_polars_snapshot = False
        return self._entities_df_cache

    @entities_df.setter
    def entities_df(self, value: pl.DataFrame) -> None:
        old_width = self._store.occupancy_width
        old_height = self._store.occupancy_height
        self._store = EntityStore.from_polars(value)
        self._store.ensure_occupancy_shape(old_width, old_height)
        self._entities_df_cache = value
        self._store.dirty_polars_snapshot = False

    def __init__(self: Self):
        log.info("Initializing EntityRegistry with body_plan schema")
        global ENTITY_SCHEMA
        if "equipped_item_ids" in ENTITY_SCHEMA and not isinstance(
            ENTITY_SCHEMA["equipped_item_ids"], pl.List
        ):
            log.warning("Correcting equipped_item_ids dtype in ENTITY_SCHEMA")
            ENTITY_SCHEMA["equipped_item_ids"] = pl.List(pl.UInt64)
        if "status_effects" in ENTITY_SCHEMA and not isinstance(
            ENTITY_SCHEMA["status_effects"], pl.List
        ):
            log.warning("Correcting status_effects dtype in ENTITY_SCHEMA")
            ENTITY_SCHEMA["status_effects"] = pl.List(
                pl.Struct(
                    {"id": pl.Utf8, "duration": pl.Int16, "intensity": pl.Float32}
                )
            )

        self._store = EntityStore()
        self._entities_df_cache = None
        self._next_entity_id: int = 0

        # Migrate existing entities_df to include any new columns from ENTITY_SCHEMA
        self._migrate_schema()

        # Vectorized skill system
        self.skills_df: pl.DataFrame = pl.DataFrame(schema=SKILL_TABLE_SCHEMA)
        self.use_vectorized_skills: bool = True  # Enable by default
        self._skills_lock: Lock = Lock()

        log.debug("EntityRegistry initialized", schema=list(ENTITY_SCHEMA.keys()))

    def _migrate_schema(self: Self) -> None:
        """
        Migrate entities_df to include any missing columns from ENTITY_SCHEMA.
        This ensures compatibility when loading registries created before new columns were added.
        """
        if self.entities_df.height == 0:
            # Empty dataframe already has the correct schema
            return

        for col, dtype in ENTITY_SCHEMA.items():
            if col not in self.entities_df.columns:
                # Determine default value based on dtype
                if dtype in (pl.Float32, pl.Float64):
                    default = 0.0
                elif dtype in (
                    pl.Int16,
                    pl.Int32,
                    pl.Int64,
                    pl.UInt16,
                    pl.UInt32,
                    pl.UInt64,
                ):
                    default = 0
                elif dtype == pl.Boolean:
                    default = False
                elif dtype == pl.Utf8:
                    default = None
                elif _is_list_dtype(dtype):
                    default = []
                elif dtype == pl.Object:
                    default = None
                else:
                    default = None

                # Add the missing column with default values
                log.info(
                    "Migrating schema: adding missing column",
                    column=col,
                    dtype=str(dtype),
                    default=default,
                )
                # Use repeat for better performance on large DataFrames
                default_series = (
                    pl.Series([default]).repeat(self.entities_df.height).cast(dtype)
                )
                self.entities_df = self.entities_df.with_columns(
                    default_series.alias(col)
                )

    def _get_next_id(self: Self) -> int:
        current_id = self._next_entity_id
        self._next_entity_id += 1
        if self._next_entity_id > 2**32 - 1:
            log.critical("Entity ID counter overflowed", next_id=self._next_entity_id)
            raise OverflowError("Entity ID counter overflowed (UInt32 limit reached).")
        return current_id

    def create_entity(
        self: Self,
        x: int,
        y: int,
        glyph: int,
        color_fg: tuple[int, int, int],
        name: str,
        blocks_movement: bool = True,
        ai_type: str | None = None,
        species: str | None = None,
        intelligence: int = 1,
        faction: str | None = None,
        strategy_state: str | None = None,
        hp: int = 1,
        max_hp: int = 1,
        strength: int = 0,
        defense: int = 0,
        armor: int = 0,
        xp: int = 0,
        xp_reward: int = 0,
        inventory_capacity: int = 26,
        carried_weight: float = 0.0,
        weight_capacity: float = 0.0,
        mana: float = 0.0,
        max_mana: float = 0.0,
        fullness: float = 100.0,
        max_fullness: float = 100.0,
        fuel: float = 0.0,
        max_fuel: float = 0.0,
        status_effects: list | None = None,
        initial_body_plan: dict[str, int] | None = None,
        resistances: dict[str, float] | None = None,
        vulnerabilities: dict[str, float] | None = None,
        drop_table: list[dict] | None = None,
    ) -> int:
        new_id = self._get_next_id()
        log_context = {"name": name, "pos": (x, y), "glyph": glyph, "hp": hp}
        log.debug("Attempting to create entity", **log_context)
        default_body_plan = {
            "finger": 10,
            "hand": 2,
            "wrist": 2,
            "head": 1,
            "face": 1,
            "eyes": 1,
            "neck": 2,
            "upper_body_inner": 1,
            "upper_body_outer": 1,
            "lower_body_inner": 1,
            "lower_body_outer": 1,
            "feet": 2,
            "back": 1,
            "belt": 1,
        }
        body_plan = default_body_plan.copy()
        if initial_body_plan:
            if BodySlotType is Any:
                validated_initial = initial_body_plan
            else:
                try:
                    valid_keys = BodySlotType.__args__
                    validated_initial = {
                        k: v for k, v in initial_body_plan.items() if k in valid_keys
                    }
                    if len(validated_initial) != len(initial_body_plan):
                        log.warning(
                            "Invalid keys found in initial_body_plan, ignored.",
                            invalid_keys=set(initial_body_plan.keys())
                            - set(valid_keys),
                        )
                except AttributeError:
                    log.warning(
                        "BodySlotType definition not available, cannot validate initial_body_plan keys."
                    )
                    validated_initial = initial_body_plan
            body_plan.update(validated_initial)

        try:
            self._store.create_entity(
                entity_id=new_id,
                x=x,
                y=y,
                glyph=glyph,
                color_fg=color_fg,
                name=name,
                blocks_movement=blocks_movement,
                ai_type=ai_type,
                species=species,
                intelligence=intelligence,
                faction=faction,
                strategy_state=strategy_state,
                hp=hp,
                max_hp=max_hp,
                strength=strength,
                defense=defense,
                armor=armor,
                xp=xp,
                xp_reward=xp_reward,
                inventory_capacity=inventory_capacity,
                carried_weight=carried_weight,
                weight_capacity=weight_capacity,
                status_effects=status_effects if status_effects is not None else [],
                mana=mana,
                max_mana=max_mana,
                fullness=fullness,
                max_fullness=max_fullness,
                fuel=fuel,
                max_fuel=max_fuel,
                equipped_item_ids=[],
                body_plan=body_plan,
                resistances=resistances if resistances is not None else {},
                vulnerabilities=vulnerabilities if vulnerabilities is not None else {},
                drop_table=drop_table if drop_table is not None else [],
                linked_positions=[],
                target_map=None,
                seal_tags=[],
                font_sources=[],
                vent_targets=[],
                community_ai=None,
                community_profile=None,
                skills={},
                skill_training=None,
                active_manuals={},
                shapeshifted_form=None,
                training_mode=TrainingMode.MANUAL.value,
            )
            log.info("Entity created successfully", entity_id=new_id, **log_context)
            return new_id
        except Exception as e:
            log.error(
                "Failed to create entity",
                error=str(e),
                exc_info=True,
            )
            raise

    def get_entity_component(
        self: Self, entity_id: int, component_name: str
    ) -> Any | None:
        """Retrieves the value of a specific component for a given *active* entity."""
        log_context = {"entity_id": entity_id, "component": component_name}
        if component_name not in ENTITY_SCHEMA:
            log.warning("Component does not exist", **log_context)
            raise ValueError(
                f"Component '{component_name}' does not exist in ENTITY_SCHEMA."
            )
        return self._store.get_component(entity_id, component_name)

    def set_entity_component(
        self: Self, entity_id: int, component_name: str, value: Any
    ) -> bool:
        log_context = {
            "entity_id": entity_id,
            "component": component_name,
            "new_value": value,
        }
        if component_name not in ENTITY_SCHEMA:
            log.warning("Component does not exist", **log_context)
            raise ValueError(
                f"Component '{component_name}' does not exist in ENTITY_SCHEMA."
            )
        if component_name in ("entity_id", "is_active"):
            log.warning("Attempted to set protected component", **log_context)
            raise ValueError(f"Cannot directly set '{component_name}' component.")
        return self._store.set_component(entity_id, component_name, value)

    def get_position(self: Self, entity_id: int) -> Position | None:
        """Return the Position component for an entity if available."""
        return self._store.get_position(entity_id)

    def get_entity_components(
        self: Self, entity_id: int, component_names: list[str]
    ) -> dict[str, Any]:
        return self._store.get_components(entity_id, component_names)

    def set_position(self: Self, entity_id: int, position: Position) -> bool:
        """Update an entity's position component."""
        return self._store.set_position(entity_id, position)

    def get_entities_at(self: Self, x: int, y: int) -> pl.DataFrame:
        try:
            return (
                self.entities_df.lazy()
                .filter((pl.col("x") == x) & (pl.col("y") == y) & pl.col("is_active"))
                .collect()
            )
        except Exception as e:
            log.error(
                "Error getting entities at position",
                error=str(e),
                exc_info=True,
                pos=(x, y),
            )
            return pl.DataFrame(schema=ENTITY_SCHEMA)

    def get_blocking_entity_at(self: Self, x: int, y: int) -> int | None:
        return self._store.get_blocking_entity_at(x, y)

    def ensure_occupancy_shape(self, width: int, height: int) -> None:
        self._store.ensure_occupancy_shape(width, height)

    def rebuild_occupancy(self) -> None:
        self._store.rebuild_occupancy()

    def try_move_entity(
        self,
        entity_id: int,
        dx: int,
        dy: int,
        *,
        width: int,
        height: int,
        is_walkable: Callable[[int, int], bool],
    ) -> tuple[bool, int, int]:
        return self._store.try_move_entity(
            entity_id,
            dx,
            dy,
            width=width,
            height=height,
            is_walkable=is_walkable,
        )

    def active_indices(self) -> np.ndarray:
        return self._store.active_indices()

    def ai_indices(self) -> np.ndarray:
        return self._store.ai_indices()

    def entity_id_at(self, idx: int) -> int:
        return self._store.entity_id_at(idx)

    def position_at(self, idx: int) -> tuple[int, int]:
        return self._store.position_at(idx)

    def kind_at(self, idx: int) -> str:
        return self._store.kind_at(idx)

    def row_dict_at(self, idx: int) -> dict[str, object]:
        return self._store.row_dict_at(idx)

    def ai_type_of(self, entity_id: int) -> str | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return self._store.ai_type[idx]

    def species_of(self, entity_id: int) -> str | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return self._store.species[idx]

    def intelligence_of(self, entity_id: int) -> int | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return int(self._store.intelligence[idx])

    def faction_of(self, entity_id: int) -> str | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return self._store.faction[idx]

    def xy_of(self, entity_id: int) -> tuple[int, int] | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return int(self._store.x[idx]), int(self._store.y[idx])

    def hp_of(self, entity_id: int) -> int | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return int(self._store.hp[idx])

    def max_hp_of(self, entity_id: int) -> int | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return int(self._store.max_hp[idx])

    def strategy_state_of(self, entity_id: int) -> str | None:
        idx = self._store.index_of(entity_id)
        if idx is None or not self._store.is_active[idx]:
            return None
        return self._store.strategy_state[idx]

    def active_non_player_indices(self, player_id: int) -> np.ndarray:
        return self._store.active_non_player_indices(player_id)

    def has_perception_profile_at(self, idx: int) -> bool:
        return self._store.has_perception_profile_at(idx)

    def visible_target_at(self, idx: int) -> dict[str, object]:
        return self._store.visible_target_at(idx)

    def faction_at(self, idx: int) -> str | None:
        return self._store.faction_at(idx)

    def xy_at(self, idx: int) -> tuple[int, int]:
        return self._store.xy_at(idx)

    def name_at(self, idx: int) -> str | None:
        return self._store.name_at(idx)

    def index_of_entity(self, entity_id: int) -> int | None:
        return self._store.index_of_entity(entity_id)

    def is_active_at(self, idx: int) -> bool:
        return self._store.is_active_at(idx)

    def get_component_at(self, idx: int, component: str) -> object | None:
        return self._store.get_component_at(idx, component)

    def monster_perception_records(self, player_id: int) -> list[dict[str, object]]:
        return self._store.monster_perception_records(player_id)

    def monster_perception_arrays(
        self, player_id: int
    ) -> tuple["NDArray[np.int64]", "NDArray[np.int64]", "NDArray[np.int64]", "NDArray[np.bool_]", "NDArray[np.int64]"]:
        """Return NumPy arrays for monster perception without materializing entities_df.

        Returns (ids, fy, fx, is_dead, perception_stat) arrays for all active
        non-player entities. This is the array-based alternative to
        monster_perception_records() for use in hot paths.
        """
        return self._store.monster_perception_arrays(player_id)

    def delete_entity(self: Self, entity_id: int) -> bool:
        log_context = {"entity_id": entity_id}
        log.debug("Deleting entity (marking inactive)", **log_context)
        success = self._store.delete_entity(entity_id)
        if success:
            log.info("Entity marked as inactive", **log_context)
        else:
            log.debug("Entity already inactive or does not exist", **log_context)
        return success

    def compact_registry(self: Self) -> None:
        log.info("Compacting entity registry...")
        try:
            initial_count = self._store.count
            self._store.compact_store()
            final_count = self._store.count
            removed_count = initial_count - final_count
            log.info(
                "Registry compacted",
                initial_count=initial_count,
                final_count=final_count,
                removed_count=removed_count,
            )
        except Exception as e:
            log.error("Error compacting registry", error=str(e), exc_info=True)

    def get_active_entities(self: Self) -> pl.DataFrame:
        try:
            return self.entities_df.filter(pl.col("is_active"))
        except Exception as e:
            log.error("Error getting active entities", error=str(e), exc_info=True)
            return pl.DataFrame(schema=ENTITY_SCHEMA)

    def get_body_plan(self, entity_id: int) -> dict[str, int] | None:
        # (Implementation unchanged)
        plan = self.get_entity_component(entity_id, "body_plan")
        return plan if isinstance(plan, dict) else None

    def set_body_plan(self, entity_id: int, body_plan: dict[str, int]) -> bool:
        # (Implementation unchanged)
        if not isinstance(body_plan, dict):
            log.error(
                "Invalid body_plan type provided to set_body_plan",
                entity_id=entity_id,
                type=type(body_plan),
            )
            return False
        return self.set_entity_component(entity_id, "body_plan", body_plan)

    def get_equipped_ids(self, entity_id: int) -> list[int] | None:
        """Gets the list of directly equipped item IDs for an active entity."""
        ids = self.get_entity_component(entity_id, "equipped_item_ids")
        # --- REMOVED Series check ---
        # The get_entity_component method should now handle returning a list directly.
        # Ensure a list is returned (or None if component retrieval failed)
        # Return None if not a list
        return ids if isinstance(ids, list) else None

    def set_equipped_ids(self, entity_id: int, equipped_ids: list[int]) -> bool:
        # (Implementation unchanged)
        if not isinstance(equipped_ids, list):
            log.error(
                "Invalid equipped_ids type provided to set_equipped_ids",
                entity_id=entity_id,
                type=type(equipped_ids),
            )
            return False
        return self.set_entity_component(entity_id, "equipped_item_ids", equipped_ids)

    # ===== Skill System Methods =====
    # Mixin methods from SkillSystemMixin

    initialize_entity_skills = SkillSystemMixin.initialize_entity_skills
    _initialize_entity_skills_impl = SkillSystemMixin._initialize_entity_skills_impl
    _sync_skills_to_legacy = SkillSystemMixin._sync_skills_to_legacy
    _set_skills_impl = SkillSystemMixin._set_skills_impl

    def get_skills(self, entity_id: int) -> dict[Skill, SkillProgress]:
        """Get the skills dictionary for an entity."""
        if self.use_vectorized_skills:
            # Use vectorized path from mixin
            return SkillSystemMixin.get_skills(self, entity_id)  # type: ignore[arg-type]
        else:
            # Legacy path
            skills = self.get_entity_component(entity_id, "skills")
            return skills if skills is not None else {}

    def set_skills(self, entity_id: int, skills: dict[Skill, SkillProgress]) -> None:
        """Set the skills dictionary for an entity."""
        if not isinstance(skills, dict):
            log.error(
                "Invalid skills type provided to set_skills",
                entity_id=entity_id,
                type=type(skills),
            )
            return
        if self.use_vectorized_skills:
            # Use vectorized path from mixin
            SkillSystemMixin.set_skills(self, entity_id, skills)  # type: ignore[arg-type]
        else:
            # Legacy path
            self.set_entity_component(entity_id, "skills", skills)

    def get_skill_training(self, entity_id: int) -> SkillTrainingConfig | None:
        """Get the skill training configuration for an entity."""
        if self.use_vectorized_skills:
            # Use vectorized path from mixin
            return SkillSystemMixin.get_skill_training(self, entity_id)  # type: ignore[arg-type]
        else:
            # Legacy path
            return self.get_entity_component(entity_id, "skill_training")

    def set_skill_training(self, entity_id: int, config: SkillTrainingConfig) -> None:
        """Set the skill training configuration for an entity."""
        if self.use_vectorized_skills:
            # Store mode in entity component
            self.set_entity_component(entity_id, "training_mode", config.mode.value)
        else:
            # Legacy path
            self.set_entity_component(entity_id, "skill_training", config)

    def _get_skills_legacy(self, entity_id: int) -> dict[Skill, SkillProgress]:
        """Legacy implementation - delegates to existing storage."""
        skills = self.get_entity_component(entity_id, "skills")
        return skills if skills is not None else {}

    def _get_skill_training_legacy(self, entity_id: int) -> SkillTrainingConfig | None:
        """Legacy implementation - delegates to existing storage."""
        return self.get_entity_component(entity_id, "skill_training")
