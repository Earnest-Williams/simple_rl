"""Lighting and visual effect helpers for rendering."""

import math
from collections.abc import Iterable

import numpy as np
import structlog

try:
    from numba import float32, njit, uint8

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(func=None, **options):  # type: ignore
        if func:
            return func
        return lambda f: f

    uint8 = np.uint8  # type: ignore
    float32 = np.float32  # type: ignore

try:
    from game.world.game_map import TILE_ID_FLOOR, TILE_ID_WALL, GameMap
except ImportError:
    GameMap = object  # type: ignore
    TILE_ID_FLOOR = 0  # type: ignore
    TILE_ID_WALL = 1  # type: ignore
    structlog.get_logger().error(
        "CRITICAL: Failed to import tile IDs in render_lighting."
    )

try:
    from utils.game_rng import GameRNG
except ImportError:

    class GameRNG:  # type: ignore
        pass

    structlog.get_logger().error(
        "CRITICAL: Failed to import GameRNG in render_lighting."
    )

try:
    from game.world.fov import compute_light_color_array
except ImportError:
    compute_light_color_array = None  # type: ignore
    structlog.get_logger().error(
        "CRITICAL: Failed to import compute_light_color_array in render_lighting."
    )

log = structlog.get_logger()

MEMORY_WALL_GLYPHS = np.array(
    [ord("▓"), ord("▒"), ord("░"), ord("⋅"), ord(" ")], dtype=np.uint16
)
MEMORY_FLOOR_GLYPHS = np.array(
    [ord("."), ord("·"), ord("⋅"), ord(" "), ord(" ")], dtype=np.uint16
)
NOISY_MEMORY_WALL_GLYPHS = np.array(
    [ord("█"), ord("▓"), ord("▒"), ord("░"), ord(" ")], dtype=np.uint16
)
NOISY_MEMORY_FLOOR_GLYPHS = np.array(
    [ord("#"), ord("~"), ord(":"), ord("."), ord(" ")], dtype=np.uint16
)
MEMORY_LEVEL_COUNT = MEMORY_WALL_GLYPHS.size


@njit(
    float32(float32, float32, float32, float32), cache=True, fastmath=True, nogil=True
)
def _calculate_light_intensity_scalar(
    dist_sq: np.float32,
    radius_sq: np.float32,
    falloff_power: np.float32,
    min_light_level: np.float32,
) -> np.float32:
    """Calculates light intensity based on distance squared."""
    if radius_sq < 1e-6:
        return np.float32(1.0) if dist_sq < 1e-6 else np.float32(0.0)
    if dist_sq >= radius_sq:
        return np.float32(0.0)

    dist = math.sqrt(dist_sq)
    radius = math.sqrt(radius_sq)
    falloff_ratio = dist / radius
    light_value = max(np.float32(0.0), np.float32(1.0) - falloff_ratio) ** falloff_power
    intensity = max(light_value, min_light_level)
    return max(np.float32(0.0), min(np.float32(1.0), intensity))


@njit("uint8[:](uint8[:], float32)", cache=True, fastmath=True, nogil=True)
def _interpolate_color_numba_vector(
    base_color: np.ndarray, intensity: np.float32
) -> np.ndarray:
    """Interpolates an RGB color towards black based on intensity."""
    if base_color.shape[0] < 3:
        return np.zeros(3, dtype=uint8)

    intensity_clamped = max(np.float32(0.0), min(np.float32(1.0), intensity))
    result = np.empty(3, dtype=uint8)
    for i in range(3):
        result[i] = max(0, min(255, int(base_color[i] * intensity_clamped)))
    return result


