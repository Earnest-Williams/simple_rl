from __future__ import annotations

from collections import deque
from typing import Final, cast

import numpy as np

from settlegen import (
    Facility,
    MagicMode,
    Settlement,
    SettlementConfig,
    SettlementGenerator,
    SettlementKind,
    TerrainCode,
    TerrainFeature,
)
from worldgen.settlements.translate import (
    _OVERLAND_MATERIAL_BY_TERRAIN,
    _SETTLEMENT_TILE_BY_TERRAIN,
    SettlementTile,
    terrain_to_settlement_tile,
)


def _is_walkable(code: int) -> bool:
    walkables: Final[set[SettlementTile]] = {
        SettlementTile.GROUND,
        SettlementTile.WOODS,
        SettlementTile.FARM,
        SettlementTile.ROAD,
        SettlementTile.PLAZA,
        SettlementTile.SHORE,
        SettlementTile.BRIDGE,
        SettlementTile.GATE,
        SettlementTile.CEMETERY,
        SettlementTile.DOCK,
        SettlementTile.MAGIC,
    }
    return terrain_to_settlement_tile(code) in walkables


def test_deterministic_summary() -> None:
    cfg: Final[SettlementConfig] = SettlementConfig(
        kind=SettlementKind.VILLAGE,
        width=80,
        height=64,
        terrain=(TerrainFeature.RIVER,),
    )
    a: Final[Settlement] = SettlementGenerator(seed=99).generate(cfg)
    b: Final[Settlement] = SettlementGenerator(seed=99).generate(cfg)

    assert a.facility_counts() == b.facility_counts()
    assert a.tile_summary() == b.tile_summary()
    assert a.population == b.population
    assert a.metadata == b.metadata


def test_all_terrain_codes_translatable() -> None:
    for code in TerrainCode:
        assert (
            code in _SETTLEMENT_TILE_BY_TERRAIN
        ), f"TerrainCode {code.name} is missing from _SETTLEMENT_TILE_BY_TERRAIN"
        assert (
            code in _OVERLAND_MATERIAL_BY_TERRAIN
        ), f"TerrainCode {code.name} is missing from _OVERLAND_MATERIAL_BY_TERRAIN"


def test_all_requested_facilities_accounted_for() -> None:
    # A config with a mix of standard and magic/waterfront facilities to test placement & failure tracking
    cfg: Final[SettlementConfig] = SettlementConfig(
        kind=SettlementKind.TOWN,
        width=96,
        height=72,
        facilities=(
            Facility.TEMPLE,
            Facility.DOCKS,
            Facility.MAGE_TOWER,
            Facility.CASTLE,
            Facility.LIBRARY,
        ),
    )
    settlement: Final[Settlement] = SettlementGenerator(seed=12345).generate(cfg)

    placed: Final[set[Facility]] = {b.facility for b in settlement.buildings}
    failed: Final[list[str]] = cast(
        list[str], settlement.metadata.get("failed_facilities", [])
    )

    for requested in cfg.facilities:
        facility_val = requested if isinstance(requested, str) else requested.value
        is_placed = requested in placed
        is_failed = facility_val in failed
        assert (
            is_placed or is_failed
        ), f"Requested facility {facility_val} is neither placed nor reported as failed"


def test_no_buildings_outside_bounds() -> None:
    cfg: Final[SettlementConfig] = SettlementConfig(
        kind=SettlementKind.PORT_CITY,
        width=128,
        height=96,
        terrain=(TerrainFeature.BAY, TerrainFeature.RIVER),
    )
    settlement: Final[Settlement] = SettlementGenerator(seed=42).generate(cfg)
    width: Final[int] = settlement.width
    height: Final[int] = settlement.height

    for building in settlement.buildings:
        rect = building.rect
        assert 0 <= rect.x < width, f"Building {building.id} x out of bounds: {rect.x}"
        assert (
            0 <= rect.x2 <= width
        ), f"Building {building.id} x2 out of bounds: {rect.x2}"
        assert 0 <= rect.y < height, f"Building {building.id} y out of bounds: {rect.y}"
        assert (
            0 <= rect.y2 <= height
        ), f"Building {building.id} y2 out of bounds: {rect.y2}"


