# game/world/memory.py
"""Persistent map-memory update algorithms."""

import numpy as np
import numpy.typing as npt


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
    became_invisible = prev_visible & (~visible) & (memory_intensity > 0.0)
    needs_update_mask |= became_invisible

    # Prepare for next call.
    prev_visible[:] = visible

    if not np.any(needs_update_mask):
        return

    ys, xs = np.where(needs_update_mask)
    elapsed_time = current_time - last_seen_time[ys, xs]
    elapsed_time = np.maximum(elapsed_time, 0.0)

    strength = memory_strength[ys, xs]
    modifiers = tile_modifiers[ys, xs]
    scale = (1.0 + strength) * modifiers
    decay_rate = steepness / scale
    midpoint_scaled = midpoint * scale
    exponent = decay_rate * (elapsed_time - midpoint_scaled)

    new_intensity = np.zeros_like(elapsed_time, dtype=np.float32)
    mask = exponent < 70.0
    safe_exp = np.exp(np.minimum(exponent[mask], 70.0))
    denom = 1.0 + safe_exp
    new_intensity[mask] = np.where(denom > 1e-9, 1.0 / denom, 0.0)

    memory_intensity[ys, xs] = np.maximum(0.0, new_intensity)

    # Prune tiles that have faded completely.
    needs_update_mask[ys, xs] = memory_intensity[ys, xs] > 0.0
