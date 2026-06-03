# engine/render_entities.py
"""Rendering helpers for tiles, items, and entities."""

import numpy as np

# Fallback removed
from numba import njit, uint8
from numba.typed import Dict as NumbaDict

_NUMBA_AVAILABLE = True


# FIXED: Complete sentinel variable name
NJIT_SENTINEL_TILE_ARRAY_SHAPE = (0, 0, 4)


def _extract_color_components(color_dict: dict) -> tuple[int, int, int, int]:
    """Internal helper to normalize color information.

    The rendering code expects RGBA color components in the range 0-255 and of
    ``np.uint8`` dtype.  Entity and item dictionaries may store colour
    information in a few different ways (either a single ``color``/``color_fg``
    sequence or separate ``color_fg_r``/``color_fg_g``/``color_fg_b`` keys).

    Parameters
    ----------
    color_dict:
        Dictionary representing an entity/item; must contain some colour
        information.  Missing channels default to ``0`` for RGB and ``255`` for
        alpha.

    Returns
    -------
    tuple[int, int, int, int]
        Normalised ``(r, g, b, a)`` components.
    """

    if "color" in color_dict and isinstance(color_dict["color"], list | tuple):
        seq = color_dict["color"]
    elif "color_fg" in color_dict and isinstance(color_dict["color_fg"], list | tuple):
        seq = color_dict["color_fg"]
    else:
        seq = (
            color_dict.get("color_fg_r", 0),
            color_dict.get("color_fg_g", 0),
            color_dict.get("color_fg_b", 0),
            color_dict.get("color_fg_a"),
        )

    r = int(seq[0]) if len(seq) > 0 and seq[0] is not None else 0
    g = int(seq[1]) if len(seq) > 1 and seq[1] is not None else 0
    b = int(seq[2]) if len(seq) > 2 and seq[2] is not None else 0
    a = int(seq[3]) if len(seq) > 3 and seq[3] is not None else 255
    return r, g, b, a


def pack_ground_items(
    items: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Pack a list of ground item dictionaries into typed NumPy arrays.

    Parameters
    ----------
    items:
        Sequence of dictionaries each containing at least ``x``, ``y``,
        ``glyph`` and colour information.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]
        ``xs``, ``ys``, ``glyphs`` and ``colors`` arrays ready for the Numba
        rendering functions.  Arrays are empty with correct dtype if ``items``
        is empty.
    """

    n = len(items)
    xs = np.empty(n, dtype=np.int64)
    ys = np.empty(n, dtype=np.int64)
    glyphs = np.empty(n, dtype=np.int32)
    colors = np.empty((n, 4), dtype=np.uint8)

    assert xs.dtype == np.int64, f"Expected xs to have dtype int64, got {xs.dtype}"
    assert ys.dtype == np.int64, f"Expected ys to have dtype int64, got {ys.dtype}"
    assert (
        glyphs.dtype == np.int32
    ), f"Expected glyphs to have dtype int32, got {glyphs.dtype}"
    assert (
        colors.dtype == np.uint8 and colors.shape[1] == 4
    ), f"Expected colors to have dtype uint8 and shape (n, 4), got dtype {colors.dtype} and shape {colors.shape}"

    for i, item in enumerate(items):
        xs[i] = int(item.get("x", 0))
        ys[i] = int(item.get("y", 0))
        glyphs[i] = int(item.get("glyph", 0))
        r, g, b, a = _extract_color_components(item)
        colors[i, 0] = r
        colors[i, 1] = g
        colors[i, 2] = b
        colors[i, 3] = a

    return xs, ys, glyphs, colors


def pack_entities(
    entities: list[dict],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Pack a list of entity dictionaries into typed NumPy arrays.

    Behaviour mirrors :func:`pack_ground_items` but is provided separately for
    clarity.  The input is a sequence of dictionaries describing entities with
    ``x``, ``y``, ``glyph`` and colour information.
    """

    n = len(entities)
    xs = np.empty(n, dtype=np.int64)
    ys = np.empty(n, dtype=np.int64)
    glyphs = np.empty(n, dtype=np.int32)
    colors = np.empty((n, 4), dtype=np.uint8)

    assert xs.dtype == np.int64, f"Expected xs to have dtype int64, got {xs.dtype}"
    assert ys.dtype == np.int64, f"Expected ys to have dtype int64, got {ys.dtype}"
    assert (
        glyphs.dtype == np.int32
    ), f"Expected glyphs to have dtype int32, got {glyphs.dtype}"
    assert (
        colors.dtype == np.uint8 and colors.shape[1] == 4
    ), f"Expected colors to have dtype uint8 and shape (n, 4), got dtype {colors.dtype} and shape {colors.shape}"

    for i, ent in enumerate(entities):
        xs[i] = int(ent.get("x", 0))
        ys[i] = int(ent.get("y", 0))
        glyphs[i] = int(ent.get("glyph", 0))
        r, g, b, a = _extract_color_components(ent)
        colors[i, 0] = r
        colors[i, 1] = g
        colors[i, 2] = b
        colors[i, 3] = a

    return xs, ys, glyphs, colors


