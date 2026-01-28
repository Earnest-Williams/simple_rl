#!/usr/bin/env python
"""
lights_dev.lighting

Directional lights + channels + height/incidence + 8 directions + per-cell masks,
with premultiplied RGBA accumulation and optional incremental (dirty) updates.

COORDINATE SYSTEM CONVENTION:
============================
This module uses SCREEN COORDINATES (Y increases downward), matching fov.py.

Angle interpretation:
  0°        (0 rad)      = East  (→)  [+X direction]
  90°       (π/2 rad)    = South (↓)  [+Y direction]
  180°      (π rad)      = West  (←)  [-X direction]
  270°      (3π/2 rad)   = North (↑)  [-Y direction]

This differs from standard mathematical coordinates where Y increases upward
and π/2 points north.

For directional lights:
  light.direction = math.atan2(dy_screen, dx_screen)
  where dy_screen > 0 means "downward" in screen space

Example:
  To aim a light toward the tile at (target_x, target_y) from (light.x, light.y):
    dx = target_x - light.x
    dy = target_y - light.y  # positive if target is below light
    light.direction = math.atan2(dy, dx)

Key behaviors:
- Core radius: no inverse-distance attenuation inside CORE_NO_ATTEN_RADIUS tiles.
- Directional lights: can constrain FOV to outer cone if FOV supports angles; per-tile softness
  is applied in the accumulator via cosine-space interpolation.
- Incidence: clamped dz/len3, with a fast per-light short-circuit for height <= 0.0.
- Masks: no full-array copies by default. If cell_mask is provided, this module expects the FOV
  routine to accept (cell_mask, light_channels) and treat masked cells as transparent for blocking.
  Masked cells are also excluded from lighting post-FOV.
- Visibility: prefers subtractive visibility output from FOV. If unavailable, computes subtractive
  visibility fallback (excluding the endpoint, so opaque tiles can still be lit).

Incremental updates:
- If you pass stable Light IDs and do not mutate scene geometry without calling invalidate_scene(),
  unchanged lights are skipped and their cached contributions are reused.
- If your scene (opaque/transparency/cell_mask contents) changes, call invalidate_scene() or pass
  a scene_seq that changes.

Premultiplied blending:
- Per-side accumulation stores float32 premultiplied RGBA in 0..255 space.
  For intensity ratio r:
    rgb_add  = light_rgb * r
    a_add    = r * 255
  Later composition uses premultiplied "over":
    out = src_rgb + dst_rgb * (1 - src_a/255)

The module expects lights_dev.fov.compute_fov_all_octants to exist.

Author: rewritten per review and requested changes, with fov.py compatibility fixes integrated.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numba
import numpy as np
from numpy.typing import NDArray

from lights_dev import constants
from lights_dev._numba_fov import Slope, _compute_octant_for_color
from lights_dev.dungeon_data import Dungeon
from lights_dev.entities import Entity

# import compute_fov_all_octants from lights_dev.fov (must be present)
try:
    from lights_dev.fov import compute_fov_all_octants
except Exception:
    compute_fov_all_octants = None  # fail at runtime if used without fov


# ---------------- types ----------------
U8Grid = NDArray[np.uint8]
I32Grid = NDArray[np.int32]
F32Grid = NDArray[np.float32]
U32Grid = NDArray[np.uint32]


# ---------------- constants ----------------
# Side indices (match JS ordering)
# JS order: North=0, East=1, South=2, West=3, NorthEast=4, SouthEast=5, SouthWest=6, NorthWest=7
SIDE_N: int = 0
SIDE_E: int = 1
SIDE_S: int = 2
SIDE_W: int = 3
SIDE_NE: int = 4
SIDE_SE: int = 5
SIDE_SW: int = 6
SIDE_NW: int = 7
NUM_SIDES: int = 8

DEFAULT_CHANNEL_MASK: int = 0xFFFFFFFF

CORE_NO_ATTEN_RADIUS: float = 3.0
_CORE_NO_ATTEN_RADIUS_SQ: float = CORE_NO_ATTEN_RADIUS * CORE_NO_ATTEN_RADIUS


# ---------------- data model ----------------
@dataclass
class Light:
    """
    Light source with optional directionality, channels, and height.
    
    INCIDENCE MODEL:
    ===============
    Lighting attenuation includes an incidence factor based on light height:
      incidence = dz / len3
      where:
        dz = light.height (tile height, z-up)
        len3 = sqrt(dx² + dy² + dz²) (3D distance)
    
    Current behavior for height <= 0:
      - Lights are SKIPPED entirely in update_all_lights
      - Rationale: incidence = 0/len3 = 0 would zero all lighting anyway
    
    Design intent:
      - Height > 0: Full 3D lighting with incidence factor
      - Height = 0: Skipped (no 2D fallback mode implemented)
      - Height < 0: Skipped (negative heights unsupported)
    
    To enable pure 2D lighting (height=0 with incidence=1.0):
      1. Remove the height <= 0 short-circuit in update_all_lights
      2. Modify incidence calculation in _accumulate_light_premult_rgba:
         if light_height <= 0.0:
             incidence = 1.0  # 2D mode
         else:
             # existing 3D calculation
    """
    x: int
    y: int
    radius: int
    intensity: float
    color_rgb: tuple[int, int, int]  # 0..255
    direction: float | None = None  # radians; None means omni
    cone_angle: float = math.tau  # full cone in radians (tau = 2*pi => omni)
    cone_softness: float = 0.0  # 0.0 hard edge; (0..1] soft interpolation
    channels: int = DEFAULT_CHANNEL_MASK  # bitmask
    id: int = -1
    height: float = 0.0  # tile height for incidence (z-up)

    def light_center_x(self) -> float:
        return float(self.x) + 0.5

    def light_center_y(self) -> float:
        return float(self.y) + 0.5

    def cache_key(self) -> tuple[object, ...]:
        # Everything that changes the computed contribution for this light.
        return (
            self.x,
            self.y,
            self.radius,
            float(self.intensity),
            int(self.color_rgb[0]),
            int(self.color_rgb[1]),
            int(self.color_rgb[2]),
            None if self.direction is None else float(self.direction),
            float(self.cone_angle),
            float(self.cone_softness),
            int(self.channels),
            float(self.height),
        )


# ---------------- main context ----------------
class LightContext:
    def __init__(
        self,
        width: int,
        height: int,
        ambient: tuple[int, int, int] = (0, 0, 0),
    ) -> None:
        self.width: int = int(width)
        self.height: int = int(height)
        self.ambient: tuple[int, int, int] = tuple(int(c) for c in ambient)

        # Total per-side premultiplied RGBA accumulators: (h,w,side,rgba), float32 in 0..255 space.
        self.side_rgba: NDArray[np.float32] = np.zeros(
            (self.height, self.width, NUM_SIDES, 4), dtype=np.float32
        )

        # Shared FOV temporaries (reused for per-light recomputes).
        self._visible_tmp: U8Grid = np.zeros((self.height, self.width), dtype=np.uint8)
        self._dist_tmp: I32Grid = -np.ones((self.height, self.width), dtype=np.int32)
        self._side_bits_tmp: U8Grid = np.zeros((self.height, self.width), dtype=np.uint8)
        self._visibility_tmp: F32Grid = np.zeros((self.height, self.width), dtype=np.float32)

        # Incremental caches (per-light contribution buffer and parameter key).
        self._light_rgba_cache: dict[int, NDArray[np.float32]] = {}
        self._light_key_cache: dict[int, tuple[object, ...]] = {}
        self._active_ids_last: set[int] = set()

        # Scene invalidation: if your opaque/transparency/cell_mask contents change,
        # call invalidate_scene() or pass a changing scene_seq to update_all_lights.
        self._scene_seq_last: int | None = None
        self._scene_invalidated: bool = True

        # ID assignment for lights without IDs.
        self._next_id: int = 1

    def invalidate_scene(self) -> None:
        self._scene_invalidated = True

    def reset_totals(self) -> None:
        self.side_rgba.fill(0.0)

    def _ensure_light_id(self, light: Light) -> int:
        if light.id >= 0:
            return light.id
        lid = self._next_id
        self._next_id += 1
        light.id = lid
        return lid

    def update_all_lights(
        self,
        lights: Iterable[Light],
        opaque: U8Grid,
        transparency: F32Grid,
        channel_mask: int = DEFAULT_CHANNEL_MASK,
        cell_mask: U32Grid | None = None,
        scene_seq: int | None = None,
        copy_fallback_for_mask: bool = False,
    ) -> None:
        """
        Recompute (or incrementally update) per-side premultiplied RGBA accumulators.

        opaque: uint8 shape (h,w)
        transparency: float32 0..1 shape (h,w)
        cell_mask: optional uint32 shape (h,w) per-cell mask bitfield

        Incremental behavior:
        - If scene_seq is provided and changes, caches are invalidated and everything is rebuilt.
        - If scene_seq is not provided, this method assumes the scene is unchanged unless
          invalidate_scene() was called.

        Mask behavior:
        - If cell_mask is provided, the preferred path is to pass (cell_mask, light.channels)
          into the FOV routine so masked cells are transparent for blocking.
        - By default, this code does not create full array copies. If your FOV does not support
          mask passthrough, set copy_fallback_for_mask=True to use the slower copy-based fallback.
        """
        h = self.height
        w = self.width
        if opaque.shape != (h, w):
            raise ValueError("opaque must have shape (height,width).")
        if transparency.shape != (h, w):
            raise ValueError("transparency must have shape (height,width).")
        if cell_mask is not None and cell_mask.shape != (h, w):
            raise ValueError("cell_mask must have shape (height,width).")

        if compute_fov_all_octants is None:
            raise RuntimeError(
                "compute_fov_all_octants is not available; ensure lights_dev.fov is present."
            )

        # Scene invalidation logic.
        if scene_seq is not None:
            if self._scene_seq_last is None or scene_seq != self._scene_seq_last:
                self._scene_invalidated = True
            self._scene_seq_last = int(scene_seq)

        full_rebuild: bool = self._scene_invalidated

        # Determine current active set (filtered by channel_mask).
        active_lights: list[Light] = []
        active_ids: set[int] = set()

        for light in lights:
            lid = self._ensure_light_id(light)

            if (int(light.channels) & int(channel_mask)) == 0:
                continue

            # Per-light micro-optimization: height <= 0 yields incidence 0 in current model.
            if float(light.height) <= 0.0:
                # If you want purely 2D lighting at height==0, remove this short-circuit and
                # adjust the incidence model in _accumulate_light_premult_rgba.
                continue

            active_lights.append(light)
            active_ids.add(lid)

        # If rebuilding, clear totals and caches for removed lights.
        if full_rebuild:
            self.reset_totals()
            self._active_ids_last = set()
            # Keep caches allocated, but invalidate keys so contributions get recomputed.
            self._light_key_cache.clear()

        # Remove lights that are no longer active (or were filtered out by channel_mask).
        removed_ids = self._active_ids_last - active_ids
        for rid in removed_ids:
            old_buf = self._light_rgba_cache.get(rid)
            if old_buf is not None:
                self.side_rgba -= old_buf
            self._light_rgba_cache.pop(rid, None)
            self._light_key_cache.pop(rid, None)

        # Update or reuse each active light.
        for light in active_lights:
            lid = int(light.id)
            key = light.cache_key()
            needs_recompute = full_rebuild or (self._light_key_cache.get(lid) != key)

            if not needs_recompute:
                continue

            # Remove old contribution if present.
            old_buf = self._light_rgba_cache.get(lid)
            if old_buf is not None:
                self.side_rgba -= old_buf

            # Allocate per-light buffer if needed.
            buf = self._light_rgba_cache.get(lid)
            if buf is None:
                buf = np.zeros((h, w, NUM_SIDES, 4), dtype=np.float32)
                self._light_rgba_cache[lid] = buf
            else:
                buf.fill(0.0)

            # Compute per-light contribution into buf.
            self._compute_light_contribution(
                light=light,
                opaque=opaque,
                transparency=transparency,
                cell_mask=cell_mask,
                out_side_rgba=buf,
                copy_fallback_for_mask=copy_fallback_for_mask,
            )

            # Add new contribution and update key.
            self.side_rgba += buf
            self._light_key_cache[lid] = key

        self._active_ids_last = active_ids
        self._scene_invalidated = False

    def _compute_light_contribution(
        self,
        light: Light,
        opaque: U8Grid,
        transparency: F32Grid,
        cell_mask: U32Grid | None,
        out_side_rgba: NDArray[np.float32],
        copy_fallback_for_mask: bool,
    ) -> None:
        visible = self._visible_tmp
        dist = self._dist_tmp
        side_bits = self._side_bits_tmp
        visibility = self._visibility_tmp

        visible.fill(0)
        dist.fill(-1)
        side_bits.fill(0)
        visibility.fill(0.0)

        # Directional parameters.
        if light.direction is None:
            is_dir = 0
            dir_x = 0.0
            dir_y = 0.0
            use_soft = 0
            half_angle = math.pi
            cos_outer = 1.0
            cos_inner = 1.0
            start_angle: float | None = None
            end_angle: float | None = None
        else:
            is_dir = 1
            dir_x = float(math.cos(light.direction))
            dir_y = float(math.sin(light.direction))

            half_angle = 0.5 * float(light.cone_angle)
            if half_angle <= 0.0:
                cos_outer = 1.0
            elif half_angle >= math.pi:
                cos_outer = -1.0
            else:
                cos_outer = float(math.cos(half_angle))

            if float(light.cone_softness) <= 0.0:
                use_soft = 0
                cos_inner = cos_outer
            else:
                use_soft = 1
                inner_half = half_angle * max(0.0, 1.0 - float(light.cone_softness))
                cos_inner = float(math.cos(inner_half))

            start_angle = float(light.direction - half_angle)
            end_angle = float(light.direction + half_angle)

        # Call FOV. Prefer signatures that accept visibility and mask passthrough.
        called_with_visibility = self._call_fov(
            opaque=opaque,
            transparency=transparency,
            cell_mask=cell_mask,
            light_channels=int(light.channels),
            visible=visible,
            dist=dist,
            side_bits=side_bits,
            visibility=visibility,
            src_x=int(light.x),
            src_y=int(light.y),
            radius=int(light.radius),
            start_angle=start_angle,
            end_angle=end_angle,
            copy_fallback_for_mask=copy_fallback_for_mask,
        )

        # If no visibility output, compute subtractive visibility fallback.
        # FIX: Now passes opaque and cell_mask to match fov.py semantics exactly.
        if not called_with_visibility:
            _compute_visibility_subtractive(
                visible=visible,
                opaque=opaque,
                transparency=transparency,
                cell_mask=cell_mask,
                light_channels=int(light.channels),
                visibility=visibility,
                src_x=int(light.x),
                src_y=int(light.y),
            )

        # FIX: Removed source tile visibility override.
        # FOV already sets visibility[src] = 1.0 with proper mask awareness.
        # Old code here would ignore cell_mask at source tile.

        # CRITICAL: Mask post-processing.
        # FOV marks masked cells as visible (they're transparent for *blocking*),
        # but we must exclude them from *lighting*. Zero out visible, side_bits,
        # and visibility for all cells where (light.channels & cell_mask) == 0.
        if cell_mask is not None:
            masked = ((int(light.channels) & cell_mask) == 0)
            if np.any(masked):
                visible[masked] = 0
                side_bits[masked] = 0
                visibility[masked] = 0.0

        # Accumulate into per-light buffer (Numba hot path).
        lr, lg, lb = light.color_rgb
        _accumulate_light_premult_rgba(
            visible=visible,
            dist=dist,
            side_bits=side_bits,
            visibility=visibility,
            out_side_rgba=out_side_rgba,
            light_intensity=float(light.intensity),
            light_r=float(lr),
            light_g=float(lg),
            light_b=float(lb),
            is_directional=int(is_dir),
            dir_x=float(dir_x),
            dir_y=float(dir_y),
            use_soft=int(use_soft),
            cos_outer=float(cos_outer),
            cos_inner=float(cos_inner),
            light_src_x=float(light.light_center_x()),
            light_src_y=float(light.light_center_y()),
            light_height=float(light.height),
        )

    def _call_fov(
        self,
        opaque: U8Grid,
        transparency: F32Grid,
        cell_mask: U32Grid | None,
        light_channels: int,
        visible: U8Grid,
        dist: I32Grid,
        side_bits: U8Grid,
        visibility: F32Grid,
        src_x: int,
        src_y: int,
        radius: int,
        start_angle: float | None,
        end_angle: float | None,
        copy_fallback_for_mask: bool,
    ) -> bool:
        """
        Attempts multiple compute_fov_all_octants signatures, preferring:
        - visibility output
        - angle constraints
        - mask passthrough (cell_mask, light_channels)

        Returns True if visibility was provided by the FOV routine.
        """
        opq = opaque.astype(np.uint8, copy=False)
        trn = transparency.astype(np.float32, copy=False)

        def _is_signature_typeerror(e: TypeError) -> bool:
            msg = str(e)
            # Best-effort heuristic. If FOV throws TypeError internally, this can still misclassify,
            # but this reduces the chance of masking a genuine bug.
            return (
                "positional argument" in msg
                or "required positional" in msg
                or "takes" in msg
                or "given" in msg
                or "unexpected keyword" in msg
            )

        if cell_mask is not None:
            cm = cell_mask.astype(np.uint32, copy=False)

            # Preferred: mask + visibility + angles
            if start_angle is not None and end_angle is not None:
                try:
                    compute_fov_all_octants(  # type: ignore[misc]
                        opq,
                        trn,
                        cm,
                        int(light_channels),
                        visible,
                        dist,
                        side_bits,
                        visibility,
                        src_x,
                        src_y,
                        radius,
                        float(start_angle),
                        float(end_angle),
                    )
                    return True
                except TypeError as e:
                    if not _is_signature_typeerror(e):
                        raise

            # mask + visibility (no angles)
            try:
                compute_fov_all_octants(  # type: ignore[misc]
                    opq,
                    trn,
                    cm,
                    int(light_channels),
                    visible,
                    dist,
                    side_bits,
                    visibility,
                    src_x,
                    src_y,
                    radius,
                )
                return True
            except TypeError as e:
                if not _is_signature_typeerror(e):
                    raise

            # mask + angles (no visibility)
            if start_angle is not None and end_angle is not None:
                try:
                    compute_fov_all_octants(  # type: ignore[misc]
                        opq,
                        trn,
                        cm,
                        int(light_channels),
                        visible,
                        dist,
                        side_bits,
                        src_x,
                        src_y,
                        radius,
                        float(start_angle),
                        float(end_angle),
                    )
                    return False
                except TypeError as e:
                    if not _is_signature_typeerror(e):
                        raise

            # mask (no visibility, no angles)
            try:
                compute_fov_all_octants(  # type: ignore[misc]
                    opq,
                    trn,
                    cm,
                    int(light_channels),
                    visible,
                    dist,
                    side_bits,
                    src_x,
                    src_y,
                    radius,
                )
                return False
            except TypeError as e:
                if not _is_signature_typeerror(e):
                    raise

            # If we reach here, FOV does not support mask passthrough signatures.
            if not copy_fallback_for_mask:
                raise RuntimeError(
                    "compute_fov_all_octants does not support mask passthrough "
                    "(cell_mask, light_channels). Update the FOV signature or set "
                    "copy_fallback_for_mask=True."
                )

            # Copy fallback: emulate masked transparency for blocking by copying arrays.
            masked = ((int(light_channels) & cell_mask) == 0)
            if np.any(masked):
                opq2 = opq.copy()
                trn2 = trn.copy()
                opq2[masked] = np.uint8(0)
                trn2[masked] = np.float32(1.0)
            else:
                opq2 = opq
                trn2 = trn

            # Now call non-mask variants.
            return self._call_fov(
                opaque=opq2,
                transparency=trn2,
                cell_mask=None,
                light_channels=light_channels,
                visible=visible,
                dist=dist,
                side_bits=side_bits,
                visibility=visibility,
                src_x=src_x,
                src_y=src_y,
                radius=radius,
                start_angle=start_angle,
                end_angle=end_angle,
                copy_fallback_for_mask=False,
            )

        # No mask: prefer visibility + angles
        if start_angle is not None and end_angle is not None:
            try:
                compute_fov_all_octants(  # type: ignore[misc]
                    opq,
                    trn,
                    visible,
                    dist,
                    side_bits,
                    visibility,
                    src_x,
                    src_y,
                    radius,
                    float(start_angle),
                    float(end_angle),
                )
                return True
            except TypeError as e:
                if not _is_signature_typeerror(e):
                    raise

        # visibility (no angles)
        try:
            compute_fov_all_octants(  # type: ignore[misc]
                opq,
                trn,
                visible,
                dist,
                side_bits,
                visibility,
                src_x,
                src_y,
                radius,
            )
            return True
        except TypeError as e:
            if not _is_signature_typeerror(e):
                raise

        # angles (no visibility)
        if start_angle is not None and end_angle is not None:
            try:
                compute_fov_all_octants(  # type: ignore[misc]
                    opq,
                    trn,
                    visible,
                    dist,
                    side_bits,
                    src_x,
                    src_y,
                    radius,
                    float(start_angle),
                    float(end_angle),
                )
                return False
            except TypeError as e:
                if not _is_signature_typeerror(e):
                    raise

        # minimal (no visibility, no angles)
        compute_fov_all_octants(  # type: ignore[misc]
            opq,
            trn,
            visible,
            dist,
            side_bits,
            src_x,
            src_y,
            radius,
        )
        return False

    def compose_frame(
        self,
        base_rgb: NDArray[np.uint8] | None = None,
        blend_mode: str = "over",
    ) -> NDArray[np.uint8]:
        """
        Compose final RGB frame.

        base_rgb: optional (h,w,3) uint8 base tiles.
        blend_mode:
          - "over": premultiplied alpha over base: out = Lrgb + base*(1 - La/255)
          - "add":  additive light: out = base + Lrgb

        Returns: (h,w,3) uint8.
        """
        h = self.height
        w = self.width

        total_rgba = np.sum(self.side_rgba, axis=2)  # (h,w,4) float32
        light_rgb = total_rgba[:, :, 0:3]
        light_a = total_rgba[:, :, 3]

        # Premultiplied alpha saturation fix:
        # When alpha > 255, scale RGB proportionally to preserve unmultiplied color.
        # This maintains the invariant: rgb_component <= alpha.
        oversaturated = light_a > 255.0
        if np.any(oversaturated):
            scale = 255.0 / light_a[oversaturated]
            light_rgb[oversaturated] *= scale[:, None]
        
        # Clamp alpha to 0..255.
        np.clip(light_a, 0.0, 255.0, out=light_a)

        if base_rgb is None:
            dst = np.zeros((h, w, 3), dtype=np.float32)
        else:
            if base_rgb.shape != (h, w, 3):
                raise ValueError("base_rgb must have shape (height,width,3).")
            dst = base_rgb.astype(np.float32)

        # Add ambient into destination.
        amb = np.array(self.ambient, dtype=np.float32).reshape((1, 1, 3))
        dst = dst + amb

        if blend_mode == "add":
            out = dst + light_rgb
        elif blend_mode == "over":
            inv = 1.0 - (light_a / 255.0)
            out = light_rgb + (dst * inv[:, :, None])
        else:
            raise ValueError("blend_mode must be 'over' or 'add'.")

        np.clip(out, 0.0, 255.0, out=out)
        return out.astype(np.uint8)


# ---------------- fallback helper: subtractive visibility via Bresenham ----------------
# FIX: Updated to match fov.py's visibility semantics exactly.


@numba.njit(inline="always")
def _opacity_for_visibility(
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: np.uint32,
    x: int,
    y: int,
) -> np.float32:
    """
    Compute opacity for visibility calculation, matching fov.py semantics.
    Returns opacity value (0.0 = transparent, 1.0 = opaque).
    """
    if use_mask != 0 and (cell_mask[y, x] & light_channels) == np.uint32(0):
        return np.float32(0.0)
    if opaque[y, x] != np.uint8(0):
        return np.float32(1.0)
    t = transparency[y, x]
    return np.float32(1.0) - np.float32(t)


@numba.njit(nogil=True, cache=True)
def _compute_visibility_subtractive_numba(
    visible: np.uint8[:, :],
    opaque: np.uint8[:, :],
    transparency: np.float32[:, :],
    cell_mask: np.uint32[:, :],
    use_mask: int,
    light_channels: np.uint32,
    visibility: np.float32[:, :],
    src_x: int,
    src_y: int,
) -> None:
    """
    Compute subtractive visibility using Bresenham ray marching.
    Matches fov.py's _compute_visibility_subtractive_ex exactly.
    """
    h, w = visible.shape

    for ty in range(h):
        for tx in range(w):
            if visible[ty, tx] == np.uint8(0):
                continue

            if tx == src_x and ty == src_y:
                visibility[ty, tx] = np.float32(1.0)
                continue

            x0 = src_x
            y0 = src_y
            x1 = tx
            y1 = ty

            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            sx = 1 if x0 < x1 else -1
            sy = 1 if y0 < y1 else -1

            cur_vis = np.float32(1.0)

            if dy <= dx:
                err = dx // 2
                x = x0
                y = y0
                while True:
                    if x == x1 and y == y1:
                        break

                    err -= dy
                    if err < 0:
                        y += sy
                        err += dx
                    x += sx

                    if x == x1 and y == y1:
                        break

                    if x < 0 or y < 0 or x >= w or y >= h:
                        cur_vis = np.float32(0.0)
                        break

                    cur_vis -= _opacity_for_visibility(
                        opaque, transparency, cell_mask, use_mask, light_channels, x, y
                    )
                    if cur_vis <= np.float32(0.0):
                        cur_vis = np.float32(0.0)
                        break
            else:
                err = dy // 2
                x = x0
                y = y0
                while True:
                    if x == x1 and y == y1:
                        break

                    err -= dx
                    if err < 0:
                        x += sx
                        err += dy
                    y += sy

                    if x == x1 and y == y1:
                        break

                    if x < 0 or y < 0 or x >= w or y >= h:
                        cur_vis = np.float32(0.0)
                        break

                    cur_vis -= _opacity_for_visibility(
                        opaque, transparency, cell_mask, use_mask, light_channels, x, y
                    )
                    if cur_vis <= np.float32(0.0):
                        cur_vis = np.float32(0.0)
                        break

            visibility[ty, tx] = cur_vis


def _compute_visibility_subtractive(
    visible: U8Grid,
    opaque: U8Grid,
    transparency: F32Grid,
    cell_mask: U32Grid | None,
    light_channels: int,
    visibility: F32Grid,
    src_x: int,
    src_y: int,
) -> None:
    """
    Compute subtractive visibility per visible cell when the FOV routine does not provide it.

    Semantics:
    - Start at visibility 1.0 at the source.
    - March along the ray and subtract opacity = (1 - transparency) for each *intermediate* cell.
    - The endpoint cell is not subtracted, so opaque tiles can still be lit.
    - Masked cells (where light_channels & cell_mask == 0) are treated as transparent.
    - Opaque cells are treated as fully opaque regardless of transparency value.

    FIX: Now matches fov.py's _compute_visibility_subtractive_ex exactly.
    """
    h, w = visible.shape

    if cell_mask is None:
        # Create dummy mask (all ones, no masking)
        dummy_mask = np.ones((h, w), dtype=np.uint32) * np.uint32(0xFFFFFFFF)
        use_mask = 0
    else:
        dummy_mask = cell_mask.astype(np.uint32, copy=False)
        use_mask = 1

    _compute_visibility_subtractive_numba(
        visible=visible,
        opaque=opaque,
        transparency=transparency,
        cell_mask=dummy_mask,
        use_mask=use_mask,
        light_channels=np.uint32(light_channels),
        visibility=visibility,
        src_x=src_x,
        src_y=src_y,
    )


# ---------------- numba hot path: premultiplied RGBA accumulation ----------------
@numba.njit(nogil=True, cache=True)
def _accumulate_light_premult_rgba(
    visible: NDArray[np.uint8],
    dist: NDArray[np.int32],
    side_bits: NDArray[np.uint8],
    visibility: NDArray[np.float32],
    out_side_rgba: NDArray[np.float32],
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
    """
    Accumulate a single light into out_side_rgba (premultiplied RGBA float32 in 0..255 space).

    For intensity ratio r:
      rgb_add = light_rgb * r
      a_add   = r * 255
    """
    h, w = visible.shape
    core_radius_sq = _CORE_NO_ATTEN_RADIUS_SQ

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

            # Core attenuation rule (2D).
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

            # Apply FOV subtractive visibility.
            t = float(visibility[y, x])
            atten *= t
            if atten <= 0.0:
                continue

            # Incidence: dz/len3, clamped, with dz>0 guaranteed by per-light short-circuit.
            dz = float(light_height)
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

            # Directional cone weighting.
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

            # Premultiplied additions.
            r_ratio = atten
            rgb_add_r = light_r * r_ratio
            rgb_add_g = light_g * r_ratio
            rgb_add_b = light_b * r_ratio
            a_add = r_ratio * 255.0

            # Distribute to exposed sides.
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


@numba.njit(cache=True)
def _bresenham_product_transparency(
    transparency: NDArray[np.float32], sx: int, sy: int, tx: int, ty: int
) -> float:
    """
    Compute multiplicative transparency product along Bresenham line from (sx, sy) to (tx, ty).
    
    Excludes the target tile (tx, ty) from the product. Returns 0.0 if any cell
    along the path is fully opaque.
    
    Args:
        transparency: 2D array of transparency values (0.0 = opaque, 1.0 = transparent).
        sx: Source x coordinate.
        sy: Source y coordinate.
        tx: Target x coordinate.
        ty: Target y coordinate.
    
    Returns:
        Product of transparency values along the path, or 0.0 if blocked.
    """
    dx = abs(tx - sx)
    dy = abs(ty - sy)
    sx_step = 1 if sx < tx else -1
    sy_step = 1 if sy < ty else -1
    x, y = sx, sy
    prod = 1.0
    if dx >= dy:
        err = dx // 2
        while True:
            if x == tx and y == ty:
                break
            x += sx_step
            err -= dy
            if err < 0:
                y += sy_step
                err += dx
            if x == tx and y == ty:
                break
            prod *= transparency[y, x]
            if prod <= 0.0:
                return 0.0
    else:
        err = dy // 2
        while True:
            if x == tx and y == ty:
                break
            y += sy_step
            err -= dx
            if err < 0:
                x += sx_step
                err += dy
            if x == tx and y == ty:
                break
            prod *= transparency[y, x]
            if prod <= 0.0:
                return 0.0
    return prod


def compute_illumination_color_array(
    *,
    origin: tuple[int, int],
    range_limit: int,
    dungeon_instance: Dungeon,
    target_rgb_sum_array: NDArray[np.float32],
    base_color_rgb: tuple[int, int, int],
    source_height: float = 1.0,
) -> None:
    ox, oy = origin
    if not (0 <= ox < dungeon_instance.width and 0 <= oy < dungeon_instance.height):
        return
    if range_limit <= 0:
        return

    target_rgb_sum_array[oy, ox, 0] += float(base_color_rgb[0])
    target_rgb_sum_array[oy, ox, 1] += float(base_color_rgb[1])
    target_rgb_sum_array[oy, ox, 2] += float(base_color_rgb[2])

    h = dungeon_instance.height
    w = dungeon_instance.width

    opaque: NDArray[np.uint8] = np.zeros((h, w), dtype=np.uint8)
    transparency: NDArray[np.float32] = np.zeros((h, w), dtype=np.float32)

    for y in range(h):
        for x in range(w):
            blocks = dungeon_instance.blocks_light(x, y)
            opaque[y, x] = np.uint8(1) if blocks else np.uint8(0)
            transparency[y, x] = np.float32(0.0) if blocks else np.float32(1.0)

    visible: NDArray[np.uint8] = np.zeros((h, w), dtype=np.uint8)
    dist: NDArray[np.int32] = -np.ones((h, w), dtype=np.int32)
    side_bits: NDArray[np.uint8] = np.zeros((h, w), dtype=np.uint8)

    # Call FOV with legacy signature - compute_fov_all_octants handles
    # multiple signatures internally via varargs inspection.
    compute_fov_all_octants(
        transparency, visible, dist, side_bits, int(ox), int(oy), int(range_limit)
    )

    light_src_x = float(ox) + 0.5
    light_src_y = float(oy) + 0.5
    dz = float(source_height)

    br = float(base_color_rgb[0])
    bg = float(base_color_rgb[1])
    bb = float(base_color_rgb[2])

    for y in range(h):
        for x in range(w):
            if visible[y, x] == 0:
                continue
            # visibility as product of transparency along line (excludes target cell)
            vis = _bresenham_product_transparency(transparency, int(ox), int(oy), x, y)
            if vis <= 0.0:
                continue

            dx = float((x + 0.5) - light_src_x)
            dy = float((y + 0.5) - light_src_y)
            len3_sq = dx * dx + dy * dy + dz * dz
            if len3_sq <= 1e-9:
                incidence = 1.0
            else:
                len3 = math.sqrt(len3_sq)
                incidence = dz / len3
                if incidence < 0.0:
                    incidence = 0.0

            intensity_ratio = vis * incidence
            if intensity_ratio <= 0.0:
                continue

            target_rgb_sum_array[y, x, 0] += br * intensity_ratio
            target_rgb_sum_array[y, x, 1] += bg * intensity_ratio
            target_rgb_sum_array[y, x, 2] += bb * intensity_ratio


def _interpolate_color(
    factor: float, start_rgb: tuple[int, int, int], end_rgb: tuple[int, int, int]
) -> tuple[int, int, int]:
    factor = max(0.0, min(1.0, factor))
    r = int(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * factor)
    g = int(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * factor)
    b = int(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * factor)
    return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def _get_brightness_from_rgb_sum(rgb_sum: NDArray[np.float32]) -> float:
    max_comp = float(np.max(rgb_sum))
    return min(1.0, max_comp / 255.0)


def _apply_lighting_to_base(
    base_rgb: tuple[int, int, int],
    rgb_sum: NDArray[np.float32],
    brightness: float,
) -> tuple[int, int, int]:
    max_comp = max(float(rgb_sum[0]), float(rgb_sum[1]), float(rgb_sum[2]), 1.0)
    tint_scale_r = float(rgb_sum[0]) / max_comp
    tint_scale_g = float(rgb_sum[1]) / max_comp
    tint_scale_b = float(rgb_sum[2]) / max_comp
    tinted_rgb = (
        int(max(0, min(255, base_rgb[0] * tint_scale_r))),
        int(max(0, min(255, base_rgb[1] * tint_scale_g))),
        int(max(0, min(255, base_rgb[2] * tint_scale_b))),
    )
    return _interpolate_color(brightness, constants.AMBIENT_COLOR_RGB, tinted_rgb)


class LightingSystem:
    @staticmethod
    def compute_illumination(
        dungeon: Dungeon, sources: List[Entity], rgb_sum_array: NDArray[np.float32]
    ) -> None:
        rgb_sum_array.fill(0.0)
        for source in sources:
            if source.light_radius > 0:
                source_height = float(getattr(source, "height", 1.0))
                compute_illumination_color_array(
                    origin=source.position,
                    range_limit=source.light_radius,
                    dungeon_instance=dungeon,
                    target_rgb_sum_array=rgb_sum_array,
                    base_color_rgb=source.base_color_rgb,
                    source_height=source_height,
                )

    @staticmethod
    def apply_lighting(
        base_rgb: Tuple[int, int, int],
        rgb_sum: NDArray[np.float32],
        brightness: float,
    ) -> Tuple[int, int, int]:
        return _apply_lighting_to_base(base_rgb, rgb_sum, brightness)

    @staticmethod
    def compute_final_rgb_map(
        dungeon: Dungeon,
        rgb_sum_array: NDArray[np.float32],
        base_color_map: NDArray[np.int32],
    ) -> NDArray[np.int32]:
        height = dungeon.height
        width = dungeon.width
        result: NDArray[np.int32] = np.zeros((height, width, 3), dtype=np.int32)
        for y in range(height):
            for x in range(width):
                rgb_sum = rgb_sum_array[y, x]
                brightness = _get_brightness_from_rgb_sum(rgb_sum)
                base_rgb = (
                    int(base_color_map[y, x, 0]),
                    int(base_color_map[y, x, 1]),
                    int(base_color_map[y, x, 2]),
                )
                result[y, x] = _apply_lighting_to_base(
                    base_rgb,
                    rgb_sum,
                    brightness,
                )
        return result

    @staticmethod
    def precompile(dungeon: Dungeon, origin: tuple[int, int]) -> None:
        dummy_rgb_sum_array = np.zeros(
            (dungeon.height, dungeon.width, 3), dtype=np.float32
        )
        compute_illumination_color_array(
            origin=origin,
            range_limit=0,
            dungeon_instance=dungeon,
            target_rgb_sum_array=dummy_rgb_sum_array,
            base_color_rgb=constants.AMBIENT_COLOR_RGB,
            source_height=1.0,
        )
