from __future__ import annotations

from dataclasses import replace
from math import sin, pi
from typing import Optional

import numpy as np

from .acceleration import smooth2d, stamp_disk
from .algorithms import (
    astar_path,
    cells_within_radius,
    clamp,
    distance,
    draw_points,
    ellipse_ring,
    find_shore_cells,
    nearest_cell,
    passable_mask,
    polyline,
    random_point_in_annulus,
    rect_is_clear,
    rect_ring,
    shore_mask,
    stamp_rect,
    weighted_choice,
)
from .config import (
    BuildingMaterial,
    DefenseStyle,
    Facility,
    LayoutStyle,
    MagicMode,
    PopulationMode,
    SettlementConfig,
    SettlementKind,
    SettlementState,
    TerrainFeature,
    Wealth,
)
from .facilities import (
    REGISTRY,
    FacilitySpec,
    default_facilities_for,
    desired_population,
    district_count_for,
    material_for_palette,
)
from .model import Building, District, MagicSite, Rect, RoadSegment, Settlement, TerrainCode

WATER_FEATURES = {
    TerrainFeature.RIVER,
    TerrainFeature.STREAM,
    TerrainFeature.LAKESIDE,
    TerrainFeature.BAY,
    TerrainFeature.COAST,
    TerrainFeature.ISLAND,
    TerrainFeature.DELTA,
    TerrainFeature.OASIS,
}

MAGIC_FACILITIES = {
    Facility.MAGE_TOWER,
    Facility.ARCANE_ACADEMY,
    Facility.ALCHEMIST,
    Facility.RUNESTONE_CIRCLE,
    Facility.WARDING_OBELISK,
    Facility.PORTAL,
    Facility.LEYLINE_WELL,
    Facility.NECROPOLIS,
}

LINEAR_FACILITIES = {
    Facility.STONE_WALL,
    Facility.PALISADE,
    Facility.MOAT,
    Facility.DYKE,
    Facility.EARTHWORK,
    Facility.BRIDGE,
}

OPEN_FACILITIES = {
    Facility.MARKET_SQUARE,
    Facility.CEMETERY,
    Facility.RUNESTONE_CIRCLE,
    Facility.FIELD,
    Facility.ORCHARD,
    Facility.PASTURE,
    Facility.EMPTY_LOT,
}

HOUSING_FACILITIES = {Facility.HOUSE, Facility.HOVEL, Facility.TENEMENT, Facility.MANOR}


