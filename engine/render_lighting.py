"""Lighting and visual effect helpers for rendering."""

import math
from collections.abc import Iterable
from typing import Any

import numpy as np
import structlog

from common.tuning import MEMORY_LEVEL_COUNT

try:
    from numba import float32, njit, uint8

    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

    def njit(*args, **options):  # type: ignore
        """No-op jit; returns the decorated function unchanged."""
        for a in args:
            if callable(a):
                return a
        return lambda f: f

    def float32(*args):  # type: ignore
        """Fallback float32: casts a single value; multi-arg calls are numba
        type-signature expressions (e.g. ``float32(float32, …)`` in ``@njit``
        decorators) and intentionally return ``None`` so the surrounding
        ``njit(None, …)`` call still yields a pass-through decorator."""
        if len(args) == 1:
            return np.float32(args[0])
        return None  # numba signature sentinel — see njit fallback above

    def uint8(*args):  # type: ignore
        """Fallback uint8: same convention as float32 above."""
        if len(args) == 1:
            return np.uint8(args[0])
        return None  # numba signature sentinel — see njit fallback above


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
    from game.world.fov import compute_light_color_array, compute_visibility
except ImportError:
    compute_light_color_array = None  # type: ignore

    def _fov_euclidean(oy: int, ox: int, y: int, x: int) -> float:
        return math.sqrt((y - oy) ** 2 + (x - ox) ** 2)

    def compute_visibility(  # type: ignore[misc]  # conditional redefinition
        height: int,
        width: int,
        *,
        origin_y: int,
        origin_x: int,
        radius: int,
        is_opaque: Any,
        distance: Any = None,
    ) -> set[tuple[int, int]]:
        """Pure-Python shadowcasting FOV fallback (used when numba is absent)."""
        dist_fn = distance if distance is not None else _fov_euclidean
        visible: set[tuple[int, int]] = set()

        def blocks(cy: int, cx: int) -> bool:
            return not (0 <= cy < height and 0 <= cx < width) or is_opaque(cy, cx)

        def mark(cy: int, cx: int) -> None:
            if 0 <= cy < height and 0 <= cx < width:
                visible.add((cy, cx))

        def cast(  # noqa: PLR0912 — recursive shadowcasting octant sweep
            row: int,
            start: float,
            end: float,
            xx: int,
            xy: int,
            yx: int,
            yy: int,
        ) -> None:
            """Sweep one octant row by row, pruning by slope boundaries.

            ``start``/``end`` define the visible slope window.  Opaque cells
            split the window (recursive call) or terminate the current sweep
            (``blocked`` flag).  Octant transform ``(xx,xy,yx,yy)`` maps the
            canonical (+x,+y) octant to each of the 8 real-space octants.
            """
            if start < end:
                return
            nstart = start
            for d in range(row, radius + 1):
                dx, dy = -d, -d
                blocked = False
                while dx <= 0:
                    dx += 1
                    cx = origin_x + dx * xx + dy * xy
                    cy = origin_y + dx * yx + dy * yy
                    ls = (dx - 0.5) / (dy + 0.5)
                    rs = (dx + 0.5) / (dy - 0.5)
                    if start < rs:
                        continue
                    if end > ls:
                        break
                    if dist_fn(origin_y, origin_x, cy, cx) <= radius:
                        mark(cy, cx)
                    cell_blocks = blocks(cy, cx)
                    if blocked:
                        if cell_blocks:
                            nstart = rs
                            continue
                        blocked = False
                        start = nstart
                    elif cell_blocks and d < radius:
                        blocked = True
                        cast(d + 1, start, ls, xx, xy, yx, yy)
                        nstart = rs
                if blocked:
                    break

        mark(origin_y, origin_x)
        for xx, xy, yx, yy in (
            (1, 0, 0, 1),
            (0, 1, 1, 0),
            (0, -1, 1, 0),
            (-1, 0, 0, 1),
            (-1, 0, 0, -1),
            (0, -1, -1, 0),
            (0, 1, -1, 0),
            (1, 0, 0, -1),
        ):
            cast(1, 1.0, 0.0, xx, xy, yx, yy)
        return visible

    structlog.get_logger().warning(
        "numba not available: using pure-Python FOV fallback in render_lighting."
    )

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Phase 4: RGB blend policy abstraction
# ---------------------------------------------------------------------------