@njit(cache=True, nogil=True)
def render_map_tiles(
    output_image_array: np.ndarray,
    glyph_indices: np.ndarray,
    drawn_mask: np.ndarray,
    final_fg: np.ndarray,
    final_bg: np.ndarray,
    tile_arrays: NumbaDict,
    vp_h: int,
    vp_w: int,
    tile_h: int,
    tile_w: int,
) -> None:
    """Render map tiles with proper glyph drawing and error handling."""
    tile_buffer = np.empty((tile_h, tile_w, 4), dtype=uint8)

    for vp_y in range(vp_h):
        for vp_x in range(vp_w):
            if not drawn_mask[vp_y, vp_x]:
                continue

            tile_glyph_idx = glyph_indices[vp_y, vp_x]

            # Check if tile exists in arrays and validate shape
            if tile_glyph_idx in tile_arrays:
                tile_rgba_array = tile_arrays[tile_glyph_idx]

                # FIXED: Complete shape validation
                if (
                    tile_rgba_array.shape == (tile_h, tile_w, 4)
                    and tile_rgba_array.shape != NJIT_SENTINEL_TILE_ARRAY_SHAPE
                ):
                    # Extract alpha channel and create draw mask
                    glyph_alpha_channel = tile_rgba_array[:, :, 3]
                    glyph_draw_mask_2d = glyph_alpha_channel > 10
                    mask_rows, mask_cols = np.where(glyph_draw_mask_2d)

                    # Get foreground color for this tile
                    tile_fg_color_rgb = final_fg[vp_y, vp_x]

                    # First, fill with background
                    tile_bg_color_rgb = final_bg[vp_y, vp_x]
                    tile_buffer[:, :, 0] = max(0, min(255, tile_bg_color_rgb[0]))
                    tile_buffer[:, :, 1] = max(0, min(255, tile_bg_color_rgb[1]))
                    tile_buffer[:, :, 2] = max(0, min(255, tile_bg_color_rgb[2]))
                    tile_buffer[:, :, 3] = 255

                    # Then draw glyph pixels
                    for i in range(mask_rows.shape[0]):
                        r, c = mask_rows[i], mask_cols[i]
                        tile_buffer[r, c, 0] = max(0, min(255, tile_fg_color_rgb[0]))
                        tile_buffer[r, c, 1] = max(0, min(255, tile_fg_color_rgb[1]))
                        tile_buffer[r, c, 2] = max(0, min(255, tile_fg_color_rgb[2]))
                        tile_buffer[r, c, 3] = glyph_alpha_channel[r, c]
                else:
                    # Invalid shape - just fill with background
                    tile_bg_color_rgb = final_bg[vp_y, vp_x]
                    tile_buffer[:, :, 0] = max(0, min(255, tile_bg_color_rgb[0]))
                    tile_buffer[:, :, 1] = max(0, min(255, tile_bg_color_rgb[1]))
                    tile_buffer[:, :, 2] = max(0, min(255, tile_bg_color_rgb[2]))
                    tile_buffer[:, :, 3] = 255
            else:
                # Tile not found - fill with background color
                tile_bg_color_rgb = final_bg[vp_y, vp_x]
                tile_buffer[:, :, 0] = max(0, min(255, tile_bg_color_rgb[0]))
                tile_buffer[:, :, 1] = max(0, min(255, tile_bg_color_rgb[1]))
                tile_buffer[:, :, 2] = max(0, min(255, tile_bg_color_rgb[2]))
                tile_buffer[:, :, 3] = 255

            # Copy tile buffer to output image
            px_start_y = vp_y * tile_h
            px_start_x = vp_x * tile_w
            dest_slice_y = slice(px_start_y, px_start_y + tile_h)
            dest_slice_x = slice(px_start_x, px_start_x + tile_w)
            output_image_array[dest_slice_y, dest_slice_x, :] = tile_buffer[:, :]


