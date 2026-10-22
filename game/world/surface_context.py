"""SurfaceContext semantic query verbs over ``GameMap`` and overland metadata.

Implements Phase 2 of ``docs/Surface Map Plan.md``. ``SurfaceContext`` is
the sole API seam gameplay systems should use to ask semantic questions
about the playable surface layer. It wraps the runtime ``GameMap`` and its
``overland_metadata`` sidecar (built by ``worldgen.overland.convert``), so
gameplay code never reads overland grids directly and later surface work
(materialization, chunking, persistence; Phases 3+) can proceed behind a
stable interface.

Material semantics below are data-driven first-pass tables. They are
deliberately explicit and tunable: adjust the frozensets and dicts at the
top of this module rather than scattering material checks through gameplay
code. When the Surface Materializer (Phase 3) lands, these tables are the
natural place for per-template overrides.

Without an overland sidecar the context falls back to the base ``GameMap``
tile map for walkability and to conservative defaults for the semantic
verbs.
"""

from __future__ import annotations

from enum import IntEnum, auto
from typing import Any, Final

from common.constants import Material
from game.world.game_map import TILE_TYPES, GameMap
from worldgen.overland.actor_traversal import ActorTraversalProfile, can_actor_enter
from worldgen.overland.schema import HydroRole

DIGGABLE_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.GRASS,
        Material.FOREST_FLOOR,
        Material.FERN_UNDERSTORY,
        Material.MOSS,
        Material.REEDBED,
        Material.HEATH,
        Material.BUTTON_GRASS,
        Material.DIRT,
        Material.CLAY,
        Material.MUD,
        Material.DEEP_MUD,
        Material.MUDFLAT,
        Material.CRACKED_MUD,
        Material.SILT,
        Material.GRAVEL,
        Material.SCREE,
        Material.PEAT,
        Material.PEAT_BOG,
        Material.SPHAGNUM,
        Material.VOLCANIC_ASH,
        Material.FIELD,
        Material.ORCHARD,
        Material.PASTURE,
        Material.CLEARCUT,
        Material.TRACK,
        Material.TRAIL,
        Material.ANIMAL_TRAIL,
    }
)
"""Unconsolidated or earth surfaces (soil, mud, silt, ash), not solid rock."""

BURNABLE_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.GRASS,
        Material.FERN_UNDERSTORY,
        Material.MOSS,
        Material.REEDBED,
        Material.HEATH,
        Material.BUTTON_GRASS,
        Material.SPHAGNUM,
        Material.PEAT,
        Material.PEAT_BOG,
        Material.FOREST_FLOOR,
        Material.CLEARCUT,
        Material.WOOD_WALL,
        Material.BOARDWALK,
        Material.BRIDGE,
    }
)
"""Flammable organics: dry vegetation, peat, and built wood."""

TRACKABLE_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.MUD,
        Material.DEEP_MUD,
        Material.MUDFLAT,
        Material.CRACKED_MUD,
        Material.SILT,
        Material.CLAY,
        Material.PEAT,
        Material.PEAT_BOG,
        Material.SPHAGNUM,
        Material.VOLCANIC_ASH,
        Material.GRAVEL,
        Material.SCREE,
    }
)
"""Soft or loose surfaces that retain footprint impressions."""

SHELTER_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.BUILDING_FLOOR,
        Material.RUIN_FLOOR,
        Material.CAVE_FLOOR,
        Material.LAVA_TUBE_FLOOR,
    }
)
"""Interior floors covered by roofs, ceilings, or overhangs."""

FORAGE_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.GRASS,
        Material.FOREST_FLOOR,
        Material.FERN_UNDERSTORY,
        Material.MOSS,
        Material.REEDBED,
        Material.HEATH,
        Material.BUTTON_GRASS,
        Material.SPHAGNUM,
        Material.FIELD,
        Material.ORCHARD,
        Material.PASTURE,
    }
)
"""Surfaces offering player-relevant food or material foraging."""

SETTLEMENT_ANCHOR_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.BUILDING_FLOOR,
        Material.RUIN_FLOOR,
        Material.DOCK,
        Material.ROAD,
        Material.TRACK,
        Material.FIELD,
        Material.ORCHARD,
        Material.PASTURE,
    }
)
"""Human-scale settlement activity anchors."""

