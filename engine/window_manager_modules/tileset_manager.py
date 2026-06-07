# engine/window_manager_modules/tileset_manager.py
"""
Manages loading, caching, and providing access to tileset data,
including Numba-compatible NumPy arrays.
"""

# Standard Imports
from pathlib import Path
from typing import Any

# Third-party Imports
import numpy as np
import structlog

# Numba imports with fallback
# Fallback removed
from numba import types as nb_types
from numba.typed import Dict as NumbaTypedDict
from PIL import Image

_NUMBA_AVAILABLE = True

# Local Application Imports
from engine.tileset_loader import load_tiles

# Ensure GameMap and TILE_TYPES can be imported
# Fallback removed
from game.world.game_map import TILE_TYPES

log = structlog.get_logger(__name__)

SENTINEL_TILE_ARRAY_SHAPE = (0, 0, 4)
SENTINEL_TILE_ARRAY = np.empty(SENTINEL_TILE_ARRAY_SHAPE, dtype=np.uint8)


class TilesetManager:
    """Handles loading and caching of tile assets."""

    def __init__(
        self,
        initial_tileset_path: str,
        initial_tile_width: int,
        initial_tile_height: int,
        min_tile_size_cfg: int,
    ):
        log.info("Initializing TilesetManager...")
        self.min_tile_size: int = min_tile_size_cfg
        self.current_tileset_path: str = ""
        # PIL images {tile_index: Image}
        self.tiles: dict[int, Image.Image] = {}
        self.tiles_loaded: dict[int, np.ndarray] = {}
        self.tile_width: int = 0
        self.tile_height: int = 0

        # --- Numba Cache and Render Data ---
        self.tile_arrays: NumbaTypedDict | dict = {}
        self.max_defined_tile_id: int = -1
        self._tile_fg_colors: np.ndarray | None = None
        self._tile_bg_colors: np.ndarray | None = None
        self._tile_indices_render: np.ndarray | None = None
        self._change_counter: int = 0  # Track tileset changes

        # Check Numba availability
        self._numba_available = _NUMBA_AVAILABLE
        self._NumbaDict = NumbaTypedDict if _NUMBA_AVAILABLE else dict
        self._nb_types = nb_types

        # Perform initial load
        self.load_new_tileset(
            initial_tileset_path, initial_tile_width, initial_tile_height
        )
        log.debug("TilesetManager initialized.")

    def load_new_tileset(self, folder: str, width: int, height: int) -> bool:
        """Loads a new tileset from the specified folder and dimensions."""
        target_abs_path_str = "unknown"
        try:
            clamped_width = max(self.min_tile_size, width)
            clamped_height = max(self.min_tile_size, height)

            # Resolve path correctly
            target_path_obj = Path(folder)
            if not target_path_obj.is_absolute():
                try:
                    base_path = Path(__file__).parent.parent.parent
                except NameError:
                    base_path = Path(".")
                target_abs_path = (base_path / folder).resolve()
            else:
                target_abs_path = target_path_obj.resolve()
            target_abs_path_str = str(target_abs_path)

            if (
                clamped_width == self.tile_width
                and clamped_height == self.tile_height
                and target_abs_path_str == self.current_tileset_path
            ):
                log.info(
                    "Tileset unchanged, skipping reload.", path=target_abs_path_str
                )
                return True

            log.info(
                "Loading tileset",
                path=target_abs_path_str,
                w=clamped_width,
                h=clamped_height,
            )

            # Load tiles
            loaded_tiles, _ = load_tiles(
                target_abs_path_str, clamped_width, clamped_height
            )

            self.current_tileset_path = target_abs_path_str

            # Ensure loaded_tiles is the correct type
            if isinstance(loaded_tiles, dict):
                self.tiles = loaded_tiles
                # Convert to numpy arrays for caching
                self.tiles_loaded = {}
                for tile_id, img in loaded_tiles.items():
                    if img is not None and isinstance(img, Image.Image):
                        if img.mode != "RGBA":
                            img = img.convert("RGBA")
                        self.tiles_loaded[tile_id] = np.array(img, dtype=np.uint8)
            else:
                log.error(
                    "load_tiles did not return a dictionary",
                    received_type=type(loaded_tiles),
                )
                self.tiles = {}
                self.tiles_loaded = {}
                return False

            self.tile_width = clamped_width
            self.tile_height = clamped_height
            self._change_counter += 1  # Mark as changed

            self._update_tile_array_cache()
            self._populate_render_data_cache()

            log.info(
                "Tileset loaded successfully",
                path=target_abs_path_str,
                final_w=self.tile_width,
                final_h=self.tile_height,
                count=len(self.tiles),
            )
            return True

        except Exception as e:
            log.error(
                "Error loading tileset",
                path_param=folder,
                abs_path=target_abs_path_str,
                error=str(e),
                exc_info=True,
            )
            return False

    def _populate_tile_arrays_cache(self) -> None:
        """Populate the tile arrays cache ensuring NumbaDict consistency."""
        if not self.tiles_loaded:
            log.warning("No tiles loaded, cannot populate tile arrays cache")
            self.tile_arrays = None
            return

        try:
            if self._numba_available and self._nb_types:
                # Create NumbaDict for tile arrays
                _array_type = self._nb_types.uint8[:, :, ::1]
                self.tile_arrays = self._NumbaDict.empty(
                    key_type=self._nb_types.int_, value_type=_array_type
                )
            else:
                # Fallback to Python dict
                self.tile_arrays = {}

            # Populate with tile data
            for tile_id, tile_data in self.tiles_loaded.items():
                if isinstance(tile_data, np.ndarray):
                    # Ensure correct shape and type
                    if tile_data.ndim == 3 and tile_data.shape[2] == 4:
                        # Ensure C-contiguous for Numba
                        if not tile_data.flags["C_CONTIGUOUS"]:
                            tile_data = np.ascontiguousarray(tile_data, dtype=np.uint8)
                        else:
                            tile_data = tile_data.astype(np.uint8, copy=False)

                        self.tile_arrays[int(tile_id)] = tile_data
                    else:
                        log.warning(
                            f"Tile {tile_id} has invalid shape: {tile_data.shape}"
                        )

            log.info(f"Populated tile arrays cache with {len(self.tile_arrays)} tiles")

        except Exception as e:
            log.error(f"Failed to populate tile arrays cache: {e}", exc_info=True)
            # Create empty fallback
            if self._numba_available and self._nb_types:
                _array_type = self._nb_types.uint8[:, :, ::1]
                self.tile_arrays = self._NumbaDict.empty(
                    key_type=self._nb_types.int_, value_type=_array_type
                )
            else:
                self.tile_arrays = {}

    def _update_tile_array_cache(self) -> None:
        """Updates the Numba-compatible NumPy array cache and render data."""
        log.debug("Updating tile array cache...")

        if self._numba_available and self._nb_types:
            _array_value_type = self._nb_types.uint8[:, :, ::1]
            temp_tile_arrays = self._NumbaDict.empty(
                key_type=self._nb_types.int_, value_type=_array_value_type
            )
        else:
            temp_tile_arrays = {}

        # Reset caches
        self.max_defined_tile_id = -1
        pil_tile_count = 0
        numba_tile_count = 0

        # Process tiles
        if not self.tiles or self.tile_width <= 0 or self.tile_height <= 0:
            log.warning("Cannot update cache: Invalid tiles or dimensions.")
            self.tile_arrays = temp_tile_arrays
            return

        pil_tile_count = len(self.tiles)

        for tile_index, img in self.tiles.items():
            if img is None:
                temp_tile_arrays[tile_index] = SENTINEL_TILE_ARRAY
                continue

            try:
                if img.size != (self.tile_width, self.tile_height):
                    img = img.resize(
                        (self.tile_width, self.tile_height), Image.Resampling.NEAREST
                    )
                if img.mode != "RGBA":
                    img = img.convert("RGBA")

                tile_np_array = np.array(img, dtype=np.uint8)

                # Ensure C-contiguity for Numba compatibility
                if not tile_np_array.flags["C_CONTIGUOUS"]:
                    tile_np_array = np.ascontiguousarray(tile_np_array)

                # Check final shape
                if tile_np_array.shape == (self.tile_height, self.tile_width, 4):
                    temp_tile_arrays[tile_index] = tile_np_array
                    numba_tile_count += 1
                else:
                    log.warning(f"Tile {tile_index} shape mismatch, using sentinel")
                    temp_tile_arrays[tile_index] = SENTINEL_TILE_ARRAY

            except Exception as e:
                log.warning(f"Could not convert tile {tile_index}: {e}")
                temp_tile_arrays[tile_index] = SENTINEL_TILE_ARRAY

        self.tile_arrays = temp_tile_arrays
        log.info(f"Cache updated: PIL={pil_tile_count}, Numba={numba_tile_count}")

    def _populate_render_data_cache(self) -> None:
        """Update render data cache from TILE_TYPES with validation."""
        if not TILE_TYPES or not isinstance(TILE_TYPES, dict):
            log.warning("TILE_TYPES is empty or invalid")
            self.max_defined_tile_id = -1
            self._tile_fg_colors = None
            self._tile_bg_colors = None
            self._tile_indices_render = None
            return

        try:
            # Get valid integer tile IDs
            valid_tile_ids = [k for k in TILE_TYPES if isinstance(k, int) and k >= 0]
            if not valid_tile_ids:
                log.warning("No valid integer tile IDs found")
                self.max_defined_tile_id = -1
                return

            self.max_defined_tile_id = max(valid_tile_ids)
            array_size = self.max_defined_tile_id + 1

            # Initialize arrays
            self._tile_fg_colors = np.zeros((array_size, 3), dtype=np.uint8)
            self._tile_bg_colors = np.zeros((array_size, 3), dtype=np.uint8)
            self._tile_indices_render = np.zeros(array_size, dtype=np.uint16)

            # Set default colors
            self._tile_fg_colors[:] = (255, 255, 255)  # Default white
            self._tile_bg_colors[:] = (0, 0, 0)  # Default black

            # Populate from TILE_TYPES
            valid_count = 0
            for tile_id, tile_data in TILE_TYPES.items():
                if not isinstance(tile_id, int) or tile_id < 0 or tile_id >= array_size:
                    continue

                # Extract colors with validation
                fg_color = getattr(tile_data, "color_fg", (255, 255, 255))
                bg_color = getattr(tile_data, "color_bg", (0, 0, 0))
                tile_index = getattr(tile_data, "tile_index", 0)

                # Validate and set colors
                if isinstance(fg_color, tuple | list) and len(fg_color) >= 3:
                    self._tile_fg_colors[tile_id] = [
                        max(0, min(255, int(fg_color[0]))),
                        max(0, min(255, int(fg_color[1]))),
                        max(0, min(255, int(fg_color[2]))),
                    ]

                if isinstance(bg_color, tuple | list) and len(bg_color) >= 3:
                    self._tile_bg_colors[tile_id] = [
                        max(0, min(255, int(bg_color[0]))),
                        max(0, min(255, int(bg_color[1]))),
                        max(0, min(255, int(bg_color[2]))),
                    ]

                # Ensure tile index is valid
                self._tile_indices_render[tile_id] = max(0, int(tile_index))
                valid_count += 1

            log.info(f"Render cache populated: {valid_count}/{array_size} tiles")

        except Exception as e:
            log.error(f"Failed to populate render cache: {e}", exc_info=True)
            self.max_defined_tile_id = -1

    def get_render_data(self) -> dict[str, Any]:
        """Get render data with proper validation and fallback."""
        # Validate all components
        cache_valid = (
            self._tile_fg_colors is not None
            and self._tile_bg_colors is not None
            and self._tile_indices_render is not None
            and self.max_defined_tile_id >= 0
            and self.tile_arrays is not None
        )

        if not cache_valid:
            log.warning("Render cache invalid, attempting rebuild")
            self._update_tile_array_cache()
            self._populate_render_data_cache()

            # Check again
            cache_valid = (
                self._tile_fg_colors is not None
                and self._tile_bg_colors is not None
                and self._tile_indices_render is not None
                and self.max_defined_tile_id >= 0
                and self.tile_arrays is not None
            )

        if not cache_valid:
            log.error("Failed to build valid render cache, returning empty data")
            # Return minimal valid structure
            if self._numba_available and self._nb_types:
                _array_type = self._nb_types.uint8[:, :, ::1]
                empty_arrays = self._NumbaDict.empty(
                    key_type=self._nb_types.int_, value_type=_array_type
                )
            else:
                empty_arrays = {}

            return {
                "tile_arrays": empty_arrays,
                "tile_fg_colors": np.zeros((1, 3), dtype=np.uint8),
                "tile_bg_colors": np.zeros((1, 3), dtype=np.uint8),
                "tile_indices_render": np.zeros(1, dtype=np.uint16),
                "max_defined_tile_id": -1,
                "tile_w": self.tile_width or 16,
                "tile_h": self.tile_height or 16,
            }

        # Ensure tile_arrays is the correct type for current environment
        if (
            self._numba_available
            and self._nb_types
            and not isinstance(self.tile_arrays, self._NumbaDict)
        ):
            log.warning("Converting tile_arrays to NumbaDict")
            old_arrays = self.tile_arrays
            _array_type = self._nb_types.uint8[:, :, ::1]
            self.tile_arrays = self._NumbaDict.empty(
                key_type=self._nb_types.int_, value_type=_array_type
            )
            if isinstance(old_arrays, dict):
                for k, v in old_arrays.items():
                    if isinstance(v, np.ndarray):
                        self.tile_arrays[int(k)] = np.ascontiguousarray(
                            v, dtype=np.uint8
                        )

        log.debug(
            "TilesetManager.get_render_data returning data",
            cache_ready=cache_valid,
            max_id=self.max_defined_tile_id,
            tile_arrays_items=len(self.tile_arrays) if self.tile_arrays else 0,
        )

        return {
            "tile_arrays": self.tile_arrays,
            "tile_fg_colors": self._tile_fg_colors,
            "tile_bg_colors": self._tile_bg_colors,
            "tile_indices_render": self._tile_indices_render,
            "max_defined_tile_id": self.max_defined_tile_id,
            "tile_w": self.tile_width,
            "tile_h": self.tile_height,
        }

    def invalidate_cache(self) -> None:
        """Force cache rebuild on next access."""
        log.info("Invalidating tileset cache")
        self.tile_arrays = None
        self._tile_fg_colors = None
        self._tile_bg_colors = None
        self._tile_indices_render = None
        self._change_counter += 1
