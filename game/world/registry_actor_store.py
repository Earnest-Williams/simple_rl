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

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from game.entities.registry import EntityRegistry

from game.world.lod_hydration import ACTOR_ID_KEY

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
)
"""ENTITY_SCHEMA components captured in dehydration snapshots."""


class EntityRegistryActorStore:
    """``ActorStore`` implementation over the production registry."""

    def __init__(self, registry: "EntityRegistry") -> None:
        self._registry = registry

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
        for name, value in components.items():
            snapshot[name] = _plain_value(value)
        return snapshot

    def despawn_actor(self, actor_id: int) -> None:
        """Mark the entity inactive (registry deletion semantics)."""
        self._registry.delete_entity(actor_id)

    def spawn_actor(self, snapshot: dict[str, Any]) -> None:
        """Re-create the entity with its stable ID and saved state."""
        entity_id = int(snapshot[ACTOR_ID_KEY])
        status_effects = [
            dict(effect) if not isinstance(effect, dict) else effect
            for effect in snapshot.get("status_effects", [])
        ]
        self._registry.create_entity(
            entity_id=entity_id,
            x=int(snapshot["x"]),
            y=int(snapshot["y"]),
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
        equipped_ids = snapshot.get("equipped_item_ids")
        if equipped_ids:
            self._registry.set_equipped_ids(entity_id, list(equipped_ids))

    def is_tile_blocked(self, x: int, y: int) -> bool:
        """Whether a movement-blocking entity occupies the tile."""
        return self._registry.get_blocking_entity_at(x, y) is not None

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
                actor_id, Position(x=int(x), y=int(y))
            )
        )


def _plain_value(value: Any) -> Any:
    """Normalize a component value to JSON-serializable data."""
    if isinstance(value, (bool, int, float, str)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_plain_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _plain_value(item) for key, item in value.items()}
    if hasattr(value, "item"):  # numpy scalar
        return value.item()
    return str(value)


__all__ = ["EntityRegistryActorStore"]
