"""Lightweight perception helpers for AI modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

import numpy as np
import structlog
from numpy.typing import NDArray

from game.perception_events import AIMemoryFact
from game.world.los import line_of_sight_many_u8
from pathfinding.perception_systems import FlowType

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from game.game_state import GameState

log = structlog.get_logger()

PerceptionSignal = Literal["idle", "visual", "audio", "scent", "memory"]
HeardFlow = Literal["real_noise"]


class EntityRow(TypedDict, total=False):
    """Subset of entity registry columns consumed by perception helpers."""

    entity_id: int
    x: int
    y: int
    faction: str
    ai_type: str
    species: str
    intelligence: int
    vision_range: int


class VisibleTarget(TypedDict):
    """AI-facing visible target snapshot with stable coordinate fields."""

    entity_id: int
    x: int
    y: int
    faction: NotRequired[str]


def _row_int(row: dict[str, object], key: str) -> int | None:
    value = row.get(key)
    return value if isinstance(value, int) else None


def _row_str(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) else None


def _has_perception_profile(row: dict[str, object]) -> bool:
    return bool(_row_str(row, "ai_type") or _row_str(row, "species")) or (
        _row_int(row, "intelligence") is not None
    )


def _visible_target_from_row(row: dict[str, object]) -> VisibleTarget | None:
    entity_id = _row_int(row, "entity_id")
    x = _row_int(row, "x")
    y = _row_int(row, "y")
    if entity_id is None or x is None or y is None:
        return None

    target: VisibleTarget = {"entity_id": entity_id, "x": x, "y": y}
    faction = _row_str(row, "faction")
    if faction is not None:
        target["faction"] = faction
    return target


def _active_memory_fact(game_state: GameState, entity_id: int) -> AIMemoryFact | None:
    memory = game_state.ai_memory.get(entity_id)
    if memory is None:
        return None
    if memory.expires_at_turn <= game_state.turn_count:
        return None
    return memory


@dataclass(slots=True)
class PerceptionFact:
    """Structured perception fact for a single entity."""

    signal_type: PerceptionSignal = "idle"
    confidence: float = 0.0
    visible_targets: list[VisibleTarget] = field(default_factory=list)
    heard_source: tuple[int, int] | None = None
    heard_flow: HeardFlow | None = None
    scent_strength: float = 0.0
    scent_position: tuple[int, int] | None = None
    last_known_position: tuple[int, int] | None = None


@dataclass(slots=True)
class PerceptionSnapshot:
    """Structured AI-facing perception snapshot plus optional debug maps."""

    los_map: NDArray[np.bool_]
    entity_facts: dict[int, PerceptionFact] = field(default_factory=dict)
    debug_noise_map: NDArray[np.float64] | None = None
    debug_scent_map: NDArray[np.float64] | None = None


def gather_perception(
    game_state: GameState,
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]]:
    """Generate legacy perception maps used by AI systems.

    Production sound/scent fields are advanced by ``GameState``. This function
    remains tuple-compatible for existing callers and tests. If legacy callers
    enqueue events and call this function directly, it advances those queued
    events without adding an automatic player scent stamp.
    """

    game_map = game_state.game_map
    if getattr(game_state, "noise_events", []) or getattr(
        game_state, "scent_events", []
    ):
        game_state.update_perception_fields(include_player_scent=False)

    noise_map = game_map.noise_map.copy()
    scent_map = game_map.scent_map.copy()
    los_map = game_map.visible.copy()
    log.debug("Perception maps generated", shape=noise_map.shape)
    return noise_map, scent_map, los_map


def find_visible_enemies_for_index(
    actor_idx: int,
    game_state: GameState,
    los_map: NDArray[np.bool_],
) -> list[VisibleTarget]:
    """Return a list of enemies visible to the entity at `actor_idx`."""
    registry = game_state.entity_registry
    actor_id = registry.entity_id_at(actor_idx)
    ex, ey = registry.xy_at(actor_idx)
    actor_faction = registry.faction_at(actor_idx)
    vision_range = (
        registry.get_component_at(actor_idx, "vision_range") or game_state.fov_radius
    )
    game_map = game_state.game_map
    enemies: list[VisibleTarget] = []

    spatial_index = getattr(game_state, "spatial_index", None)
    nearby = None
    if spatial_index is not None and hasattr(spatial_index, "query_radius"):
        nearby = spatial_index.query_radius((ex, ey), vision_range)

    if not nearby:
        # Fallback to scanning all active entities if spatial index is missing or empty
        nearby = []
        for other_idx in registry.active_indices():
            other_id = registry.entity_id_at(other_idx)
            ox, oy = registry.position_at(other_idx)
            nearby.append((other_id, ox, oy))

    prune_by_player_fov: bool = bool(
        getattr(game_state, "prune_npc_vision_by_player_fov", False)
    )

    candidate_indices: list[int] = []
    target_x: list[int] = []
    target_y: list[int] = []

    for candidate_id, ox, oy in nearby:
        if candidate_id == actor_id:
            continue

        candidate_idx = registry.index_of_entity(candidate_id)
        if candidate_idx is None:
            continue

        if not registry.is_active_at(candidate_idx):
            continue

        candidate_faction = registry.faction_at(candidate_idx)
        if actor_faction is not None:
            if candidate_faction is None or candidate_faction == actor_faction:
                continue

        if not game_map.in_bounds(ox, oy):
            continue

        if prune_by_player_fov and not los_map[oy, ox]:
            continue

        candidate_indices.append(candidate_idx)
        target_x.append(int(ox))
        target_y.append(int(oy))

    n_queries = len(candidate_indices)
    if n_queries > 0:
        sx = np.full(n_queries, int(ex), dtype=np.int32)
        sy = np.full(n_queries, int(ey), dtype=np.int32)
        ex_arr = np.asarray(target_x, dtype=np.int32)
        ey_arr = np.asarray(target_y, dtype=np.int32)

        visibility_mask = line_of_sight_many_u8(
            sx,
            sy,
            ex_arr,
            ey_arr,
            game_map.transparent,
        )

        for i, is_visible in enumerate(visibility_mask):
            if is_visible != 0:
                target = registry.visible_target_at(candidate_indices[i])
                if target is not None:
                    enemies.append(target)

    log.debug(
        "Visible enemies located for index",
        entity_id=actor_id,
        count=len(enemies),
    )
    return enemies


def _batch_visible_targets_for_actors(
    actor_indices: list[int],
    game_state: GameState,
    los_map: NDArray[np.bool_],
) -> dict[int, list[VisibleTarget]]:
    """Query LOS in a single batch for all listed actors and return visible targets by actor entity_id."""
    registry = game_state.entity_registry
    game_map = game_state.game_map
    spatial_index = getattr(game_state, "spatial_index", None)
    prune_by_player_fov = bool(
        getattr(game_state, "prune_npc_vision_by_player_fov", False)
    )

    sx_list: list[int] = []
    sy_list: list[int] = []
    ex_list: list[int] = []
    ey_list: list[int] = []
    query_meta: list[tuple[int, int]] = []

    for actor_idx in actor_indices:
        actor_id = registry.entity_id_at(actor_idx)
        ex, ey = registry.xy_at(actor_idx)
        actor_faction = registry.faction_at(actor_idx)
        vision_range = (
            registry.get_component_at(actor_idx, "vision_range")
            or game_state.fov_radius
        )

        nearby = None
        if spatial_index is not None and hasattr(spatial_index, "query_radius"):
            nearby = spatial_index.query_radius((ex, ey), vision_range)

        if not nearby:
            nearby = []
            for other_idx in registry.active_indices():
                other_id = registry.entity_id_at(other_idx)
                ox, oy = registry.position_at(other_idx)
                nearby.append((other_id, ox, oy))

        for candidate_id, ox, oy in nearby:
            if candidate_id == actor_id:
                continue

            candidate_idx = registry.index_of_entity(candidate_id)
            if candidate_idx is None:
                continue

            if not registry.is_active_at(candidate_idx):
                continue

            candidate_faction = registry.faction_at(candidate_idx)
            if actor_faction is not None:
                if candidate_faction is None or candidate_faction == actor_faction:
                    continue

            if not game_map.in_bounds(ox, oy):
                continue

            if prune_by_player_fov and not los_map[oy, ox]:
                continue

            sx_list.append(int(ex))
            sy_list.append(int(ey))
            ex_list.append(int(ox))
            ey_list.append(int(oy))
            query_meta.append((actor_id, candidate_idx))

    n_queries = len(sx_list)
    visible_targets_by_actor: dict[int, list[VisibleTarget]] = {
        int(registry.entity_id_at(idx)): [] for idx in actor_indices
    }

    if n_queries == 0:
        return visible_targets_by_actor

    sx = np.asarray(sx_list, dtype=np.int32)
    sy = np.asarray(sy_list, dtype=np.int32)
    ex_arr = np.asarray(ex_list, dtype=np.int32)
    ey_arr = np.asarray(ey_list, dtype=np.int32)

    visibility_mask = line_of_sight_many_u8(
        sx,
        sy,
        ex_arr,
        ey_arr,
        game_map.transparent,
    )

    for i, is_visible in enumerate(visibility_mask):
        if is_visible != 0:
            actor_id, candidate_idx = query_meta[i]
            target = registry.visible_target_at(candidate_idx)
            if target is not None:
                visible_targets_by_actor[actor_id].append(target)

    return visible_targets_by_actor


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

    registry = game_state.entity_registry
    cave_when = game_state.perception_cave_when
    game_map = game_state.game_map

    # 1. Collect all perceptive actor indices once
    actor_indices: list[int] = []
    for idx in registry.active_non_player_indices(game_state.player_id):
        idx = int(idx)
        if registry.has_perception_profile_at(idx):
            actor_indices.append(idx)

    # 2. Build and execute all actor-target LOS queries in one batch
    visible_targets_by_actor = _batch_visible_targets_for_actors(
        actor_indices,
        game_state,
        los_map,
    )

    for idx in actor_indices:
        ent_id = registry.entity_id_at(idx)
        ex, ey = registry.xy_at(idx)

        # 3. Retrieve pre-computed visible targets for this actor
        visible_targets = visible_targets_by_actor.get(ent_id, [])

        # 2. Audio facts
        heard_source = None
        if ent_id in alerted_set and ent_id != game_state.perception_noise_source_id:
            heard_source = global_heard_source
        heard_flow = "real_noise" if heard_source else None

        # 3. Scent facts
        current_scent = get_scent(cave_when, ey, ex)
        best_scent_val = current_scent
        best_scent_pos = None

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = ex + dx, ey + dy
            if (
                0 <= nx < game_map.width
                and 0 <= ny < game_map.height
                and game_map.transparent[ny, nx]
            ):
                n_scent = get_scent(cave_when, ny, nx)
                if n_scent > best_scent_val:
                    best_scent_val = n_scent
                    best_scent_pos = (nx, ny)

        scent_position = best_scent_pos
        scent_strength = best_scent_val if best_scent_pos else current_scent

        # Prioritize the current signals
        confidence = 0.0
        signal_type: PerceptionSignal = "idle"
        current_target_pos: tuple[int, int] | None = None

        if visible_targets:
            signal_type = "visual"
            confidence = 1.0
            first = visible_targets[0]
            current_target_pos = (first["x"], first["y"])
        elif heard_source:
            signal_type = "audio"
            confidence = 1.0
            current_target_pos = heard_source
        elif scent_position:
            signal_type = "scent"
            confidence = 0.8
            current_target_pos = scent_position

        last_known_position: tuple[int, int] | None = None
        active_memory = _active_memory_fact(game_state, ent_id)

        if signal_type in ("visual", "audio") and current_target_pos is not None:
            last_known_position = current_target_pos
        else:
            if active_memory is not None:
                last_known_position = active_memory.pos
                if signal_type == "idle":
                    signal_type = "memory"
                    confidence = 0.5

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


def apply_perception_memory_updates(
    game_state: GameState, snapshot: PerceptionSnapshot
) -> None:
    """Refresh GameState-owned AI memory exactly once per turn from a snapshot."""
    expires_at_turn = game_state.turn_count + game_state.ai_memory_duration_turns

    game_state.ai_memory = {
        entity_id: memory
        for entity_id, memory in game_state.ai_memory.items()
        if memory.expires_at_turn > game_state.turn_count
    }

    for entity_id, fact in snapshot.entity_facts.items():
        if fact.visible_targets:
            first = fact.visible_targets[0]
            game_state.ai_memory[entity_id] = AIMemoryFact(
                pos=(first["x"], first["y"]),
                expires_at_turn=expires_at_turn,
                source="visual",
            )
        elif fact.heard_source is not None:
            game_state.ai_memory[entity_id] = AIMemoryFact(
                pos=fact.heard_source,
                expires_at_turn=expires_at_turn,
                source="audio",
            )


def find_visible_enemies(
    entity_row: dict[str, object],
    game_state: GameState,
    los_map: NDArray[np.bool_],
) -> list[VisibleTarget]:
    """Return a list of enemies visible to ``entity_row``.

    Entities are considered enemies if they belong to a different faction.
    Visibility is determined using both the provided ``los_map`` and a
    line-of-sight check against the game map's transparency grid.
    """

    ex = _row_int(entity_row, "x")
    ey = _row_int(entity_row, "y")
    faction = _row_str(entity_row, "faction")
    entity_id = _row_int(entity_row, "entity_id")
    game_map = game_state.game_map
    enemies: list[VisibleTarget] = []

    if ex is None or ey is None or entity_id is None:
        return enemies

    # Use store accessors instead of entities_df for efficiency
    registry = game_state.entity_registry
    vision_range = _row_int(entity_row, "vision_range") or game_state.fov_radius
    spatial_index = getattr(game_state, "spatial_index", None)
    prune_by_player_fov = bool(
        getattr(game_state, "prune_npc_vision_by_player_fov", False)
    )

    # Build a dict of all valid enemy targets using store accessors
    enemy_rows: dict[int, VisibleTarget] = {}
    for idx in registry.active_indices():
        if not registry.is_active_at(int(idx)):
            continue
        other_id = registry.entity_id_at(int(idx))
        other_faction = registry.faction_at(int(idx))
        # Skip self
        if other_id == entity_id:
            continue
        # Skip same faction only if actor has a faction
        if faction is not None and other_faction == faction:
            continue
        target = registry.visible_target_at(int(idx))
        if target is not None:
            enemy_rows[other_id] = target

    # Get nearby entities from spatial index if available
    nearby: object = None
    if spatial_index is not None and hasattr(spatial_index, "query_radius"):
        nearby = spatial_index.query_radius((ex, ey), vision_range)

    sx_list: list[int] = []
    sy_list: list[int] = []
    ex_list: list[int] = []
    ey_list: list[int] = []
    query_meta: list[int] = []

    # Process candidates
    if nearby:
        # Use spatial index results - these are (entity_id, x, y) tuples
        for candidate in nearby:
            other_id, ox, oy = candidate
            # Skip if not in our pre-filtered enemy_rows
            other_row = enemy_rows.get(other_id)
            if other_row is None:
                continue
            if not game_map.in_bounds(int(ox), int(oy)):
                continue
            if prune_by_player_fov and not los_map[int(oy), int(ox)]:
                continue

            sx_list.append(int(ex))
            sy_list.append(int(ey))
            ex_list.append(int(ox))
            ey_list.append(int(oy))
            query_meta.append(other_id)
    else:
        # Fallback to all enemy_rows
        for other_id, other_row in enemy_rows.items():
            ox = other_row["x"]
            oy = other_row["y"]
            if not game_map.in_bounds(int(ox), int(oy)):
                continue
            if prune_by_player_fov and not los_map[int(oy), int(ox)]:
                continue

            sx_list.append(int(ex))
            sy_list.append(int(ey))
            ex_list.append(int(ox))
            ey_list.append(int(oy))
            query_meta.append(other_id)

    if not sx_list:
        return enemies

    visibility_mask = line_of_sight_many_u8(
        np.asarray(sx_list, dtype=np.int32),
        np.asarray(sy_list, dtype=np.int32),
        np.asarray(ex_list, dtype=np.int32),
        np.asarray(ey_list, dtype=np.int32),
        game_map.transparent,
    )

    for i, is_visible in enumerate(visibility_mask):
        if is_visible == 0:
            continue

        other_id = query_meta[i]
        target = enemy_rows.get(other_id)
        if target is not None:
            enemies.append(target)

    log.debug(
        "Visible enemies located",
        entity_id=entity_id,
        count=len(enemies),
    )
    return enemies


__all__ = [
    "PerceptionFact",
    "PerceptionSnapshot",
    "VisibleTarget",
    "apply_perception_memory_updates",
    "gather_perception",
    "gather_perception_snapshot",
    "find_visible_enemies",
    "find_visible_enemies_for_index",
]
