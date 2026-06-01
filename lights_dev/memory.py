# memory.py
"""
Memory Fade System for FOV/Lighting Simulation.

This module implements a sophisticated memory decay system for roguelike games,
where the player's recollection of explored areas gradually fades over time.
The system uses sigmoid-based decay with support for agent trait modifiers.

Key Features:
- Vectorized Numba-accelerated memory updates for performance
- Sparse tile tracking to avoid processing forgotten/unseen tiles
- Quantized batch updates for consistent frame times
- Agent trait modifiers (intelligence, conditions, magic effects)
- JIT-compiled character index lookup for fast rendering

Usage:
    from memory import MemorySystem, MemoryTraits

    # Create system with default traits
    memory_system = MemorySystem(width=100, height=100)

    # Or with custom agent traits
    traits = MemoryTraits(intelligence=14, has_confusion=True)
    memory_system = MemorySystem(width=100, height=100, traits=traits)

    # Each frame:
    memory_system.update(dt=0.016, visible_mask=fov_visible_array)

    # Rendering:
    char_indices = memory_system.get_character_indices(tile_ids)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Final

import numba
import numpy as np
from numpy.typing import NDArray

from lights_dev import constants

# Use the local vectorized implementations in this module for fading.
# (Removed the old helper import from _numba_fov; we keep that module for legacy code
# but the public API should use this file's implementation.)

# =============================================================================
# Constants
# =============================================================================

# --- Base Memory Parameters (slowed down from original) ---
# Original was 60.0; increased for slower decay
BASE_MEMORY_DURATION: Final[float] = 90.0  # Time units for full fade
BASE_SIGMOID_MIDPOINT: Final[float] = BASE_MEMORY_DURATION / 2.0  # 45.0
# Original steepness was 6.0/60.0 = 0.1; reduced for gentler curve
BASE_SIGMOID_STEEPNESS: Final[float] = 5.0 / BASE_MEMORY_DURATION  # ~0.056

# --- Memory Level Rendering (imported from central tuning) ---
from common.tuning import MEMORY_LEVEL_COUNT as MEMORY_LEVEL_COUNT  # noqa: E402

# Character arrays for each tile type at each decay level
# Index 0 = freshest memory, Index 4 = almost forgotten
MEMORY_WALL_CHARS: Final[tuple[str, ...]] = ("▓", "▒", "░", "⋅", " ")
MEMORY_PILLAR_CHARS: Final[tuple[str, ...]] = ("▤", "▥", "▫", "◦", " ")
MEMORY_FLOOR_CHARS: Final[tuple[str, ...]] = (".", "·", "⋅", " ", " ")
MEMORY_LIGHT_CHAR: Final[str] = "+"
UNSEEN_CHAR: Final[str] = " "

# --- Tile IDs (must match dungeon constants) ---
TILE_WALL: Final[int] = 0
TILE_FLOOR: Final[int] = 1
TILE_PILLAR: Final[int] = 2

# --- Trait Modifier Bounds ---
MIN_INTELLIGENCE: Final[int] = 1
MAX_INTELLIGENCE: Final[int] = 30
BASE_INTELLIGENCE: Final[int] = 10

# --- Update Configuration ---
DEFAULT_UPDATE_INTERVAL: Final[float] = 0.1  # Seconds between memory updates
MIN_INTENSITY_THRESHOLD: Final[float] = 0.001  # Below this, treat as forgotten

# --- Numba constant for exp overflow prevention ---
_EXP_CLAMP: Final[float] = 70.0  # Prevent exp overflow


# =============================================================================
# Trait Modifiers
# =============================================================================


@dataclass(frozen=True, slots=True)
class MemoryTraits:
    """
    Agent traits that modify memory decay behavior.

    All modifiers combine multiplicatively into a final decay rate modifier.
    Values > 1.0 = faster decay (worse memory)
    Values < 1.0 = slower decay (better memory)

    Attributes:
        intelligence: Agent's intelligence stat (1-30, base 10).
            Higher intelligence = slower decay.
            Formula: modifier = BASE_INT / intelligence
            Example: INT 20 -> 0.5x decay rate (memories last twice as long)

        has_confusion: Whether agent is confused/disoriented.
            Doubles decay rate when True.

        has_illness: Whether agent is ill (fever, poison, etc.).
            Increases decay by 50% when True.

        fatigue_level: Agent's fatigue (0.0 = rested, 1.0 = exhausted).
            Scales decay rate: 1.0 + (fatigue * 0.5)
            Example: 0.8 fatigue -> 1.4x decay rate

        magic_memory_bonus: Magical enhancement to memory retention.
            Direct multiplier on duration. Range [0.0, 10.0].
            Example: 0.5 -> 50% slower decay (1.5x duration)

        location_familiarity: How familiar the agent is with the area.
            Range [0.0, 1.0] where 1.0 = home territory.
            Familiar areas decay 50% slower at max.
    """

    intelligence: int = BASE_INTELLIGENCE
    has_confusion: bool = False
    has_illness: bool = False
    fatigue_level: float = 0.0
    magic_memory_bonus: float = 0.0
    location_familiarity: float = 0.0

    def __post_init__(self) -> None:
        """Validate trait values."""
        # Use object.__setattr__ since frozen=True
        int_clamped = max(MIN_INTELLIGENCE, min(MAX_INTELLIGENCE, self.intelligence))
        object.__setattr__(self, "intelligence", int_clamped)

        fatigue_clamped = max(0.0, min(1.0, self.fatigue_level))
        object.__setattr__(self, "fatigue_level", fatigue_clamped)

        magic_clamped = max(0.0, min(10.0, self.magic_memory_bonus))
        object.__setattr__(self, "magic_memory_bonus", magic_clamped)

        familiarity_clamped = max(0.0, min(1.0, self.location_familiarity))
        object.__setattr__(self, "location_familiarity", familiarity_clamped)

    def compute_decay_modifier(self) -> float:
        """
        Compute the combined decay rate modifier from all traits.

        Returns:
            float: Combined modifier where:
                - 1.0 = base decay rate
                - < 1.0 = slower decay (better memory)
                - > 1.0 = faster decay (worse memory)
        """
        modifier = 1.0

        # Intelligence: higher int = slower decay
        # BASE_INT / current_int, so INT 20 -> 0.5, INT 5 -> 2.0
        modifier *= BASE_INTELLIGENCE / self.intelligence

        # Confusion: doubles decay
        if self.has_confusion:
            modifier *= 2.0

        # Illness: 50% faster decay
        if self.has_illness:
            modifier *= 1.5

        # Fatigue: up to 50% faster decay at full fatigue
        modifier *= 1.0 + (self.fatigue_level * 0.5)

        # Magic bonus: reduces decay rate
        # magic_memory_bonus of 0.5 -> modifier *= 1/(1+0.5) = 0.667
        if self.magic_memory_bonus > 0.0:
            modifier /= 1.0 + self.magic_memory_bonus

        # Location familiarity: up to 50% slower decay
        # familiarity of 1.0 -> modifier *= 0.5
        modifier *= 1.0 - (self.location_familiarity * 0.5)

        return max(0.01, modifier)  # Clamp to prevent zero/negative

    def get_effective_parameters(self) -> tuple[float, float]:
        """
        Get the effective sigmoid parameters after applying trait modifiers.

        Returns:
            tuple[float, float]: (steepness, midpoint) adjusted for traits
        """
        decay_mod = self.compute_decay_modifier()

        # Higher decay_mod = faster decay = higher steepness, lower midpoint
        effective_steepness = BASE_SIGMOID_STEEPNESS * decay_mod
        effective_midpoint = BASE_SIGMOID_MIDPOINT / decay_mod

        return (effective_steepness, effective_midpoint)


# =============================================================================
# Numba-Accelerated Core Functions
# =============================================================================


@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _sigmoid_decay(elapsed: float, steepness: float, midpoint: float) -> float:
    """
    Compute sigmoid decay value for a single tile.

    Args:
        elapsed: Time since tile was last seen
        steepness: Sigmoid steepness parameter
        midpoint: Sigmoid midpoint parameter

    Returns:
        Memory intensity in range [0.0, 1.0]
    """
    exponent = steepness * (elapsed - midpoint)
    if exponent >= _EXP_CLAMP:
        return 0.0
    if exponent <= -_EXP_CLAMP:
        return 1.0
    return 1.0 / (1.0 + math.exp(exponent))


@numba.jit(nopython=True, parallel=True, cache=True)  # type: ignore[untyped-decorator]
def _update_memory_vectorized(
    current_time: np.float32,
    last_seen_time: NDArray[np.float32],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
    steepness: np.float32,
    midpoint: np.float32,
    min_threshold: np.float32,
) -> int:
    """
    Vectorized memory fade update using Numba parallel execution.

    Only processes tiles that:
    1. Have non-zero memory intensity
    2. Are not currently visible

    Args:
        current_time: Current simulation time
        last_seen_time: 2D array of when each tile was last seen
        memory_intensity: 2D array of memory intensity values (modified in-place)
        visible: 2D boolean array of currently visible tiles
        steepness: Sigmoid steepness parameter
        midpoint: Sigmoid midpoint parameter
        min_threshold: Minimum intensity below which tile is considered forgotten

    Returns:
        Number of tiles that were updated
    """
    height, width = memory_intensity.shape
    updated_count = 0

    for y in numba.prange(height):
        for x in range(width):
            intensity = memory_intensity[y, x]

            # Skip if already forgotten or currently visible
            if intensity <= min_threshold or visible[y, x]:
                if intensity > 0.0 and intensity <= min_threshold:
                    memory_intensity[y, x] = 0.0  # Clean up near-zero values
                continue

            # Calculate elapsed time
            elapsed = current_time - last_seen_time[y, x]
            if elapsed < 0.0:
                elapsed = 0.0

            # Compute new intensity via sigmoid
            exponent = steepness * (elapsed - midpoint)
            if exponent >= _EXP_CLAMP:
                new_intensity = 0.0
            elif exponent <= -_EXP_CLAMP:
                new_intensity = 1.0
            else:
                new_intensity = 1.0 / (1.0 + math.exp(exponent))

            # Apply threshold
            if new_intensity < min_threshold:
                new_intensity = 0.0

            memory_intensity[y, x] = new_intensity
            updated_count += 1

    return updated_count


@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _refresh_visible_tiles(
    current_time: np.float32,
    last_seen_time: NDArray[np.float32],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
) -> int:
    """
    Refresh memory for all currently visible tiles.

    Sets memory_intensity to 1.0 and updates last_seen_time for visible tiles.

    Args:
        current_time: Current simulation time
        last_seen_time: 2D array of when each tile was last seen (modified in-place)
        memory_intensity: 2D array of memory intensity values (modified in-place)
        visible: 2D boolean array of currently visible tiles

    Returns:
        Number of tiles refreshed
    """
    height, width = visible.shape
    count = 0

    for y in range(height):
        for x in range(width):
            if visible[y, x]:
                last_seen_time[y, x] = current_time
                memory_intensity[y, x] = 1.0
                count += 1

    return count


@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _compute_character_indices(
    tile_ids: NDArray[np.int8],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
    level_count: int,
) -> NDArray[np.int8]:
    """
    Compute character indices for rendering based on memory intensity.

    Returns an array where each value represents:
    - -1: Tile is currently visible (render normally)
    - -2: Tile is unseen/forgotten (render as empty)
    - 0 to level_count-1: Memory decay level for the tile type

    The actual character lookup must be done in Python using the tile type
    and the returned index.

    Args:
        tile_ids: 2D array of tile type IDs
        memory_intensity: 2D array of memory intensity values
        visible: 2D boolean array of currently visible tiles
        level_count: Number of decay levels (typically 5)

    Returns:
        2D array of character indices (int8)
    """
    height, width = tile_ids.shape
    result = np.empty((height, width), dtype=np.int8)

    for y in range(height):
        for x in range(width):
            if visible[y, x]:
                result[y, x] = -1  # Currently visible
            elif memory_intensity[y, x] <= 0.0:
                result[y, x] = -2  # Unseen/forgotten
            else:
                # Map intensity to level: 1.0 -> 0, 0.0 -> level_count-1
                intensity = memory_intensity[y, x]
                level = int((1.0 - intensity) * level_count)
                result[y, x] = min(level_count - 1, max(0, level))

    return result


# --- fast scalar character index helper (Numba-jitted) ---------------------
@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _compute_character_index_scalar(
    tile_id: int,
    memory_intensity: float,
    visible: bool,
    level_count: int,
) -> int:
    """
    Scalar variant of _compute_character_indices for a single tile.

    Returns:
      -1 : tile is currently visible
      -2 : tile is unseen/forgotten (memory_intensity <= 0)
      0..level_count-1 : memory decay level index
    """
    if visible:
        return -1
    if memory_intensity <= 0.0:
        return -2

    level = int((1.0 - memory_intensity) * level_count)
    if level < 0:
        level = 0
    elif level >= level_count:
        level = level_count - 1
    return level


@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _count_active_memory_tiles(
    memory_intensity: NDArray[np.float32],
    min_threshold: np.float32,
) -> int:
    """
    Count tiles with active (non-forgotten) memory.

    Args:
        memory_intensity: 2D array of memory intensity values
        min_threshold: Minimum intensity to be considered active

    Returns:
        Number of active memory tiles
    """
    height, width = memory_intensity.shape
    count = 0

    for y in range(height):
        for x in range(width):
            if memory_intensity[y, x] > min_threshold:
                count += 1

    return count


@numba.jit(nopython=True, cache=True)  # type: ignore[untyped-decorator]
def _batch_update_region(
    current_time: np.float32,
    last_seen_time: NDArray[np.float32],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
    steepness: np.float32,
    midpoint: np.float32,
    min_threshold: np.float32,
    y_start: int,
    y_end: int,
) -> int:
    """
    Update memory for a horizontal slice of the map (for batched updates).

    Args:
        current_time: Current simulation time
        last_seen_time: 2D array of when each tile was last seen
        memory_intensity: 2D array of memory intensity values (modified in-place)
        visible: 2D boolean array of currently visible tiles
        steepness: Sigmoid steepness parameter
        midpoint: Sigmoid midpoint parameter
        min_threshold: Minimum intensity threshold
        y_start: Starting row (inclusive)
        y_end: Ending row (exclusive)

    Returns:
        Number of tiles updated in this batch
    """
    width = memory_intensity.shape[1]
    updated_count = 0

    for y in range(y_start, y_end):
        for x in range(width):
            intensity = memory_intensity[y, x]

            if intensity <= min_threshold or visible[y, x]:
                if intensity > 0.0 and intensity <= min_threshold:
                    memory_intensity[y, x] = 0.0
                continue

            elapsed = current_time - last_seen_time[y, x]
            if elapsed < 0.0:
                elapsed = 0.0

            exponent = steepness * (elapsed - midpoint)
            if exponent >= _EXP_CLAMP:
                new_intensity = 0.0
            elif exponent <= -_EXP_CLAMP:
                new_intensity = 1.0
            else:
                new_intensity = 1.0 / (1.0 + math.exp(exponent))

            if new_intensity < min_threshold:
                new_intensity = 0.0

            memory_intensity[y, x] = new_intensity
            updated_count += 1

    return updated_count


# =============================================================================
# Memory System Class
# =============================================================================


@dataclass
class MemorySystem:
    """
    High-performance memory fade system for roguelike FOV.

    Manages the decay of player memory for explored tiles, with support for:
    - Vectorized Numba-accelerated updates
    - Agent trait modifiers (intelligence, conditions, magic)
    - Quantized batch updates for consistent performance
    - Efficient character index computation for rendering

    Attributes:
        width: Map width in tiles
        height: Map height in tiles
        traits: Agent memory trait modifiers
        update_interval: Minimum time between full updates (for batching)
        batch_count: Number of batches to split updates into (0 = no batching)

    Example:
        >>> system = MemorySystem(100, 100)
        >>> system.update(0.016, visible_mask)
        >>> indices = system.get_character_indices(tile_ids)
    """

    width: int
    height: int
    traits: MemoryTraits = field(default_factory=MemoryTraits)
    update_interval: float = DEFAULT_UPDATE_INTERVAL
    batch_count: int = 0  # 0 = process all at once, >0 = split into N batches

    # Internal state (initialized in __post_init__)
    _memory_intensity: NDArray[np.float32] = field(init=False, repr=False)
    _last_seen_time: NDArray[np.float32] = field(init=False, repr=False)
    _current_time: np.float32 = field(init=False, repr=False)
    _time_since_update: float = field(init=False, repr=False)
    _current_batch: int = field(init=False, repr=False)
    _cached_steepness: np.float32 = field(init=False, repr=False)
    _cached_midpoint: np.float32 = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialize arrays and cached values."""
        self._memory_intensity = np.zeros((self.height, self.width), dtype=np.float32)
        self._last_seen_time = np.zeros((self.height, self.width), dtype=np.float32)
        self._current_time = np.float32(0.0)
        self._time_since_update = 0.0
        self._current_batch = 0
        self._update_cached_parameters()

    def _update_cached_parameters(self) -> None:
        """Recompute cached sigmoid parameters from current traits."""
        steepness, midpoint = self.traits.get_effective_parameters()
        self._cached_steepness = np.float32(steepness)
        self._cached_midpoint = np.float32(midpoint)

    def set_traits(self, traits: MemoryTraits) -> None:
        """
        Update agent traits and recompute decay parameters.

        Args:
            traits: New memory trait configuration
        """
        self.traits = traits
        self._update_cached_parameters()

    def update(
        self,
        dt: float,
        visible: NDArray[np.bool_],
        force_full_update: bool = False,
    ) -> tuple[int, int]:
        """
        Update memory state for one frame.

        Refreshes memory for visible tiles and decays memory for non-visible
        tiles according to the sigmoid decay function and trait modifiers.

        Args:
            dt: Delta time since last update (seconds)
            visible: 2D boolean array indicating currently visible tiles
            force_full_update: If True, ignore batching and update everything

        Returns:
            tuple[int, int]: (tiles_refreshed, tiles_decayed)
        """
        self._current_time += np.float32(dt)
        self._time_since_update += dt

        # Always refresh visible tiles immediately
        refreshed = _refresh_visible_tiles(
            self._current_time,
            self._last_seen_time,
            self._memory_intensity,
            visible,
        )

        # Check if we should process decay this frame
        if self._time_since_update < self.update_interval and not force_full_update:
            return (refreshed, 0)

        self._time_since_update = 0.0

        # Decay non-visible tiles
        if self.batch_count <= 0 or force_full_update:
            # Full update
            decayed = _update_memory_vectorized(
                self._current_time,
                self._last_seen_time,
                self._memory_intensity,
                visible,
                self._cached_steepness,
                self._cached_midpoint,
                np.float32(MIN_INTENSITY_THRESHOLD),
            )
        else:
            # Batched update - process one slice per frame
            batch_height = (self.height + self.batch_count - 1) // self.batch_count
            y_start = self._current_batch * batch_height
            y_end = min(y_start + batch_height, self.height)

            decayed = _batch_update_region(
                self._current_time,
                self._last_seen_time,
                self._memory_intensity,
                visible,
                self._cached_steepness,
                self._cached_midpoint,
                np.float32(MIN_INTENSITY_THRESHOLD),
                y_start,
                y_end,
            )

            self._current_batch = (self._current_batch + 1) % self.batch_count

        return (refreshed, decayed)

    def get_character_indices(
        self,
        tile_ids: NDArray[np.int8],
    ) -> NDArray[np.int8]:
        """
        Compute character indices for rendering.

        Returns an array where:
        - -1: Tile is currently visible (use normal rendering)
        - -2: Tile is unseen/forgotten (use UNSEEN_CHAR)
        - 0-4: Memory decay level (index into MEMORY_*_CHARS arrays)

        Args:
            tile_ids: 2D array of tile type IDs

        Returns:
            2D array of character indices
        """
        # Need visible state to distinguish visible vs remembered
        # For this, we check if memory_intensity == 1.0 and last_seen == current
        visible = (self._memory_intensity == 1.0) & (
            self._last_seen_time == self._current_time
        )
        return _compute_character_indices(
            tile_ids,
            self._memory_intensity,
            visible,
            MEMORY_LEVEL_COUNT,
        )

    def get_character_indices_with_visible(
        self,
        tile_ids: NDArray[np.int8],
        visible: NDArray[np.bool_],
    ) -> NDArray[np.int8]:
        """
        Compute character indices using explicit visibility array.

        More accurate than get_character_indices when FOV may have changed
        since last update.

        Args:
            tile_ids: 2D array of tile type IDs
            visible: 2D boolean array of currently visible tiles

        Returns:
            2D array of character indices
        """
        return _compute_character_indices(
            tile_ids,
            self._memory_intensity,
            visible,
            MEMORY_LEVEL_COUNT,
        )

    def get_memory_character(
        self,
        tile_id: int,
        char_index: int,
    ) -> str:
        """
        Get the display character for a remembered tile.

        Args:
            tile_id: Tile type ID (TILE_WALL, TILE_FLOOR, TILE_PILLAR)
            char_index: Character index from get_character_indices (-1, -2, or 0-4)

        Returns:
            Character to display
        """
        if char_index == -1:
            # Currently visible - caller should handle this
            return ""
        if char_index == -2:
            return UNSEEN_CHAR

        index = min(MEMORY_LEVEL_COUNT - 1, max(0, char_index))

        if tile_id == TILE_WALL:
            return MEMORY_WALL_CHARS[index]
        elif tile_id == TILE_PILLAR:
            return MEMORY_PILLAR_CHARS[index]
        elif tile_id == TILE_FLOOR:
            return MEMORY_FLOOR_CHARS[index]
        else:
            return UNSEEN_CHAR

    def get_intensity(self, x: int, y: int) -> float:
        """
        Get memory intensity at a specific location.

        Args:
            x: X coordinate
            y: Y coordinate

        Returns:
            Memory intensity (0.0 = forgotten, 1.0 = fresh)
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            return float(self._memory_intensity[y, x])
        return 0.0

    def get_intensity_array(self) -> NDArray[np.float32]:
        """
        Get the full memory intensity array (read-only view).

        Returns:
            2D array of memory intensities
        """
        view = self._memory_intensity.view()
        view.flags.writeable = False
        return view

    def get_active_tile_count(self) -> int:
        """
        Count tiles with active (non-forgotten) memory.

        Returns:
            Number of tiles being tracked
        """
        return int(
            _count_active_memory_tiles(
                self._memory_intensity,
                np.float32(MIN_INTENSITY_THRESHOLD),
            )
        )

    def reset(self) -> None:
        """Reset all memory state (as if map was never explored)."""
        self._memory_intensity.fill(0.0)
        self._last_seen_time.fill(0.0)
        self._current_time = np.float32(0.0)
        self._time_since_update = 0.0
        self._current_batch = 0

    def clear_tile(self, x: int, y: int) -> None:
        """
        Clear memory of a specific tile (instant forget).

        Useful for magical effects or map changes.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self._memory_intensity[y, x] = 0.0

    def refresh_tile(self, x: int, y: int) -> None:
        """
        Refresh memory of a specific tile (instant recall).

        Useful for magical effects like clairvoyance.

        Args:
            x: X coordinate
            y: Y coordinate
        """
        if 0 <= x < self.width and 0 <= y < self.height:
            self._memory_intensity[y, x] = 1.0
            self._last_seen_time[y, x] = self._current_time

    @property
    def current_time(self) -> float:
        """Get current simulation time."""
        return float(self._current_time)

    @property
    def effective_duration(self) -> float:
        """Get effective memory duration after trait modifiers."""
        decay_mod = self.traits.compute_decay_modifier()
        return BASE_MEMORY_DURATION / decay_mod

    @property
    def effective_steepness(self) -> float:
        """Get effective sigmoid steepness after trait modifiers."""
        return float(self._cached_steepness)

    @property
    def effective_midpoint(self) -> float:
        """Get effective sigmoid midpoint after trait modifiers."""
        return float(self._cached_midpoint)

    def save_state(self) -> dict[str, NDArray[np.float32] | float]:
        """
        Save memory state for serialization.

        Returns a dictionary containing all state needed to restore memory.
        Use with load_state() for save/load functionality.

        Returns:
            Dictionary with keys:
                - 'memory_intensity': 2D array of memory intensities
                - 'last_seen_time': 2D array of last seen times
                - 'current_time': Current simulation time
        """
        return {
            "memory_intensity": self._memory_intensity.copy(),
            "last_seen_time": self._last_seen_time.copy(),
            "current_time": float(self._current_time),
        }

    def load_state(self, state: dict[str, NDArray[np.float32] | float]) -> None:
        """
        Restore memory state from saved data.

        Args:
            state: Dictionary from save_state() containing:
                - 'memory_intensity': 2D array of memory intensities
                - 'last_seen_time': 2D array of last seen times
                - 'current_time': Current simulation time

        Raises:
            ValueError: If state arrays have wrong dimensions
            KeyError: If required keys are missing
        """
        intensity = state["memory_intensity"]
        last_seen = state["last_seen_time"]
        current_time = state["current_time"]

        # Validate array shapes
        if not isinstance(intensity, np.ndarray) or not isinstance(
            last_seen, np.ndarray
        ):
            raise ValueError("State arrays must be numpy arrays")

        if intensity.shape != (self.height, self.width):
            raise ValueError(
                f"memory_intensity shape {intensity.shape} does not match "
                f"system dimensions ({self.height}, {self.width})"
            )
        if last_seen.shape != (self.height, self.width):
            raise ValueError(
                f"last_seen_time shape {last_seen.shape} does not match "
                f"system dimensions ({self.height}, {self.width})"
            )

        # Restore state
        np.copyto(self._memory_intensity, intensity.astype(np.float32))
        np.copyto(self._last_seen_time, last_seen.astype(np.float32))
        self._current_time = np.float32(current_time)
        self._time_since_update = 0.0


