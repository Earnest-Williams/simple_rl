# engine/renderer.py
"""
Handles rendering the game state to a PIL Image, using
pre-calculated data and optimized techniques.
"""
# Standard Library Imports
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict as PyDict

# Third-party Imports
import numpy as np
import polars as pl
import structlog
from PIL import Image, ImageDraw

# Local imports
from .render_entities import (
    pack_ground_items,
    pack_entities,
    render_map_tiles,
    render_ground_items_py,
    render_entities_py,
)
from .render_lighting import (
    calculate_lighting,
    apply_height_visualization,
    apply_memory_fade,
)
from .render_base_layers import prepare_base_layers

# Numba for acceleration
try:
    from numba.typed import Dict as NumbaDict
    from numba import types as nb_types

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False
    NumbaDict = dict  # Fallback type hint
    nb_types = None

# Local Application Imports
try:
    from game.game_state import GameState
    from game.world.game_map import GameMap
    from game.world.fov import compute_light_color_array
except ImportError as exc:
    raise RuntimeError("Failed to import GameState or GameMap in renderer") from exc

try:
    from utils.game_rng import GameRNG
except ImportError as exc:
    raise RuntimeError("Failed to import GameRNG in renderer") from exc

if TYPE_CHECKING:
    pass

log = structlog.get_logger()


@dataclass
class RenderConfig:
    """Configuration settings passed to the renderer."""

    show_height_vis: bool
    vis_max_diff: int
    vis_color_high_np: np.ndarray
    vis_color_mid_np: np.ndarray
    vis_color_low_np: np.ndarray
    vis_blend_factor: np.float32
    lighting_ambient: np.float32
    lighting_min_fov: np.float32
    lighting_falloff: np.float32
    fov_radius_sq: np.float32
    enable_memory_fade: bool = True
    enable_colored_lights: bool = True
    memory_fade_color_np: np.ndarray = field(
        default_factory=lambda: np.array([128, 128, 128], dtype=np.uint8)
    )
    memory_fade_variance: np.float32 = np.float32(0.0)
    memory_noise_level: np.float32 = np.float32(0.0)


@dataclass
class ViewportParams:
    """Collects parameters required for viewport rendering."""

    viewport_x: int
    viewport_y: int
    viewport_width: int
    viewport_height: int
    tile_arrays: NumbaDict | PyDict
    tile_fg_colors: np.ndarray
    tile_bg_colors: np.ndarray
    tile_indices_render: np.ndarray
    max_defined_tile_id: int
    tile_w: int
    tile_h: int
    coord_arrays: PyDict[str, np.ndarray]


def convert_to_numba_dict(py_dict: dict) -> NumbaDict:
    """Convert a Python dictionary of tile arrays to NumbaDict."""
    if not _NUMBA_AVAILABLE or nb_types is None:
        return py_dict

    _array_type = nb_types.uint8[:, :, ::1]
    numba_dict = NumbaDict.empty(key_type=nb_types.int_, value_type=_array_type)

    for key, value in py_dict.items():
        if isinstance(value, np.ndarray):
            # Ensure contiguous C-order array
            if not value.flags["C_CONTIGUOUS"]:
                value = np.ascontiguousarray(value, dtype=np.uint8)
            numba_dict[int(key)] = value

    return numba_dict


def create_error_image(width: int, height: int, message: str = "Error") -> Image.Image:
    """Create an error indicator image with message."""
    img = Image.new("RGBA", (max(1, width), max(1, height)), (100, 0, 100, 255))
    try:
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), message, fill=(255, 255, 255, 255))
    except:
        pass  # If text fails, just return purple image
    return img