@njit(cache=True, nogil=True)
def render_ground_items(
    output_image_array: np.ndarray,
    item_xs: np.ndarray,
    item_ys: np.ndarray,
    item_glyphs: np.ndarray,
    item_colors: np.ndarray,
    tile_arrays: NumbaDict,
    intensity_map: np.ndarray,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    tile_w: int,
    tile_h: int,
) -> None:
    """Render ground items with proper validation."""
    n_items = item_xs.shape[0]
    if n_items == 0:
        return

    for i in range(n_items):
        map_x = item_xs[i]
        map_y = item_ys[i]
        item_glyph_idx = item_glyphs[i]

        if item_glyph_idx <= 0:
            continue

        # Convert to viewport coordinates
        vp_x = map_x - viewport_x
        vp_y = map_y - viewport_y

        if not (0 <= vp_y < vp_h and 0 <= vp_x < vp_w):
            continue

        if item_glyph_idx in tile_arrays:
            item_tile_rgba_array = tile_arrays[item_glyph_idx]

            # FIXED: Complete shape validation
            if (
                item_tile_rgba_array.shape == (tile_h, tile_w, 4)
                and item_tile_rgba_array.shape != NJIT_SENTINEL_TILE_ARRAY_SHAPE
            ):
                # Apply lighting
                light_intensity = intensity_map[vp_y, vp_x]
                item_fg = item_colors[i, :3]
                lit_item_fg_rgb = (item_fg * light_intensity).astype(uint8)

                # Calculate pixel positions
                px_start_y = vp_y * tile_h
                px_start_x = vp_x * tile_w
                dest_slice_y = slice(px_start_y, px_start_y + tile_h)
                dest_slice_x = slice(px_start_x, px_start_x + tile_w)
                target_pixel_block = output_image_array[dest_slice_y, dest_slice_x]

                # Draw item pixels
                item_alpha_channel = item_tile_rgba_array[:, :, 3]
                item_draw_mask = item_alpha_channel > 10

                # Fix: Use np.where instead of multi-dimensional boolean indexing
                mask_rows, mask_cols = np.where(item_draw_mask)
                for j in range(mask_rows.shape[0]):
                    r, c = mask_rows[j], mask_cols[j]
                    target_pixel_block[r, c, 0] = lit_item_fg_rgb[0]
                    target_pixel_block[r, c, 1] = lit_item_fg_rgb[1]
                    target_pixel_block[r, c, 2] = lit_item_fg_rgb[2]
                    target_pixel_block[r, c, 3] = item_alpha_channel[r, c]


