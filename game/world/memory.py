# game/world/memory.py
"""Persistent map-memory update algorithms."""

from typing import Final

import numpy as np
import numpy.typing as npt

MIN_SCALE: Final[float] = 1e-5  # lower bound to avoid divide-by-zero decay rates


def update_memory_fade(
    current_time: int,
    *,
    last_seen_time: npt.NDArray[np.int32],
    memory_intensity: npt.NDArray[np.float32],
    visible: npt.NDArray[np.bool_],
    needs_update_mask: npt.NDArray[np.bool_],
    prev_visible: npt.NDArray[np.bool_],
    memory_strength: npt.NDArray[np.float32],
    tile_modifiers: npt.NDArray[np.float32],
    steepness: float,
    midpoint: float,
) -> None:
    """Sigmoid-based fading of remembered tiles.

    Only tiles tracked in ``needs_update_mask`` are processed. The mask is
    dynamically updated to include tiles that transition from visible to
    invisible and pruned when tiles become visible again or their intensity
    reaches zero.
    """

    # Remove tiles that no longer need fading.
    needs_update_mask[visible] = False
    needs_update_mask[memory_intensity <= 0.0] = False

    # Add tiles that have just become invisible with non-zero intensity.
    became_invisible: npt.NDArray[np.bool_] = (
        prev_visible & (~visible) & (memory_intensity > 0.0)
    )
    needs_update_mask |= became_invisible

    # Prepare for next call.
    prev_visible[:] = visible

    if not np.any(needs_update_mask):
        return

    ys: npt.NDArray[np.intp]
    xs: npt.NDArray[np.intp]
    ys, xs = np.where(needs_update_mask)
    elapsed_time: npt.NDArray[np.float32] = np.maximum(
        current_time - last_seen_time[ys, xs], 0.0
    ).astype(np.float32, copy=False)

    strength: npt.NDArray[np.float32] = memory_strength[ys, xs]
    modifiers: npt.NDArray[np.float32] = tile_modifiers[ys, xs]
    scale: npt.NDArray[np.float32] = (1.0 + strength) * modifiers
    safe_scale: npt.NDArray[np.float32] = np.maximum(scale, MIN_SCALE)
    decay_rate: npt.NDArray[np.float32] = steepness / safe_scale
    midpoint_scaled: npt.NDArray[np.float32] = midpoint * scale
    exponent: npt.NDArray[np.float32] = decay_rate * (elapsed_time - midpoint_scaled)

    new_intensity: npt.NDArray[np.float32] = np.zeros_like(elapsed_time, dtype=np.float32)
    mask: npt.NDArray[np.bool_] = exponent < 70.0
    safe_exp: npt.NDArray[np.float32] = np.exp(np.minimum(exponent[mask], 70.0))
    denom: npt.NDArray[np.float32] = 1.0 + safe_exp
    # denom is always >= 1.0 because safe_exp is exp(x) for finite x.
    new_intensity[mask] = 1.0 / denom

    memory_intensity[ys, xs] = np.maximum(0.0, new_intensity)

    # Prune tiles that have faded completely.
    needs_update_mask[ys, xs] = memory_intensity[ys, xs] > 0.0