class SettlementGenerator:
    """Drop-in settlement generator.

    The generator returns plain dataclasses and NumPy arrays; there is no UI or
    engine dependency in this module. Use renderers/exporters only at tooling
    boundaries.
    """

    def __init__(self, seed: Optional[int] = None):
        if seed is None:
            seed = int(np.random.SeedSequence().generate_state(1)[0])
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self._building_id = 0
        self._road_id = 0

    def generate(self, config: SettlementConfig) -> Settlement:
        cfg = self._augment_config(config.normalized())
        self._building_id = 0
        self._road_id = 0

        design_population = desired_population(cfg.kind, SettlementState.ORDINARY, cfg.population_target)
        actual_population = self._apply_population_switches(
            desired_population(cfg.kind, cfg.state, cfg.population_target), cfg.population_mode
        )

        terrain = self._generate_terrain(cfg)
        overlay = np.zeros_like(terrain, dtype=np.int16)
        anchor = self._choose_anchor(cfg, terrain)
        self._clear_buildable_area(terrain, anchor, max(10, min(cfg.width, cfg.height) // 5))
        districts = self._generate_districts(cfg, terrain, anchor, design_population)

        roads: list[RoadSegment] = []
        gates: list[tuple[int, int]] = []
        docks: list[tuple[int, int]] = []
        buildings: list[Building] = []

        roads.extend(self._draw_external_roads(cfg, terrain, overlay, anchor))
        wall_points = self._draw_defenses(cfg, terrain, overlay, anchor, design_population, gates)
        roads.extend(self._draw_gate_roads(cfg, terrain, overlay, anchor, gates))
        for gx, gy in gates:
            stamp_disk(overlay, gx, gy, max(1, cfg.road_width), int(TerrainCode.GATE))

        facilities = self._facility_plan(cfg)
        self._place_core_open_space(cfg, terrain, overlay, anchor, buildings, districts)
        docks.extend(self._place_waterfront(cfg, terrain, overlay, anchor, buildings, districts, facilities))
        self._place_facilities(cfg, terrain, overlay, anchor, districts, buildings, facilities, design_population)
        self._place_rural_belt(cfg, terrain, overlay, anchor, districts, buildings, design_population)
        self._place_housing(cfg, terrain, overlay, anchor, districts, buildings, design_population, actual_population)
        self._apply_decline_and_ruin(cfg, overlay, buildings)
        magic_sites = self._place_magic(cfg, terrain, overlay, anchor, buildings)
        self._repair_connectivity(cfg, terrain, overlay, anchor, buildings, roads)

        if cfg.state == SettlementState.GHOST_TOWN or cfg.population_mode == PopulationMode.UNPOPULATED:
            final_population = 0
            for b in buildings:
                b.occupants = 0
        else:
            final_population = max(0, int(actual_population))

        return Settlement(
            config=cfg,
            seed=self.seed,
            name=cfg.name or self._make_name(cfg),
            terrain=terrain,
            overlay=overlay,
            districts=districts,
            roads=roads,
            buildings=buildings,
            gates=gates,
            docks=docks,
            magic_sites=magic_sites,
            population=final_population,
            metadata=self._metadata(cfg, design_population, final_population, anchor, wall_points),
        )

    # ------------------------------------------------------------------
    # Config and terrain
    # ------------------------------------------------------------------

    def _augment_config(self, cfg: SettlementConfig) -> SettlementConfig:
        terrain = set(cfg.terrain)
        if cfg.kind in (SettlementKind.FISHING_VILLAGE, SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY):
            if not terrain & WATER_FEATURES:
                terrain.add(TerrainFeature.BAY)
        if cfg.kind == SettlementKind.MINING_CAMP:
            terrain.add(TerrainFeature.HILL)
        if cfg.kind in (SettlementKind.FARMING_VILLAGE, SettlementKind.HAMLET, SettlementKind.VILLAGE):
            terrain.add(TerrainFeature.FERTILE_VALLEY)
        if cfg.kind in (SettlementKind.ANCIENT_CITY, SettlementKind.RUINED_CITY):
            terrain.add(TerrainFeature.FOREST)
        if cfg.kind in (SettlementKind.WALLED_TOWN, SettlementKind.CITY, SettlementKind.CAPITAL, SettlementKind.PORT_CITY):
            if cfg.defense == DefenseStyle.NONE:
                cfg = replace(cfg, defense=DefenseStyle.STONE_WALL)
        if cfg.kind == SettlementKind.FORT and cfg.defense == DefenseStyle.NONE:
            cfg = replace(cfg, defense=DefenseStyle.PALISADE)
        return replace(cfg, terrain=tuple(sorted(terrain, key=lambda t: t.value)))

    def _generate_terrain(self, cfg: SettlementConfig) -> np.ndarray:
        h, w = cfg.height, cfg.width
        height = smooth2d(self.rng.random((h, w), dtype=np.float32), 6)
        moisture = smooth2d(self.rng.random((h, w), dtype=np.float32), 5)
        terrain = np.full((h, w), int(TerrainCode.GRASS), dtype=np.int16)

        forest_threshold = max(0.35, 0.82 - cfg.forest_density)
        terrain[moisture > forest_threshold] = int(TerrainCode.FOREST)
        terrain[moisture > min(0.96, forest_threshold + 0.16)] = int(TerrainCode.DENSE_FOREST)
        terrain[height > 0.78] = int(TerrainCode.HILL)
        terrain[height > 0.91] = int(TerrainCode.MOUNTAIN)

        features = set(cfg.terrain)
        if TerrainFeature.DESERT_EDGE in features:
            terrain[moisture < 0.44] = int(TerrainCode.GRASS)
        if TerrainFeature.FERTILE_VALLEY in features:
            terrain[(height < 0.60) & (moisture > 0.32)] = int(TerrainCode.GRASS)
        if TerrainFeature.FOREST in features:
            terrain[moisture > 0.56] = int(TerrainCode.FOREST)
        if TerrainFeature.DENSE_FOREST in features:
            terrain[moisture > 0.48] = int(TerrainCode.FOREST)
            terrain[moisture > 0.65] = int(TerrainCode.DENSE_FOREST)
        if TerrainFeature.HILL in features:
            terrain[smooth2d(self.rng.random((h, w), dtype=np.float32), 4) > 0.70] = int(TerrainCode.HILL)
        if TerrainFeature.MOUNTAIN_PASS in features:
            self._apply_mountain_pass(terrain)
        if TerrainFeature.COAST in features or TerrainFeature.BAY in features:
            self._apply_coast_or_bay(terrain, bay=TerrainFeature.BAY in features)
        if TerrainFeature.ISLAND in features:
            self._apply_island(terrain)
        if TerrainFeature.LAKESIDE in features or TerrainFeature.OASIS in features:
            self._apply_lake(terrain, oasis=TerrainFeature.OASIS in features)
        if TerrainFeature.RIVER in features or TerrainFeature.DELTA in features:
            self._apply_river(terrain, wide=TerrainFeature.DELTA in features)
        if TerrainFeature.STREAM in features:
            self._apply_stream(terrain)
        if TerrainFeature.SWAMP in features or TerrainFeature.MARSH in features:
            self._apply_swamp(terrain, heavy=TerrainFeature.SWAMP in features)
        if TerrainFeature.CLIFF in features:
            self._apply_cliff(terrain)
        if TerrainFeature.VOLCANIC in features:
            self._apply_volcanic(terrain)
        self._mark_shores(terrain)
        return terrain

    def _apply_coast_or_bay(self, terrain: np.ndarray, *, bay: bool) -> None:
        h, w = terrain.shape
        side = str(self.rng.choice(["west", "east", "north", "south"]))
        depth = int(self.rng.integers(max(8, min(w, h) // 10), max(12, min(w, h) // 4)))
        for y in range(h):
            for x in range(w):
                wave = int(4 * sin((y if side in ("west", "east") else x) / 8.0) + self.rng.normal(0, 1.2))
                if side == "west" and x < depth + wave:
                    terrain[y, x] = int(TerrainCode.DEEP_WATER if x < depth + wave - 5 else TerrainCode.WATER)
                elif side == "east" and x > w - depth - wave:
                    terrain[y, x] = int(TerrainCode.DEEP_WATER if x > w - depth - wave + 5 else TerrainCode.WATER)
                elif side == "north" and y < depth + wave:
                    terrain[y, x] = int(TerrainCode.DEEP_WATER if y < depth + wave - 5 else TerrainCode.WATER)
                elif side == "south" and y > h - depth - wave:
                    terrain[y, x] = int(TerrainCode.DEEP_WATER if y > h - depth - wave + 5 else TerrainCode.WATER)
        if bay:
            cx = int(self.rng.integers(w // 4, 3 * w // 4))
            cy = int(self.rng.integers(h // 4, 3 * h // 4))
            rx = int(self.rng.integers(max(8, w // 8), max(10, w // 4)))
            ry = int(self.rng.integers(max(7, h // 9), max(9, h // 4)))
            yy, xx = np.mgrid[0:h, 0:w]
            mask = ((xx - cx) / max(1, rx)) ** 2 + ((yy - cy) / max(1, ry)) ** 2 < 1.0
            terrain[mask] = int(TerrainCode.WATER)

    def _apply_island(self, terrain: np.ndarray) -> None:
        h, w = terrain.shape
        yy, xx = np.mgrid[0:h, 0:w]
        cx, cy = w // 2, h // 2
        island = ((xx - cx) / (w * 0.43)) ** 2 + ((yy - cy) / (h * 0.43)) ** 2 < 1.0
        terrain[~island] = int(TerrainCode.DEEP_WATER)

    def _apply_lake(self, terrain: np.ndarray, *, oasis: bool) -> None:
        h, w = terrain.shape
        cx = int(self.rng.integers(w // 5, 4 * w // 5))
        cy = int(self.rng.integers(h // 5, 4 * h // 5))
        rx = int(self.rng.integers(max(5, w // 12), max(6, w // 5)))
        ry = int(self.rng.integers(max(5, h // 12), max(6, h // 5)))
        yy, xx = np.mgrid[0:h, 0:w]
        water = ((xx - cx) / max(1, rx)) ** 2 + ((yy - cy) / max(1, ry)) ** 2 < 1.0
        terrain[water] = int(TerrainCode.WATER)
        if oasis:
            green = ((xx - cx) / max(1, rx + 8)) ** 2 + ((yy - cy) / max(1, ry + 8)) ** 2 < 1.0
            terrain[green & ~water] = int(TerrainCode.GRASS)

    def _apply_river(self, terrain: np.ndarray, *, wide: bool) -> None:
        h, w = terrain.shape
        horizontal = bool(self.rng.random() < 0.5)
        amp = int(self.rng.integers(6, max(8, min(w, h) // 5)))
        phase = float(self.rng.random() * 2 * pi)
        points: list[tuple[int, int]] = []
        if horizontal:
            cy = int(self.rng.integers(h // 4, 3 * h // 4))
            for x in range(0, w, max(2, w // 32)):
                y = cy + int(sin(x / max(8.0, w / 10.0) + phase) * amp + self.rng.normal(0, 2.0))
                points.append((x, clamp(y, 2, h - 3)))
        else:
            cx = int(self.rng.integers(w // 4, 3 * w // 4))
            for y in range(0, h, max(2, h // 32)):
                x = cx + int(sin(y / max(8.0, h / 10.0) + phase) * amp + self.rng.normal(0, 2.0))
                points.append((clamp(x, 2, w - 3), y))
        draw_points(terrain, polyline(points), TerrainCode.WATER, radius=3 if wide else 2)

    def _apply_stream(self, terrain: np.ndarray) -> None:
        h, w = terrain.shape
        start = (int(self.rng.integers(0, w)), 0)
        end = (int(self.rng.integers(0, w)), h - 1)
        mid = (int(self.rng.integers(w // 4, 3 * w // 4)), int(self.rng.integers(h // 4, 3 * h // 4)))
        draw_points(terrain, polyline([start, mid, end]), TerrainCode.WATER, radius=1)

    def _apply_swamp(self, terrain: np.ndarray, *, heavy: bool) -> None:
        h, w = terrain.shape
        for _ in range(6 if heavy else 3):
            cx = int(self.rng.integers(5, w - 5))
            cy = int(self.rng.integers(5, h - 5))
            radius = int(self.rng.integers(max(4, min(w, h) // 14), max(6, min(w, h) // 7)))
            for yy, xx in cells_within_radius(w, h, (cx, cy), radius):
                if terrain[yy, xx] not in (int(TerrainCode.DEEP_WATER), int(TerrainCode.MOUNTAIN)):
                    terrain[yy, xx] = int(TerrainCode.SWAMP if heavy else TerrainCode.MARSH)

    def _apply_mountain_pass(self, terrain: np.ndarray) -> None:
        h, w = terrain.shape
        yy, xx = np.mgrid[0:h, 0:w]
        vertical = bool(self.rng.random() < 0.5)
        if vertical:
            pass_x = w // 2 + int(self.rng.normal(0, w // 12))
            dist = np.abs(xx - pass_x - np.sin(yy / max(10.0, h / 8.0)) * w / 12)
        else:
            pass_y = h // 2 + int(self.rng.normal(0, h // 12))
            dist = np.abs(yy - pass_y - np.sin(xx / max(10.0, w / 8.0)) * h / 12)
        terrain[dist > min(w, h) * 0.23] = int(TerrainCode.MOUNTAIN)
        terrain[(dist > min(w, h) * 0.14) & (dist <= min(w, h) * 0.23)] = int(TerrainCode.HILL)
        terrain[dist < min(w, h) * 0.08] = int(TerrainCode.GRASS)

    def _apply_cliff(self, terrain: np.ndarray) -> None:
        h, w = terrain.shape
        x = int(self.rng.integers(w // 5, 4 * w // 5))
        for y in range(h):
            xx = x + int(sin(y / 9.0) * 4)
            draw_points(terrain, [(xx, y)], TerrainCode.MOUNTAIN, radius=1)

    def _apply_volcanic(self, terrain: np.ndarray) -> None:
        h, w = terrain.shape
        cx = int(self.rng.integers(w // 4, 3 * w // 4))
        cy = int(self.rng.integers(h // 4, 3 * h // 4))
        for r, code in [(min(w, h) // 7, TerrainCode.MOUNTAIN), (min(w, h) // 5, TerrainCode.HILL)]:
            for yy, xx in cells_within_radius(w, h, (cx, cy), r):
                terrain[yy, xx] = int(code)

    def _mark_shores(self, terrain: np.ndarray) -> None:
        mask = shore_mask(terrain)
        land = ~np.isin(terrain, [int(TerrainCode.MOUNTAIN), int(TerrainCode.HILL)])
        terrain[mask & land] = int(TerrainCode.SHORE)

    def _choose_anchor(self, cfg: SettlementConfig, terrain: np.ndarray) -> tuple[int, int]:
        h, w = terrain.shape
        centre = (w // 2, h // 2)
        shore_cells = find_shore_cells(terrain)
        if cfg.kind in (SettlementKind.FISHING_VILLAGE, SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY) or cfg.layout == LayoutStyle.COASTAL:
            if shore_cells.size:
                return nearest_cell(shore_cells, centre)
        if TerrainFeature.RIVER in cfg.terrain or cfg.layout == LayoutStyle.RIVER_STRADDLING:
            if shore_cells.size:
                return nearest_cell(shore_cells, centre)
        passable = np.argwhere(passable_mask(terrain))
        if passable.size == 0:
            return centre
        return nearest_cell(passable, centre)

    def _clear_buildable_area(self, terrain: np.ndarray, anchor: tuple[int, int], radius: int) -> None:
        h, w = terrain.shape
        for yy, xx in cells_within_radius(w, h, anchor, radius):
            if terrain[yy, xx] in (int(TerrainCode.MOUNTAIN), int(TerrainCode.DENSE_FOREST)):
                terrain[yy, xx] = int(TerrainCode.HILL if self.rng.random() < 0.12 else TerrainCode.GRASS)
            elif terrain[yy, xx] == int(TerrainCode.FOREST) and self.rng.random() < 0.65:
                terrain[yy, xx] = int(TerrainCode.GRASS)

    # ------------------------------------------------------------------
    # Districts, roads, defenses
    # ------------------------------------------------------------------

    def _generate_districts(self, cfg: SettlementConfig, terrain: np.ndarray, anchor: tuple[int, int], design_population: int) -> list[District]:
        count = district_count_for(cfg.kind, design_population, cfg.district_count)
        h, w = terrain.shape
        base_radius = int(max(9, min(w, h) * (0.13 + min(0.22, design_population / 70000.0))))
        kinds = self._district_kind_sequence(cfg, count)
        districts: list[District] = []
        for i, kind in enumerate(kinds):
            if i == 0:
                center = anchor
            elif kind == "docks":
                shore_cells = find_shore_cells(terrain)
                center = nearest_cell(shore_cells, anchor) if shore_cells.size else random_point_in_annulus(self.rng, anchor, 6, base_radius * 1.3, w, h)
            elif cfg.layout == LayoutStyle.GRID:
                cols = max(2, int(np.ceil(np.sqrt(count))))
                row, col = divmod(i, cols)
                step = max(8, base_radius // 2)
                center = (clamp(anchor[0] + (col - cols // 2) * step, 2, w - 3), clamp(anchor[1] + (row - cols // 2) * step, 2, h - 3))
            elif cfg.layout in (LayoutStyle.LINEAR_ROAD, LayoutStyle.RIVER_STRADDLING):
                t = (i - count / 2) * max(5, base_radius // 4)
                center = (clamp(anchor[0] + int(t), 2, w - 3), clamp(anchor[1] + int(self.rng.normal(0, base_radius / 6)), 2, h - 3))
            elif kind in ("farm", "cemetery", "edge", "ruins"):
                center = random_point_in_annulus(self.rng, anchor, base_radius * 0.85, base_radius * 1.8, w, h)
            elif kind in ("noble", "military", "temple", "academic", "magic"):
                center = random_point_in_annulus(self.rng, anchor, base_radius * 0.25, base_radius * 0.9, w, h)
            else:
                center = random_point_in_annulus(self.rng, anchor, base_radius * 0.25, base_radius * 1.25, w, h)
            radius = int(self.rng.integers(max(6, base_radius // 3), max(8, base_radius)))
            districts.append(District(i, kind, center, radius, self._district_wealth(cfg, kind), tags=self._district_tags(cfg, kind)))
        return districts

    def _district_kind_sequence(self, cfg: SettlementConfig, count: int) -> list[str]:
        base = ["core", "market", "residential", "craft", "temple", "farm", "edge"]
        if cfg.kind in (SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY, SettlementKind.FISHING_VILLAGE):
            base = ["core", "docks", "market", "residential", "craft", "farm", "temple", "edge"]
        elif cfg.kind in (SettlementKind.FARMING_VILLAGE, SettlementKind.HAMLET):
            base = ["core", "farm", "residential", "temple", "edge"]
        elif cfg.kind in (SettlementKind.FORT, SettlementKind.WALLED_TOWN, SettlementKind.CAPITAL):
            base = ["core", "military", "market", "residential", "temple", "craft", "noble", "edge"]
        elif cfg.kind == SettlementKind.MONASTERY:
            base = ["core", "temple", "academic", "farm", "cemetery", "edge"]
        elif cfg.kind == SettlementKind.MINING_CAMP:
            base = ["core", "craft", "edge", "residential", "market", "military"]
        elif cfg.kind in (SettlementKind.ANCIENT_CITY, SettlementKind.RUINED_CITY):
            base = ["core", "ruins", "temple", "cemetery", "edge", "residential", "market"]
        if cfg.magic in (MagicMode.HIGH_MAGIC, MagicMode.RUNIC_MAGIC, MagicMode.WILD_MAGIC, MagicMode.TECHNO_ARCANE):
            base.insert(min(4, len(base)), "magic")
        return [base[i % len(base)] for i in range(count)]

    def _district_wealth(self, cfg: SettlementConfig, kind: str) -> str:
        if kind in ("noble", "core") and cfg.wealth in (Wealth.RICH, Wealth.IMPERIAL, Wealth.PROSPEROUS):
            return cfg.wealth.value
        if kind in ("edge", "farm"):
            return Wealth.POOR.value if cfg.wealth != Wealth.DESTITUTE else Wealth.DESTITUTE.value
        if kind == "docks" and cfg.wealth in (Wealth.RICH, Wealth.IMPERIAL):
            return Wealth.PROSPEROUS.value
        return cfg.wealth.value

    def _district_tags(self, cfg: SettlementConfig, kind: str) -> tuple[str, ...]:
        tags = [kind]
        if cfg.state in (SettlementState.RUINED, SettlementState.ANCIENT, SettlementState.GHOST_TOWN):
            tags.append("decayed")
        if kind == "magic":
            tags.append(cfg.magic.value)
        if kind == "docks":
            tags.append("waterfront")
        return tuple(tags)

    def _draw_external_roads(self, cfg: SettlementConfig, terrain: np.ndarray, overlay: np.ndarray, anchor: tuple[int, int]) -> list[RoadSegment]:
        h, w = terrain.shape
        road_count = 1 if cfg.kind in (SettlementKind.HAMLET, SettlementKind.MONASTERY, SettlementKind.NOMAD_CAMP) else 2
        if cfg.kind in (SettlementKind.TOWN, SettlementKind.WALLED_TOWN, SettlementKind.PORT_TOWN, SettlementKind.MARKET_TOWN):
            road_count = 3
        if cfg.kind in (SettlementKind.CITY, SettlementKind.CAPITAL, SettlementKind.PORT_CITY):
            road_count = 4
        sides = list(self.rng.choice(["north", "south", "west", "east"], size=road_count, replace=False))
        roads: list[RoadSegment] = []
        for side in sides:
            if side == "north":
                goal = (int(self.rng.integers(w // 5, 4 * w // 5)), 1)
            elif side == "south":
                goal = (int(self.rng.integers(w // 5, 4 * w // 5)), h - 2)
            elif side == "west":
                goal = (1, int(self.rng.integers(h // 5, 4 * h // 5)))
            else:
                goal = (w - 2, int(self.rng.integers(h // 5, 4 * h // 5)))
            path = astar_path(terrain, anchor, goal, allow_bridges=cfg.allow_bridges)
            self._draw_road_path(cfg, terrain, overlay, path)
            roads.append(self._road("external", path, tags=(str(side),)))
        return roads

    def _draw_road_path(self, cfg: SettlementConfig, terrain: np.ndarray, overlay: np.ndarray, path: list[tuple[int, int]]) -> None:
        radius = max(0, cfg.road_width - 1)
        for x, y in path:
            if terrain[y, x] in (int(TerrainCode.WATER), int(TerrainCode.DEEP_WATER)):
                stamp_disk(overlay, x, y, radius, int(TerrainCode.BRIDGE))
            else:
                stamp_disk(overlay, x, y, radius, int(TerrainCode.ROAD))

    def _draw_defenses(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        design_population: int,
        gates: list[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        facilities = set(default_facilities_for(cfg.kind, cfg.magic, cfg.defense, cfg.state)) | set(cfg.facilities)
        defense = cfg.defense
        if Facility.STONE_WALL in facilities:
            defense = DefenseStyle.STONE_WALL
        if Facility.PALISADE in facilities and defense == DefenseStyle.NONE:
            defense = DefenseStyle.PALISADE
        if defense == DefenseStyle.NONE:
            return []

        h, w = terrain.shape
        rx = clamp(int(10 + design_population ** 0.45 + cfg.wall_margin), 10, max(12, w // 2 - 4))
        ry = clamp(int(8 + design_population ** 0.42 + cfg.wall_margin), 8, max(10, h // 2 - 4))
        if cfg.layout == LayoutStyle.GRID or defense == DefenseStyle.CASTLE_WALL:
            rect = Rect(clamp(anchor[0] - rx, 2, w - 4), clamp(anchor[1] - ry, 2, h - 4), min(rx * 2, w - 5), min(ry * 2, h - 5))
            ring = rect_ring(rect)
        else:
            ring = ellipse_ring(anchor[0], anchor[1], rx, ry, samples=320, jitter=0.06, rng=self.rng)

        if defense in (DefenseStyle.STONE_WALL, DefenseStyle.CASTLE_WALL):
            code = TerrainCode.WALL
        elif defense == DefenseStyle.DYKE:
            code = TerrainCode.DYKE
        elif defense == DefenseStyle.DITCH:
            code = TerrainCode.MOAT
        else:
            code = TerrainCode.PALISADE
        draw_points(overlay, ring, code, radius=0)

        gate_targets = [(anchor[0], anchor[1] - ry), (anchor[0] + rx, anchor[1]), (anchor[0], anchor[1] + ry), (anchor[0] - rx, anchor[1])]
        for gx, gy in gate_targets:
            gx, gy = clamp(gx, 1, w - 2), clamp(gy, 1, h - 2)
            gates.append((gx, gy))
            stamp_disk(overlay, gx, gy, max(1, cfg.road_width), int(TerrainCode.GATE))

        if defense in (DefenseStyle.WATCHTOWERS, DefenseStyle.STONE_WALL, DefenseStyle.CASTLE_WALL):
            stride = max(1, len(ring) // 8)
            for tx, ty in ring[::stride]:
                rect = Rect(clamp(tx - 1, 1, w - 4), clamp(ty - 1, 1, h - 4), 3, 3)
                if rect_is_clear(rect, terrain, overlay):
                    stamp_rect(overlay, rect, TerrainCode.BUILDING)
        return ring

    def _draw_gate_roads(self, cfg: SettlementConfig, terrain: np.ndarray, overlay: np.ndarray, anchor: tuple[int, int], gates: list[tuple[int, int]]) -> list[RoadSegment]:
        roads: list[RoadSegment] = []
        for gate in gates:
            path = astar_path(terrain, gate, anchor, allow_bridges=cfg.allow_bridges)
            self._draw_road_path(cfg, terrain, overlay, path)
            roads.append(self._road("gate", path, tags=("defense",)))
        return roads

    def _road(self, kind: str, points: list[tuple[int, int]], tags: tuple[str, ...] = tuple()) -> RoadSegment:
        road = RoadSegment(self._road_id, kind, points, tags)
        self._road_id += 1
        return road

    # ------------------------------------------------------------------
    # Facilities and buildings
    # ------------------------------------------------------------------

    def _facility_plan(self, cfg: SettlementConfig) -> tuple[Facility, ...]:
        facilities = list(default_facilities_for(cfg.kind, cfg.magic, cfg.defense, cfg.state))
        facilities.extend(cfg.facilities)
        forbidden = set(cfg.forbidden_facilities)
        if cfg.magic == MagicMode.NO_MAGIC:
            forbidden |= MAGIC_FACILITIES
        out = [f for f in facilities if f not in forbidden and f not in LINEAR_FACILITIES]
        return tuple(dict.fromkeys(out))

    def _place_core_open_space(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        buildings: list[Building],
        districts: list[District],
    ) -> None:
        if cfg.kind in (SettlementKind.HAMLET, SettlementKind.MONASTERY, SettlementKind.FORT, SettlementKind.NOMAD_CAMP):
            facility = Facility.WELL
            size = 3
        else:
            facility = Facility.MARKET_SQUARE
            size = int(self.rng.integers(5, 10))
        rect = Rect(clamp(anchor[0] - size // 2, 2, terrain.shape[1] - size - 2), clamp(anchor[1] - size // 2, 2, terrain.shape[0] - size - 2), size, size)
        stamp_rect(overlay, rect, TerrainCode.PLAZA if facility == Facility.MARKET_SQUARE else TerrainCode.ROAD)
        b = self._make_building(cfg, facility, rect, self._nearest_district_id(districts, rect.center), open_space=True)
        b.tags += ("core", "always_present")
        buildings.append(b)

    def _place_waterfront(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        buildings: list[Building],
        districts: list[District],
        facilities: tuple[Facility, ...],
    ) -> list[tuple[int, int]]:
        waterfront: list[tuple[int, int]] = []
        shore_cells = find_shore_cells(terrain)
        if shore_cells.size == 0:
            return waterfront
        wants_port = cfg.kind in (SettlementKind.FISHING_VILLAGE, SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY) or any(
            f in facilities for f in (Facility.DOCKS, Facility.WHARF, Facility.FISHERY, Facility.SHIPYARD, Facility.LIGHTHOUSE)
        )
        if not wants_port:
            return waterfront
        counts = 1 if cfg.kind == SettlementKind.FISHING_VILLAGE else 2 if cfg.kind == SettlementKind.PORT_TOWN else 4 if cfg.kind == SettlementKind.PORT_CITY else 1
        for i in range(counts):
            sx, sy = nearest_cell(shore_cells, (anchor[0] + i * 9, anchor[1]))
            bw = int(self.rng.integers(5, 12))
            bh = int(self.rng.integers(3, 5))
            rect = Rect(clamp(sx - bw // 2, 1, terrain.shape[1] - bw - 1), clamp(sy - bh // 2, 1, terrain.shape[0] - bh - 1), bw, bh)
            stamp_rect(overlay, rect, TerrainCode.DOCK)
            facility = Facility.DOCKS if i == 0 else weighted_choice(self.rng, [Facility.WHARF, Facility.FISHERY, Facility.WAREHOUSE], [0.45, 0.35, 0.20])
            buildings.append(self._make_building(cfg, facility, rect, self._nearest_district_id(districts, rect.center), open_space=True))
            waterfront.append(rect.center)
            self._draw_road_path(cfg, terrain, overlay, astar_path(terrain, rect.center, anchor, allow_bridges=cfg.allow_bridges))
        return waterfront

    def _place_facilities(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        districts: list[District],
        buildings: list[Building],
        facilities: tuple[Facility, ...],
        design_population: int,
    ) -> None:
        explicit = set(cfg.facilities)
        ordered = sorted(facilities, key=self._facility_priority)
        for facility in ordered:
            if facility in HOUSING_FACILITIES or facility in {Facility.FIELD, Facility.ORCHARD, Facility.PASTURE, Facility.FARMSTEAD, Facility.BARN}:
                continue
            # Core square and waterfront have dedicated logic.
            if facility in (Facility.MARKET_SQUARE, Facility.DOCKS, Facility.WHARF):
                continue
            spec = REGISTRY.get(facility)
            if spec is None:
                continue
            count = self._target_count(cfg, facility, spec, design_population, is_explicit=facility in explicit)
            for _ in range(count):
                rect = self._find_site_for_facility(cfg, terrain, overlay, anchor, districts, spec)
                if rect is None:
                    continue
                stamp_rect(overlay, rect, self._overlay_code_for(facility))
                buildings.append(self._make_building(cfg, facility, rect, self._nearest_district_id(districts, rect.center)))

    def _place_rural_belt(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        districts: list[District],
        buildings: list[Building],
        design_population: int,
    ) -> None:
        rural_bias = 2.2 if cfg.kind in (SettlementKind.FARMING_VILLAGE, SettlementKind.HAMLET, SettlementKind.VILLAGE, SettlementKind.MONASTERY) else 0.6 if cfg.kind in (SettlementKind.CITY, SettlementKind.CAPITAL, SettlementKind.PORT_CITY) else 1.0
        count = int(max(1, (design_population / 250.0) * cfg.farmland_density * rural_bias))
        count = min(count, 70)
        options = [Facility.FIELD, Facility.ORCHARD, Facility.PASTURE, Facility.FARMSTEAD, Facility.BARN]
        weights = [0.45, 0.16, 0.15, 0.14, 0.10]
        if cfg.kind == SettlementKind.FISHING_VILLAGE:
            weights = [0.20, 0.08, 0.08, 0.14, 0.10]
        for _ in range(count):
            facility = weighted_choice(self.rng, options, weights)
            spec = REGISTRY[facility]
            rect = self._find_site_for_facility(cfg, terrain, overlay, anchor, districts, spec, rural=True)
            if rect is None:
                continue
            code = self._overlay_code_for(facility)
            if facility in (Facility.FIELD, Facility.ORCHARD, Facility.PASTURE):
                stamp_rect(terrain, rect, code)
            else:
                stamp_rect(overlay, rect, code)
            buildings.append(self._make_building(cfg, facility, rect, self._nearest_district_id(districts, rect.center), open_space=facility in OPEN_FACILITIES))

    def _place_housing(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        districts: list[District],
        buildings: list[Building],
        design_population: int,
        actual_population: int,
    ) -> None:
        if cfg.kind == SettlementKind.FORT:
            mix, weights = [Facility.BARRACKS, Facility.HOUSE, Facility.STABLE], [0.55, 0.35, 0.10]
        elif cfg.kind == SettlementKind.NOMAD_CAMP:
            mix, weights = [Facility.HOVEL, Facility.HOUSE], [0.70, 0.30]
        elif design_population > 8000:
            mix, weights = [Facility.TENEMENT, Facility.HOUSE, Facility.MANOR, Facility.HOVEL], [0.45, 0.35, 0.06, 0.14]
        elif cfg.wealth in (Wealth.RICH, Wealth.IMPERIAL):
            mix, weights = [Facility.HOUSE, Facility.MANOR, Facility.TENEMENT, Facility.HOVEL], [0.58, 0.16, 0.18, 0.08]
        elif cfg.wealth in (Wealth.DESTITUTE, Wealth.POOR):
            mix, weights = [Facility.HOVEL, Facility.HOUSE, Facility.TENEMENT], [0.52, 0.38, 0.10]
        else:
            mix, weights = [Facility.HOUSE, Facility.HOVEL, Facility.TENEMENT, Facility.MANOR], [0.65, 0.18, 0.12, 0.05]

        target_capacity = max(design_population, actual_population)
        if cfg.state in (SettlementState.RUINED, SettlementState.ANCIENT, SettlementState.GHOST_TOWN):
            target_capacity = design_population
        current_capacity = sum(b.occupants for b in buildings)
        max_buildings = int(min(450, max(8, design_population / 3)))
        attempts = 0
        while current_capacity < target_capacity and attempts < max_buildings:
            attempts += 1
            facility = weighted_choice(self.rng, mix, weights)
            spec = REGISTRY.get(facility, REGISTRY[Facility.HOUSE])
            rect = self._find_site_for_facility(cfg, terrain, overlay, anchor, districts, spec)
            if rect is None:
                continue
            stamp_rect(overlay, rect, TerrainCode.BUILDING)
            b = self._make_building(cfg, facility, rect, self._nearest_district_id(districts, rect.center))
            if cfg.state == SettlementState.GHOST_TOWN:
                b.occupants = 0
            current_capacity += b.occupants
            buildings.append(b)

    def _facility_priority(self, facility: Facility) -> int:
        if facility in (Facility.CASTLE, Facility.KEEP, Facility.CATHEDRAL, Facility.MONASTERY, Facility.ARCANE_ACADEMY):
            return 0
        if facility in (Facility.CITY_HALL, Facility.COURTHOUSE, Facility.MARKET, Facility.MARKET_SQUARE, Facility.CHURCH, Facility.TEMPLE):
            return 1
        if facility in (Facility.CEMETERY, Facility.DOCKS, Facility.SHIPYARD, Facility.LIGHTHOUSE):
            return 2
        return 3

    def _target_count(self, cfg: SettlementConfig, facility: Facility, spec: FacilitySpec, design_population: int, *, is_explicit: bool) -> int:
        if spec.unique:
            return 1
        base = 1 if is_explicit or spec.base_weight >= 0.12 or design_population >= 3000 else 0
        if facility in (Facility.WELL, Facility.SHRINE):
            return max(base, int(design_population / 600) + 1)
        if facility in (Facility.INN, Facility.TAVERN):
            return max(base, int(design_population / 1400) + (1 if cfg.kind in (SettlementKind.MARKET_TOWN, SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY) else 0))
        if facility in (Facility.BLACKSMITH, Facility.BAKERY, Facility.WAREHOUSE, Facility.GRANARY):
            return max(base, int(design_population / 1800) + 1)
        if facility in (Facility.WATCHTOWER, Facility.TOWER):
            return max(base, 2 if cfg.defense != DefenseStyle.NONE else 1)
        if facility in MAGIC_FACILITIES:
            if cfg.magic == MagicMode.NO_MAGIC:
                return 0
            if cfg.magic == MagicMode.HIGH_MAGIC:
                return max(base, int(design_population / 3000) + 1)
            return max(base, 1 if is_explicit or design_population > 1000 else 0)
        if spec.base_weight < 0.1 and not is_explicit and design_population < 8000:
            return 0
        return base

    def _find_site_for_facility(
        self,
        cfg: SettlementConfig,
        terrain: np.ndarray,
        overlay: np.ndarray,
        anchor: tuple[int, int],
        districts: list[District],
        spec: FacilitySpec,
        *,
        rural: bool = False,
    ) -> Optional[Rect]:
        h, w = terrain.shape
        for _ in range(250):
            bw = int(self.rng.integers(spec.min_size[0], spec.max_size[0] + 1))
            bh = int(self.rng.integers(spec.min_size[1], spec.max_size[1] + 1))
            target = self._target_point_for_spec(cfg, terrain, anchor, districts, spec, rural=rural)
            x = clamp(int(target[0] + self.rng.normal(0, max(3, bw * 2))) - bw // 2, 1, w - bw - 2)
            y = clamp(int(target[1] + self.rng.normal(0, max(3, bh * 2))) - bh // 2, 1, h - bh - 2)
            rect = Rect(x, y, bw, bh)
            if spec.requires_water and not self._rect_touches_water(rect, terrain):
                continue
            if spec.requires_hill and not bool(np.any(terrain[rect.y:rect.y2, rect.x:rect.x2] == int(TerrainCode.HILL))):
                continue
            allow_on: set[int] = set()
            if spec.facility in (Facility.DOCKS, Facility.WHARF, Facility.FISHERY, Facility.SHIPYARD, Facility.FERRY, Facility.BRIDGE):
                allow_on = {int(TerrainCode.WATER), int(TerrainCode.SHORE), int(TerrainCode.MARSH)}
            if spec.facility in (Facility.FIELD, Facility.ORCHARD, Facility.PASTURE):
                allow_on = {int(TerrainCode.GRASS), int(TerrainCode.FOREST), int(TerrainCode.FARMLAND), int(TerrainCode.SHORE), int(TerrainCode.HILL)}
            if rect_is_clear(rect, terrain, overlay, allow_on=allow_on):
                return rect
        return None

    def _target_point_for_spec(self, cfg: SettlementConfig, terrain: np.ndarray, anchor: tuple[int, int], districts: list[District], spec: FacilitySpec, *, rural: bool) -> tuple[int, int]:
        if spec.requires_water:
            shore_cells = find_shore_cells(terrain)
            if shore_cells.size:
                return nearest_cell(shore_cells, anchor)
        if spec.requires_hill:
            hill_cells = np.argwhere((terrain == int(TerrainCode.HILL)) | (terrain == int(TerrainCode.MOUNTAIN)))
            if hill_cells.size:
                return nearest_cell(hill_cells, anchor)
        if rural or "farm" in spec.district_affinity or "edge" in spec.district_affinity:
            return random_point_in_annulus(self.rng, anchor, min(terrain.shape) * 0.18, min(terrain.shape) * 0.44, terrain.shape[1], terrain.shape[0])
        candidates = [d for d in districts if any(a in d.kind or d.kind in a for a in spec.district_affinity)]
        if not candidates:
            candidates = districts
        return candidates[int(self.rng.integers(0, len(candidates)))].center

    def _rect_touches_water(self, rect: Rect, terrain: np.ndarray) -> bool:
        expanded = rect.expanded(2, terrain.shape[1], terrain.shape[0])
        sub = terrain[expanded.y:expanded.y2, expanded.x:expanded.x2]
        return bool(np.any((sub == int(TerrainCode.WATER)) | (sub == int(TerrainCode.DEEP_WATER)) | (sub == int(TerrainCode.SHORE))))

    def _overlay_code_for(self, facility: Facility) -> TerrainCode:
        if facility == Facility.FIELD:
            return TerrainCode.FIELD
        if facility == Facility.ORCHARD:
            return TerrainCode.ORCHARD
        if facility == Facility.PASTURE:
            return TerrainCode.PASTURE
        if facility == Facility.CEMETERY:
            return TerrainCode.CEMETERY
        if facility in (Facility.DOCKS, Facility.WHARF, Facility.FISHERY, Facility.SHIPYARD, Facility.FERRY):
            return TerrainCode.DOCK
        if facility in (Facility.RUNESTONE_CIRCLE, Facility.WARDING_OBELISK, Facility.PORTAL, Facility.LEYLINE_WELL):
            return TerrainCode.MAGIC
        if facility == Facility.MARKET_SQUARE:
            return TerrainCode.PLAZA
        if facility == Facility.EMPTY_LOT:
            return TerrainCode.EMPTY_LOT
        if facility in (Facility.RUIN, Facility.ANCIENT_VAULT, Facility.NECROPOLIS):
            return TerrainCode.RUIN
        return TerrainCode.BUILDING

    def _make_building(self, cfg: SettlementConfig, facility: Facility, rect: Rect, district_id: Optional[int], *, open_space: bool = False) -> Building:
        spec = REGISTRY.get(facility)
        material = material_for_palette(cfg.material, cfg.wealth, facility, spec)
        if cfg.state == SettlementState.ANCIENT and facility not in (Facility.HOUSE, Facility.HOVEL, Facility.TENEMENT, Facility.FARMSTEAD):
            if material != BuildingMaterial.MOSTLY_WOOD:
                material = BuildingMaterial.RUINED_STONE
        occupants = 0
        workers = 0
        if spec:
            if spec.occupants[1] > 0:
                occupants = int(self.rng.integers(spec.occupants[0], spec.occupants[1] + 1))
            if spec.workers[1] > 0:
                workers = int(self.rng.integers(spec.workers[0], spec.workers[1] + 1))
        quality_base = {
            Wealth.DESTITUTE: 0.15,
            Wealth.POOR: 0.28,
            Wealth.MODEST: 0.48,
            Wealth.PROSPEROUS: 0.64,
            Wealth.RICH: 0.78,
            Wealth.IMPERIAL: 0.90,
        }.get(cfg.wealth, 0.50)
        if facility in (Facility.MANOR, Facility.CASTLE, Facility.CATHEDRAL, Facility.CITY_HALL, Facility.GUILDHALL):
            quality_base += 0.12
        if cfg.state in (SettlementState.DECLINING, SettlementState.WAR_TORN):
            quality_base -= 0.15
        if cfg.state in (SettlementState.RUINED, SettlementState.GHOST_TOWN):
            quality_base -= 0.35
        quality = max(0.02, min(1.0, quality_base + float(self.rng.normal(0, 0.08))))
        tags = tuple(spec.tags if spec else tuple())
        if open_space:
            tags += ("open_space",)
        magic = cfg.magic if cfg.magic != MagicMode.NO_MAGIC and facility in MAGIC_FACILITIES else None
        building = Building(
            id=self._building_id,
            facility=facility,
            rect=rect,
            material=material,
            state=cfg.state,
            district_id=district_id,
            occupants=occupants,
            workers=workers,
            quality=quality,
            magic=magic,
            tags=tags,
            meta={"open_space": open_space},
        )
        self._building_id += 1
        return building

    def _nearest_district_id(self, districts: list[District], point: tuple[int, int]) -> Optional[int]:
        if not districts:
            return None
        return min(districts, key=lambda d: distance(d.center, point)).id

    def _apply_decline_and_ruin(self, cfg: SettlementConfig, overlay: np.ndarray, buildings: list[Building]) -> None:
        ruin_rate = cfg.ruin_rate
        if ruin_rate is None:
            ruin_rate = {
                SettlementState.RUINED: 0.65,
                SettlementState.ANCIENT: 0.48,
                SettlementState.GHOST_TOWN: 0.20,
                SettlementState.WAR_TORN: 0.30,
                SettlementState.DECLINING: 0.10,
                SettlementState.PLAGUE_STRUCK: 0.12,
            }.get(cfg.state, 0.03)
        ghost_rate = cfg.ghost_rate if cfg.ghost_rate is not None else (1.0 if cfg.state == SettlementState.GHOST_TOWN else 0.0)
        for b in buildings:
            if b.facility in (Facility.FIELD, Facility.ORCHARD, Facility.PASTURE, Facility.DOCKS, Facility.WHARF, Facility.MARKET_SQUARE):
                continue
            if self.rng.random() < ruin_rate:
                b.state = SettlementState.RUINED
                b.occupants = 0
                b.workers = 0
                b.quality = min(b.quality, 0.20)
                b.tags += ("ruined",)
                stamp_rect(overlay, b.rect, TerrainCode.RUIN)
            elif self.rng.random() < ghost_rate:
                b.state = SettlementState.GHOST_TOWN
                b.occupants = 0
                b.workers = 0
                b.tags += ("abandoned",)
        if cfg.state in (SettlementState.RUINED, SettlementState.ANCIENT):
            h, w = overlay.shape
            for _ in range(max(10, len(buildings) // 4)):
                x = int(self.rng.integers(2, w - 2))
                y = int(self.rng.integers(2, h - 2))
                if overlay[y, x] == int(TerrainCode.VOID):
                    stamp_disk(overlay, x, y, int(self.rng.integers(1, 3)), int(TerrainCode.EMPTY_LOT))

    def _place_magic(self, cfg: SettlementConfig, terrain: np.ndarray, overlay: np.ndarray, anchor: tuple[int, int], buildings: list[Building]) -> list[MagicSite]:
        if cfg.magic == MagicMode.NO_MAGIC:
            return []
        count = {
            MagicMode.LOW_MAGIC: 1,
            MagicMode.HIGH_MAGIC: 5,
            MagicMode.RUNIC_MAGIC: 4,
            MagicMode.DIVINE_MAGIC: 2,
            MagicMode.NECROMANTIC: 3,
            MagicMode.WILD_MAGIC: 4,
            MagicMode.TECHNO_ARCANE: 3,
        }.get(cfg.magic, 1)
        sites: list[MagicSite] = []
        for _ in range(count):
            if cfg.magic in (MagicMode.RUNIC_MAGIC, MagicMode.WILD_MAGIC):
                point = random_point_in_annulus(self.rng, anchor, min(terrain.shape) * 0.12, min(terrain.shape) * 0.43, terrain.shape[1], terrain.shape[0])
            elif cfg.magic == MagicMode.NECROMANTIC:
                cemetery = next((b for b in buildings if b.facility in (Facility.CEMETERY, Facility.NECROPOLIS, Facility.OSSUARY)), None)
                point = cemetery.rect.center if cemetery else random_point_in_annulus(self.rng, anchor, 6, min(terrain.shape) * 0.35, terrain.shape[1], terrain.shape[0])
            else:
                magic_building = next((b for b in buildings if b.magic is not None), None)
                point = magic_building.rect.center if magic_building else random_point_in_annulus(self.rng, anchor, 4, min(terrain.shape) * 0.24, terrain.shape[1], terrain.shape[0])
            radius = int(self.rng.integers(2, 6 if cfg.magic != MagicMode.HIGH_MAGIC else 9))
            intensity = float(np.clip(self.rng.normal(0.55 if cfg.magic != MagicMode.HIGH_MAGIC else 0.75, 0.18), 0.05, 1.0))
            stamp_disk(overlay, point[0], point[1], max(1, radius // 2), int(TerrainCode.MAGIC))
            sites.append(MagicSite(self._magic_site_kind(cfg.magic), point, radius, intensity, tags=(cfg.magic.value,)))
        return sites

    def _magic_site_kind(self, magic: MagicMode) -> str:
        return {
            MagicMode.LOW_MAGIC: "minor_charm_nexus",
            MagicMode.HIGH_MAGIC: "arcane_ley_knot",
            MagicMode.RUNIC_MAGIC: "runic_geas_stone",
            MagicMode.DIVINE_MAGIC: "consecrated_ground",
            MagicMode.NECROMANTIC: "restless_dead_pressure",
            MagicMode.WILD_MAGIC: "wild_magic_bloom",
            MagicMode.TECHNO_ARCANE: "aetheric_regulator",
        }.get(magic, "strange_power")

    def _repair_connectivity(self, cfg: SettlementConfig, terrain: np.ndarray, overlay: np.ndarray, anchor: tuple[int, int], buildings: list[Building], roads: list[RoadSegment]) -> None:
        important = {
            Facility.CASTLE,
            Facility.KEEP,
            Facility.CITY_HALL,
            Facility.COURTHOUSE,
            Facility.CHURCH,
            Facility.CATHEDRAL,
            Facility.MONASTERY,
            Facility.DOCKS,
            Facility.MARKET,
            Facility.INN,
            Facility.BARRACKS,
            Facility.MAGE_TOWER,
            Facility.ARCANE_ACADEMY,
        }
        for b in buildings:
            if b.facility not in important:
                continue
            path = astar_path(terrain, b.rect.center, anchor, allow_bridges=cfg.allow_bridges, max_expansions=30000)
            if len(path) > 1:
                self._draw_road_path(cfg, terrain, overlay, path)
                roads.append(self._road("spur", path, tags=(b.facility.value,)))

    def _metadata(self, cfg: SettlementConfig, design_population: int, final_population: int, anchor: tuple[int, int], wall_points: list[tuple[int, int]]) -> dict[str, object]:
        economy = self._economy_tags(cfg)
        hazards = self._hazards(cfg)
        factions = self._factions(cfg)
        hooks = self._hooks(cfg, economy, hazards)
        return {
            "design_population": design_population,
            "actual_population": final_population,
            "anchor": anchor,
            "economy": economy,
            "hazards": hazards,
            "factions": factions,
            "hooks": hooks,
            "wall_tiles": len(wall_points),
            "terrain_features": [t.value for t in cfg.terrain],
            "switches": {
                "kind": cfg.kind.value,
                "state": cfg.state.value,
                "magic": cfg.magic.value,
                "material": cfg.material.value,
                "population_mode": cfg.population_mode.value,
                "defense": cfg.defense.value,
                "wealth": cfg.wealth.value,
                "layout": cfg.layout.value,
            },
        }

    def _economy_tags(self, cfg: SettlementConfig) -> list[str]:
        tags: list[str] = []
        if cfg.kind in (SettlementKind.FARMING_VILLAGE, SettlementKind.HAMLET, SettlementKind.VILLAGE):
            tags.extend(["grain", "livestock", "orchards"])
        if cfg.kind in (SettlementKind.FISHING_VILLAGE, SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY):
            tags.extend(["fish", "salt", "shipping"])
        if cfg.kind == SettlementKind.MINING_CAMP or TerrainFeature.HILL in cfg.terrain or TerrainFeature.MOUNTAIN_PASS in cfg.terrain:
            tags.extend(["ore", "stone"])
        if cfg.kind in (SettlementKind.MARKET_TOWN, SettlementKind.CITY, SettlementKind.CAPITAL):
            tags.extend(["market tolls", "craft guilds"])
        if cfg.magic in (MagicMode.HIGH_MAGIC, MagicMode.TECHNO_ARCANE):
            tags.append("arcane services")
        return list(dict.fromkeys(tags or ["subsistence trade"]))

    def _hazards(self, cfg: SettlementConfig) -> list[str]:
        hazards: list[str] = []
        if cfg.state == SettlementState.GHOST_TOWN:
            hazards.extend(["haunting", "empty wells", "uncanny silence"])
        if cfg.state == SettlementState.RUINED:
            hazards.extend(["unstable masonry", "bandits", "collapsed cellars"])
        if cfg.state == SettlementState.PLAGUE_STRUCK:
            hazards.extend(["quarantine", "mass graves"])
        if cfg.magic == MagicMode.NECROMANTIC:
            hazards.append("restless dead")
        if cfg.magic == MagicMode.WILD_MAGIC:
            hazards.append("unpredictable magic zones")
        if TerrainFeature.SWAMP in cfg.terrain or TerrainFeature.MARSH in cfg.terrain:
            hazards.append("bog paths")
        if TerrainFeature.BAY in cfg.terrain or TerrainFeature.COAST in cfg.terrain:
            hazards.append("storm surge")
        return hazards

    def _factions(self, cfg: SettlementConfig) -> list[str]:
        factions: list[str] = []
        if cfg.kind in (SettlementKind.CITY, SettlementKind.CAPITAL, SettlementKind.PORT_CITY):
            factions.extend(["merchant guild", "watch captains", "temple chapter"])
        if cfg.kind in (SettlementKind.FARMING_VILLAGE, SettlementKind.VILLAGE, SettlementKind.HAMLET):
            factions.extend(["village elders", "tenant farmers"])
        if cfg.kind in (SettlementKind.FORT, SettlementKind.WALLED_TOWN, SettlementKind.CAPITAL):
            factions.append("garrison")
        if cfg.magic in (MagicMode.HIGH_MAGIC, MagicMode.RUNIC_MAGIC, MagicMode.TECHNO_ARCANE):
            factions.append("licensed arcanists")
        if cfg.state in (SettlementState.RUINED, SettlementState.GHOST_TOWN):
            factions.append("scavengers")
        return factions or ["local households"]

    def _hooks(self, cfg: SettlementConfig, economy: list[str], hazards: list[str]) -> list[str]:
        hooks: list[str] = []
        if "shipping" in economy:
            hooks.append("A delayed vessel has left warehouses full and tempers short.")
        if "ore" in economy:
            hooks.append("A newly opened seam is producing metal with an impossible sheen.")
        if cfg.magic == MagicMode.RUNIC_MAGIC:
            hooks.append("The gate stones hum in bad weather and sometimes point to forgotten roads.")
        if cfg.state == SettlementState.GHOST_TOWN:
            hooks.append("Every hearth is cold, but smoke appears above one roof at moonrise.")
        if cfg.state == SettlementState.RUINED:
            hooks.append("The old civic records mention a sealed vault beneath the market square.")
        if TerrainFeature.SWAMP in cfg.terrain:
            hooks.append("The dyke-keepers claim something has been digging from the wet side inward.")
        if not hooks and hazards:
            hooks.append(f"Locals need help with {hazards[0]} before trade can resume.")
        return hooks or ["A guild dispute has made a routine delivery politically delicate."]

    def _apply_population_switches(self, population: int, mode: PopulationMode) -> int:
        if mode == PopulationMode.UNPOPULATED:
            return 0
        if mode == PopulationMode.SCARCE:
            return max(1, int(population * 0.25))
        if mode == PopulationMode.CROWDED:
            return int(population * 1.35)
        if mode == PopulationMode.FESTIVAL:
            return int(population * 1.80)
        if mode == PopulationMode.REFUGEE_SWOLLEN:
            return int(population * 1.60)
        return max(0, int(population))

    def _make_name(self, cfg: SettlementConfig) -> str:
        prefixes = ["Alder", "Brine", "Caer", "Dun", "Eld", "Fallow", "Grey", "High", "Iron", "Kings", "Lark", "Mire", "North", "Oak", "Raven", "South", "Thorn", "Vale", "West", "Wych"]
        suffixes = ["ford", "wick", "ton", "haven", "mouth", "bridge", "wall", "mere", "brook", "hold", "market", "watch", "field", "gate", "barrow", "stead", "port", "reach", "fall", "minster"]
        if cfg.kind in (SettlementKind.PORT_TOWN, SettlementKind.PORT_CITY, SettlementKind.FISHING_VILLAGE):
            suffixes += ["harbor", "quay", "bay", "tide"]
            prefixes += ["Salt", "Gull", "Tide"]
        if cfg.kind in (SettlementKind.FORT, SettlementKind.WALLED_TOWN, SettlementKind.CAPITAL):
            suffixes += ["keep", "fort", "castle"]
        if cfg.state in (SettlementState.RUINED, SettlementState.ANCIENT, SettlementState.GHOST_TOWN):
            prefixes += ["Old", "Broken", "Hollow"]
        return str(self.rng.choice(prefixes)) + str(self.rng.choice(suffixes))
