from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum, auto

import numpy as np
import polars as pl

from common.constants import Material
from worldgen.overland.schema import (
    OverlandMapMetadata,
    RouteSegmentState,
    TraversalClass,
    Wetness,
)


class ActorTraversalProfile(IntEnum):
    HUMAN_ON_FOOT = auto()
    PACK_ANIMAL = auto()
    SMALL_AMPHIBIOUS = auto()
    SWIMMER = auto()
    BOAT = auto()


_PROFILE_MULTIPLIERS: Mapping[ActorTraversalProfile, Mapping[TraversalClass, float]] = {
    ActorTraversalProfile.HUMAN_ON_FOOT: {
        TraversalClass.NORMAL: 1.0,
        TraversalClass.SLOW: 1.25,
        TraversalClass.WADE: 1.5,
        TraversalClass.HAZARDOUS: 2.0,
        TraversalClass.TRANSITION: 1.0,
    },
    ActorTraversalProfile.PACK_ANIMAL: {
        TraversalClass.NORMAL: 1.0,
        TraversalClass.SLOW: 1.75,
        TraversalClass.WADE: 2.0,
        TraversalClass.HAZARDOUS: 3.0,
        TraversalClass.TRANSITION: 1.0,
    },
    ActorTraversalProfile.SMALL_AMPHIBIOUS: {
        TraversalClass.NORMAL: 1.0,
        TraversalClass.SLOW: 0.9,
        TraversalClass.WADE: 0.65,
        TraversalClass.SWIM_OR_BOAT: 0.85,
        TraversalClass.HAZARDOUS: 1.5,
        TraversalClass.TRANSITION: 1.0,
    },
    ActorTraversalProfile.SWIMMER: {
        TraversalClass.NORMAL: 1.25,
        TraversalClass.SLOW: 1.5,
        TraversalClass.WADE: 0.8,
        TraversalClass.SWIM_OR_BOAT: 1.0,
        TraversalClass.HAZARDOUS: 2.0,
        TraversalClass.TRANSITION: 1.0,
    },
    ActorTraversalProfile.BOAT: {
        TraversalClass.WADE: 2.0,
        TraversalClass.SWIM_OR_BOAT: 1.0,
        TraversalClass.TRANSITION: 1.0,
    },
}


def can_actor_enter(
    tile_row: Mapping[str, object],
    profile: ActorTraversalProfile,
    metadata: OverlandMapMetadata | None = None,
) -> bool:
    cost = movement_cost_for_actor(tile_row, profile, metadata=metadata)
    return bool(np.isfinite(cost))


def movement_cost_for_actor(
    tile_row: Mapping[str, object],
    profile: ActorTraversalProfile,
    metadata: OverlandMapMetadata | None = None,
) -> float:
    """Extended to respect RouteSegmentState from metadata for repair simulation.

    REPAIRED roads get cost reduction; BLOCKED = inf. Falls back to existing logic.
    """
    # Casts for mypy (tile_row from pl.DataFrame iter_rows is typed as object; legacy in inspect.py too)
    traversal = TraversalClass(int(tile_row["traversal_class"]))  # type: ignore[arg-type]
    if traversal == TraversalClass.BLOCKED:
        return float("inf")
    material = Material(int(tile_row["material"]))  # type: ignore[arg-type]
    wetness = Wetness(int(tile_row["wetness"]))  # type: ignore[arg-type]
    if not _profile_allows_material(profile, material, wetness, traversal):
        return float("inf")
    multiplier = _PROFILE_MULTIPLIERS.get(profile, {}).get(traversal)
    if multiplier is None:
        return float("inf")
    base_cost = float(tile_row["movement_cost"])  # type: ignore[arg-type]
    if not np.isfinite(base_cost):
        return float("inf")

    # Check route state from metadata for road tiles (minimal, focused; reuse RouteSegmentState).
    # Avoids Any by using list[dict] from OverlandMapMetadata and dict checks.
    if (
        metadata is not None
        and hasattr(metadata, "route_segments")
        and material == Material.ROAD
    ):
        for seg in metadata.route_segments:  # type: ignore[attr-defined]
            if isinstance(seg, dict):
                state = seg.get("state")
                if state == int(RouteSegmentState.BLOCKED):
                    return float("inf")
                if state == int(RouteSegmentState.REPAIRED):
                    multiplier *= 0.75  # repaired roads easier
                    break

    return base_cost * multiplier


def build_actor_cost_grid(
    tiles_df: pl.DataFrame,
    profile: ActorTraversalProfile,
    metadata: OverlandMapMetadata | None = None,
) -> np.ndarray:
    """Extended to pass metadata for route repair state impact on costs."""
    width = int(tiles_df.get_column("x").max()) + 1
    height = int(tiles_df.get_column("y").max()) + 1
    cost_grid = np.full((height, width), np.inf, dtype=np.float32)
    for row in tiles_df.iter_rows(named=True):
        x = int(row["x"])
        y = int(row["y"])
        cost_grid[y, x] = movement_cost_for_actor(row, profile, metadata=metadata)
    return cost_grid


def _profile_allows_material(
    profile: ActorTraversalProfile,
    material: Material,
    wetness: Wetness,
    traversal: TraversalClass,
) -> bool:
    if profile == ActorTraversalProfile.BOAT:
        return (
            material
            in {
                Material.SHALLOW_WATER,
                Material.DEEP_WATER,
                Material.FLOWING_WATER,
                Material.SPRING_WATER,
                Material.SINKING_WATER,
                Material.ESTAVELLE_WATER,
                Material.STAGNANT_WATER,
                Material.BOG_WATER,
                Material.DOCK,
            }
            or traversal == TraversalClass.TRANSITION
        )
    if profile == ActorTraversalProfile.PACK_ANIMAL:
        return (
            material
            not in {
                Material.DEEP_MUD,
                Material.PONOR,
                Material.CAVE_MOUTH,
                Material.LAVA_TUBE_SKYLIGHT,
                Material.COLLAPSED_LAVA_TUBE,
            }
            and wetness != Wetness.DEEP_FLOODED
        )
    if profile == ActorTraversalProfile.HUMAN_ON_FOOT:
        return wetness != Wetness.DEEP_FLOODED
    if profile in {
        ActorTraversalProfile.SMALL_AMPHIBIOUS,
        ActorTraversalProfile.SWIMMER,
    }:
        return True
    return True
