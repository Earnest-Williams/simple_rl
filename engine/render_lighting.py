"""Lighting and visual effect helpers for rendering."""

import math
from collections.abc import Iterable
from typing import Any, TypeAlias

import numpy as np
import structlog
from numba import float32, njit, uint8

from common.tuning import MEMORY_LEVEL_COUNT
from game.world.fov import (
    _THRESHOLD_AT_CUTOFF,
    CLOSE_RANGE_DIVISOR,
    CLOSE_RANGE_SQ_THRESHOLD,
    FAR_RANGE_DIVISOR,
)
from game.world.game_map import GameMap
from game.world.light_fov import compute_fov_all_octants
from utils.game_rng import GameRNG

# Light sources are duck-typed objects from production and tests; they expose
# x/y/radius/color/intensity attributes but do not share a common base class.
LightSourceLike: TypeAlias = Any

_NUMBA_AVAILABLE = True

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
    renderer's historical additive colored-light output.

    Subclass or replace to experiment with premultiplied RGBA or other
    policies without touching the cache or renderer.
    """

    def accumulate(
        self,
        target: np.ndarray,
        contribution: np.ndarray,
    ) -> None:
        """Add *contribution* into *target* in-place."""
        target += contribution

    def subtract(
        self,
        target: np.ndarray,
        contribution: np.ndarray,
    ) -> None:
        """Subtract *contribution* from *target* in-place."""
        target -= contribution

    def composite(self, accumulated: np.ndarray) -> np.ndarray:
        """Return the final float32 buffer clamped to ``[0, 255]``.

        Under Option B, if accumulated buffer is (h, w, 8, 4), collapses it
        to (h, w, 3) using premultiplied alpha rules before clamping.
        """
        return collapse_premult_rgba_to_rgb(accumulated)


def collapse_premult_rgba_to_rgb(buf: np.ndarray) -> np.ndarray:
    """Collapse a (h, w, 8, 4) side-aware premultiplied RGBA buffer to (h, w, 3) RGB."""
    if buf.ndim == 4:
        total_rgba = np.sum(buf, axis=2)  # shape (h, w, 4)
        light_rgb = total_rgba[:, :, 0:3].copy()
        light_a = total_rgba[:, :, 3].copy()

        oversaturated = light_a > 255.0
        if np.any(oversaturated):
            scale = 255.0 / light_a[oversaturated]
            light_rgb[oversaturated] *= scale[:, None]

        np.clip(light_rgb, 0.0, 255.0, out=light_rgb)
        return light_rgb
    else:
        return np.clip(buf, 0.0, 255.0)


# Singleton default policy instance
DEFAULT_BLEND_POLICY: RGBBlendPolicy = RGBBlendPolicy()


# ---------------------------------------------------------------------------
# Phase 3: Per-light contribution cache
# ---------------------------------------------------------------------------


def _height_threshold_for_distance(dist_sq: int) -> int:
    """Return the FOV height-difference threshold for a squared distance."""
    if dist_sq <= CLOSE_RANGE_SQ_THRESHOLD:
        return dist_sq // CLOSE_RANGE_DIVISOR
    return (
        _THRESHOLD_AT_CUTOFF + (dist_sq - CLOSE_RANGE_SQ_THRESHOLD) // FAR_RANGE_DIVISOR
    )


@njit(nogil=True, cache=True)
def _precompute_geometry_blockers(
    opaque_grid: np.ndarray,
    height_map: np.ndarray,
    ceiling_map: np.ndarray,
    origin_x: int,
    origin_y: int,
    origin_height: int,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = opaque_grid.shape
    opaque_out = opaque_grid.astype(np.uint8)
    transparency_out = np.ones((h, w), dtype=np.float32)
    # Default transparency of opaque grid is 0.0
    for y in range(h):
        for x in range(w):
            if opaque_out[y, x] != 0:
                transparency_out[y, x] = 0.0
                continue

            # Ceiling checks
            target_ceiling = int(ceiling_map[y, x])
            if target_ceiling <= origin_height:
                opaque_out[y, x] = 1
                transparency_out[y, x] = 0.0
                continue

            # Height checks
            target_height = int(height_map[y, x])
            dx = x - origin_x
            dy = y - origin_y
            dist_sq = dx * dx + dy * dy

            # _height_threshold_for_distance inlined:
            threshold = dist_sq // 8 if dist_sq <= 16 else 2 + (dist_sq - 16) // 16

            if abs(target_height - origin_height) > threshold:
                opaque_out[y, x] = 1
                transparency_out[y, x] = 0.0

    return opaque_out, transparency_out


@njit(nogil=True, cache=True)
def _accumulate_light_premult_rgba(
    visible: np.ndarray,
    dist: np.ndarray,
    side_bits: np.ndarray,
    visibility: np.ndarray,
    out_side_rgba: np.ndarray,
    light_intensity: float,
    light_r: float,
    light_g: float,
    light_b: float,
    is_directional: int,
    dir_x: float,
    dir_y: float,
    use_soft: int,
    cos_outer: float,
    cos_inner: float,
    light_src_x: float,
    light_src_y: float,
    light_height: float,
) -> None:
    h, w = visible.shape
    core_radius_sq = 4.0  # matching R&D

    for y in range(h):
        for x in range(w):
            if visible[y, x] == 0:
                continue

            sb = side_bits[y, x]
            if sb == 0:
                continue

            d = dist[y, x]

            dx = float((x + 0.5) - light_src_x)
            dy = float((y + 0.5) - light_src_y)
            len2d_sq = dx * dx + dy * dy

            if len2d_sq <= core_radius_sq or d <= 0:
                atten = light_intensity
                inv_len2d = 1.0
            else:
                len2d = math.sqrt(len2d_sq)
                if len2d <= 1e-9:
                    atten = light_intensity
                    inv_len2d = 1.0
                else:
                    inv_len2d = 1.0 / len2d
                    atten = light_intensity * inv_len2d

            t = float(visibility[y, x])
            atten *= t
            if atten <= 0.0:
                continue

            dz = float(light_height)
            if dz > 0.0:
                len3 = math.sqrt(dx * dx + dy * dy + dz * dz)
                if len3 <= 1e-9:
                    incidence = 1.0
                else:
                    incidence = dz / len3
                    if incidence < 0.0:
                        incidence = 0.0
                atten *= incidence
                if atten <= 0.0:
                    continue

            if is_directional != 0:
                if d <= 0:
                    dir_weight = 1.0
                else:
                    if len2d_sq <= core_radius_sq:
                        len2d = math.sqrt(len2d_sq)
                        if len2d <= 1e-9:
                            ndx = 0.0
                            ndy = 0.0
                        else:
                            ndx = dx / len2d
                            ndy = dy / len2d
                    else:
                        ndx = dx * inv_len2d
                        ndy = dy * inv_len2d

                    dot = ndx * dir_x + ndy * dir_y

                    if use_soft == 0:
                        dir_weight = 1.0 if dot >= cos_outer else 0.0
                    else:
                        if dot >= cos_inner:
                            dir_weight = 1.0
                        elif dot <= cos_outer:
                            dir_weight = 0.0
                        else:
                            denom = cos_inner - cos_outer
                            if denom <= 1e-9:
                                dir_weight = 1.0 if dot >= cos_inner else 0.0
                            else:
                                dir_weight = (dot - cos_outer) / denom

                if dir_weight <= 0.0:
                    continue
                atten *= dir_weight
                if atten <= 0.0:
                    continue

            r_ratio = atten
            rgb_add_r = light_r * r_ratio
            rgb_add_g = light_g * r_ratio
            rgb_add_b = light_b * r_ratio
            a_add = r_ratio * 255.0

            if sb & 1:
                out_side_rgba[y, x, 0, 0] += rgb_add_r
                out_side_rgba[y, x, 0, 1] += rgb_add_g
                out_side_rgba[y, x, 0, 2] += rgb_add_b
                out_side_rgba[y, x, 0, 3] += a_add
            if sb & 2:
                out_side_rgba[y, x, 1, 0] += rgb_add_r
                out_side_rgba[y, x, 1, 1] += rgb_add_g
                out_side_rgba[y, x, 1, 2] += rgb_add_b
                out_side_rgba[y, x, 1, 3] += a_add
            if sb & 4:
                out_side_rgba[y, x, 2, 0] += rgb_add_r
                out_side_rgba[y, x, 2, 1] += rgb_add_g
                out_side_rgba[y, x, 2, 2] += rgb_add_b
                out_side_rgba[y, x, 2, 3] += a_add
            if sb & 8:
                out_side_rgba[y, x, 3, 0] += rgb_add_r
                out_side_rgba[y, x, 3, 1] += rgb_add_g
                out_side_rgba[y, x, 3, 2] += rgb_add_b
                out_side_rgba[y, x, 3, 3] += a_add
            if sb & 16:
                out_side_rgba[y, x, 4, 0] += rgb_add_r
                out_side_rgba[y, x, 4, 1] += rgb_add_g
                out_side_rgba[y, x, 4, 2] += rgb_add_b
                out_side_rgba[y, x, 4, 3] += a_add
            if sb & 32:
                out_side_rgba[y, x, 5, 0] += rgb_add_r
                out_side_rgba[y, x, 5, 1] += rgb_add_g
                out_side_rgba[y, x, 5, 2] += rgb_add_b
                out_side_rgba[y, x, 5, 3] += a_add
            if sb & 64:
                out_side_rgba[y, x, 6, 0] += rgb_add_r
                out_side_rgba[y, x, 6, 1] += rgb_add_g
                out_side_rgba[y, x, 6, 2] += rgb_add_b
                out_side_rgba[y, x, 6, 3] += a_add
            if sb & 128:
                out_side_rgba[y, x, 7, 0] += rgb_add_r
                out_side_rgba[y, x, 7, 1] += rgb_add_g
                out_side_rgba[y, x, 7, 2] += rgb_add_b
                out_side_rgba[y, x, 7, 3] += a_add


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
    direction: float | None = None,
    cone_angle: float = math.tau,
    cone_softness: float = 0.0,
    channels: int = 0xFFFFFFFF,
    height: float = 0.0,
    cell_mask: np.ndarray | None = None,
) -> np.ndarray:
    """Compute one light's side-aware premultiplied RGBA contribution array."""
    contribution = np.zeros((scene_h, scene_w, 8, 4), dtype=np.float32)
    if radius <= 0:
        return contribution

    # Precompute geometry blocking relative to this light's origin
    if height_map is not None and ceiling_map is not None:
        origin_height = int(height_map[origin_y, origin_x])
        opaque_u8, transparency_f32 = _precompute_geometry_blockers(
            opaque_grid, height_map, ceiling_map, origin_x, origin_y, origin_height
        )
    else:
        opaque_u8 = opaque_grid.astype(np.uint8)
        transparency_f32 = (1.0 - opaque_grid).astype(np.float32)

    # Allocate outputs
    visible_out = np.zeros((scene_h, scene_w), dtype=np.uint8)
    dist_out = -np.ones((scene_h, scene_w), dtype=np.int32)
    side_bits_out = np.zeros((scene_h, scene_w), dtype=np.uint8)
    visibility_out = np.zeros((scene_h, scene_w), dtype=np.float32)

    use_cell_mask = cell_mask is not None
    if use_cell_mask:
        cell_mask_u32 = cell_mask.astype(np.uint32)

    # Angles
    if direction is not None:
        half_cone = 0.5 * cone_angle
        start_angle = direction - half_cone
        end_angle = direction + half_cone
    else:
        start_angle = None
        end_angle = None

    # Call JIT shadowcasting FOV
    if use_cell_mask:
        if start_angle is not None and end_angle is not None:
            compute_fov_all_octants(
                opaque_u8,
                transparency_f32,
                cell_mask_u32,
                channels,
                visible_out,
                dist_out,
                side_bits_out,
                visibility_out,
                origin_x,
                origin_y,
                radius,
                start_angle,
                end_angle,
            )
        else:
            compute_fov_all_octants(
                opaque_u8,
                transparency_f32,
                cell_mask_u32,
                channels,
                visible_out,
                dist_out,
                side_bits_out,
                visibility_out,
                origin_x,
                origin_y,
                radius,
            )
    else:
        if start_angle is not None and end_angle is not None:
            compute_fov_all_octants(
                opaque_u8,
                transparency_f32,
                visible_out,
                dist_out,
                side_bits_out,
                visibility_out,
                origin_x,
                origin_y,
                radius,
                start_angle,
                end_angle,
            )
        else:
            compute_fov_all_octants(
                opaque_u8,
                transparency_f32,
                visible_out,
                dist_out,
                side_bits_out,
                visibility_out,
                origin_x,
                origin_y,
                radius,
            )

    # Directional math setup for JIT accumulator
    is_directional = 0
    dir_x = 0.0
    dir_y = 0.0
    use_soft = 0
    cos_outer = 0.0
    cos_inner = 0.0

    if direction is not None:
        is_directional = 1
        dir_x = math.cos(direction)
        dir_y = math.sin(direction)
        half_cone = 0.5 * cone_angle
        cos_outer = math.cos(half_cone)
        if cone_softness > 0.0:
            use_soft = 1
            inner_angle = half_cone * (1.0 - cone_softness)
            cos_inner = math.cos(inner_angle)
        else:
            cos_inner = cos_outer

    _accumulate_light_premult_rgba(
        visible_out,
        dist_out,
        side_bits_out,
        visibility_out,
        contribution,
        float(intensity),
        float(color_rgb[0]),
        float(color_rgb[1]),
        float(color_rgb[2]),
        is_directional,
        dir_x,
        dir_y,
        use_soft,
        cos_outer,
        cos_inner,
        float(origin_x),
        float(origin_y),
        float(height),
    )

    return contribution


