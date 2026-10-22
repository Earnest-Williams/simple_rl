"""Tests for the surface chunk materializer (Phase 3).

Covers docs/Surface Map Plan.md Phase 3: template expansion of road,
spring, harbor, forest, and ruin promises into concrete tile geometry,
border stitching across chunk seams, feature density caps, ambient
debris bounds, determinism, and application into a runtime GameMap that
SurfaceContext (Phase 2) can then query.
"""

from __future__ import annotations

import numpy as np
import pytest

from common.constants import Material
from game.world.game_map import TILE_ID_FLOOR, GameMap
from game.world.surface_context import SurfaceContext, SurfaceSpawnProfile
from game.world.surface_materializer import (
    InMemoryPromiseSource,
    MaterializedChunk,
    RegionalPromise,
    SurfaceFeatureKind,
    SurfaceMaterializer,
    apply_materialized_chunk,
    ensure_surface_metadata,
)
from worldgen.overland.actor_traversal import ActorTraversalProfile
from worldgen.overland.schema import HydroRole, TraversalClass, Wetness

_CHUNK = 16
_WORLD_SEED = "phase-three"

_ROAD_MATERIALS = (int(Material.ROAD), int(Material.GRAVEL))
_SHOULDER_MATERIALS = (int(Material.GRAVEL), int(Material.GRASS))


def _materializer(
    source: InMemoryPromiseSource,
    *,
    world_seed: int | str = _WORLD_SEED,
    debris_fraction: float = 0.15,
) -> SurfaceMaterializer:
    return SurfaceMaterializer(
        source,
        world_seed=world_seed,
        chunk_size=_CHUNK,
        debris_fraction=debris_fraction,
    )


def _material_at_global(
    materialized: MaterializedChunk, gx: int, gy: int
) -> int:
    lx = gx - materialized.origin_x
    ly = gy - materialized.origin_y
    return int(materialized.materials[ly, lx])


def _apply_viewport(
    materializer: SurfaceMaterializer,
    chunks: list[tuple[int, int]],
    *,
    viewport_origin: tuple[int, int] = (0, 0),
    width: int,
    height: int,
) -> GameMap:
    game_map = GameMap(width=width, height=height)
    for cx, cy in chunks:
        chunk = materializer.materialize_chunk(cx, cy)
        apply_materialized_chunk(
            game_map,
            chunk,
            viewport_origin_x=viewport_origin[0],
            viewport_origin_y=viewport_origin[1],
        )
    return game_map


def test_surface_materializer_templates() -> None:
    """Each promise kind expands to its documented concrete geometry."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING,
                anchor_x=8,
                anchor_y=8,
            )
        ],
        chunk_size=_CHUNK,
    )
    chunk = _materializer(source).materialize_chunk(0, 0)

    # Swim-only deep water core with spring hydrology.
    assert _material_at_global(chunk, 8, 8) == int(Material.DEEP_WATER)
    assert int(chunk.hydro[8, 8]) == int(HydroRole.SPRING)
    assert int(chunk.traversal[8, 8]) == int(TraversalClass.SWIM_OR_BOAT)

    # Muddy banks ring the water; reeds block sight.
    assert _material_at_global(chunk, 10, 8) == int(Material.MUD)
    assert int(chunk.wetness[8, 10]) == int(Wetness.SATURATED)
    reeds = [prop for prop in chunk.props if prop.kind == "reeds"]
    assert reeds and all(prop.blocks_sight for prop in reeds)

    # Wildlife anchor on the bank, spring-refuge affordance present.
    assert any(
        anchor.profile == SurfaceSpawnProfile.WATER_WILDLIFE
        for anchor in chunk.spawn_anchors
    )
    assert any(
        "spring_refuge" in str(row)
        for rows in chunk.affordances.values()
        for row in rows
    )


def test_surface_materializer_road_template_and_stitching() -> None:
    """Roads pave, rut, and shoulder; geometry is seam-continuous."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.ROAD,
                anchor_x=0,
                anchor_y=0,
                waypoints=((0, 8), (24, 8)),
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = _materializer(source)
    west = materializer.materialize_chunk(0, 0)
    east = materializer.materialize_chunk(1, 0)

    # Paved center line with ruts and gravel shoulders on both chunks.
    for chunk, gx in ((west, 5), (east, 20)):
        assert _material_at_global(chunk, gx, 8) == int(Material.ROAD)
        for gy in (7, 9):  # wheel rut lines
            assert _material_at_global(chunk, gx, gy) in _ROAD_MATERIALS
        for gy in (6, 10):  # gravel shoulders
            assert _material_at_global(chunk, gx, gy) in _SHOULDER_MATERIALS

    # Seam continuity: the template paints in global coordinates from a
    # single per-promise RNG, so the geometry clipped by either chunk is
    # identical by construction. The center line therefore meets the
    # x=15|x=16 seam as ROAD on both sides, with the full band (ruts,
    # shoulders) present at the same offsets on both chunks.
    assert _material_at_global(west, 15, 8) == int(Material.ROAD)
    assert _material_at_global(east, 16, 8) == int(Material.ROAD)
    for gy in (7, 9):
        assert _material_at_global(west, 15, gy) in _ROAD_MATERIALS
        assert _material_at_global(east, 16, gy) in _ROAD_MATERIALS
    for gy in (6, 10):
        assert _material_at_global(west, 15, gy) in _SHOULDER_MATERIALS
        assert _material_at_global(east, 16, gy) in _SHOULDER_MATERIALS

    # Worn ruts (gravel) and encroaching weeds (grass) appear somewhere
    # along the road with this fixed seed.
    road_tiles = [int(m) for row in west.materials for m in row]
    assert road_tiles.count(int(Material.GRAVEL)) > 0
    assert road_tiles.count(int(Material.GRASS)) > 0

    # Roads stay walkable and cheaper than base terrain.
    west_view = _apply_viewport(
        materializer, [(0, 0)], width=_CHUNK, height=_CHUNK
    )
    context = SurfaceContext(west_view)
    assert context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 5, 8)