CAVE_ANCHOR_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.CAVE_FLOOR,
        Material.CAVE_MOUTH,
        Material.LAVA_TUBE_FLOOR,
        Material.COLLAPSED_LAVA_TUBE,
        Material.FLOWSTONE,
    }
)
"""Underground-adjacent anchors for cave-dwelling templates."""

WATER_SPAWN_MATERIALS: Final[frozenset[Material]] = frozenset(
    {
        Material.SHALLOW_WATER,
        Material.DEEP_WATER,
        Material.FLOWING_WATER,
        Material.SPRING_WATER,
        Material.SINKING_WATER,
        Material.ESTAVELLE_WATER,
        Material.STAGNANT_WATER,
        Material.BOG_WATER,
        Material.MUD,
        Material.DEEP_MUD,
        Material.MUDFLAT,
    }
)
"""Water and wet-mud surfaces for aquatic or amphibious wildlife."""

WATER_SPAWN_HYDRO_ROLES: Final[frozenset[HydroRole]] = frozenset(
    {
        HydroRole.SURFACE_CHANNEL,
        HydroRole.SPRING,
        HydroRole.SEEP,
        HydroRole.TEMPORARY_POOL,
        HydroRole.PERMANENT_POOL,
        HydroRole.SINKING_LAKE,
        HydroRole.ESTAVELLE,
    }
)

_DEFAULT_SOUND_CONDUCTIVITY: Final[float] = 0.6
_DEFAULT_SCENT_PERMEABILITY: Final[float] = 0.5

SOUND_CONDUCTIVITY: Final[dict[Material, float]] = {
    Material.BUILDING_FLOOR: 1.0,
    Material.ROAD: 0.95,
    Material.LIMESTONE: 0.9,
    Material.LIMESTONE_PAVEMENT: 0.9,
    Material.BASALT: 0.9,
    Material.BASALT_PAVEMENT: 0.9,
    Material.STONE_WALL: 0.9,
    Material.DOCK: 0.9,
    Material.FLOWING_WATER: 0.9,
    Material.SHALLOW_WATER: 0.85,
    Material.DEEP_WATER: 0.85,
    Material.CRACKED_MUD: 0.8,
    Material.GRAVEL: 0.75,
    Material.SCREE: 0.75,
    Material.DIRT: 0.7,
    Material.GRASS: 0.5,
    Material.HEATH: 0.5,
    Material.FERN_UNDERSTORY: 0.45,
    Material.FOREST_FLOOR: 0.45,
    Material.REEDBED: 0.35,
    Material.MOSS: 0.35,
    Material.PEAT: 0.35,
    Material.PEAT_BOG: 0.35,
    Material.SPHAGNUM: 0.35,
}
"""Material dampening multiplier for acoustic propagation (0.0 to 1.0).

Higher values carry sound farther across the tile; soft organic ground
absorbs footfall noise while hard built surfaces and bedrock reflect it.
"""

SCENT_PERMEABILITY: Final[dict[Material, float]] = {
    Material.MUD: 0.9,
    Material.DEEP_MUD: 0.9,
    Material.MUDFLAT: 0.9,
    Material.CRACKED_MUD: 0.85,
    Material.SILT: 0.85,
    Material.GRASS: 0.85,
    Material.DIRT: 0.8,
    Material.CLAY: 0.8,
    Material.FLOWING_WATER: 0.8,
    Material.HEATH: 0.75,
    Material.SHALLOW_WATER: 0.75,
    Material.BUTTON_GRASS: 0.7,
    Material.DEEP_WATER: 0.7,
    Material.FERN_UNDERSTORY: 0.6,
    Material.REEDBED: 0.55,
    Material.PEAT: 0.55,
    Material.PEAT_BOG: 0.55,
    Material.FOREST_FLOOR: 0.7,
    Material.SPHAGNUM: 0.5,
    Material.MOSS: 0.5,
    Material.SCREE: 0.65,
    Material.GRAVEL: 0.7,
    Material.BASALT: 0.5,
    Material.LIMESTONE: 0.5,
    Material.ROAD: 0.5,
    Material.BUILDING_FLOOR: 0.4,
}
"""Wind/terrain dampening multiplier for scent spread (0.0 to 1.0).

Wet soft ground retains scent; dense vegetation and built stone suppress
it. These are first-pass tunables pending the perception tuning pass.
"""


