"""Lightweight perception helpers for AI modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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
    visible_targets: list[object] = field(default_factory=list)
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
    from pathfinding.perception_systems import get_scent
    
    noise_map, scent_map, los_map = gather_perception(game_state)
    facts: dict[int, PerceptionFact] = {}

    flow_idx = int(FlowType.REAL_NOISE)
    center_y = int(game_state.perception_flow_centers[flow_idx, 0])
    center_x = int(game_state.perception_flow_centers[flow_idx, 1])
    global_heard_source = (center_x, center_y)
    
    alerted_set = set(game_state.perception_alerted_monster_ids)

    df = getattr(game_state.entity_registry, "entities_df", None)
    if df is not None and not df.is_empty():
        active_df = df.filter(
            (pl.col("is_active") == True) & (pl.col("entity_id") != game_state.player_id)
        )
        cave_when = game_state.perception_cave_when
        game_map = game_state.game_map
        DEFAULT_MEMORY_TURNS = 5
        
        for row in active_df.iter_rows(named=True):
            if not (row.get("ai_type") or row.get("species") or row.get("intelligence") is not None):
                continue
                
            ent_id = int(row["entity_id"])
            ex = row.get("x")
            ey = row.get("y")
            if ex is None or ey is None:
                continue
            ex, ey = int(ex), int(ey)
            
            # 1. Visible targets
            visible_targets = find_visible_enemies(row, game_state, los_map)
            
            # 2. Audio facts
            heard_source = global_heard_source if ent_id in alerted_set else None
            heard_flow = "real_noise" if heard_source else None
            
            # 3. Scent facts
            current_scent = get_scent(cave_when, ey, ex)
            best_scent_val = current_scent
            best_scent_pos = None
            
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = ex + dx, ey + dy
                if 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                    # check passable - transparent is True for walkable
                    if game_map.transparent[ny, nx]:
                        n_scent = get_scent(cave_when, ny, nx)
                        if n_scent > best_scent_val:
                            best_scent_val = n_scent
                            best_scent_pos = (nx, ny)
            
            scent_position = best_scent_pos
            scent_strength = best_scent_val if best_scent_pos else current_scent
            
            # Prioritize the current signals
            confidence = 0.0
            signal_type = "idle"
            current_target_pos: tuple[int, int] | None = None
            memorable = False

            if visible_targets:
                signal_type = "visual"
                confidence = 1.0
                first = visible_targets[0]
                current_target_pos = (int(first["x"]), int(first["y"]))
                memorable = True
            elif heard_source:
                signal_type = "audio"
                confidence = 1.0
                current_target_pos = heard_source
                memorable = True
            elif scent_position:
                signal_type = "scent"
                confidence = 0.8
                current_target_pos = scent_position
                memorable = False  # DO NOT memorize scent gradients as a "last known" position

            # Update or retrieve from explicit memory
            last_known_position: tuple[int, int] | None = None

            if memorable and current_target_pos is not None:
                # Hard signal detected: refresh memory
                game_state.ai_memory[ent_id] = {
                    "pos": current_target_pos, 
                    "turns_left": DEFAULT_MEMORY_TURNS
                }
                last_known_position = current_target_pos 
            else:
                # No hard signal: check memory
                if ent_id in game_state.ai_memory:
                    mem = game_state.ai_memory[ent_id]
                    if mem["turns_left"] > 0:
                        if not current_target_pos:
                            # Only fallback to memory if we don't even have a scent
                            signal_type = "memory"
                            confidence = 0.5
                        last_known_position = mem["pos"]
                        mem["turns_left"] -= 1
                    else:
                        del game_state.ai_memory[ent_id]
                
            facts[ent_id] = PerceptionFact(
                signal_type=signal_type,
                confidence=confidence,
                visible_targets=visible_targets,
                heard_source=heard_source,
                heard_flow=heard_flow,
                scent_strength=scent_strength,
                scent_position=scent_position,
                last_known_position=last_known_position,
            )

    log.debug("Perception snapshot generated", facts_count=len(facts))
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
