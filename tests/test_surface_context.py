"""Tests for SurfaceContext semantic query verbs (Phase 2).

Covers docs/Surface Map Plan.md Phase 2: verb queries over a runtime
GameMap with an attached OverlandMapMetadata sidecar, traversal profile
delegation, route segment state, spawn anchors, and the no-metadata
fallback.
"""

from __future__ import annotations

import numpy as np
import pytest

from common.constants import Material
from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
from game.world.surface_context import SurfaceContext, SurfaceSpawnProfile
from worldgen.overland.actor_traversal import ActorTraversalProfile
from worldgen.overland.schema import (
    HydroRole,
    OverlandMapMetadata,
    RouteSegmentState,
    TraversalClass,
    Wetness,
)

_WIDTH = 8
_HEIGHT = 8

_WATER_MATERIALS = frozenset(
    {
        Material.SHALLOW_WATER,
        Material.DEEP_WATER,
        Material.FLOWING_WATER,
        Material.SPRING_WATER,
    }
)
_BLOCKED_MATERIALS = frozenset(
    {
        Material.LIMESTONE,
        Material.LIMESTONE_PAVEMENT,
        Material.LIMESTONE_CLIFF,
        Material.BASALT,
        Material.BASALT_PAVEMENT,
        Material.BASALT_CLIFF,
    }
)


def _build_surface_map(
    materials: dict[tuple[int, int], Material],
    *,
    route_segments: list[dict[str, object]] | None = None,
    affordances: dict[tuple[int, int], list[dict[str, object]]] | None = None,
    hydro_roles: dict[tuple[int, int], HydroRole] | None = None,
    ceiling: dict[tuple[int, int], int] | None = None,
) -> GameMap:
    """Build a small runtime map with an overland metadata sidecar."""
    game_map = GameMap(width=_WIDTH, height=_HEIGHT)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()

    material_grid = np.full((_HEIGHT, _WIDTH), int(Material.GRASS), dtype=np.int16)
    traversal_grid = np.full(
        (_HEIGHT, _WIDTH), int(TraversalClass.NORMAL), dtype=np.int16
    )
    wetness_grid = np.full((_HEIGHT, _WIDTH), int(Wetness.DRY), dtype=np.int16)
    cost_grid = np.ones((_HEIGHT, _WIDTH), dtype=np.float32)
    hydro_grid = np.zeros((_HEIGHT, _WIDTH), dtype=np.int16)

    for (x, y), material in materials.items():
        material_grid[y, x] = int(material)
        if material in _WATER_MATERIALS:
            traversal_grid[y, x] = int(TraversalClass.SWIM_OR_BOAT)
            wetness_grid[y, x] = int(Wetness.DEEP_FLOODED)
        elif material in _BLOCKED_MATERIALS:
            traversal_grid[y, x] = int(TraversalClass.BLOCKED)
            cost_grid[y, x] = np.inf

    for (x, y), role in (hydro_roles or {}).items():
        hydro_grid[y, x] = int(role)

    for (x, y), height in (ceiling or {}).items():
        game_map.ceiling_map[y, x] = height

    sidecar = OverlandMapMetadata(
        material_grid=material_grid,
        biome_grid=np.zeros((_HEIGHT, _WIDTH), dtype=np.int16),
        hydro_grid=hydro_grid,
        wetness_grid=wetness_grid,
        movement_cost_grid=cost_grid,
        traversal_class_grid=traversal_grid,
        route_segments=route_segments or [],
        evidence_tags={},
        transitions={},
        affordances=affordances or {},
        starting_contract={},
    )
    game_map.overland_metadata = sidecar
    return game_map


def _default_materials() -> dict[tuple[int, int], Material]:
    return {
        (1, 1): Material.DIRT,
        (2, 1): Material.MUD,
        (3, 1): Material.LIMESTONE,
        (4, 1): Material.REEDBED,
        (5, 1): Material.BUILDING_FLOOR,
        (6, 1): Material.ROAD,
        (1, 2): Material.CAVE_FLOOR,
        (2, 2): Material.FOREST_FLOOR,
        (5, 2): Material.DEEP_WATER,
        (6, 2): Material.SPRING_WATER,
    }


def test_surface_context_verb_queries() -> None:
    context = SurfaceContext(_build_surface_map(_default_materials()))

    # Diggable soil vs solid rock.
    assert context.can_dig(1, 1) is True
    assert context.can_dig(2, 1) is True
    assert context.can_dig(3, 1) is False

    # Flammable organics vs mineral surfaces.
    assert context.can_burn(4, 1) is True
    assert context.can_burn(2, 2) is True
    assert context.can_burn(3, 1) is False
    assert context.can_burn(6, 1) is False

    # Impressionable ground retains tracks; roads and rock do not.
    assert context.can_track(2, 1) is True
    assert context.can_track(1, 1) is False
    assert context.can_track(6, 1) is False
    assert context.can_track(3, 1) is False

    # Shelter from interior floors and from explicit ceiling height.
    assert context.has_shelter(5, 1) is True
    assert context.has_shelter(1, 2) is True
    assert context.has_shelter(2, 2) is False
    ceiled = _build_surface_map(
        _default_materials(), ceiling={(3, 3): 4}
    )
    assert SurfaceContext(ceiled).has_shelter(3, 3) is True

    # Forage from vegetation surfaces and from tile affordances.
    assert context.can_forage(2, 2) is True
    assert context.can_forage(6, 1) is False
    afforded = _build_surface_map(
        _default_materials(),
        affordances={(7, 1): [{"affordance": 1}]},
    )
    assert SurfaceContext(afforded).can_forage(7, 1) is True

    # Conductivity/permeability are bounded multipliers with expected order.
    assert 0.0 < context.sound_conductivity(3, 1) <= 1.0
    assert context.sound_conductivity(5, 1) > context.sound_conductivity(4, 1)
    assert 0.0 < context.scent_permeability(2, 1) <= 1.0
    assert context.scent_permeability(2, 1) > context.scent_permeability(6, 1)