def test_no_unregistered_facilities() -> None:
    cfg: Final[SettlementConfig] = SettlementConfig(
        kind=SettlementKind.MONASTERY,
        width=80,
        height=64,
    )
    settlement: Final[Settlement] = SettlementGenerator(seed=55).generate(cfg)

    for building in settlement.buildings:
        assert isinstance(
            building.facility, Facility
        ), f"Building {building.id} has unregistered/invalid facility type: {building.facility}"


def test_no_unreachable_gates_roads() -> None:
    # Testing a fort which has defenses, gates, and roads
    cfg: Final[SettlementConfig] = SettlementConfig(
        kind=SettlementKind.FORT,
        width=96,
        height=72,
        terrain=(TerrainFeature.HILL,),
    )
    settlement: Final[Settlement] = SettlementGenerator(seed=777).generate(cfg)

    combined: Final[np.ndarray] = settlement.combined_grid()
    h: Final[int] = combined.shape[0]
    w: Final[int] = combined.shape[1]

    anchor: Final[tuple[int, int] | None] = cast(
        tuple[int, int] | None, settlement.metadata.get("anchor")
    )
    assert anchor is not None, "Anchor missing from settlement metadata"
    ax: Final[int] = anchor[0]
    ay: Final[int] = anchor[1]

    # Run BFS on walkable tiles from anchor
    queue: Final[deque[tuple[int, int]]] = deque([(ax, ay)])
    visited: Final[set[tuple[int, int]]] = {(ax, ay)}

    while queue:
        cx, cy = queue.popleft()
        for dx, dy in (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (-1, 1),
            (1, -1),
            (1, 1),
        ):
            nx = cx + dx
            ny = cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in visited:
                code = int(combined[ny, nx])
                if _is_walkable(code):
                    visited.add((nx, ny))
                    queue.append((nx, ny))

    # Verify all gates are reachable
    for gx, gy in settlement.gates:
        assert (
            gx,
            gy,
        ) in visited, f"Gate at ({gx}, {gy}) is unreachable from anchor ({ax}, {ay})"

    # Verify all road points are reachable
    for road in settlement.roads:
        for rx, ry in road.points:
            assert (
                rx,
                ry,
            ) in visited, f"Road point ({rx}, {ry}) in road {road.id} is unreachable from anchor ({ax}, {ay})"


def test_generation_report_metadata() -> None:
    from settlegen import FailedFacility, GenerationReport

    # 1. Test no_water failure
    cfg_no_water = SettlementConfig(
        kind=SettlementKind.HAMLET,
        width=48,
        height=36,
        terrain=(TerrainFeature.PLAIN,),
        facilities=(Facility.DOCKS, Facility.SHIPYARD),
    )
    s_no_water = SettlementGenerator(seed=123).generate(cfg_no_water)

    # Typed report field
    gr = s_no_water.generation_report
    assert isinstance(gr, GenerationReport)
    assert Facility.DOCKS.value in gr.requested_facilities
    assert Facility.SHIPYARD.value in gr.requested_facilities
    failed_reasons = {f.facility: f.reason for f in gr.failed_facilities}
    assert failed_reasons.get(Facility.DOCKS.value) in ("no_water", "no_clear_site")
    assert failed_reasons.get(Facility.SHIPYARD.value) in ("no_water", "no_clear_site")

    # Backward-compatible metadata dict
    report = s_no_water.metadata.get("generation_report")
    assert isinstance(report, dict)
    assert "requested_facilities" in report
    assert "placed_facilities" in report
    assert "failed_facilities" in report

    failed = report.get("failed_facilities")
    assert isinstance(failed, dict)
    assert failed.get(Facility.DOCKS.value) in ("no_water", "no_clear_site")
    assert failed.get(Facility.SHIPYARD.value) in ("no_water", "no_clear_site")

    # 2. Test no_hill failure
    cfg_no_hill = SettlementConfig(
        kind=SettlementKind.HAMLET,
        width=48,
        height=36,
        terrain=(TerrainFeature.PLAIN,),
        facilities=(Facility.MINE, Facility.QUARRY),
    )
    s_no_hill = SettlementGenerator(seed=123).generate(cfg_no_hill)

    gr_hill = s_no_hill.generation_report
    hill_reasons = {f.facility: f.reason for f in gr_hill.failed_facilities}
    assert hill_reasons.get(Facility.MINE.value) == "no_hill"
    assert hill_reasons.get(Facility.QUARRY.value) == "no_hill"

    report_no_hill = s_no_hill.metadata.get("generation_report")
    assert isinstance(report_no_hill, dict)
    failed_no_hill = report_no_hill.get("failed_facilities")
    assert isinstance(failed_no_hill, dict)
    assert failed_no_hill.get(Facility.MINE.value) == "no_hill"
    assert failed_no_hill.get(Facility.QUARRY.value) == "no_hill"

    # 3. Test forbidden failure
    cfg_forbidden = SettlementConfig(
        kind=SettlementKind.HAMLET,
        width=48,
        height=36,
        magic=MagicMode.NO_MAGIC,
        facilities=(Facility.MAGE_TOWER, Facility.TEMPLE),
        banned_facilities=(Facility.TEMPLE,),
    )
    s_forbidden = SettlementGenerator(seed=123).generate(cfg_forbidden)

    gr_forbidden = s_forbidden.generation_report
    forbidden_reasons = {f.facility: f.reason for f in gr_forbidden.failed_facilities}
    assert forbidden_reasons.get(Facility.MAGE_TOWER.value) == "forbidden"
    assert forbidden_reasons.get(Facility.TEMPLE.value) == "forbidden"

    report_forbidden = s_forbidden.metadata.get("generation_report")
    assert isinstance(report_forbidden, dict)
    failed_forbidden = report_forbidden.get("failed_facilities")
    assert isinstance(failed_forbidden, dict)
    assert failed_forbidden.get(Facility.MAGE_TOWER.value) == "forbidden"
    assert failed_forbidden.get(Facility.TEMPLE.value) == "forbidden"

    # 4. Verify .to_dict() round-trip matches metadata
    assert gr.to_dict() == report