def render_map_tiles_fallback(
    output_image_array: np.ndarray,
    glyph_indices: np.ndarray,
    drawn_mask: np.ndarray,
    final_fg: np.ndarray,
    final_bg: np.ndarray,
    tile_arrays: dict,
    vp_h: int,
    vp_w: int,
    tile_w: int,
    tile_h: int,
) -> None:
    """Python fallback for tile rendering when Numba is unavailable."""
    for vp_y in range(vp_h):
        for vp_x in range(vp_w):
            if not drawn_mask[vp_y, vp_x]:
                continue

            tile_glyph_idx = int(glyph_indices[vp_y, vp_x])

            # Calculate pixel positions
            px_start_y = vp_y * tile_h
            px_start_x = vp_x * tile_w
            px_end_y = px_start_y + tile_h
            px_end_x = px_start_x + tile_w

            # First fill with background
            bg_color = final_bg[vp_y, vp_x]
            output_image_array[px_start_y:px_end_y, px_start_x:px_end_x, :3] = bg_color
            output_image_array[px_start_y:px_end_y, px_start_x:px_end_x, 3] = 255

            # Then draw glyph if available
            if tile_glyph_idx in tile_arrays:
                tile_rgba = tile_arrays[tile_glyph_idx]
                if isinstance(tile_rgba, np.ndarray) and tile_rgba.shape == (
                    tile_h,
                    tile_w,
                    4,
                ):
                    # Apply foreground color to non-transparent pixels
                    alpha_mask = tile_rgba[:, :, 3] > 10
                    fg_color = final_fg[vp_y, vp_x]

                    for y in range(tile_h):
                        for x in range(tile_w):
                            if alpha_mask[y, x]:
                                out_y = px_start_y + y
                                out_x = px_start_x + x
                                output_image_array[out_y, out_x, :3] = fg_color
                                output_image_array[out_y, out_x, 3] = tile_rgba[y, x, 3]