# =============================================================================
# Convenience Functions
# =============================================================================


def create_memory_system(
    width: int,
    height: int,
    intelligence: int = BASE_INTELLIGENCE,
    update_interval: float = DEFAULT_UPDATE_INTERVAL,
    batch_count: int = 0,
) -> MemorySystem:
    """
    Create a memory system with a simple trait configuration.

    Args:
        width: Map width in tiles
        height: Map height in tiles
        intelligence: Agent intelligence stat (1-30, base 10)
        update_interval: Minimum time between decay updates
        batch_count: Number of batches for updates (0 = no batching)

    Returns:
        Configured MemorySystem instance
    """
    traits = MemoryTraits(intelligence=intelligence)
    return MemorySystem(
        width=width,
        height=height,
        traits=traits,
        update_interval=update_interval,
        batch_count=batch_count,
    )


def get_memory_level_characters(tile_id: int) -> tuple[str, ...]:
    """
    Get the character sequence for a tile type's memory decay levels.

    Args:
        tile_id: Tile type ID

    Returns:
        Tuple of characters from fresh to forgotten
    """
    if tile_id == TILE_WALL:
        return MEMORY_WALL_CHARS
    elif tile_id == TILE_PILLAR:
        return MEMORY_PILLAR_CHARS
    elif tile_id == TILE_FLOOR:
        return MEMORY_FLOOR_CHARS
    else:
        return (UNSEEN_CHAR,) * MEMORY_LEVEL_COUNT