def test_terrain_to_overland_columns_correctness() -> None:
    import numpy as np

    from settlegen import TerrainCode
    from worldgen.settlements.translate import terrain_to_overland_columns

    # Generate a grid containing all terrain codes
    codes = [int(c.value) for c in TerrainCode]
    grid = np.array(codes, dtype=np.int16).reshape((1, len(codes)))

    cols = terrain_to_overland_columns(grid)

    # Check that all keys are present
    expected_keys = {
        "material",
        "biome",
        "elevation_band",
        "hydro_role",
        "wetness",
        "substrate",
        "walkable",
        "blocks_sight",
        "movement_cost",
        "traversal_class",
        "surface_flags",
    }
    assert set(cols.keys()) == expected_keys

    # Verify types and shapes
    for _, v in cols.items():
        assert isinstance(v, np.ndarray)
        assert v.shape == grid.shape

    # Verify specific values for each code to guarantee exact correctness
    from worldgen.overland.rules import (
        derive_blocks_sight,
        derive_movement_cost,
        derive_traversal_class,
        derive_walkable,
    )
    from worldgen.overland.schema import Substrate, Wetness
    from worldgen.settlements.translate import (
        _OVERLAND_MATERIAL_BY_TERRAIN,
        _OVERLAND_SUBSTRATE_BY_TERRAIN,
        _OVERLAND_WETNESS_BY_TERRAIN,
        _hydro_role_for_terrain,
        _surface_flags_for_terrain,
    )

    for i, c in enumerate(TerrainCode):
        mat = _OVERLAND_MATERIAL_BY_TERRAIN[c]
        wet = _OVERLAND_WETNESS_BY_TERRAIN.get(c, Wetness.DAMP)
        sub = _OVERLAND_SUBSTRATE_BY_TERRAIN.get(c, Substrate.SOIL)
        flag_mask = _surface_flags_for_terrain(c)
        hydro = _hydro_role_for_terrain(c)
        walk = derive_walkable(mat, wet, flag_mask)
        sight = derive_blocks_sight(mat, flag_mask)
        cost = derive_movement_cost(mat, wet, flag_mask)
        trav = derive_traversal_class(mat, wet, flag_mask)

        assert cols["material"][0, i] == int(mat)
        assert cols["wetness"][0, i] == int(wet)
        assert cols["substrate"][0, i] == int(sub)
        assert cols["hydro_role"][0, i] == int(hydro)
        assert cols["surface_flags"][0, i] == flag_mask
        assert cols["walkable"][0, i] == walk
        assert cols["blocks_sight"][0, i] == sight
        assert cols["movement_cost"][0, i] == cost
        assert cols["traversal_class"][0, i] == int(trav)