class LightContributionCache:
    """Per-light side-aware contribution cache for the production lighting renderer.

    Maintains a separate ``(h × w × 8 × 4)`` float32 buffer for each light and
    a combined scene buffer.
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
        self._combined: np.ndarray = np.zeros(
            (scene_h, scene_w, 8, 4), dtype=np.float32
        )
        self._contributions: dict[int, np.ndarray] = {}
        self._param_keys: dict[int, tuple[object, ...]] = {}

    @staticmethod
    def _light_id(light: LightSourceLike, fallback_index: int) -> int:
        """Return a stable cache key for light objects without requiring IDs."""
        raw_id = getattr(light, "id", fallback_index)
        if isinstance(raw_id, int):
            return raw_id
        return fallback_index

    @staticmethod
    def _param_key(light: LightSourceLike) -> tuple[object, ...]:
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
            getattr(light, "direction", None),
            getattr(light, "cone_angle", math.tau),
            getattr(light, "cone_softness", 0.0),
            getattr(light, "channels", 0xFFFFFFFF),
            getattr(light, "height", 0.0),
        )

    def _compute_light(
        self,
        light: LightSourceLike,
        opaque_grid: np.ndarray,
        height_map: np.ndarray | None,
        ceiling_map: np.ndarray | None,
        cell_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Compute a full-scene contribution buffer for one light."""
        intensity = float(getattr(light, "intensity", 1.0))
        direction = getattr(light, "direction", None)
        cone_angle = float(getattr(light, "cone_angle", math.tau))
        cone_softness = float(getattr(light, "cone_softness", 0.0))
        channels = int(getattr(light, "channels", 0xFFFFFFFF))
        height = float(getattr(light, "height", 0.0))

        return _compute_single_light_contribution(
            origin_x=int(light.x),
            origin_y=int(light.y),
            radius=int(light.radius),
            color_rgb=tuple(light.color),
            intensity=intensity,
            opaque_grid=opaque_grid,
            scene_h=self._h,
            scene_w=self._w,
            height_map=height_map,
            ceiling_map=ceiling_map,
            direction=direction,
            cone_angle=cone_angle,
            cone_softness=cone_softness,
            channels=channels,
            height=height,
            cell_mask=cell_mask,
        )

    def _invalidate_all(
        self,
        lights: list[LightSourceLike],
        opaque_grid: np.ndarray,
        height_map: np.ndarray | None,
        ceiling_map: np.ndarray | None,
        cell_mask: np.ndarray | None = None,
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
            buf = self._compute_light(
                light, opaque_grid, height_map, ceiling_map, cell_mask
            )
            self._contributions[lid] = buf
            self._param_keys[lid] = key
            self._policy.accumulate(self._combined, buf)

    def _light_in_scene(self, light: LightSourceLike) -> bool:
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
        lights: Iterable[LightSourceLike],
        opaque_grid: np.ndarray,
        scene_seq: int | None = None,
        *,
        viewport_x: int = 0,
        viewport_y: int = 0,
        vp_h: int | None = None,
        vp_w: int | None = None,
        height_map: np.ndarray | None = None,
        ceiling_map: np.ndarray | None = None,
        cell_mask: np.ndarray | None = None,
    ) -> np.ndarray:
        """Incrementally update and return a blended RGB contribution buffer.

        The returned array is clamped through ``RGBBlendPolicy.composite``.  If
        viewport dimensions are supplied, only that viewport contribution is
        returned; otherwise the full scene contribution is returned.
        """
        lights_list = list(lights)
        if scene_seq is not None and scene_seq != self._last_scene_seq:
            self._last_scene_seq = scene_seq
            self._invalidate_all(
                lights_list, opaque_grid, height_map, ceiling_map, cell_mask
            )
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
                buf = self._compute_light(
                    light, opaque_grid, height_map, ceiling_map, cell_mask
                )
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
        light_sources: Iterable[LightSourceLike],
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

    def apply_render_lighting(
        self,
        *,
        base_fg: np.ndarray,
        base_bg: np.ndarray,
        glyph_indices: np.ndarray,
        drawn_mask: np.ndarray,
        visible_mask: np.ndarray,
        map_height_vp: np.ndarray,
        map_memory_vp: np.ndarray,
        map_tiles_vp: np.ndarray,
        light_sources: Iterable[LightSourceLike],
        game_map: GameMap,
        viewport_x: int,
        viewport_y: int,
        vp_h: int,
        vp_w: int,
        player_x: int,
        player_y: int,
        player_height: int,
        show_height_vis: bool,
        vis_max_diff: int,
        vis_color_high_np: np.ndarray,
        vis_color_mid_np: np.ndarray,
        vis_color_low_np: np.ndarray,
        vis_blend_factor: np.float32,
        lighting_ambient: np.float32,
        lighting_min_fov: np.float32,
        lighting_falloff: np.float32,
        fov_radius_sq: np.float32,
        enable_colored_lights: bool,
        enable_memory_fade: bool,
        memory_fade_color_np: np.ndarray,
        rng: GameRNG,
        memory_fade_variance: float,
        memory_noise_level: float,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Apply viewport lighting and presentation effects in render order."""
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
            lighting_ambient,
            lighting_min_fov,
            lighting_falloff,
            fov_radius_sq,
        )

        final_fg, final_bg = apply_height_visualization(
            lit_fg,
            lit_bg,
            drawn_mask,
            map_height_vp,
            player_height,
            show_height_vis,
            vis_max_diff,
            vis_color_high_np,
            vis_color_mid_np,
            vis_color_low_np,
            vis_blend_factor,
        )

        if enable_colored_lights and light_sources:
            scene_seq: int | None = getattr(game_map, "scene_geometry_version", None)
            final_fg, final_bg, _ = self.apply_colored_lighting(
                final_fg,
                final_bg,
                light_sources,
                game_map,
                viewport_x=viewport_x,
                viewport_y=viewport_y,
                vp_h=vp_h,
                vp_w=vp_w,
                scene_seq=scene_seq,
            )

        if enable_memory_fade:
            apply_memory_fade(
                final_fg,
                final_bg,
                glyph_indices,
                map_memory_vp,
                map_tiles_vp,
                drawn_mask,
                visible_mask,
                memory_fade_color_np,
                rng=rng,
                fade_color_variance=memory_fade_variance,
                noise_level=memory_noise_level,
                viewport_x=viewport_x,
                viewport_y=viewport_y,
            )

        return final_fg, final_bg, intensity_map

    def invalidate(self) -> None:
        """Invalidate cached colored-light contributions."""
        if self._cache is not None:
            self._cache.invalidate()


def apply_colored_lighting(
    lit_fg: np.ndarray,
    lit_bg: np.ndarray,
    light_sources: Iterable[LightSourceLike],
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


def apply_render_lighting(
    *,
    base_fg: np.ndarray,
    base_bg: np.ndarray,
    glyph_indices: np.ndarray,
    drawn_mask: np.ndarray,
    visible_mask: np.ndarray,
    map_height_vp: np.ndarray,
    map_memory_vp: np.ndarray,
    map_tiles_vp: np.ndarray,
    light_sources: Iterable[LightSourceLike],
    game_map: GameMap,
    viewport_x: int,
    viewport_y: int,
    vp_h: int,
    vp_w: int,
    player_x: int,
    player_y: int,
    player_height: int,
    show_height_vis: bool,
    vis_max_diff: int,
    vis_color_high_np: np.ndarray,
    vis_color_mid_np: np.ndarray,
    vis_color_low_np: np.ndarray,
    vis_blend_factor: np.float32,
    lighting_ambient: np.float32,
    lighting_min_fov: np.float32,
    lighting_falloff: np.float32,
    fov_radius_sq: np.float32,
    enable_colored_lights: bool,
    enable_memory_fade: bool,
    memory_fade_color_np: np.ndarray,
    rng: GameRNG,
    memory_fade_variance: float,
    memory_noise_level: float,
    lighting_renderer: LightingRenderer,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compatibility wrapper for the renderer-facing lighting pipeline."""
    return lighting_renderer.apply_render_lighting(
        base_fg=base_fg,
        base_bg=base_bg,
        glyph_indices=glyph_indices,
        drawn_mask=drawn_mask,
        visible_mask=visible_mask,
        map_height_vp=map_height_vp,
        map_memory_vp=map_memory_vp,
        map_tiles_vp=map_tiles_vp,
        light_sources=light_sources,
        game_map=game_map,
        viewport_x=viewport_x,
        viewport_y=viewport_y,
        vp_h=vp_h,
        vp_w=vp_w,
        player_x=player_x,
        player_y=player_y,
        player_height=player_height,
        show_height_vis=show_height_vis,
        vis_max_diff=vis_max_diff,
        vis_color_high_np=vis_color_high_np,
        vis_color_mid_np=vis_color_mid_np,
        vis_color_low_np=vis_color_low_np,
        vis_blend_factor=vis_blend_factor,
        lighting_ambient=lighting_ambient,
        lighting_min_fov=lighting_min_fov,
        lighting_falloff=lighting_falloff,
        fov_radius_sq=fov_radius_sq,
        enable_colored_lights=enable_colored_lights,
        enable_memory_fade=enable_memory_fade,
        memory_fade_color_np=memory_fade_color_np,
        rng=rng,
        memory_fade_variance=memory_fade_variance,
        memory_noise_level=memory_noise_level,
    )


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
    It expects read-only map and mask slices, such as renderer base-layer views.
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