def test_surface_context_can_walk_profiles() -> None:
    context = SurfaceContext(_build_surface_map(_default_materials()))

    human = ActorTraversalProfile.HUMAN_ON_FOOT
    boat = ActorTraversalProfile.BOAT
    amphibious = ActorTraversalProfile.SMALL_AMPHIBIOUS

    # Humans walk ordinary ground but not deep water or blocked rock.
    assert context.can_walk(human, 1, 1) is True
    assert context.can_walk(human, 5, 2) is False
    assert context.can_walk(human, 3, 1) is False

    # Boats require water surfaces.
    assert context.can_walk(boat, 5, 2) is True
    assert context.can_walk(boat, 6, 2) is True
    assert context.can_walk(boat, 1, 1) is False

    # Amphibious profiles move through both land and water, but not rock.
    assert context.can_walk(amphibious, 1, 1) is True
    assert context.can_walk(amphibious, 5, 2) is True
    assert context.can_walk(amphibious, 3, 1) is False


def test_surface_context_route_state_blocks_road() -> None:
    blocked = SurfaceContext(
        _build_surface_map(
            _default_materials(),
            route_segments=[{"state": int(RouteSegmentState.BLOCKED)}],
        )
    )
    assert blocked.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 6, 1) is False

    repaired = SurfaceContext(
        _build_surface_map(
            _default_materials(),
            route_segments=[{"state": int(RouteSegmentState.REPAIRED)}],
        )
    )
    assert repaired.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 6, 1) is True


def test_surface_context_no_metadata_fallback() -> None:
    game_map = GameMap(width=4, height=4)
    game_map.tiles[:, :] = TILE_ID_WALL
    game_map.tiles[1, 1] = TILE_ID_FLOOR
    game_map.tiles[2, 2] = TILE_ID_FLOOR
    game_map.update_tile_transparency()

    context = SurfaceContext(game_map)
    assert context.has_overland_metadata is False

    human = ActorTraversalProfile.HUMAN_ON_FOOT
    assert context.can_walk(human, 1, 1) is True
    assert context.can_walk(human, 0, 0) is False

    # Without material data the semantic verbs stay conservative.
    assert context.can_dig(1, 1) is False
    assert context.can_burn(1, 1) is False
    assert context.can_track(1, 1) is False
    assert context.can_forage(1, 1) is False
    assert context.sound_conductivity(1, 1) == pytest.approx(0.6)
    assert context.scent_permeability(1, 1) == pytest.approx(0.5)

    # Ceiling-derived shelter still works without a sidecar.
    game_map.ceiling_map[1, 1] = 3
    assert context.has_shelter(1, 1) is True


def test_surface_context_spawn_anchors() -> None:
    context = SurfaceContext(
        _build_surface_map(
            _default_materials(),
            affordances={(7, 2): [{"affordance": 1}]},
            hydro_roles={(4, 2): HydroRole.SPRING},
        )
    )

    # Settlement anchors need settlement materials and human access.
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.HUMAN_SETTLEMENT, 6, 1)
    assert not context.is_valid_spawn_anchor(
        SurfaceSpawnProfile.HUMAN_SETTLEMENT, 2, 2
    )
    assert not context.is_valid_spawn_anchor(SurfaceSpawnProfile.HUMAN_SETTLEMENT, 2, 1)

    # Water wildlife anchors: water material, affordance, or hydro role.
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.WATER_WILDLIFE, 5, 2)
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.WATER_WILDLIFE, 7, 2)
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.WATER_WILDLIFE, 4, 2)
    assert not context.is_valid_spawn_anchor(SurfaceSpawnProfile.WATER_WILDLIFE, 3, 1)

    # Forage wildlife anchors need forageable surfaces.
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.FORAGE_WILDLIFE, 2, 2)
    assert not context.is_valid_spawn_anchor(SurfaceSpawnProfile.FORAGE_WILDLIFE, 6, 1)

    # Cave monster anchors need cave-adjacent materials.
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.CAVE_MONSTER, 1, 2)
    assert not context.is_valid_spawn_anchor(SurfaceSpawnProfile.CAVE_MONSTER, 2, 2)


def test_surface_context_out_of_bounds() -> None:
    context = SurfaceContext(_build_surface_map(_default_materials()))
    with pytest.raises(IndexError):
        context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, _WIDTH, 0)
    with pytest.raises(IndexError):
        context.can_dig(-1, 0)
    with pytest.raises(IndexError):
        context.has_shelter(0, _HEIGHT)