class SurfaceSpawnProfile(IntEnum):
    """Spawn anchor categories for surface entity templates (Phase 6 seed)."""

    HUMAN_SETTLEMENT = auto()
    WATER_WILDLIFE = auto()
    FORAGE_WILDLIFE = auto()
    CAVE_MONSTER = auto()


class SurfaceContext:
    """Semantic query seam over ``GameMap`` and its overland sidecar.

    All queries are read-only and deterministic: they consult the runtime
    tile map and the attached ``OverlandMapMetadata`` without mutating
    either. Coordinates are character-scale ``(x, y)`` tile coordinates.
    """

    def __init__(self, game_map: GameMap) -> None:
        self._game_map = game_map
        metadata: Any = game_map.overland_metadata
        self._metadata: Any = metadata

    @property
    def game_map(self) -> GameMap:
        return self._game_map

    @property
    def has_overland_metadata(self) -> bool:
        return self._metadata is not None

    def can_walk(self, actor_profile: ActorTraversalProfile, x: int, y: int) -> bool:
        """Return whether ``actor_profile`` may enter tile ``(x, y)``.

        With overland metadata this delegates to the shared actor
        traversal contract (``worldgen.overland.actor_traversal``), which
        honors traversal classes, wetness, and route segment state.
        Without metadata it falls back to base ``GameMap`` walkability.
        """
        self._require_in_bounds(x, y)
        if self._metadata is None:
            tile = TILE_TYPES.get(int(self._game_map.tiles[y, x]))
            return bool(tile.walkable) if tile is not None else False
        tile_row: dict[str, object] = {
            "traversal_class": int(self._metadata.traversal_class_grid[y, x]),
            "material": int(self._metadata.material_grid[y, x]),
            "wetness": int(self._metadata.wetness_grid[y, x]),
            "movement_cost": float(self._metadata.movement_cost_grid[y, x]),
        }
        return bool(
            can_actor_enter(
                tile_row, actor_profile, metadata=self._overland_metadata()
            )
        )

    def material_at(self, x: int, y: int) -> Material | None:
        """Return the tile's material, or ``None`` without a sidecar.

        Read-only material query for gameplay systems: Phase 6 surface
        behaviors ask which material an actor stands on (e.g. to stop
        a water-seeker once it reaches water).
        """
        return self._material_at(x, y)

    def can_dig(self, x: int, y: int) -> bool:
        """Return whether the tile material is diggable (soil vs rock)."""
        material = self._material_at(x, y)
        return material is not None and material in DIGGABLE_MATERIALS

    def can_burn(self, x: int, y: int) -> bool:
        """Return whether the tile material is flammable."""
        material = self._material_at(x, y)
        return material is not None and material in BURNABLE_MATERIALS

    def can_forage(self, x: int, y: int) -> bool:
        """Return whether the tile offers food/material affordances."""
        if self._affordances_at(x, y):
            return True
        material = self._material_at(x, y)
        return material is not None and material in FORAGE_MATERIALS

    def has_shelter(self, x: int, y: int) -> bool:
        """Return whether the tile is covered by roofs or enclosures."""
        self._require_in_bounds(x, y)
        material = self._material_at(x, y)
        if material is not None and material in SHELTER_MATERIALS:
            return True
        return bool(int(self._game_map.ceiling_map[y, x]) > 0)

    def can_track(self, x: int, y: int) -> bool:
        """Return whether the tile retains footprint impressions."""
        material = self._material_at(x, y)
        return material is not None and material in TRACKABLE_MATERIALS

    def sound_conductivity(self, x: int, y: int) -> float:
        """Return the acoustic propagation multiplier for the tile."""
        material = self._material_at(x, y)
        if material is None:
            return _DEFAULT_SOUND_CONDUCTIVITY
        return SOUND_CONDUCTIVITY.get(material, _DEFAULT_SOUND_CONDUCTIVITY)

    def scent_permeability(self, x: int, y: int) -> float:
        """Return the scent dispersal multiplier for the tile."""
        material = self._material_at(x, y)
        if material is None:
            return _DEFAULT_SCENT_PERMEABILITY
        return SCENT_PERMEABILITY.get(material, _DEFAULT_SCENT_PERMEABILITY)

    def is_valid_spawn_anchor(
        self, spawn_profile: SurfaceSpawnProfile, x: int, y: int
    ) -> bool:
        """Return whether ``(x, y)`` is a valid anchor for ``spawn_profile``.

        All profiles additionally require the tile to be enterable by an
        appropriate traversal profile, so spawns never land on blocked
        geometry.
        """
        material = self._material_at(x, y)
        if spawn_profile == SurfaceSpawnProfile.HUMAN_SETTLEMENT:
            return self.can_walk(ActorTraversalProfile.HUMAN_ON_FOOT, x, y) and bool(
                material is not None and material in SETTLEMENT_ANCHOR_MATERIALS
            )
        if spawn_profile == SurfaceSpawnProfile.WATER_WILDLIFE:
            if not self.can_walk(ActorTraversalProfile.SMALL_AMPHIBIOUS, x, y):
                return False
            if self._affordances_at(x, y):
                return True
            if material is not None and material in WATER_SPAWN_MATERIALS:
                return True
            hydro_role = self._hydro_role_at(x, y)
            return hydro_role is not None and hydro_role in WATER_SPAWN_HYDRO_ROLES
        if spawn_profile == SurfaceSpawnProfile.FORAGE_WILDLIFE:
            return self.can_walk(
                ActorTraversalProfile.SMALL_AMPHIBIOUS, x, y
            ) and self.can_forage(x, y)
        if spawn_profile == SurfaceSpawnProfile.CAVE_MONSTER:
            return self.can_walk(
                ActorTraversalProfile.SMALL_AMPHIBIOUS, x, y
            ) and bool(material is not None and material in CAVE_ANCHOR_MATERIALS)
        raise ValueError(f"Unhandled spawn profile: {spawn_profile}")

    def _overland_metadata(self) -> Any:
        if self._metadata is None:
            raise RuntimeError("SurfaceContext has no overland metadata")
        return self._metadata

    def _material_at(self, x: int, y: int) -> Material | None:
        self._require_in_bounds(x, y)
        if self._metadata is None:
            return None
        grid = self._metadata.material_grid
        if grid is None:
            return None
        return Material(int(grid[y, x]))

    def _hydro_role_at(self, x: int, y: int) -> HydroRole | None:
        if self._metadata is None:
            return None
        grid = self._metadata.hydro_grid
        if grid is None:
            return None
        return HydroRole(int(grid[y, x]))

    def _affordances_at(self, x: int, y: int) -> list[dict[str, Any]]:
        self._require_in_bounds(x, y)
        if self._metadata is None:
            return []
        rows = self._metadata.affordances.get((x, y))
        return list(rows) if rows else []

    def _require_in_bounds(self, x: int, y: int) -> None:
        height, width = self._game_map.tiles.shape
        if not 0 <= int(x) < int(width) or not 0 <= int(y) < int(height):
            raise IndexError(
                f"Surface coordinates out of bounds: ({x}, {y}) "
                f"for map {int(width)}x{int(height)}"
            )


__all__ = [
    "BURNABLE_MATERIALS",
    "CAVE_ANCHOR_MATERIALS",
    "DIGGABLE_MATERIALS",
    "FORAGE_MATERIALS",
    "SCENT_PERMEABILITY",
    "SETTLEMENT_ANCHOR_MATERIALS",
    "SHELTER_MATERIALS",
    "SOUND_CONDUCTIVITY",
    "SurfaceContext",
    "SurfaceSpawnProfile",
    "TRACKABLE_MATERIALS",
    "WATER_SPAWN_HYDRO_ROLES",
    "WATER_SPAWN_MATERIALS",
]