@njit(cache=True, nogil=True)
def render_entities(
    output_image_array: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    glyphs: np.ndarray,
    colors: np.ndarray,
    tile_arrays: NumbaDict,
    intensity_map: np.ndarray,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    tile_w: int,
    tile_h: int,
) -> None:
    """Render entities with proper validation and lighting."""
    n_entities = xs.shape[0]
    if n_entities == 0:
        return

    for i in range(n_entities):
        map_x = xs[i]
        map_y = ys[i]
        glyph_idx = glyphs[i]

        if glyph_idx <= 0:
            continue

        # Convert to viewport coordinates
        cons_x = map_x - viewport_x
        cons_y = map_y - viewport_y

        if not (0 <= cons_y < vp_h and 0 <= cons_x < vp_w):
            continue

        if glyph_idx in tile_arrays:
            entity_tile_rgba_array = tile_arrays[glyph_idx]

            # FIXED: Complete shape validation
            if (
                entity_tile_rgba_array.shape == (tile_h, tile_w, 4)
                and entity_tile_rgba_array.shape != NJIT_SENTINEL_TILE_ARRAY_SHAPE
            ):
                # Apply lighting
                light_intensity = intensity_map[cons_y, cons_x]
                entity_fg = colors[i, :3]
                lit_entity_fg_rgb = (entity_fg * light_intensity).astype(uint8)

                # Calculate pixel positions
                px_start_y = cons_y * tile_h
                px_start_x = cons_x * tile_w
                dest_slice_y = slice(px_start_y, px_start_y + tile_h)
                dest_slice_x = slice(px_start_x, px_start_x + tile_w)
                target_pixel_block = output_image_array[dest_slice_y, dest_slice_x]

                # Draw entity pixels
                entity_alpha_channel = entity_tile_rgba_array[:, :, 3]
                entity_draw_mask = entity_alpha_channel > 10
                mask_rows, mask_cols = np.where(entity_draw_mask)

                for j in range(mask_rows.shape[0]):
                    r, c = mask_rows[j], mask_cols[j]
                    target_pixel_block[r, c, 0] = lit_entity_fg_rgb[0]
                    target_pixel_block[r, c, 1] = lit_entity_fg_rgb[1]
                    target_pixel_block[r, c, 2] = lit_entity_fg_rgb[2]
                    target_pixel_block[r, c, 3] = entity_alpha_channel[r, c]


def _validate_render_arrays(xs, ys, glyphs, colors):
    """Validate array shapes and dtypes for rendering functions."""
    if xs is None or ys is None or glyphs is None or colors is None:
        return False

    if xs.size != ys.size or xs.size != glyphs.size or xs.size != colors.shape[0]:
        return False

    if xs.dtype != np.int64 or ys.dtype != np.int64:
        return False

    if glyphs.dtype != np.int32:
        return False

    return colors.dtype == np.uint8 and colors.ndim == 2 and colors.shape[1] == 4


def render_ground_items_py(
    output_image_array: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    glyphs: np.ndarray,
    colors: np.ndarray,
    tile_arrays: NumbaDict,
    intensity_map: np.ndarray,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    tile_w: int,
    tile_h: int,
) -> None:
    """Python wrapper for render_ground_items that validates inputs."""
    if not _validate_render_arrays(xs, ys, glyphs, colors):
        return

    render_ground_items(
        output_image_array,
        xs,
        ys,
        glyphs,
        colors,
        tile_arrays,
        intensity_map,
        viewport_x,
        viewport_y,
        vp_h,
        vp_w,
        tile_w,
        tile_h,
    )


def render_entities_py(
    output_image_array: np.ndarray,
    xs: np.ndarray,
    ys: np.ndarray,
    glyphs: np.ndarray,
    colors: np.ndarray,
    tile_arrays: NumbaDict,
    intensity_map: np.ndarray,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    tile_w: int,
    tile_h: int,
) -> None:
    """Python wrapper for render_entities that validates inputs."""
    if not _validate_render_arrays(xs, ys, glyphs, colors):
        return

    render_entities(
        output_image_array,
        xs,
        ys,
        glyphs,
        colors,
        tile_arrays,
        intensity_map,
        viewport_x,
        viewport_y,
        vp_h,
        vp_w,
        tile_w,
        tile_h,
    )
