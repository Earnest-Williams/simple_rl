# game/world/game_map.py
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NamedTuple

import numpy as np
import structlog
import yaml

from engine.glyphs import tile_id_for
from game.world import memory
from game.world.fov import compute_visibility_into
from game.world.memory import MemoryTraits, resolve_memory_decay_parameters

log = structlog.get_logger()

ROLE_GLYPH_DEFAULTS: Final[dict[str, str]] = {
    "floor": "blank_tile_a",
    "wall": "wall_stone_bricks",
}


def _load_role_glyph_defaults() -> dict[str, str]:
    role_defaults = dict(ROLE_GLYPH_DEFAULTS)
    cfg_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
    if not cfg_path.exists():
        return role_defaults
    try:
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        log.warning("Invalid config yaml; using tile defaults", error=str(exc))
        return role_defaults
    if not isinstance(cfg, dict):
        return role_defaults
    tiles_cfg = cfg.get("tiles")
    if not isinstance(tiles_cfg, dict):
        return role_defaults
    for role, glyph_name in tiles_cfg.items():
        if isinstance(role, str) and isinstance(glyph_name, str):
            role_defaults[role.lower()] = glyph_name
    return role_defaults


_ROLE_GLYPHS = _load_role_glyph_defaults()

_FLOOR_GLYPH = _ROLE_GLYPHS.get("floor", ROLE_GLYPH_DEFAULTS["floor"])
_WALL_GLYPH = _ROLE_GLYPHS.get("wall", ROLE_GLYPH_DEFAULTS["wall"])

TILE_ID_FLOOR: Final[int] = int(tile_id_for(_FLOOR_GLYPH, 0) or 0)
TILE_ID_WALL: Final[int] = int(tile_id_for(_WALL_GLYPH, 1) or 1)
# Maximum number of times a tile can strengthen its memory
MAX_MEMORY_STRENGTH: Final[float] = 5.0


class TileType(NamedTuple):
    walkable: bool
    transparent: bool
    tile_index: int
    color_fg: tuple[int, int, int]
    color_bg: tuple[int, int, int]
    memory_modifier: float


TILE_TYPES: Final[dict[int, TileType]] = {
    TILE_ID_FLOOR: TileType(
        walkable=True,
        transparent=True,
        tile_index=TILE_ID_FLOOR,
        color_fg=(200, 200, 200),
        color_bg=(10, 10, 30),
        memory_modifier=1.0,
    ),
    TILE_ID_WALL: TileType(
        walkable=False,
        transparent=False,
        tile_index=TILE_ID_WALL,
        color_fg=(180, 180, 180),
        color_bg=(30, 30, 50),
        memory_modifier=2.0,
    ),
    # Add other tile types here...
}


TILE_NAME_TO_ID: Final[dict[str, int]] = {
    "floor": TILE_ID_FLOOR,
    "wall": TILE_ID_WALL,
}


def _normalize_tile_modifier_overrides(
    overrides: dict[str | int, float],
) -> dict[int, float]:
    """Convert user-provided keys (names or IDs) to tile ID -> modifier."""
    normalized: dict[int, float] = {}
    for key, value in overrides.items():
        tile_id: int | None
        tile_id = key if isinstance(key, int) else TILE_NAME_TO_ID.get(str(key).lower())
        if tile_id is None:
            continue
        normalized[tile_id] = float(value)
    return normalized


def get_memory_modifier_map(
    tiles: np.ndarray, overrides: dict[int, float] | None = None
) -> np.ndarray:
    """Return an array of memory modifiers per tile."""
    modifiers = np.ones_like(tiles, dtype=np.float32)
    for tile_id, tile_type in TILE_TYPES.items():
        modifiers[tiles == tile_id] = tile_type.memory_modifier
    if overrides:
        for tile_id, mod in overrides.items():
            modifiers[tiles == tile_id] = mod
    return modifiers