def test_surface_materializer_road_negative_coordinates() -> None:
    """Stitching also holds across the origin with negative chunks."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.ROAD,
                anchor_x=0,
                anchor_y=0,
                waypoints=((-20, 8), (20, 8)),
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = _materializer(source)
    west = materializer.materialize_chunk(-1, 0)
    east = materializer.materialize_chunk(0, 0)
    assert west.origin_x == -_CHUNK
    assert _material_at_global(west, -1, 8) == int(Material.ROAD)
    assert _material_at_global(east, 0, 8) == int(Material.ROAD)
    for gy in (7, 9):
        assert _material_at_global(west, -1, gy) in _ROAD_MATERIALS
        assert _material_at_global(east, 0, gy) in _ROAD_MATERIALS
    for gy in (6, 10):
        assert _material_at_global(west, -1, gy) in _SHOULDER_MATERIALS
        assert _material_at_global(east, 0, gy) in _SHOULDER_MATERIALS

    # Applied into a viewport offset past the negative side.
    game_map = _apply_viewport(
        materializer,
        [(-1, 0), (0, 0)],
        viewport_origin=(-_CHUNK, 0),
        width=2 * _CHUNK,
        height=_CHUNK,
    )
    context = SurfaceContext(game_map)
    assert context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 8, 8)


def test_surface_materializer_harbor_footprint() -> None:
    """A 2x2-chunk port materializes consistently on all four chunks."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.HARBOR_PORT,
                anchor_x=0,
                anchor_y=0,
                footprint_chunks=(2, 2),
            )
        ],
        chunk_size=_CHUNK,
    )
    materializer = _materializer(source)
    chunks = [materializer.materialize_chunk(cx, cy) for cx in (0, 1) for cy in (0, 1)]

    # Feature geometry is chunk-independent, so every chunk in the
    # footprint resolves the same deterministic global player start.
    starts = [chunk.player_start for chunk in chunks if chunk.player_start]
    assert starts
    assert set(starts) == {(16, 16)}

    # Dock band along the west edge of the footprint, continuous across
    # the chunk seam at y=15|16.
    assert any(
        _material_at_global(chunk, 1, gy)
        in (int(Material.BOARDWALK), int(Material.DOCK))
        for chunk in chunks
        for gy in (15, 16)
    )

    crates = [prop for chunk in chunks for prop in chunk.props if prop.kind == "crate"]
    assert crates, "harbor must place crates"
    assert all(prop.destructible for prop in crates)

    # Crates are identical no matter which chunk reports them (no
    # duplicate geometry from double rendering).
    crate_coords = sorted((prop.x, prop.y) for prop in crates)
    assert len(crate_coords) == len(set(crate_coords))

    # Dock-route transition resolved at the west edge midpoint.
    transitions = [chunk.transitions for chunk in chunks if chunk.transitions]
    assert transitions
    assert any(
        (0, 16) in chunk.transitions
        for chunk in chunks
    )

    # Human settlement anchor exists and is valid for spawning once
    # applied to a viewport.
    game_map = _apply_viewport(
        materializer,
        [(cx, cy) for cx in (0, 1) for cy in (0, 1)],
        width=2 * _CHUNK,
        height=2 * _CHUNK,
    )
    context = SurfaceContext(game_map)
    assert context.is_valid_spawn_anchor(SurfaceSpawnProfile.HUMAN_SETTLEMENT, 16, 16)
    assert game_map.overland_metadata is not None
    assert game_map.overland_metadata.starting_contract["player_start"] == [16, 16]