def update_memory_fade(
    current_time: np.float32,
    last_seen_time: NDArray[np.float32],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
) -> None:
    """
    Update memory_intensity in-place using the local MemorySystem parameters.

    Uses the module's vectorized Numba routines and the MemoryTraits default
    so decays follow the configured sigmoid curve (smooth fade).
    """
    # Refresh currently visible tiles immediately (set intensity=1 and update last_seen)
    _refresh_visible_tiles(
        np.float32(current_time), last_seen_time, memory_intensity, visible
    )

    # Use default traits for effective sigmoid parameters (caller may adapt later)
    traits = MemoryTraits()
    steepness, midpoint = traits.get_effective_parameters()

    # Run the vectorized decay update (in-place)
    _update_memory_vectorized(
        np.float32(current_time),
        last_seen_time,
        memory_intensity,
        visible,
        np.float32(steepness),
        np.float32(midpoint),
        np.float32(MIN_INTENSITY_THRESHOLD),
    )


def get_character_indices(
    tile_ids: NDArray[np.int8],
    memory_intensity: NDArray[np.float32],
    visible: NDArray[np.bool_],
) -> NDArray[np.int8]:
    return _compute_character_indices(
        tile_ids,
        memory_intensity,
        visible,
        constants.MEMORY_LEVEL_COUNT,
    )