class RGBBlendPolicy:
    """Deterministic, additive RGB light blending with channel clamping.

    Provides a stable policy for accumulating per-light color contributions
    into a scene buffer.  The default strategy is additive accumulation,
    where each light's contribution is added to the buffer and the result
    is clamped to ``[0, 255]`` only on final composite.  This matches the
    behavior of the pre-existing ``apply_light_sources`` function so that
    existing renderer output is unchanged.

    Subclass or replace to experiment with premultiplied RGBA or other
    policies without touching the cache or renderer.
    """

    def accumulate(
        self,
        target: np.ndarray,
        contribution: np.ndarray,
    ) -> None:
        """Add *contribution* (h × w × 3, float32) into *target* in-place."""
        target += contribution

    def subtract(
        self,
        target: np.ndarray,
        contribution: np.ndarray,
    ) -> None:
        """Subtract *contribution* (h × w × 3, float32) from *target* in-place."""
        target -= contribution

    def composite(self, accumulated: np.ndarray) -> np.ndarray:
        """Return the final float32 buffer clamped to ``[0, 255]``."""
        return np.clip(accumulated, 0.0, 255.0)


# Singleton default policy instance
DEFAULT_BLEND_POLICY: RGBBlendPolicy = RGBBlendPolicy()


# ---------------------------------------------------------------------------
# Phase 3: Per-light contribution cache
# ---------------------------------------------------------------------------


def _compute_single_light_contribution(
    *,
    origin_x: int,
    origin_y: int,
    radius: int,
    color_rgb: tuple[int, int, int],
    intensity: float,
    opaque_grid: np.ndarray,
    scene_h: int,
    scene_w: int,
    height_map: np.ndarray | None = None,
    ceiling_map: np.ndarray | None = None,
) -> np.ndarray:
    """Compute one light's RGB contribution array.

    The production path delegates to ``compute_light_color_array`` so cached
    colored lighting and legacy callers share one single-light implementation.
    A pure visibility fallback remains available only for environments where the
    accelerated FOV helper cannot be imported.
    """
    contribution: np.ndarray = np.zeros((scene_h, scene_w, 3), dtype=np.float32)
    if radius <= 0:
        return contribution

    scaled_color: tuple[int, int, int] = (
        int(color_rgb[0] * float(intensity)),
        int(color_rgb[1] * float(intensity)),
        int(color_rgb[2] * float(intensity)),
    )
    has_geometry: bool = height_map is not None and ceiling_map is not None
    if compute_light_color_array is not None and has_geometry:
        origin_h: int = int(height_map[origin_y, origin_x])
        compute_light_color_array(
            origin_xy=(origin_x, origin_y),
            range_limit=radius,
            opaque_grid=opaque_grid,
            height_map=height_map,
            ceiling_map=ceiling_map,
            origin_height=origin_h,
            target_rgb_array=contribution,
            base_color_rgb=scaled_color,
        )
        return contribution

    if compute_visibility is None:
        return contribution

    def _is_opaque(y: int, x: int) -> bool:
        return bool(opaque_grid[y, x])

    visible = compute_visibility(
        scene_h,
        scene_w,
        origin_y=origin_y,
        origin_x=origin_x,
        radius=radius,
        is_opaque=_is_opaque,
    )
    radius_sq = float(radius * radius)
    color = np.array(scaled_color, dtype=np.float32)
    for cy, cx in visible:
        dist_sq = (cx - origin_x) ** 2 + (cy - origin_y) ** 2
        if dist_sq > radius_sq:
            continue
        fade = 1.0 - dist_sq / radius_sq
        contribution[cy, cx, :] += color * fade
    return contribution