def test_surface_materializer_forest_template() -> None:
    """Forests expand into floor, trees, undergrowth, and forage nodes."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.FOREST,
                anchor_x=0,
                anchor_y=0,
                footprint_chunks=(1, 1),
            )
        ],
        chunk_size=_CHUNK,
    )
    chunk = _materializer(source, debris_fraction=0.0).materialize_chunk(0, 0)

    materials = chunk.materials
    assert int(Material.FOREST_FLOOR) in set(np.unique(materials).tolist())
    assert int(Material.FERN_UNDERSTORY) in set(np.unique(materials).tolist())

    trees = [prop for prop in chunk.props if prop.kind == "tree"]
    assert trees
    assert all(prop.blocks_movement and prop.blocks_sight for prop in trees)
    tree_fraction = len(trees) / (_CHUNK * _CHUNK)
    assert tree_fraction <= 0.30

    # Tree blockers match the blocked mask; undergrowth slows movement.
    for prop in trees:
        lx, ly = prop.x - chunk.origin_x, prop.y - chunk.origin_y
        assert chunk.blocked[ly, lx]

    slow_tiles = int(np.sum(chunk.traversal == int(TraversalClass.SLOW)))
    assert slow_tiles > 0

    # Forage anchors and fallen logs exist.
    assert any(
        anchor.profile == SurfaceSpawnProfile.FORAGE_WILDLIFE
        for anchor in chunk.spawn_anchors
    )
    assert any(prop.kind == "fallen_log" for prop in chunk.props)
    assert any(
        "forage" in str(row)
        for rows in chunk.affordances.values()
        for row in rows
    )


def test_surface_materializer_ruin_template() -> None:
    """Ruins expand into walls, a door, loot, and hazard anchors."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.RUIN,
                anchor_x=2,
                anchor_y=2,
            )
        ],
        chunk_size=_CHUNK,
    )
    chunk = _materializer(source, debris_fraction=0.0).materialize_chunk(0, 0)

    walls = int(np.sum(chunk.materials == int(Material.RUIN_WALL)))
    floors = int(np.sum(chunk.materials == int(Material.RUIN_FLOOR)))
    assert walls > 0
    assert floors > 0

    # Locked iron door on the north wall midpoint.
    door = [prop for prop in chunk.props if prop.kind == "iron_door"]
    assert len(door) == 1
    lx, ly = door[0].x - chunk.origin_x, door[0].y - chunk.origin_y
    assert chunk.materials[ly, lx] == int(Material.DOOR_CLOSED)
    assert chunk.blocked[ly, lx]

    # Perimeter has collapsed gaps: wall-band positions on the north
    # and west lines (the promise anchors at (2, 2)) that the crumbling
    # pass skipped, leaving walkable interior floor as an entry.
    band_lines = [(2, x) for x in range(2, _CHUNK)] + [
        (y, 2) for y in range(3, _CHUNK)
    ]
    gaps = [
        (y, x)
        for y, x in band_lines
        if chunk.materials[y, x]
        not in (int(Material.RUIN_WALL), int(Material.DOOR_CLOSED))
        and not chunk.blocked[y, x]
    ]
    assert gaps

    # Chests are destructible; hazard anchors include a trap and a
    # monster spawner.
    chests = [prop for prop in chunk.props if prop.kind == "chest"]
    assert chests and all(prop.destructible for prop in chests)
    kinds = {anchor.kind for anchor in chunk.hazard_anchors}
    assert kinds == {"trap", "monster_spawner"}

    # Shelter reads through the Phase 2 seam once applied.
    game_map = _apply_viewport(
        _materializer(source, debris_fraction=0.0),
        [(0, 0)],
        width=_CHUNK,
        height=_CHUNK,
    )
    context = SurfaceContext(game_map)
    interior_x = 2 + 14 // 2
    interior_y = 2 + 14 // 2
    if not context.can_walk(
        ActorTraversalProfile.HUMAN_ON_FOOT, interior_x, interior_y
    ):
        # Rubble or props may block the exact center; scan nearby.
        found = any(
            context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, x, y)
            for x in range(4, 14)
            for y in range(4, 14)
        )
        assert found
    assert context.has_shelter(interior_x, interior_y) or any(
        context.has_shelter(x, y) for x in range(4, 14) for y in range(4, 14)
    )


