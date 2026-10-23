"""Adapter bridging the production ``EntityRegistry`` to hydration.

Implements the ``ActorStore`` protocol from
:mod:`game.world.lod_hydration` (Surface Map Plan Phase 5) over the
real ECS registry, so ``ChunkHydrationManager`` can dehydrate and
hydrate live actors without knowing registry internals.

Snapshot fields are the JSON-serializable subset of ``ENTITY_SCHEMA``:
identity, presentation, AI, combat stats, resources, and equipment IDs.
Object-typed columns (body plans, skills, community profiles) are not
snapshotted here; Phase 5 scope is actor identity, position, and core
state (HP, stats, resources, equipped items).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import polars as pl

from game.world.lod_hydration import ACTOR_ID_KEY
from skills.models import (
    ManualBonus,
    Skill,
    SkillProgress,
    SkillTrainingConfig,
    TrainingMode,
)
from skills.registry_integration import SKILL_TABLE_SCHEMA

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry

_SNAPSHOT_COMPONENTS: tuple[str, ...] = (
    "name",
    "ai_type",
    "species",
    "intelligence",
    "blocks_movement",
    "faction",
    "strategy_state",
    "x",
    "y",
    "glyph",
    "color_fg_r",
    "color_fg_g",
    "color_fg_b",
    "hp",
    "max_hp",
    "strength",
    "defense",
    "armor",
    "xp",
    "xp_reward",
    "inventory_capacity",
    "carried_weight",
    "weight_capacity",
    "mana",
    "max_mana",
    "fullness",
    "max_fullness",
    "fuel",
    "max_fuel",
    "status_effects",
    "equipped_item_ids",
    "surface_actor_state",
    "body_plan",
    "resistances",
    "vulnerabilities",
    "drop_table",
    "linked_positions",
    "target_map",
    "seal_tags",
    "font_sources",
    "vent_targets",
    "community_ai",
    "community_profile",
    "skills",
    "skill_training",
    "active_manuals",
    "shapeshifted_form",
    "training_mode",
)
"""ENTITY_SCHEMA components captured in dehydration snapshots."""


class EntityRegistryActorStore:
    """``ActorStore`` implementation over the production registry."""

    def __init__(
        self,
        registry: EntityRegistry,
        *,
        viewport_origin_x: int = 0,
        viewport_origin_y: int = 0,
    ) -> None:
        self._registry = registry
        self._origin_x = int(viewport_origin_x)
        self._origin_y = int(viewport_origin_y)

    def can_dehydrate_actor(self, actor_id: int) -> bool:
        """Exclude the player and non-surface residents from LOD eviction."""
        state = self._registry.get_entity_component(actor_id, "surface_actor_state")
        return (
            isinstance(state, dict)
            and isinstance(state.get("template_id"), str)
            and state.get("behavior")
            in {"wander", "seek_water", "forage", "anchor_leash"}
        )

    def active_actor_ids(self) -> list[int]:
        """Return every active entity ID (registry-index backed)."""
        return [
            int(self._registry.entity_id_at(idx))
            for idx in self._registry.active_indices()
        ]

    def snapshot_actor(self, actor_id: int) -> dict[str, Any]:
        """Capture a JSON-serializable snapshot of an active entity."""
        components = self._registry.get_entity_components(
            actor_id, list(_SNAPSHOT_COMPONENTS)
        )
        snapshot: dict[str, Any] = {ACTOR_ID_KEY: int(actor_id)}
        # Skills live in their own vectorized registry, not the entity row.
        rows = self._registry.skills_df.filter(
            pl.col("entity_id") == actor_id
        ).to_dicts()
        if rows:
            snapshot["skill_rows"] = _plain_value(rows)
        for name, value in components.items():
            if name == "x":
                snapshot[name] = int(value) + self._origin_x
                continue
            if name == "y":
                snapshot[name] = int(value) + self._origin_y
                continue
            if name == "surface_actor_state":
                if isinstance(value, dict):
                    snapshot.update(_plain_value(value))
                continue
            snapshot[name] = _plain_value(value)
        return snapshot

    def despawn_actor(self, actor_id: int) -> None:
        """Release its active slot; the journal retains its world identity."""
        if not self._registry.release_entity(actor_id):
            raise KeyError(f"Actor {actor_id} is not active")

    def spawn_actor(self, snapshot: dict[str, Any]) -> None:
        """Re-create the entity with its stable ID and saved state."""
        entity_id = int(snapshot[ACTOR_ID_KEY])
        status_effects = [
            dict(effect) if not isinstance(effect, dict) else effect
            for effect in snapshot.get("status_effects", [])
        ]
        self._registry.create_entity(
            entity_id=entity_id,
            x=int(snapshot["x"]) - self._origin_x,
            y=int(snapshot["y"]) - self._origin_y,
            glyph=int(snapshot["glyph"]),
            color_fg=(
                int(snapshot["color_fg_r"]),
                int(snapshot["color_fg_g"]),
                int(snapshot["color_fg_b"]),
            ),
            name=snapshot["name"],
            blocks_movement=bool(snapshot["blocks_movement"]),
            ai_type=snapshot.get("ai_type"),
            species=snapshot.get("species"),
            intelligence=int(snapshot.get("intelligence", 1)),
            faction=snapshot.get("faction"),
            strategy_state=snapshot.get("strategy_state"),
            hp=int(snapshot["hp"]),
            max_hp=int(snapshot["max_hp"]),
            strength=int(snapshot.get("strength", 0)),
            defense=int(snapshot.get("defense", 0)),
            armor=int(snapshot.get("armor", 0)),
            xp=int(snapshot.get("xp", 0)),
            xp_reward=int(snapshot.get("xp_reward", 0)),
            inventory_capacity=int(snapshot.get("inventory_capacity", 26)),
            carried_weight=float(snapshot.get("carried_weight", 0.0)),
            weight_capacity=float(snapshot.get("weight_capacity", 0.0)),
            mana=float(snapshot.get("mana", 0.0)),
            max_mana=float(snapshot.get("max_mana", 0.0)),
            fullness=float(snapshot.get("fullness", 100.0)),
            max_fullness=float(snapshot.get("max_fullness", 100.0)),
            fuel=float(snapshot.get("fuel", 0.0)),
            max_fuel=float(snapshot.get("max_fuel", 0.0)),
            status_effects=status_effects,
        )
        # Restore the complete set of serializable ECS components. An
        # unsupported object fails at snapshot time instead of being
        # silently replaced by its Python string representation.
        extra_components = (
            "body_plan",
            "resistances",
            "vulnerabilities",
            "drop_table",
            "linked_positions",
            "target_map",
            "seal_tags",
            "font_sources",
            "vent_targets",
            "community_ai",
            "community_profile",
            "skills",
            "skill_training",
            "active_manuals",
            "shapeshifted_form",
            "training_mode",
        )
        for name in extra_components:
            if name not in snapshot:
                continue
            value = _restore_value(snapshot[name])
            if name == "skills" and isinstance(value, dict):
                value = {Skill(int(k)): v for k, v in value.items()}
            if name == "active_manuals" and isinstance(value, dict):
                value = {int(k): v for k, v in value.items()}
            self._registry.set_entity_component(entity_id, name, value)

        skill_rows = snapshot.get("skill_rows", [])
        if skill_rows:
            restored = pl.DataFrame(skill_rows, schema=SKILL_TABLE_SCHEMA)
            with self._registry._skills_lock:
                self._registry.skills_df = pl.concat(
                    [
                        self._registry.skills_df.filter(
                            pl.col("entity_id") != entity_id
                        ),
                        restored,
                    ],
                    how="vertical",
                )

        core = set(_SNAPSHOT_COMPONENTS) | {ACTOR_ID_KEY, "skill_rows"}
        surface_state = {k: v for k, v in snapshot.items() if k not in core}
        if surface_state:
            self._registry.set_entity_component(
                entity_id, "surface_actor_state", surface_state
            )
        equipped_ids = snapshot.get("equipped_item_ids")
        if equipped_ids:
            self._registry.set_equipped_ids(entity_id, list(equipped_ids))

    def is_tile_blocked(self, x: int, y: int) -> bool:
        """Whether a movement-blocking entity occupies the tile."""
        return (
            self._registry.get_blocking_entity_at(
                x - self._origin_x, y - self._origin_y
            )
            is not None
        )

    def move_actor(self, actor_id: int, x: int, y: int) -> bool:
        """Move an active actor to a behavior-validated tile.

        Thin bridge for the Phase 6 surface behaviors: the caller has
        already validated walkability, bounds, and occupancy through
        ``SurfaceContext`` and the store's own ``is_tile_blocked``.
        Occupancy structures are refreshed by the engine's normal turn
        pipeline (``rebuild_occupancy``) rather than here.
        """
        from game.entities.components import Position

        if self._registry.get_position(actor_id) is None:
            return False
        return bool(
            self._registry.set_position(
                actor_id, Position(x=int(x) - self._origin_x, y=int(y) - self._origin_y)
            )
        )


def _plain_value(value: Any) -> Any:
    """Normalize supported components without silently losing object state.

    Snapshot payloads cross a JSON boundary; unknown Python objects must
    fail closed until an explicit serializer has been defined for them.
    """
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    if isinstance(value, SkillProgress):
        return {
            "__skill_progress__": {
                "skill": int(value.skill),
                "level": value.level,
                "xp": value.xp,
                "aptitude": value.aptitude,
            }
        }
    if isinstance(value, SkillTrainingConfig):
        return {
            "__skill_training__": {
                "mode": int(value.mode),
                "weights": {str(int(k)): v for k, v in value.weights.items()},
                "targets": {str(int(k)): v for k, v in value.targets.items()},
            }
        }
    if isinstance(value, ManualBonus):
        return {
            "__manual_bonus__": {
                "skill": int(value.skill),
                "bonus_aptitude": value.bonus_aptitude,
                "remaining_xp": value.remaining_xp,
            }
        }
    if isinstance(value, list | tuple):
        return [_plain_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if hasattr(value, "item"):
        scalar = value.item()
        if isinstance(scalar, bool | int | float | str):
            return scalar
    raise TypeError(f"Unsupported dehydration component: {type(value).__name__}")


def _restore_value(value: Any) -> Any:
    """Rehydrate explicitly tagged skill value objects."""
    if isinstance(value, list):
        return [_restore_value(item) for item in value]
    if not isinstance(value, dict):
        return value
    progress = value.get("__skill_progress__")
    if isinstance(progress, dict):
        return SkillProgress(
            skill=Skill(int(progress["skill"])),
            level=int(progress["level"]),
            xp=int(progress["xp"]),
            aptitude=int(progress["aptitude"]),
        )
    training = value.get("__skill_training__")
    if isinstance(training, dict):
        return SkillTrainingConfig(
            mode=TrainingMode(int(training["mode"])),
            weights={Skill(int(k)): float(v) for k, v in training["weights"].items()},
            targets={Skill(int(k)): int(v) for k, v in training["targets"].items()},
        )
    manual = value.get("__manual_bonus__")
    if isinstance(manual, dict):
        return ManualBonus(
            skill=Skill(int(manual["skill"])),
            bonus_aptitude=int(manual["bonus_aptitude"]),
            remaining_xp=int(manual["remaining_xp"]),
        )
    return {k: _restore_value(v) for k, v in value.items()}


__all__ = ["EntityRegistryActorStore"]