class LightContributionCache:
    """Per-light RGB contribution cache for the production lighting renderer.

    Maintains a separate ``(h × w × 3)`` float32 buffer for each light and
    a combined scene buffer.  The cache receives current lights, opacity, scene
    geometry, an optional viewport, and a scene geometry version, then returns
    the canonical blended RGB contribution for that view.
    """

    def __init__(
        self,
        scene_h: int,
        scene_w: int,
        blend_policy: RGBBlendPolicy | None = None,
    ) -> None:
        self._h: int = scene_h
        self._w: int = scene_w
        self._policy: RGBBlendPolicy = blend_policy or DEFAULT_BLEND_POLICY
        self._last_scene_seq: int | None = None
        self._combined: np.ndarray = np.zeros((scene_h, scene_w, 3), dtype=np.float32)
        self._contributions: dict[int, np.ndarray] = {}
        self._param_keys: dict[int, tuple[Any, ...]] = {}

    @staticmethod
    def _light_id(light: Any, fallback_index: int) -> int:
        """Return a stable cache key for light objects without requiring IDs."""
        raw_id = getattr(light, "id", fallback_index)
        if isinstance(raw_id, int):
            return raw_id
        return fallback_index

    @staticmethod
    def _param_key(light: Any) -> tuple[Any, ...]:
        """Build a hashable key from a light's rendering parameters."""
        color = getattr(light, "color", None)
        if color is not None:
            color = tuple(color)
        return (
            getattr(light, "x", None),
            getattr(light, "y", None),
            getattr(light, "radius", None),
            color,
            getattr(light, "intensity", 1.0),
        )

    def _compute_light(
        self,
        light: Any,
        opaque_grid: np.ndarray,
        height_map: np.ndarray | None,
        ceiling_map: np.ndarray | None,
    ) -> np.ndarray:
        """Compute a full-scene contribution buffer for one light."""
        return _compute_single_light_contribution(
            origin_x=int(light.x),
            origin_y=int(light.y),
            radius=int(light.radius),
            color_rgb=tuple(light.color),
            intensity=float(getattr(light, "intensity", 1.0)),
            opaque_grid=opaque_grid,
            scene_h=self._h,
            scene_w=self._w,
            height_map=height_map,
            ceiling_map=ceiling_map,
        )

    def _invalidate_all(
        self,
        lights: list[Any],
        opaque_grid: np.ndarray,
        height_map: np.ndarray | None,
        ceiling_map: np.ndarray | None,
    ) -> None:
        """Rebuild every light's contribution from scratch."""
        self._combined[:] = 0.0
        self._contributions.clear()
        self._param_keys.clear()
        for index, light in enumerate(lights):
            if not self._light_in_scene(light):
                continue
            lid = self._light_id(light, index)
            key = self._param_key(light)
            buf = self._compute_light(light, opaque_grid, height_map, ceiling_map)
            self._contributions[lid] = buf
            self._param_keys[lid] = key
            self._policy.accumulate(self._combined, buf)

    def _light_in_scene(self, light: Any) -> bool:
        """Return whether a light origin is inside this cache's scene."""
        x = getattr(light, "x", None)
        y = getattr(light, "y", None)
        return (
            isinstance(x, int)
            and isinstance(y, int)
            and 0 <= x < self._w
            and 0 <= y < self._h
        )

    def _viewport_slice(
        self,
        viewport_x: int,
        viewport_y: int,
        vp_h: int,
        vp_w: int,
    ) -> tuple[slice, slice]:
        """Return safe scene slices for a viewport rectangle."""
        y_start = max(0, viewport_y)
        x_start = max(0, viewport_x)
        y_end = min(self._h, viewport_y + vp_h)
        x_end = min(self._w, viewport_x + vp_w)
        return slice(y_start, y_end), slice(x_start, x_end)

    def update(
        self,
        lights: Iterable[Any],
        opaque_grid: np.ndarray,
        scene_seq: int | None = None,
        *,
        viewport_x: int = 0,
        viewport_y: int = 0,
        vp_h: int | None = None,
        vp_w: int | None = None,
        height_map: np.ndarray | None = None,
        ceiling_map: np.ndarray | None = None,
    ) -> np.ndarray:
        """Incrementally update and return a blended RGB contribution buffer.

        The returned array is clamped through ``RGBBlendPolicy.composite``.  If
        viewport dimensions are supplied, only that viewport contribution is
        returned; otherwise the full scene contribution is returned.
        """
        lights_list = list(lights)
        if scene_seq is not None and scene_seq != self._last_scene_seq:
            self._last_scene_seq = scene_seq
            self._invalidate_all(lights_list, opaque_grid, height_map, ceiling_map)
        else:
            incoming_ids = {
                self._light_id(light, index)
                for index, light in enumerate(lights_list)
                if self._light_in_scene(light)
            }
            cached_ids = set(self._contributions.keys())

            for lid in cached_ids - incoming_ids:
                old_buf = self._contributions.pop(lid)
                self._policy.subtract(self._combined, old_buf)
                self._param_keys.pop(lid, None)

            for index, light in enumerate(lights_list):
                if not self._light_in_scene(light):
                    continue
                lid = self._light_id(light, index)
                new_key = self._param_key(light)
                if lid in self._contributions:
                    if self._param_keys.get(lid) == new_key:
                        continue
                    old_buf = self._contributions[lid]
                    self._policy.subtract(self._combined, old_buf)
                buf = self._compute_light(light, opaque_grid, height_map, ceiling_map)
                self._contributions[lid] = buf
                self._param_keys[lid] = new_key
                self._policy.accumulate(self._combined, buf)

        composite = self._policy.composite(self._combined)
        if vp_h is None or vp_w is None:
            return composite.copy()

        y_slice, x_slice = self._viewport_slice(viewport_x, viewport_y, vp_h, vp_w)
        viewport_rgb = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
        dest_y = max(0, -viewport_y)
        dest_x = max(0, -viewport_x)
        src = composite[y_slice, x_slice, :]
        y_size = src.shape[0]
        x_size = src.shape[1]
        if y_size > 0 and x_size > 0:
            viewport_rgb[dest_y : dest_y + y_size, dest_x : dest_x + x_size, :] = src
        return viewport_rgb

    def invalidate(self) -> None:
        """Force a full rebuild on the next :meth:`update` call."""
        self._last_scene_seq = None
        self._combined[:] = 0.0
        self._contributions.clear()
        self._param_keys.clear()


