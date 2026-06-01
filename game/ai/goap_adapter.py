"""GOAP planning adapter for the main game."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl

from auto.goap_engine import Action, AgentAI
from game.world.game_map import TILE_TYPES

if TYPE_CHECKING:  # pragma: no cover
    from game.game_state import GameState


def _build_walkable(game_state: GameState) -> np.ndarray:
    walkable_ids = [tid for tid, t in TILE_TYPES.items() if t.walkable]
    return np.isin(game_state.game_map.tiles, walkable_ids)


def _entity_kind_matches(row: dict[str, Any], kind: str) -> bool:
    if kind == "enemy":
        return row.get("species") == "enemy" or row.get("ai_type") in {"goap", "combat"}
    if kind == "slime":
        return row.get("species") == "slime"
    return False


def _infer_item_kind(item_row: dict[str, Any]) -> str:
    name = (item_row.get("name") or "").lower()
    template_id = (item_row.get("template_id") or "").lower()
    if "weapon" in name or "weapon" in template_id:
        return "weapon"
    if "potion" in name or "slime" in name:
        return "consumable"
    return "misc"


@dataclass
class _GameAgentAdapter:
    entity_id: int
    health: float
    hunger: float
    max_inventory: int
    inventory: list[dict[str, Any]]
    equipped_weapon: dict[str, Any] | None
    _position: tuple[int, int]

    def get_position(self) -> tuple[int, int]:
        return self._position


@dataclass
class _GameItemAdapter:
    item_id: int
    name: str
    kind: str


@dataclass
class _GameEntityAdapter:
    entity_id: int
    x: int
    y: int

    def get_position(self) -> tuple[int, int]:
        return (self.x, self.y)


class _GameStateWorldAdapter:
    def __init__(self, game_state: GameState) -> None:
        self.game_state = game_state
        self.entity_df = game_state.entity_registry.entities_df
        self.item_df = game_state.item_registry.items_df
        self.walkable = _build_walkable(game_state)

    def get_nearest_entity(
        self, agent: _GameAgentAdapter, kind: str
    ) -> tuple[Any | None, float]:
        ax, ay = agent.get_position()
        best_id = None
        best_dist = float("inf")

        if kind == "item":
            item_df = self.item_df
            if item_df.is_empty():
                return None, float("inf")
            for row in item_df.filter(
                (pl.col("location_type") == "ground") & pl.col("is_active")
            ).iter_rows(named=True):
                x = row.get("x")
                y = row.get("y")
                if x is None or y is None:
                    continue
                dist = abs(x - ax) + abs(y - ay)
                if dist < best_dist:
                    best_dist = dist
                    best_id = row.get("item_id")
            return best_id, best_dist

        spatial_index = getattr(self.game_state, "spatial_index", None)
        if spatial_index is not None and hasattr(spatial_index, "query_radius"):
            nearby = spatial_index.query_radius((ax, ay), radius=50, kind=kind)
            for entity_id, x, y in nearby:
                if entity_id == agent.entity_id:
                    continue
                dist = abs(x - ax) + abs(y - ay)
                if dist < best_dist:
                    best_dist = dist
                    best_id = entity_id
            if best_id is not None:
                return best_id, best_dist

        entity_df = self.entity_df
        if entity_df.is_empty():
            return None, float("inf")

        for row in entity_df.filter(
            pl.col("is_active") & (pl.col("entity_id") != agent.entity_id)
        ).iter_rows(named=True):
            if not _entity_kind_matches(row, kind):
                continue
            x = row.get("x")
            y = row.get("y")
            if x is None or y is None:
                continue
            dist = abs(x - ax) + abs(y - ay)
            if dist < best_dist:
                best_dist = dist
                best_id = row.get("entity_id")
        return best_id, best_dist

    def get_entity_object(self, entity_id: int) -> Any | None:
        item_df = self.item_df
        if not item_df.is_empty():
            item_rows = item_df.filter(pl.col("item_id") == entity_id)
            if not item_rows.is_empty():
                row = item_rows.row(0, named=True)
                return _GameItemAdapter(
                    item_id=entity_id,
                    name=row.get("name") or "",
                    kind=_infer_item_kind(row),
                )

        entity_df = self.entity_df
        if not entity_df.is_empty():
            entity_rows = entity_df.filter(pl.col("entity_id") == entity_id)
            if not entity_rows.is_empty():
                row = entity_rows.row(0, named=True)
                x = row.get("x")
                y = row.get("y")
                if x is None or y is None:
                    return None
                return _GameEntityAdapter(entity_id=entity_id, x=int(x), y=int(y))

        return None


def _build_agent_adapter(game_state: GameState, entity_id: int) -> _GameAgentAdapter:
    entity_df = game_state.entity_registry.entities_df
    entity_rows = entity_df.filter(pl.col("entity_id") == entity_id)
    if entity_rows.is_empty():
        raise ValueError(f"Entity {entity_id} not found")
    entity_row = entity_rows.row(0, named=True)
    x = entity_row.get("x")
    y = entity_row.get("y")
    if x is None or y is None:
        raise ValueError(f"Entity {entity_id} has no position")

    item_df = game_state.item_registry.items_df
    inventory_items: list[dict[str, Any]] = []
    equipped_weapon = None
    if not item_df.is_empty():
        owned_items = item_df.filter(
            (pl.col("owner_entity_id") == entity_id) & pl.col("is_active")
        )
        for row in owned_items.iter_rows(named=True):
            item = {
                "item_id": row.get("item_id"),
                "name": row.get("name"),
                "kind": _infer_item_kind(row),
            }
            if row.get("location_type") == "equipped" and item["kind"] == "weapon":
                equipped_weapon = item
            else:
                inventory_items.append(item)

    return _GameAgentAdapter(
        entity_id=entity_id,
        health=float(entity_row.get("hp") or 0),
        hunger=float(entity_row.get("fullness") or 0),
        max_inventory=int(entity_row.get("inventory_capacity") or 0),
        inventory=inventory_items,
        equipped_weapon=equipped_weapon,
        _position=(int(x), int(y)),
    )


def plan_for_agent(game_state: GameState, entity_id: int) -> list[Action]:
    """Build and return a GOAP plan for a single entity."""
    world = _GameStateWorldAdapter(game_state)
    agent = _build_agent_adapter(game_state, entity_id)
    planner = AgentAI(world, game_state.rng_instance)
    return planner.plan_for(agent)


__all__ = ["plan_for_agent"]
