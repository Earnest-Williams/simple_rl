"""Overland worldgen schema, generation, and artifact utilities."""

from worldgen.overland.actor_traversal import (
    ActorTraversalProfile,
    build_actor_cost_grid,
    can_actor_enter,
    movement_cost_for_actor,
)
from worldgen.overland.affordances import generate_affordances
from worldgen.overland.convert import overland_to_game_map
from worldgen.overland.export import load_worldgen_bundle, write_overland_bundle
from worldgen.overland.generator import generate_overland_region
from worldgen.overland.hydrology import apply_hydrology_state
from worldgen.overland.inspect import render_overland_ascii
from worldgen.overland.pathfinding import OverlandRoute, find_overland_path
from worldgen.overland.queries import (
    find_feature,
    find_nearest_feature,
    find_tiles_by_hydro_role,
    find_tiles_by_material,
    first_tile_by_hydro_role,
    first_tile_by_material,
)
from worldgen.overland.routes import generate_debug_routes, overland_routes_to_df
from worldgen.overland.schema import (
    Affordance,
    Biome,
    EvidenceTag,
    FeatureType,
    HydroRole,
    HydroState,
    OverlandBundle,
    OverlandMapMetadata,
    RouteSegmentState,
    Substrate,
    SurfaceTransitionRequest,
    TransitionType,
    TraversalClass,
    Wetness,
)
from worldgen.overland.settlement_merge import merge_settlement_into_overland
from worldgen.overland.transitions import (
    generate_transition_requests,
    transition_requests_to_df,
)

__all__ = [
    "Affordance",
    "ActorTraversalProfile",
    "Biome",
    "EvidenceTag",
    "FeatureType",
    "HydroRole",
    "HydroState",
    "OverlandBundle",
    "OverlandMapMetadata",
    "OverlandRoute",
    "RouteSegmentState",
    "Substrate",
    "SurfaceTransitionRequest",
    "TransitionType",
    "TraversalClass",
    "Wetness",
    "apply_hydrology_state",
    "build_actor_cost_grid",
    "can_actor_enter",
    "generate_affordances",
    "generate_debug_routes",
    "generate_overland_region",
    "generate_transition_requests",
    "find_feature",
    "find_nearest_feature",
    "find_overland_path",
    "find_tiles_by_hydro_role",
    "find_tiles_by_material",
    "first_tile_by_hydro_role",
    "first_tile_by_material",
    "load_worldgen_bundle",
    "merge_settlement_into_overland",
    "movement_cost_for_actor",
    "overland_to_game_map",
    "overland_routes_to_df",
    "render_overland_ascii",
    "transition_requests_to_df",
    "write_overland_bundle",
]