class LightingRenderer:
    """Renderer-facing owner for cached colored light contributions."""

    def __init__(self, blend_policy: RGBBlendPolicy | None = None) -> None:
        self._policy: RGBBlendPolicy = blend_policy or DEFAULT_BLEND_POLICY
        self._cache: LightContributionCache | None = None
        self._cache_shape: tuple[int, int] | None = None

    def _get_cache(self, scene_h: int, scene_w: int) -> LightContributionCache:
        shape = (scene_h, scene_w)
        if self._cache is None or self._cache_shape != shape:
            self._cache = LightContributionCache(scene_h, scene_w, self._policy)
            self._cache_shape = shape
        return self._cache

    def apply_colored_lighting(
        self,
        lit_fg: np.ndarray,
        lit_bg: np.ndarray,
        light_sources: Iterable[Any],
        game_map: GameMap,
        *,
        viewport_x: int,
        viewport_y: int,
        vp_h: int,
        vp_w: int,
        scene_seq: int | None,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply cached colored lights to lit buffers within a viewport."""
        if not light_sources:
            empty = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
            return lit_fg, lit_bg, empty

        if not isinstance(game_map, GameMap) or GameMap is object:
            log.warning("Invalid GameMap supplied; skipping colored lights")
            empty = np.zeros((vp_h, vp_w, 3), dtype=np.float32)
            return lit_fg, lit_bg, empty

        opaque_grid = ~game_map.transparent
        cache = self._get_cache(game_map.height, game_map.width)
        light_rgb_vp = cache.update(
            light_sources,
            opaque_grid,
            scene_seq,
            viewport_x=viewport_x,
            viewport_y=viewport_y,
            vp_h=vp_h,
            vp_w=vp_w,
            height_map=game_map.height_map,
            ceiling_map=game_map.ceiling_map,
        )
        fg_f32 = lit_fg.astype(np.float32)
        bg_f32 = lit_bg.astype(np.float32)
        self._policy.accumulate(fg_f32, light_rgb_vp)
        self._policy.accumulate(bg_f32, light_rgb_vp)
        final_fg = self._policy.composite(fg_f32).astype(np.uint8)
        final_bg = self._policy.composite(bg_f32).astype(np.uint8)
        lit_fg[:] = final_fg
        lit_bg[:] = final_bg
        return lit_fg, lit_bg, light_rgb_vp

    def invalidate(self) -> None:
        """Invalidate cached colored-light contributions."""
        if self._cache is not None:
            self._cache.invalidate()


def apply_colored_lighting(
    lit_fg: np.ndarray,
    lit_bg: np.ndarray,
    light_sources: Iterable[Any],
    game_map: GameMap,
    *,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    scene_seq: int | None,
    lighting_renderer: LightingRenderer,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Renderer-facing cached colored-light entrypoint."""
    return lighting_renderer.apply_colored_lighting(
        lit_fg,
        lit_bg,
        light_sources,
        game_map,
        viewport_x=viewport_x,
        viewport_y=viewport_y,
        vp_h=vp_h,
        vp_w=vp_w,
        scene_seq=scene_seq,
    )


_LEGACY_LIGHTING_RENDERER: LightingRenderer = LightingRenderer()


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

# Validate that glyph arrays match the centralized MEMORY_LEVEL_COUNT
assert MEMORY_WALL_GLYPHS.size == MEMORY_LEVEL_COUNT, (
    f"MEMORY_WALL_GLYPHS size ({MEMORY_WALL_GLYPHS.size}) "
    f"does not match MEMORY_LEVEL_COUNT ({MEMORY_LEVEL_COUNT})"
)
assert MEMORY_FLOOR_GLYPHS.size == MEMORY_LEVEL_COUNT, (
    f"MEMORY_FLOOR_GLYPHS size ({MEMORY_FLOOR_GLYPHS.size}) "
    f"does not match MEMORY_LEVEL_COUNT ({MEMORY_LEVEL_COUNT})"
)


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
    light_sources: Iterable[Any],
    game_map: GameMap,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Backward-compatible wrapper around the cached colored-light path."""
    scene_seq: int | None = getattr(game_map, "scene_geometry_version", None)
    return apply_colored_lighting(
        lit_fg,
        lit_bg,
        light_sources,
        game_map,
        viewport_x=viewport_x,
        viewport_y=viewport_y,
        vp_h=vp_h,
        vp_w=vp_w,
        scene_seq=scene_seq,
        lighting_renderer=_LEGACY_LIGHTING_RENDERER,
    )


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
    fade_vals = 1.0 - map_memory_vp[memory_mask].astype(np.float32)

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
