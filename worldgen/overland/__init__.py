"""Overland worldgen schema, generation, and artifact utilities."""

from worldgen.overland.affordances import generate_affordances
from worldgen.overland.convert import overland_to_game_map
from worldgen.overland.export import load_worldgen_bundle, write_overland_bundle
from worldgen.overland.generator import generate_overland_region
from worldgen.overland.hydrology import apply_hydrology_state
from worldgen.overland.inspect import render_overland_ascii
from worldgen.overland.schema import (
    Affordance,
    Biome,
    HydroRole,
    HydroState,
    OverlandBundle,
    Substrate,
    SurfaceTransitionRequest,
    TransitionType,
    Wetness,
)
from worldgen.overland.settlement_merge import merge_settlement_into_overland
from worldgen.overland.transitions import generate_transition_requests

__all__ = [
    "Affordance",
    "Biome",
    "HydroRole",
    "HydroState",
    "OverlandBundle",
    "Substrate",
    "SurfaceTransitionRequest",
    "TransitionType",
    "Wetness",
    "apply_hydrology_state",
    "generate_affordances",
    "generate_overland_region",
    "generate_transition_requests",
    "load_worldgen_bundle",
    "merge_settlement_into_overland",
    "overland_to_game_map",
    "render_overland_ascii",
    "write_overland_bundle",
]