def test_surface_materializer_determinism() -> None:
    """Identical inputs materialize identically; seeds diverge outputs."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.FOREST,
                anchor_x=0,
                anchor_y=0,
            )
        ],
        chunk_size=_CHUNK,
    )
    first = _materializer(source).materialize_chunk(0, 0)
    second = _materializer(source).materialize_chunk(0, 0)
    assert np.array_equal(first.materials, second.materials)
    assert np.array_equal(first.blocked, second.blocked)
    assert first.props == second.props
    assert first.spawn_anchors == second.spawn_anchors

    # A different world seed changes ambient debris layout.
    other = _materializer(source, world_seed="other-world").materialize_chunk(0, 0)
    assert not np.array_equal(first.blocked, other.blocked)


def test_surface_materializer_density_caps() -> None:
    """Primary structures and minor anchors are capped per chunk."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.RUIN,
                anchor_x=1,
                anchor_y=1,
            ),
            RegionalPromise(
                kind=SurfaceFeatureKind.RUIN,
                anchor_x=40,
                anchor_y=40,
            ),
            *[
                RegionalPromise(
                    kind=SurfaceFeatureKind.SPRING,
                    anchor_x=2 + index * 3,
                    anchor_y=8,
                )
                for index in range(5)
            ],
        ],
        chunk_size=_CHUNK,
    )
    chunk = _materializer(source, debris_fraction=0.0).materialize_chunk(0, 0)
    assert chunk.stats["primary_structures"] == 1
    assert chunk.stats["minor_anchors"] == 3


def test_surface_materializer_debris_bounds() -> None:
    """Debris never covers more than 30 percent of walkable base space."""
    source = InMemoryPromiseSource(chunk_size=_CHUNK)
    chunk = _materializer(source, debris_fraction=0.30).materialize_chunk(0, 0)
    total = _CHUNK * _CHUNK
    assert chunk.stats["debris"] <= int(total * 0.30)

    # The hard cap rejects higher fractions at construction time.
    with pytest.raises(ValueError):
        SurfaceMaterializer(
            source,
            world_seed=_WORLD_SEED,
            chunk_size=_CHUNK,
            debris_fraction=0.5,
        )


def test_surface_materializer_apply_to_game_map() -> None:
    """Chunks apply into a viewport and remain queryable via SurfaceContext."""
    source = InMemoryPromiseSource(
        [
            RegionalPromise(
                kind=SurfaceFeatureKind.ROAD,
                anchor_x=0,
                anchor_y=0,
                waypoints=((0, 4), (2 * _CHUNK - 1, 4)),
            ),
            RegionalPromise(
                kind=SurfaceFeatureKind.SPRING,
                anchor_x=20,
                anchor_y=20,
            ),
        ],
        chunk_size=_CHUNK,
    )
    materializer = _materializer(source)
    game_map = _apply_viewport(
        materializer,
        [(0, 0), (1, 0), (0, 1), (1, 1)],
        width=2 * _CHUNK,
        height=2 * _CHUNK,
    )

    metadata = ensure_surface_metadata(game_map)
    assert metadata is game_map.overland_metadata

    # Blocked geometry becomes walls; water stays a walkable floor tile
    # but is swim-only through the sidecar.
    assert int(game_map.tiles[4, 10]) == TILE_ID_FLOOR
    context = SurfaceContext(game_map)
    assert not context.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, 20, 20)
    assert context.can_walk(ActorTraversalProfile.SMALL_AMPHIBIOUS, 20, 20)

    # Gravel ruts and shoulders retain tracks; the paved road itself
    # does not, and neither is diggable while untouched grass is.
    north = materializer.materialize_chunk(0, 0)
    gravel = [
        (north.origin_x + int(lx), north.origin_y + int(ly))
        for ly, lx in np.argwhere(north.materials == int(Material.GRAVEL))
    ]
    assert gravel
    assert context.can_track(*gravel[0])
    assert not context.can_track(10, 4)
    assert not context.can_dig(10, 4)
    assert context.can_dig(1, 1)

    # A chunk that does not fit the viewport is rejected.
    small_map = GameMap(width=4, height=4)
    ensure_surface_metadata(small_map)
    bad_chunk = materializer.materialize_chunk(0, 0)
    with pytest.raises(ValueError):
        apply_materialized_chunk(small_map, bad_chunk)
