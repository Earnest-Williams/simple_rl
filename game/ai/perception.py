"""Lightweight perception helpers for AI modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import numpy as np
import polars as pl
import structlog

from game.world.los import line_of_sight
from pathfinding.perception_systems import FlowType

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from polars import series

    from game.game_state import GameState

log = structlog.get_logger()


@dataclass(slots=True)
class PerceptionFact:
    """Structured perception fact for a single entity."""

    signal_type: str | None = None
    confidence: float = 0.0
    visible_targets: list[Any] = field(default_factory=list)
    heard_source: tuple[int, int] | None = None
    heard_flow: str | None = None
    scent_strength: float = 0.0
    scent_position: tuple[int, int] | None = None
    last_known_position: tuple[int, int] | None = None


@dataclass(slots=True)
class PerceptionSnapshot:
    """Structured AI-facing perception snapshot plus optional debug maps."""

    los_map: np.ndarray
    entity_facts: dict[int, PerceptionFact] = field(default_factory=dict)
    debug_noise_map: np.ndarray | None = None
    debug_scent_map: np.ndarray | None = None


def gather_perception(
    game_state: GameState,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate legacy perception maps used by AI systems.

    Production sound/scent fields are advanced by ``GameState``. This function
    remains tuple-compatible for existing callers and tests. If legacy callers
    enqueue events and call this function directly, it advances those queued
    events without adding an automatic player scent stamp.
    """

    game_map = game_state.game_map
    if getattr(game_state, "noise_events", []) or getattr(game_state, "scent_events", []):
        game_state.update_perception_fields(include_player_scent=False)

    noise_map = game_map.noise_map.copy()
    scent_map = game_map.scent_map.copy()
    los_map = game_map.visible.copy()
    log.debug("Perception maps generated", shape=noise_map.shape)
    return noise_map, scent_map, los_map


def gather_perception_snapshot(game_state: GameState) -> PerceptionSnapshot:
    """Return structured AI-facing perception facts without breaking legacy callers."""
    noise_map, scent_map, los_map = gather_perception(game_state)
    facts: dict[int, PerceptionFact] = {}

    flow_idx = int(FlowType.REAL_NOISE)
    center_y = int(game_state.perception_flow_centers[flow_idx, 0])
    center_x = int(game_state.perception_flow_centers[flow_idx, 1])
    heard_source = (center_x, center_y)

    for entity_id in game_state.perception_alerted_monster_ids:
        facts[int(entity_id)] = PerceptionFact(
            signal_type="audio",
            confidence=1.0,
            heard_source=heard_source,
            heard_flow="real_noise",
            last_known_position=heard_source,
        )

    log.debug("Perception snapshot generated", alerted_count=len(facts))
    return PerceptionSnapshot(
        los_map=los_map,
        entity_facts=facts,
        debug_noise_map=noise_map,
        debug_scent_map=scent_map,
    )


def find_visible_enemies(
    entity_row: series,
    game_state: GameState,
    los_map: np.ndarray,
) -> list[series]:
    """Return a list of enemies visible to ``entity_row``.

    Entities are considered enemies if they belong to a different faction.
    Visibility is determined using both the provided ``los_map`` and a
    line-of-sight check against the game map's transparency grid.
    """

    ex, ey = entity_row.get("x"), entity_row.get("y")
    faction = entity_row.get("faction")
    game_map = game_state.game_map
    enemies: list[series] = []

    if ex is None or ey is None:
        return enemies

    filter_expr = pl.col("is_active") is True
    if faction is not None:
        filter_expr &= pl.col("faction") != faction
    enemy_df = game_state.entity_registry.entities_df.filter(filter_expr)
    enemy_rows = {int(row["entity_id"]): row for row in enemy_df.iter_rows(named=True)}

    vision_range = int(entity_row.get("vision_range") or game_state.fov_radius)
    spatial_index = getattr(game_state, "spatial_index", None)
    nearby = None
    if spatial_index is not None and hasattr(spatial_index, "query_radius"):
        nearby = spatial_index.query_radius((int(ex), int(ey)), vision_range)

    candidates = nearby if nearby is not None else enemy_rows.values()
    for other in candidates:
        if isinstance(other, dict):
            other_row = other
            ox, oy = other_row.get("x"), other_row.get("y")
            other_id = other_row.get("entity_id")
        else:
            other_id, ox, oy = other
            other_row = enemy_rows.get(int(other_id))
            if other_row is None:
                continue
        if other_id == entity_row.get("entity_id"):
            continue
        if ox is None or oy is None:
            continue
        if not game_map.in_bounds(int(ox), int(oy)):
            continue
        if not los_map[int(oy), int(ox)]:
            continue
        if line_of_sight(int(ex), int(ey), int(ox), int(oy), game_map.transparent):
            enemies.append(other_row)

    log.debug(
        "Visible enemies located",
        entity_id=entity_row.get("entity_id"),
        count=len(enemies),
    )
    return enemies


__all__ = [
    "PerceptionFact",
    "PerceptionSnapshot",
    "gather_perception",
    "gather_perception_snapshot",
    "find_visible_enemies",
]