def get_transparency_map(tiles: np.ndarray) -> np.ndarray:
    """Creates a boolean array indicating transparency based on TILE_TYPES."""
    # Initialize with False (opaque)
    transparency = np.zeros_like(tiles, dtype=bool)
    # Iterate through defined types and set transparency
    for tile_id, tile_type in TILE_TYPES.items():
        transparency[tiles == tile_id] = tile_type.transparent
    return transparency


@dataclass(slots=True)
class LightSource:
    x: int
    y: int
    radius: int
    color: tuple[int, int, int]
    intensity: float = 1.0
    direction: float | None = None
    cone_angle: float = math.tau
    cone_softness: float = 0.0
    channels: int = 0xFFFFFFFF
    id: int = -1
    height: float = 0.0


class GameMap:
    def __init__(
        self,
        width: int,
        height: int,
        tile_memory_modifiers: dict[str | int, float] | None = None,
    ) -> None:
        """Initializes the game map with dimensions and default tile arrays."""
        if width <= 0 or height <= 0:
            log.error("Invalid map dimensions", width=width, height=height)
            raise ValueError("Map width and height must be positive integers.")
        self._width = width
        self._height = height
        log.info("Initializing GameMap", width=self._width, height=self._height)

        # Core map data arrays - Use C order for compatibility with many libraries
        self.tiles: np.ndarray = np.full(
            (height, width), fill_value=TILE_ID_WALL, dtype=np.uint8, order="C"
        )
        # Visibility/Exploration state
        self.explored: np.ndarray = np.zeros((height, width), dtype=bool, order="C")
        self.visible: np.ndarray = np.zeros((height, width), dtype=bool, order="C")
        # Cached transparency map
        self.transparent: np.ndarray = get_transparency_map(self.tiles)
        # Persistent tile-shaped memory state
        self._tile_modifier_overrides: dict[int, float] = {}
        self.tile_memory_modifiers: np.ndarray = get_memory_modifier_map(self.tiles)
        if tile_memory_modifiers:
            self.apply_memory_modifier_overrides(tile_memory_modifiers)
        # Height and Ceiling maps
        self.height_map: np.ndarray = np.zeros(
            (height, width), dtype=np.int16, order="C"
        )
        self.ceiling_map: np.ndarray = np.zeros(
            (height, width), dtype=np.int16, order="C"
        )
        self.light_channel_mask: np.ndarray = np.full(
            (height, width), 0xFFFFFFFF, dtype=np.uint32, order="C"
        )
        self.memory_intensity: np.ndarray = np.zeros(
            (height, width), dtype=np.float32, order="C"
        )
        self.memory_strength: np.ndarray = np.zeros(
            (height, width), dtype=np.float32, order="C"
        )
        self.last_seen_time: np.ndarray = np.zeros(
            (height, width), dtype=np.int32, order="C"
        )
        self.memory_fade_mask: np.ndarray = np.zeros(
            (height, width), dtype=bool, order="C"
        )
        self.prev_visible: np.ndarray = np.zeros((height, width), dtype=bool, order="C")
        # Perception layers reused across turns
        self.noise_map: np.ndarray = np.zeros(
            (height, width), dtype=np.float32, order="C"
        )
        self.scent_map: np.ndarray = np.zeros(
            (height, width), dtype=np.float32, order="C"
        )
        self.light_sources: list[LightSource] = []
        self._scene_geometry_version: int = 0
        # Vertical transitions like stairs or shafts
        self.vertical_transitions: list[dict[str, int | str]] = []
        # Environmental storytelling hooks (annotations on the map)
        self.story_hooks: list[dict[str, str | int]] = []
        log.debug("GameMap arrays initialized", shape=(height, width))

    def update_tile_transparency(self) -> None:
        """Recalculates the transparency map based on current self.tiles."""
        # This should be called whenever self.tiles is modified (e.g., after digging)
        self.transparent = np.zeros((self._height, self._width), dtype=bool)
        for tile_id, tile_type in TILE_TYPES.items():
            self.transparent[self.tiles == tile_id] = tile_type.transparent
        # Recompute memory modifiers in case tiles changed
        self.tile_memory_modifiers = get_memory_modifier_map(
            self.tiles, self._tile_modifier_overrides
        )
        self._scene_geometry_version += 1
        transparent_count = np.sum(self.transparent)
        log.info("Transparency map updated", transparent_count=transparent_count)

    def apply_memory_modifier_overrides(
        self, overrides: dict[str | int, float]
    ) -> None:
        """Apply designer-provided memory fade overrides per tile type."""
        self._tile_modifier_overrides = _normalize_tile_modifier_overrides(overrides)
        self.tile_memory_modifiers = get_memory_modifier_map(
            self.tiles, self._tile_modifier_overrides
        )

    def set_light_channel_mask(self, x: int, y: int, channels: int) -> None:
        """Set the lighting channel mask for a specific cell and increment geometry version."""
        if self.in_bounds(x, y):
            self.light_channel_mask[y, x] = np.uint32(channels)
            self._scene_geometry_version += 1

    def set_height(self, x: int, y: int, height: int) -> None:
        """Set the floor height for a specific cell and increment geometry version."""
        if self.in_bounds(x, y):
            self.height_map[y, x] = np.int16(height)
            self._scene_geometry_version += 1

    def set_ceiling(self, x: int, y: int, height: int) -> None:
        """Set the ceiling height for a specific cell and increment geometry version."""
        if self.in_bounds(x, y):
            self.ceiling_map[y, x] = np.int16(height)
            self._scene_geometry_version += 1

    def set_height_region(
        self, x0: int, y0: int, x1: int, y1: int, height: int
    ) -> None:
        """Set the floor height for a region and increment geometry version."""
        x0, x1 = max(0, min(x0, x1)), min(self._width, max(x0, x1))
        y0, y1 = max(0, min(y0, y1)), min(self._height, max(y0, y1))
        self.height_map[y0:y1, x0:x1] = np.int16(height)
        self._scene_geometry_version += 1

    def set_ceiling_region(
        self, x0: int, y0: int, x1: int, y1: int, height: int
    ) -> None:
        """Set the ceiling height for a region and increment geometry version."""
        x0, x1 = max(0, min(x0, x1)), min(self._width, max(x0, x1))
        y0, y1 = max(0, min(y0, y1)), min(self._height, max(y0, y1))
        self.ceiling_map[y0:y1, x0:x1] = np.int16(height)
        self._scene_geometry_version += 1

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def scene_geometry_version(self) -> int:
        """Monotone version for tile, opacity, height, and ceiling changes."""
        return self._scene_geometry_version

    def in_bounds(self, x: int, y: int) -> bool:
        """Checks if the given coordinates are within the map boundaries."""
        return 0 <= x < self._width and 0 <= y < self._height

    def is_walkable(self, x: int, y: int) -> bool:
        """Checks if the tile at (x, y) is walkable."""
        if not self.in_bounds(x, y):
            return False
        tile_id = self.tiles[y, x]
        tile_type = TILE_TYPES.get(tile_id)
        return tile_type.walkable if tile_type else False

    def is_transparent(self, x: int, y: int) -> bool:
        """Checks if the tile at (x, y) is transparent (for FOV)."""
        if not self.in_bounds(x, y):
            # Treat out of bounds as non-transparent for FOV calculations
            return False
        # Directly use the cached transparency map
        return self.transparent[y, x]

    def refresh_visible_memory(self, current_time: int) -> None:
        """Refresh memory state for currently visible tiles."""
        self.memory_intensity[self.visible] = 1.0
        self.last_seen_time[self.visible] = current_time
        self.memory_strength[self.visible] = np.minimum(
            self.memory_strength[self.visible] + 1.0, MAX_MEMORY_STRENGTH
        )
        not_visible: np.ndarray = ~self.visible
        self.memory_strength[not_visible] = np.maximum(
            self.memory_strength[not_visible] - 1.0, 0.0
        )

    def fade_memory(
        self,
        current_time: int,
        *,
        traits: MemoryTraits,
        base_steepness: float,
        base_midpoint: float,
    ) -> None:
        """Fade remembered tiles using actor memory traits and base decay config."""
        steepness, midpoint = resolve_memory_decay_parameters(
            traits,
            base_steepness=base_steepness,
            base_midpoint=base_midpoint,
        )
        memory.update_memory_fade(
            current_time,
            last_seen_time=self.last_seen_time,
            memory_intensity=self.memory_intensity,
            visible=self.visible,
            needs_update_mask=self.memory_fade_mask,
            prev_visible=self.prev_visible,
            memory_strength=self.memory_strength,
            tile_modifiers=self.tile_memory_modifiers,
            steepness=steepness,
            midpoint=midpoint,
        )

    def compute_fov(self, x: int, y: int, radius: int) -> None:
        """Calculate field of view from ``(x, y)`` with the given ``radius``."""
        log_context = {"origin": (x, y), "radius": radius}
        if not self.in_bounds(x, y):
            log.warning(
                "FOV origin out of bounds in GameMap.compute_fov", **log_context
            )
            self.visible.fill(False)
            return

        def blocks_light(tile_y: int, tile_x: int) -> bool:
            return not self.transparent[tile_y, tile_x]

        def set_visible(tile_y: int, tile_x: int) -> None:
            self.visible[tile_y, tile_x] = True
            self.explored[tile_y, tile_x] = True

        def get_distance(
            origin_y: int, origin_x: int, target_y: int, target_x: int
        ) -> float:
            return math.hypot(target_x - origin_x, target_y - origin_y)

        self.visible.fill(False)
        compute_visibility_into(
            self.height,
            self.width,
            origin_y=y,
            origin_x=x,
            radius=radius,
            is_opaque=blocks_light,
            mark_visible=set_visible,
            distance=get_distance,
        )

    def create_test_room(self) -> None:
        """Creates a simple rectangular room for testing."""
        room_x, room_y = self.width // 4, self.height // 4
        room_w, room_h = self.width // 2, self.height // 2

        # Ensure indices are within bounds for slicing
        x_start = max(0, room_x)
        y_start = max(0, room_y)
        x_end = min(self.width, room_x + room_w)
        y_end = min(self.height, room_y + room_h)

        # Assign FLOOR tile ID to the room area
        self.tiles[y_start:y_end, x_start:x_end] = TILE_ID_FLOOR

        # --- Assign default height/ceiling to test room ---
        test_floor_height = 0
        test_ceiling_height = 6  # e.g., 3 meters high
        self.set_height_region(x_start, y_start, x_end, y_end, test_floor_height)
        self.set_ceiling_region(x_start, y_start, x_end, y_end, test_ceiling_height)
        # --- End Assignment ---

        # Update transparency after changing tiles
        self.update_tile_transparency()
        log.info(
            "Created test room",
            x_start=x_start,
            y_start=y_start,
            x_end=x_end,
            y_end=y_end,
            floor_h=test_floor_height,
            ceil_h=test_ceiling_height,
        )
        transparent_count = np.sum(self.transparent)
        log.info("Map contains transparent tiles", count=transparent_count)

    def update_fov_with_tracking(
        self, x: int, y: int, radius: int
    ) -> set[tuple[int, int]]:  # Use Tuple, Set imported
        """
        Updates FOV and returns a set of (x, y) coordinates where
        visibility changed (either became visible or hidden).
        """
        previous_visible = self.visible.copy()
        self.compute_fov(x, y, radius)
        changed_positions = set()

        # Optimization: Use np.where for potentially faster comparison on large maps
        diff_indices = np.argwhere(previous_visible != self.visible)
        for y_idx, x_idx in diff_indices:
            changed_positions.add((int(x_idx), int(y_idx)))  # Store as (x, y)

        if changed_positions:
            log.debug("Visibility changed", changed_count=len(changed_positions))
        return changed_positions