@njit(cache=True, nogil=True)
def calculate_lighting(
    base_fg: np.ndarray,
    base_bg: np.ndarray,
    visible_mask: np.ndarray,
    vp_h: int,
    vp_w: int,
    viewport_x: int,
    viewport_y: int,
    player_x: int,
    player_y: int,
    config_ambient: float32,
    config_min_fov: float32,
    config_falloff: float32,
    fov_radius_sq: float32,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Calculates lighting intensity and applies it."""
    intensity_map = np.full((vp_h, vp_w), config_ambient, dtype=np.float32)

    if np.any(visible_mask):
        visible_y_coords, visible_x_coords = np.where(visible_mask)
        map_abs_x_visible = visible_x_coords + viewport_x
        map_abs_y_visible = visible_y_coords + viewport_y

        dx = map_abs_x_visible - player_x
        dy = map_abs_y_visible - player_y
        dist_sq_map_visible = (dx * dx + dy * dy).astype(np.float32)

        visible_intensities = np.empty_like(dist_sq_map_visible, dtype=np.float32)
        for i in range(dist_sq_map_visible.shape[0]):
            visible_intensities[i] = _calculate_light_intensity_scalar(
                dist_sq_map_visible[i],
                fov_radius_sq,
                config_falloff,
                config_min_fov,
            )

        for i in range(visible_y_coords.shape[0]):
            y = visible_y_coords[i]
            x = visible_x_coords[i]
            intensity_map[y, x] = visible_intensities[i]

    intensity_broadcast = intensity_map[..., None]
    lit_fg = (base_fg.astype(np.float32) * intensity_broadcast).astype(np.uint8)
    lit_bg = (base_bg.astype(np.float32) * intensity_broadcast).astype(np.uint8)
    return lit_fg, lit_bg, intensity_map


def apply_light_sources(
    lit_fg: np.ndarray,
    lit_bg: np.ndarray,
    light_sources: Iterable,
    game_map: GameMap,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Apply colored light sources to lit buffers within the viewport."""
    if not light_sources:
        empty = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
        return lit_fg, lit_bg, empty

    if compute_light_color_array is None:
        log.warning("compute_light_color_array unavailable; skipping colored lights")
        empty = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
        return lit_fg, lit_bg, empty

    if not isinstance(game_map, GameMap) or GameMap is object:
        log.warning("Invalid GameMap supplied; skipping colored lights")
        empty = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
        return lit_fg, lit_bg, empty

    light_rgb_map = np.zeros((game_map.height, game_map.width, 3), dtype=np.float32)
    opaque_grid = ~game_map.transparent

    for ls in light_sources:
        if not game_map.in_bounds(ls.x, ls.y):
            continue
        try:
            origin_h = int(game_map.height_map[ls.y, ls.x])
            compute_light_color_array(
                origin_xy=(ls.x, ls.y),
                range_limit=ls.radius,
                opaque_grid=opaque_grid,
                height_map=game_map.height_map,
                ceiling_map=game_map.ceiling_map,
                origin_height=origin_h,
                target_rgb_array=light_rgb_map,
                base_color_rgb=ls.color,
            )
        except Exception as exc:
            log.error("Error computing light source", error=str(exc), light=ls)

    light_rgb_vp = light_rgb_map[
        viewport_y : viewport_y + vp_h, viewport_x : viewport_x + vp_w
    ]
    final_fg = lit_fg
    final_bg = lit_bg
    fg_f32 = final_fg.astype(np.float32)
    bg_f32 = final_bg.astype(np.float32)
    fg_f32 += light_rgb_vp
    bg_f32 += light_rgb_vp
    np.clip(fg_f32, 0, 255, out=fg_f32)
    np.clip(bg_f32, 0, 255, out=bg_f32)
    final_fg[:] = fg_f32.astype(np.uint8)
    final_bg[:] = bg_f32.astype(np.uint8)
    return final_fg, final_bg, light_rgb_vp


@njit(cache=True, nogil=True)
def apply_height_visualization(
    lit_fg: np.ndarray,
    lit_bg: np.ndarray,
    drawn_mask: np.ndarray,
    map_height_vp: np.ndarray,
    player_height: int,
    config_show_vis: bool,
    config_max_diff: int,
    config_color_high: np.ndarray,
    config_color_mid: np.ndarray,
    config_color_low: np.ndarray,
    config_blend_factor: float32,
) -> tuple[np.ndarray, np.ndarray]:
    """Applies height visualization tinting."""
    if not config_show_vis:
        return lit_fg, lit_bg

    final_fg = lit_fg
    final_bg = lit_bg
    relative_height_vp = map_height_vp - player_height

    max_diff_f32 = np.float32(config_max_diff)
    blend = config_blend_factor

    drawn_and_valid_diff = drawn_mask & (max_diff_f32 > np.float32(0.0))

    high_mask = (
        drawn_and_valid_diff
        & (relative_height_vp > 0)
        & (relative_height_vp <= config_max_diff)
    )
    if np.any(high_mask):
        high_y_coords, high_x_coords = np.where(high_mask)
        target_color_high_f32 = config_color_high.astype(np.float32)

        for i in range(high_y_coords.shape[0]):
            y = high_y_coords[i]
            x = high_x_coords[i]
            t = np.float32(relative_height_vp[y, x]) / max_diff_f32
            blend_t = blend * t
            current_fg_f32 = final_fg[y, x].astype(np.float32)
            current_bg_f32 = final_bg[y, x].astype(np.float32)
            final_fg[y, x] = np.clip(
                current_fg_f32 * (np.float32(1.0) - blend_t)
                + target_color_high_f32 * blend_t,
                0,
                255,
            ).astype(np.uint8)
            final_bg[y, x] = np.clip(
                current_bg_f32 * (np.float32(1.0) - blend_t)
                + target_color_high_f32 * blend_t,
                0,
                255,
            ).astype(np.uint8)

    low_mask = (
        drawn_and_valid_diff
        & (relative_height_vp < 0)
        & (relative_height_vp >= -config_max_diff)
    )
    if np.any(low_mask):
        low_y_coords, low_x_coords = np.where(low_mask)
        target_color_low_f32 = config_color_low.astype(np.float32)
        for i in range(low_y_coords.shape[0]):
            y = low_y_coords[i]
            x = low_x_coords[i]
            t = np.float32(np.abs(relative_height_vp[y, x])) / max_diff_f32
            blend_t = blend * t
            current_fg_f32 = final_fg[y, x].astype(np.float32)
            current_bg_f32 = final_bg[y, x].astype(np.float32)
            final_fg[y, x] = np.clip(
                current_fg_f32 * (np.float32(1.0) - blend_t)
                + target_color_low_f32 * blend_t,
                0,
                255,
            ).astype(np.uint8)
            final_bg[y, x] = np.clip(
                current_bg_f32 * (np.float32(1.0) - blend_t)
                + target_color_low_f32 * blend_t,
                0,
                255,
            ).astype(np.uint8)

    return final_fg, final_bg


def apply_memory_fade(
    final_fg: np.ndarray,
    final_bg: np.ndarray,
    glyph_indices: np.ndarray,
    map_memory_vp: np.ndarray,
    map_tiles_vp: np.ndarray,
    drawn_mask: np.ndarray,
    visible_mask: np.ndarray,
    fade_color_np: np.ndarray,
    rng: GameRNG,
    fade_color_variance: float = 0.0,
    noise_level: float = 0.0,
    viewport_x: int = 0,
    viewport_y: int = 0,
) -> None:
    """Blend colors for tiles remembered in the fog without changing glyph indices.

    IMPORTANT: this function intentionally does NOT write Unicode ordinals into
    `glyph_indices`. Glyph indices must remain tile indices that index into
    the tileset (tile_arrays). Memory is expressed purely via color/brightness.
    """
    # memory_mask = cells that are drawn but not currently visible
    memory_mask = drawn_mask & (~visible_mask)
    if not np.any(memory_mask):
        return

    # Per-tile fade value (shape = N,)
    fade_vals = map_memory_vp[memory_mask].astype(np.float32)

    # For color blending we'll broadcast fade_vals -> (N,1)
    fade_vals_b = fade_vals[:, None]  # shape (N, 1)

    # Simple deterministic blend: final = base*(1 - fade) + fade_color*fade
    # We do this for both FG and BG. This is the clean tile-based approach:
    # tiles stay the same; colors/brightness change to indicate memory.
    try:
        # Gather base colors for the memory cells
        coords_y, coords_x = np.nonzero(memory_mask)
        base_fg = final_fg[coords_y, coords_x].astype(np.float32)
        base_bg = final_bg[coords_y, coords_x].astype(np.float32)
        target_color = np.asarray(fade_color_np, dtype=np.float32)[None, :]  # (1,3)

        blended_fg = base_fg * (1.0 - fade_vals_b) + target_color * fade_vals_b
        blended_bg = base_bg * (1.0 - fade_vals_b) + target_color * fade_vals_b

        # Optional: clamp and write back as uint8
        np.clip(blended_fg, 0, 255, out=blended_fg)
        np.clip(blended_bg, 0, 255, out=blended_bg)

        final_fg[coords_y, coords_x] = blended_fg.astype(np.uint8)
        final_bg[coords_y, coords_x] = blended_bg.astype(np.uint8)

    except Exception as exc:
        # Be conservative: if blending fails, leave colors alone but do not touch glyphs.
        log.error(
            "apply_memory_fade: color blending failed", error=str(exc), exc_info=True
        )
        return

    # NOTE: We deliberately do NOT touch `glyph_indices`. Tiles stay the same;
    # memory is represented by adjusted FG/BG colors (brightness/tint).
    # If you later want tile-based memory variants (e.g., darker tile images),
    # implement a mapping from tile_id -> memory_tile_id and write those tile
    # indices here instead of Unicode ordinals.