def render_viewport(
    game_state: GameState,
    viewport: ViewportParams,
    render_config: RenderConfig,
) -> Image.Image | None:
    """Render the visible portion of the game world to a PIL Image."""

    log.debug(
        "render_viewport called",
        vp_x=viewport.viewport_x,
        vp_y=viewport.viewport_y,
        vp_w=viewport.viewport_width,
        vp_h=viewport.viewport_height,
        tile_dims=f"{viewport.tile_w}x{viewport.tile_h}",
        max_tile_id=viewport.max_defined_tile_id,
    )

    # Unpack viewport parameters
    viewport_x = viewport.viewport_x
    viewport_y = viewport.viewport_y
    viewport_width = viewport.viewport_width
    viewport_height = viewport.viewport_height
    tile_w = viewport.tile_w
    tile_h = viewport.tile_h
    tile_arrays = viewport.tile_arrays
    tile_fg_colors = viewport.tile_fg_colors
    tile_bg_colors = viewport.tile_bg_colors
    tile_indices_render = viewport.tile_indices_render
    max_defined_tile_id = viewport.max_defined_tile_id
    coord_arrays = viewport.coord_arrays

    # Calculate output dimensions
    output_pixel_w = viewport_width * tile_w
    output_pixel_h = viewport_height * tile_h

    # FIXED: Validate tile arrays before proceeding
    if not tile_arrays:
        log.error("No tile arrays available for rendering")
        return create_error_image(output_pixel_w, output_pixel_h, "No tiles loaded")

    # FIXED: Ensure we have valid NumbaDict when Numba is available
    if _NUMBA_AVAILABLE:
        if not isinstance(tile_arrays, NumbaDict):
            log.warning("Converting tile_arrays to NumbaDict for rendering")
            try:
                tile_arrays = convert_to_numba_dict(tile_arrays)
            except Exception as e:
                log.error(f"Failed to convert tile_arrays: {e}")
                return create_error_image(
                    output_pixel_w, output_pixel_h, "Tile conversion failed"
                )

    # Input Validation
    if not isinstance(game_state, GameState):
        log.error("render_viewport called with invalid GameState object")
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (255, 0, 0, 255)
        )

    gs = game_state
    gm = gs.game_map

    if tile_w <= 0 or tile_h <= 0 or max_defined_tile_id < 0:
        log.warning("Cannot render: Invalid params/cache")
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (0, 0, 0, 255)
        )

    player_pos = gs.player_position
    if player_pos is None:
        log.warning("Cannot render: Player position not found")
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (0, 0, 0, 255)
        )

    player_x, player_y = player_pos
    player_height = 0

    try:
        if gm.in_bounds(player_x, player_y):
            player_height = int(gm.height_map[player_y, player_x])
    except Exception as e:
        log.error(f"Error getting player height: {e}")

    # Viewport dimensions
    vp_w = viewport_width
    vp_h = viewport_height

    # Prepare base layers
    try:
        result = prepare_base_layers(
            gm,
            viewport_x,
            viewport_y,
            vp_h,
            vp_w,
            tile_fg_colors,
            tile_bg_colors,
            tile_indices_render,
            max_defined_tile_id,
        )

        if result is None or len(result) != 7:
            log.error("prepare_base_layers returned invalid result")
            return Image.new(
                "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (0, 0, 0, 0)
            )

        (
            base_fg,
            base_bg,
            glyph_indices,
            drawn_mask,
            visible_mask,
            map_height_vp,
            map_memory_vp,
        ) = result
        map_tiles_vp = gm.tiles[
            viewport_y : viewport_y + vp_h, viewport_x : viewport_x + vp_w
        ]

    except Exception as e:
        log.error(f"Error during prepare_base_layers: {e}", exc_info=True)
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (255, 0, 0, 255)
        )

    # Apply Lighting and Height Visualization
    lit_fg, lit_bg, intensity_map = calculate_lighting(
        base_fg,
        base_bg,
        visible_mask,
        vp_h,
        vp_w,
        viewport_x,
        viewport_y,
        player_x,
        player_y,
        render_config.lighting_ambient,
        render_config.lighting_min_fov,
        render_config.lighting_falloff,
        render_config.fov_radius_sq,
    )

    final_fg, final_bg = apply_height_visualization(
        lit_fg,
        lit_bg,
        drawn_mask,
        map_height_vp,
        player_height,
        render_config.show_height_vis,
        render_config.vis_max_diff,
        render_config.vis_color_high_np,
        render_config.vis_color_mid_np,
        render_config.vis_color_low_np,
        render_config.vis_blend_factor,
    )

    # Apply colored lights
    if (
        render_config.enable_colored_lights
        and hasattr(gs, "light_sources")
        and len(gs.light_sources) > 0
    ):
        light_rgb_map = np.zeros((gm.height, gm.width, 3), dtype=np.float32)
        opaque_grid = ~gm.transparent

        for ls in gs.light_sources:
            try:
                origin_h = int(gm.height_map[ls.y, ls.x])
                compute_light_color_array(
                    (ls.x, ls.y),
                    ls.radius,
                    opaque_grid,
                    gm.height_map,
                    gm.ceiling_map,
                    origin_h,
                    light_rgb_map,
                    ls.color,
                )
            except Exception as e:
                log.error(f"Error computing light source: {e}")

        light_rgb_vp = light_rgb_map[
            viewport_y : viewport_y + vp_h, viewport_x : viewport_x + vp_w
        ]
        final_fg = np.clip(final_fg.astype(np.float32) + light_rgb_vp, 0, 255).astype(
            np.uint8
        )
        final_bg = np.clip(final_bg.astype(np.float32) + light_rgb_vp, 0, 255).astype(
            np.uint8
        )

    # Apply memory fade
    if render_config.enable_memory_fade:
        apply_memory_fade(
            final_fg,
            final_bg,
            glyph_indices,
            map_memory_vp,
            map_tiles_vp,
            drawn_mask,
            visible_mask,
            render_config.memory_fade_color_np,
            gs.rng_instance,
            float(render_config.memory_fade_variance),
            float(render_config.memory_noise_level),
            viewport_x,
            viewport_y,
        )

    # Prepare Output Buffer
    if output_pixel_h <= 0 or output_pixel_w <= 0:
        log.warning("Calculated output pixel size is zero or negative")
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    output_image_array = np.zeros((output_pixel_h, output_pixel_w, 4), dtype=np.uint8)

    # Fill Background Layer
    try:
        if (
            not coord_arrays
            or "tile_coord_y" not in coord_arrays
            or "tile_coord_x" not in coord_arrays
        ):
            raise KeyError("Coordinate arrays missing or invalid.")

        tile_coord_y = coord_arrays["tile_coord_y"]
        tile_coord_x = coord_arrays["tile_coord_x"]

        if tile_coord_y.shape != (
            output_pixel_h,
            output_pixel_w,
        ) or tile_coord_x.shape != (output_pixel_h, output_pixel_w):
            raise ValueError(f"Coordinate array shape mismatch")

        if final_bg.shape != (vp_h, vp_w, 3):
            raise ValueError(f"Background color shape mismatch")

        output_image_array[:, :, :3] = final_bg[tile_coord_y, tile_coord_x]
        output_image_array[:, :, 3] = 255

    except (KeyError, IndexError, ValueError) as e:
        log.error(f"Error preparing output buffer: {e}", exc_info=True)
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (100, 0, 100, 255)
        )
    except Exception as e:
        log.error(f"Unexpected error during background fill: {e}", exc_info=True)
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (100, 0, 100, 255)
        )

    # FIXED: Render Map Tiles with Proper Fallback
    try:
        if not tile_arrays:
            log.warning("render_map_tiles skipped: tile_arrays dictionary is empty.")
        elif np.sum(drawn_mask) == 0:
            log.debug("render_map_tiles skipped: no tiles to draw.")
        elif _NUMBA_AVAILABLE and isinstance(tile_arrays, NumbaDict):
            # FIXED: Validate indices before rendering
            if np.any(drawn_mask):
                max_glyph_idx = np.max(glyph_indices[drawn_mask])
                available_indices = set(tile_arrays.keys())

                if max_glyph_idx > 0 and max_glyph_idx not in available_indices:
                    log.warning(
                        f"Glyph index {max_glyph_idx} not in tile_arrays, clamping indices"
                    )
                    max_available = max(available_indices) if available_indices else 0
                    glyph_indices = np.clip(glyph_indices, 0, max_available)

            # Call Numba compiled function
            render_map_tiles(
                output_image_array,
                glyph_indices,
                drawn_mask,
                final_fg,
                final_bg,
                tile_arrays,
                vp_h,
                vp_w,
                tile_w,
                tile_h,
            )
        else:
            # FIXED: Python fallback for non-Numba environments
            log.info("Using Python fallback for tile rendering")
            render_map_tiles_fallback(
                output_image_array,
                glyph_indices,
                drawn_mask,
                final_fg,
                final_bg,
                tile_arrays,
                vp_h,
                vp_w,
                tile_w,
                tile_h,
            )
    except Exception as e:
        log.error(f"Critical error during tile rendering: {e}", exc_info=True)
        log.info("Attempting to continue with background-only rendering")

    # Prepare and render ground items
    item_xs = None
    item_ys = None
    item_glyphs = None
    item_colors = None

    if np.any(visible_mask):
        try:
            vp_x_min, vp_y_min = viewport_x, viewport_y
            vp_x_max, vp_y_max = viewport_x + vp_w, viewport_y + vp_h

            items_in_vp_df = gs.item_registry.items_df.filter(
                (pl.col("x") >= vp_x_min)
                & (pl.col("x") < vp_x_max)
                & (pl.col("y") >= vp_y_min)
                & (pl.col("y") < vp_y_max)
                & (pl.col("location_type") == "ground")
                & pl.col("is_active")
                & (pl.col("glyph") > 0)
            )

            if items_in_vp_df.height > 0:
                top_items_df = items_in_vp_df.group_by(["x", "y"]).last()
                item_coords_x_abs = top_items_df["x"].to_numpy()
                item_coords_y_abs = top_items_df["y"].to_numpy()
                item_coords_x_vp = item_coords_x_abs - viewport_x
                item_coords_y_vp = item_coords_y_abs - viewport_y

                valid_indices_mask = (
                    (item_coords_x_vp >= 0)
                    & (item_coords_x_vp < vp_w)
                    & (item_coords_y_vp >= 0)
                    & (item_coords_y_vp < vp_h)
                )

                visibility_mask = visible_mask[
                    item_coords_y_vp[valid_indices_mask],
                    item_coords_x_vp[valid_indices_mask],
                ]
                visible_items_df = top_items_df.filter(
                    pl.Series(valid_indices_mask)
                ).filter(pl.Series(visibility_mask))

                if visible_items_df.height > 0:
                    packed_items = pack_ground_items(visible_items_df.to_dicts())
                    item_xs, item_ys, item_glyphs, item_colors = packed_items

        except Exception as e:
            log.error(f"Error querying/processing items: {e}", exc_info=True)

    # Render ground items
    if item_xs is not None and item_xs.size > 0:
        try:
            if _NUMBA_AVAILABLE and isinstance(tile_arrays, NumbaDict):
                render_ground_items_py(
                    output_image_array,
                    item_xs,
                    item_ys,
                    item_glyphs,
                    item_colors,
                    tile_arrays,
                    intensity_map,
                    viewport_x,
                    viewport_y,
                    vp_h,
                    vp_w,
                    tile_w,
                    tile_h,
                )
            else:
                log.warning(
                    "render_ground_items skipped: Numba not available or tile_arrays is not NumbaDict."
                )
        except Exception as e:
            log.error(f"Error during render_ground_items: {e}", exc_info=True)

    # Prepare and render entities
    entity_xs = None
    entity_ys = None
    entity_glyphs = None
    entity_colors = None

    if isinstance(gs.entity_registry, object) and gs.entity_registry is not object:
        try:
            active_entities_df = gs.entity_registry.get_active_entities()
            if active_entities_df.height > 0:
                vp_y_min = viewport_y
                vp_y_max = viewport_y + vp_h
                entities_in_vp_bounds = active_entities_df.filter(
                    (pl.col("x") >= viewport_x)
                    & (pl.col("x") < viewport_x + vp_w)
                    & (pl.col("y") >= vp_y_min)
                    & (pl.col("y") < vp_y_max)
                    & (pl.col("glyph") > 0)
                )

                if entities_in_vp_bounds.height > 0:
                    packed_entities = pack_entities(entities_in_vp_bounds.to_dicts())
                    entity_xs, entity_ys, entity_glyphs, entity_colors = packed_entities

        except Exception as e:
            log.error(f"Error querying/processing entities: {e}", exc_info=True)

    # Render entities
    if entity_xs is not None and entity_xs.size > 0:
        try:
            if _NUMBA_AVAILABLE and isinstance(tile_arrays, NumbaDict):
                render_entities_py(
                    output_image_array,
                    entity_xs,
                    entity_ys,
                    entity_glyphs,
                    entity_colors,
                    tile_arrays,
                    intensity_map,
                    viewport_x,
                    viewport_y,
                    vp_h,
                    vp_w,
                    tile_w,
                    tile_h,
                )
            else:
                log.warning(
                    "render_entities skipped: Numba not available or tile_arrays is not NumbaDict."
                )
        except Exception as e:
            log.error(f"Error during render_entities: {e}", exc_info=True)

    # Final Image Conversion
    try:
        if output_pixel_h > 0 and output_pixel_w > 0:
            final_image = Image.fromarray(output_image_array, "RGBA")
            return final_image
        else:
            log.warning("Output pixel dimensions were non-positive after processing")
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    except Exception as e:
        log.error(f"Error converting final array to PIL Image: {e}", exc_info=True)
        return Image.new(
            "RGBA", (max(1, output_pixel_w), max(1, output_pixel_h)), (50, 50, 50, 255)
        )