def get_memory_character(tile_id: int, intensity: float) -> str:
    """
    Return the memory-character for a single tile_id and memory intensity.

    Uses a Numba scalar helper to avoid allocating temporary 1x1 arrays and calling
    the full-array _compute_character_indices for single-tile lookups.
    """
    idx = int(
        _compute_character_index_scalar(
            tile_id, float(intensity), False, MEMORY_LEVEL_COUNT
        )
    )
    if idx == -2:
        return UNSEEN_CHAR

    level_index = max(0, min(MEMORY_LEVEL_COUNT - 1, idx))
    if tile_id == TILE_WALL:
        return MEMORY_WALL_CHARS[level_index]
    if tile_id == TILE_PILLAR:
        return MEMORY_PILLAR_CHARS[level_index]
    if tile_id == TILE_FLOOR:
        return MEMORY_FLOOR_CHARS[level_index]
    return UNSEEN_CHAR


def precompile(height: int, width: int) -> None:
    dummy_last_seen = np.zeros((height, width), dtype=np.float32)
    dummy_memory = np.zeros((height, width), dtype=np.float32)
    dummy_visible = np.zeros((height, width), dtype=np.bool_)
    update_memory_fade(
        np.float32(0.0),
        dummy_last_seen,
        dummy_memory,
        dummy_visible,
    )
