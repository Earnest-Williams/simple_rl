from __future__ import annotations

"""Integrated GameRNG module.

Platform Requirements & Quirks:
- Built for NumPy 1.24+ (uses default_rng and BitGenerator state structures).
- Fallback support: Detects and handles NumPy runtimes lacking 'endpoint' kwarg.
- JSON Compatibility: get_state() returns lists instead of ndarrays for JSON safety.
- Roundtrip Determinism: set_state() handles both JSON-decoded lists and native
  NumPy types, but requires consistent bit-depth (64-bit) for state restoration.
- Thread Safety: All metrics updates are performed outside the RNG lock to
  prevent lock-order inversion with the MetricsCollector background thread.

Final refinements applied:
- Implemented _NP_INTEGERS_SUPPORTS_ENDPOINT runtime detection.
- Moved metrics.update calls after releasing _rng_lock across all methods.
- Standardized distribution normalization (Enum vs String) in get_dist_range.
- Defensive set_state with clearer error message.
- Cached CDFs are stored as read-only arrays to avoid accidental mutation.
- Strictly avoided semicolons and multi-line f-strings.
"""

import json
import math
import random
import threading
import time
import uuid
import warnings
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Sequence

import numpy as np

# Detect whether the RNG integers(...) supports 'endpoint' kwarg.
try:
    np.random.default_rng().integers(0, 1, endpoint=True)
    _NP_INTEGERS_SUPPORTS_ENDPOINT = True
except TypeError:
    _NP_INTEGERS_SUPPORTS_ENDPOINT = False


# ---------------------------------------------------------------------------
# Metrics collection
# ---------------------------------------------------------------------------


@dataclass
class MetricsCollector:
    """Collect simple metrics in a background thread for performance tracking.

    Note:
        - `bits_consumed` is an approximate diagnostic metric (53 bits per
          IEEE-754 double float, etc.) intended for coarse diagnostics rather
          than cryptographic accounting.
    """

    collection_interval: float = 1.0
    metrics: Dict[str, int] = field(
        default_factory=lambda: {
            "weighted_choices": 0,
            "weighted_samples_ares": 0,
            "integers_generated": 0,
            "floats_generated": 0,
            "shuffles": 0,
            "samples": 0,
            "choices": 0,
            "batch_operations": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "bits_consumed": 0,
        }
    )
    stats: Dict[str, float] = field(
        default_factory=lambda: {
            "start_time": time.monotonic(),
            "last_collection_time": time.monotonic(),
            "operations_per_second": 0.0,
            "bits_per_second": 0.0,
            "cache_hit_rate": 0.0,
            "last_ops_total": 0.0,
            "last_bits_total": 0.0,
        }
    )
    updates_queue: deque[tuple[str, int]] = field(default_factory=deque)
    running: bool = False
    stop_event: threading.Event = field(default_factory=threading.Event)
    collection_thread: threading.Thread | None = None
    lock: threading.RLock = field(default_factory=threading.RLock)

    def start(self) -> None:
        """Starts the background metrics collection thread."""
        if self.collection_thread is not None:
            return
        self.running = True
        self.stop_event.clear()
        self.collection_thread = threading.Thread(target=self._loop, daemon=True)
        self.collection_thread.start()

    def stop(self) -> None:
        """Stops the collection thread and waits for it to join."""
        self.running = False
        self.stop_event.set()
        if self.collection_thread is not None:
            self.collection_thread.join(timeout=self.collection_interval + 0.5)
            self.collection_thread = None

    def update(self, metric: str, value: int = 1) -> None:
        """Queues a metric update for the background thread."""
        with self.lock:
            if metric in self.metrics:
                self.updates_queue.append((metric, value))
            else:
                msg = f"Unknown metric '{metric}'"
                warnings.warn(msg, RuntimeWarning, stacklevel=2)

    def _loop(self) -> None:
        """Internal thread loop for processing updates."""
        while not self.stop_event.wait(self.collection_interval):
            self._process_updates()
            self._update_stats()

    def _process_updates(self) -> None:
        """Moves updates from the queue into the main metrics dictionary."""
        with self.lock:
            while self.updates_queue:
                metric, value = self.updates_queue.popleft()
                self.metrics[metric] += value

    def _update_stats(self) -> None:
        """Calculates derivative statistics like ops/sec, bits/sec and hit rates."""
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.stats["last_collection_time"]
            if elapsed > 0:
                ops_keys = {"shuffles", "samples", "choices", "weighted_choices"}
                ops_total = sum(
                    v
                    for k, v in self.metrics.items()
                    if k.endswith("_generated") or k in ops_keys
                )
                ops_delta = ops_total - self.stats["last_ops_total"]
                self.stats["operations_per_second"] = ops_delta / elapsed
                self.stats["last_ops_total"] = float(ops_total)

                bits_total = self.metrics["bits_consumed"]
                bits_delta = bits_total - self.stats["last_bits_total"]
                self.stats["bits_per_second"] = bits_delta / elapsed
                self.stats["last_bits_total"] = float(bits_total)

                total_cache = self.metrics["cache_hits"] + self.metrics["cache_misses"]
                self.stats["cache_hit_rate"] = (
                    self.metrics["cache_hits"] / total_cache if total_cache else 0.0
                )
            self.stats["last_collection_time"] = now

    def get_metrics(self) -> Dict[str, Any]:
        """Returns a snapshot of current metrics and statistics."""
        self._process_updates()
        self._update_stats()
        return {"metrics": dict(self.metrics), "stats": dict(self.stats)}


# ---------------------------------------------------------------------------
# RNG implementation
# ---------------------------------------------------------------------------


class Distribution(Enum):
    """Supported non-uniform distributions."""

    BELL = auto()
    TRIANGLE = auto()
    POWER = auto()
    EXPONENTIAL = auto()


class GameRNG:
    """Thread-safe, deterministic RNG engine for game logic and procedural generation."""

    def __init__(
        self,
        seed: int | None = None,
        metrics: bool = False,
        noise_seed: int | None = None,
    ) -> None:
        self.initial_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
        self.rng = np.random.default_rng(self.initial_seed)
        self._rng_lock = threading.RLock()

        self.noise_seed = noise_seed if noise_seed is not None else self.initial_seed

        self.metrics_enabled = metrics
        self.metrics = MetricsCollector() if metrics else None
        if self.metrics:
            self.metrics.start()

        self.weighted_choice_cache: OrderedDict[Any, tuple[np.ndarray, float, int]] = (
            OrderedDict()
        )
        self.weighted_choice_cache_size = 100

        self.distributions: Dict[str, Callable[..., float]] = {
            "bell": self._bell_dist,
            "triangle": self._triangle_dist,
            "power": self._power_dist,
            "exponential": self._exp_dist,
        }

    # ------------------------------------------------------------------
    # small helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize_dist(dist_type: str | Distribution) -> str:
        """Return lowercase distribution key for either enum or string input."""
        if isinstance(dist_type, Distribution):
            return dist_type.name.lower()
        return str(dist_type).lower()

    # ------------------------------------------------------------------
    # basic random helpers
    # ------------------------------------------------------------------
    def _get_float_raw(self) -> float:
        """Internal raw float generation [0.0, 1.0). Assumes _rng_lock is held.

        IMPORTANT: Do not call metrics.update(...) while holding _rng_lock to avoid
        lock-order inversion with the MetricsCollector.
        """
        return float(self.rng.random())

    def get_int(self, a: int, b: int) -> int:
        """Returns a random integer in [a, b] inclusive."""
        if a > b:
            raise ValueError("a <= b constraint violated")
        with self._rng_lock:
            if _NP_INTEGERS_SUPPORTS_ENDPOINT:
                val = int(self.rng.integers(a, b, endpoint=True))
            else:
                val = int(self.rng.integers(a, b + 1))
        if self.metrics:
            self.metrics.update("integers_generated")
            # approximate bits consumed for the range
            self.metrics.update("bits_consumed", (b - a).bit_length())
        return val

    def get_ints(self, a: int, b: int, count: int) -> List[int]:
        """Returns a list of random integers in [a, b] inclusive."""
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return []
        with self._rng_lock:
            if _NP_INTEGERS_SUPPORTS_ENDPOINT:
                vals = self.rng.integers(a, b, endpoint=True, size=count)
            else:
                vals = self.rng.integers(a, b + 1, size=count)
        if self.metrics:
            self.metrics.update("integers_generated", count)
            self.metrics.update("bits_consumed", (b - a).bit_length() * count)
        return [int(x) for x in vals]

    def get_randrange(self, start: int, stop: int | None = None, step: int = 1) -> int:
        """Returns a random element from range(start, stop, step)."""
        if step == 0:
            raise ValueError("step must not be zero")
        if stop is None:
            stop = start
            start = 0
        width = stop - start
        if step > 0:
            if width <= 0:
                raise ValueError("empty range for get_randrange()")
            n = (width + step - 1) // step
        else:
            if width >= 0:
                raise ValueError("empty range for get_randrange()")
            n = (abs(width) + abs(step) - 1) // abs(step)
        idx = self.get_int(0, n - 1)
        return start + idx * step

    def get_float(self, a: float = 0.0, b: float = 1.0) -> float:
        """Returns a random float in [a, b)."""
        if a > b:
            raise ValueError("a <= b constraint violated")
        with self._rng_lock:
            val = self._get_float_raw()
        if self.metrics:
            self.metrics.update("floats_generated")
            self.metrics.update("bits_consumed", 53)
        return a + (b - a) * val

    def get_floats(self, a: float, b: float, count: int) -> List[float]:
        """Returns a list of random floats in [a, b)."""
        if count < 0:
            raise ValueError("count must be non-negative")
        if count == 0:
            return []
        with self._rng_lock:
            vals = self.rng.random(size=count)
        if self.metrics:
            self.metrics.update("floats_generated", count)
            self.metrics.update("bits_consumed", 53 * count)
        return [float(a + (b - a) * x) for x in vals]

    # ------------------------------------------------------------------
    # logic & boolean helpers
    # ------------------------------------------------------------------
    def chance(self, probability: float) -> bool:
        """Returns True if a random roll is < probability (0.0 to 1.0)."""
        return self.get_float() < probability

    def percent_chance(self, chance: float) -> bool:
        """Returns True if a random roll [0, 100] is < chance."""
        return self.get_float(0, 100) < chance

    # ------------------------------------------------------------------
    # distributions
    # ------------------------------------------------------------------
    def _bell_dist(self) -> float:
        """Returns a value in [-1.0, 1.0] approximating a normal distribution."""
        # Uses 4 uniform samples (Irwin–Hall) scaled to approximate normal
        # Batch generate to reduce lock acquisitions
        samples = self.get_floats(0.0, 1.0, 4)
        return (sum(samples) - 2.0) * 0.5

    def _triangle_dist(self) -> float:
        """Returns a value in [0.0, 1.0] with a triangular distribution peak at 0.5."""
        # Batch generate to reduce lock acquisitions
        samples = self.get_floats(0.0, 1.0, 2)
        return (samples[0] + samples[1]) * 0.5

    def _power_dist(self, power: float = 2.0) -> float:
        """Returns a value in [0.0, 1.0] weighted toward 0 by the given power."""
        if power <= 0:
            raise ValueError("power must be positive")
        return self.get_float() ** power

    def _exp_dist(self, lambd: float = 1.0) -> float:
        """Returns a random value from an exponential distribution."""
        if lambd <= 0:
            raise ValueError("lambda must be positive")
        u = self.get_float(0.0, np.nextafter(1.0, 0.0))
        return -math.log(1.0 - u) / lambd

    def get_distribution(self, dist_type: str | Distribution, **kwargs: Any) -> float:
        """Retrieves a single sample from a named distribution."""
        key = self._normalize_dist(dist_type)

        if key not in self.distributions:
            msg = f"Unknown dist: {dist_type}"
            raise ValueError(msg)

        dist_func = self.distributions[key]
        if key == "power":
            result = dist_func(power=float(kwargs.get("power", 2.0)))
        elif key == "exponential":
            result = dist_func(lambd=float(kwargs.get("lambd", 1.0)))
        else:
            if kwargs:
                msg = f"Unused args for {key}: {list(kwargs.keys())}"
                warnings.warn(msg, RuntimeWarning)
            result = dist_func()
        return float(result)

    def get_dist_range(
        self,
        min_val: float,
        max_val: float,
        dist_type: str | Distribution,
        **kwargs: Any,
    ) -> float:
        """Returns a distributed value mapped to the range [min_val, max_val]."""
        key = self._normalize_dist(dist_type)
        val = self.get_distribution(key, **kwargs)

        # Bell distributions centered at 0 in [-1, 1] range.
        # Shift to [0, 1] before applying range mapping.
        if key == "bell":
            val = (val + 1.0) / 2.0

        return min_val + (max_val - min_val) * val

    # ------------------------------------------------------------------
    # weighted helpers
    # ------------------------------------------------------------------
    def _validate_weights(self, weights: Sequence[float]) -> np.ndarray:
        """Ensures weights are numeric, finite, and non-negative."""
        w_arr = np.asarray(weights, dtype=float)
        if not np.all(np.isfinite(w_arr)):
            raise ValueError("Weights must be finite")
        if np.any(w_arr < 0):
            raise ValueError("Weights must be non-negative")
        return w_arr

    def weighted_choice(
        self,
        items: Sequence[Any],
        weights: Sequence[float],
        cache_key: Any | None = None,
    ) -> Any:
        """Selects a single item based on relative weights."""
        if len(items) != len(weights):
            raise ValueError("items/weights length mismatch")

        w_arr = self._validate_weights(weights)
        total = float(math.fsum(w_arr.tolist()))
        if total <= 0:
            raise ValueError("Weight sum must be positive")

        cdf = None
        cache_hit = False

        with self._rng_lock:
            if cache_key is not None:
                cached_data = self.weighted_choice_cache.get(cache_key)
                if cached_data:
                    c_cdf, c_total, c_len = cached_data
                    if c_len == len(weights) and math.isclose(
                        c_total, total, rel_tol=1e-9
                    ):
                        cdf = c_cdf
                        total = c_total
                        self.weighted_choice_cache.move_to_end(cache_key)
                        cache_hit = True
                    else:
                        # If lengths/total differ, remove the stale entry
                        try:
                            del self.weighted_choice_cache[cache_key]
                        except KeyError:
                            pass

            if cdf is None:
                cdf = np.cumsum(w_arr)
                cdf[-1] = total
                if cache_key is not None:
                    if (
                        len(self.weighted_choice_cache)
                        >= self.weighted_choice_cache_size
                    ):
                        self.weighted_choice_cache.popitem(last=False)
                    # store as read-only copy to avoid accidental mutation
                    cdf_copy = cdf.copy()
                    cdf_copy.flags.writeable = False
                    self.weighted_choice_cache[cache_key] = (
                        cdf_copy,
                        total,
                        len(weights),
                    )

            r = self._get_float_raw() * total
            idx = int(np.searchsorted(cdf, r, side="left"))
            idx = min(idx, len(items) - 1)

        # Metrics updates are intentionally performed after releasing _rng_lock.
        if self.metrics:
            self.metrics.update("cache_hits" if cache_hit else "cache_misses")
            self.metrics.update("weighted_choices")
            # count the internal float draw this operation used
            self.metrics.update("floats_generated")
            self.metrics.update("bits_consumed", 53)
        return items[idx]

    def weighted_sample_ares(
        self, items: Sequence[Any], weights: Sequence[float], k: int
    ) -> List[Any]:
        """Weighted selection without replacement using Accelerated Reservoir Sampling."""
        if len(items) != len(weights):
            raise ValueError("items/weights length mismatch")
        if k < 0 or k > len(items):
            raise ValueError("invalid k")
        if k == 0:
            return []

        w_arr = self._validate_weights(weights)
        positive = w_arr > 0
        if np.count_nonzero(positive) < k:
            raise ValueError("not enough positive weights for k")

        items_pos = [items[i] for i in range(len(items)) if positive[i]]
        weights_pos = w_arr[positive]

        with self._rng_lock:
            rng_vals = self.rng.random(len(items_pos))
            log_keys = np.log(rng_vals) / weights_pos
            idx = np.argpartition(-log_keys, k - 1)[:k]
            idx = idx[np.argsort(-log_keys[idx])]

        if self.metrics:
            self.metrics.update("bits_consumed", 53 * len(items_pos))
            self.metrics.update("weighted_samples_ares")
        return [items_pos[i] for i in idx]

    # ------------------------------------------------------------------
    # sequence utilities
    # ------------------------------------------------------------------
    def choice(self, items: Sequence[Any]) -> Any:
        """Returns a random element from a non-empty sequence."""
        if not items:
            raise ValueError("choice from empty sequence")
        idx = self.get_int(0, len(items) - 1)
        if self.metrics:
            self.metrics.update("choices")
        return items[idx]

    def shuffle(self, seq: List[Any]) -> None:
        """Shuffles the sequence in-place."""
        with self._rng_lock:
            self.rng.shuffle(seq)
        if self.metrics:
            # Approximation of bits consumed by Durstenfeld shuffle
            self.metrics.update("bits_consumed", len(seq) * 4)
            self.metrics.update("shuffles")

    def sample(
        self,
        items: Sequence[Any],
        k: int,
        replacement: bool = False,
        weights: Sequence[float] | None = None,
    ) -> List[Any]:
        """Picks k items from a sequence, optionally with weights or replacement."""
        if k < 0:
            raise ValueError("k must be non-negative")
        if k == 0:
            return []

        n = len(items)
        if not replacement and k > n:
            raise ValueError("k <= len(items) without replacement")

        if weights is None:
            with self._rng_lock:
                if replacement:
                    idxs = self.rng.integers(0, n, size=k)
                else:
                    idxs = self.rng.choice(n, size=k, replace=False)
                choices = [items[int(i)] for i in idxs]
        else:
            if replacement:
                choices = [self.weighted_choice(items, weights) for _ in range(k)]
            else:
                choices = self.weighted_sample_ares(items, weights, k)

        if self.metrics:
            self.metrics.update("samples")
        return list(choices)

    # ------------------------------------------------------------------
    # dice, cards, and loot helpers
    # ------------------------------------------------------------------
    def roll_dice(
        self, num_dice: int = 1, sides: int = 6, modifier: int = 0
    ) -> Dict[str, Any]:
        """Simulates dice rolls (e.g., 2d6+1)."""
        if sides < 1 or num_dice < 0:
            raise ValueError("invalid dice parameters")
        rolls = self.get_ints(1, sides, num_dice) if num_dice > 0 else []
        total = sum(rolls) + modifier
        return {"total": total, "rolls": rolls, "modifier": modifier}

    def coin_flip(
        self, num_flips: int = 1, heads_probability: float = 0.5
    ) -> str | List[str]:
        """Simulates coin flips with a specific bias toward 'heads'."""
        if not 0.0 <= heads_probability <= 1.0:
            raise ValueError("probability out of range")

        floats = self.get_floats(0.0, 1.0, num_flips)
        results = ["heads" if f < heads_probability else "tails" for f in floats]
        return results[0] if num_flips == 1 else results

    def deck_of_cards(self, shuffled: bool = True) -> List[Dict[str, str]]:
        """Returns a standard 52-card deck as list of rank/suit dicts."""
        suits = ("hearts", "diamonds", "clubs", "spades")
        ranks = (
            "ace",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
            "jack",
            "queen",
            "king",
        )
        deck = [{"rank": r, "suit": s} for s in suits for r in ranks]
        if shuffled:
            self.shuffle(deck)
        return deck

    def loot_table(
        self, table: Dict[Any, float], count: int = 1, unique: bool = False
    ) -> List[Any]:
        """Selects items from a weighted dict."""
        if count < 0:
            raise ValueError("count >= 0")
        if count == 0 or not table:
            return []
        items = list(table.keys())
        weights = [float(w) for w in table.values()]
        return self.sample(items, count, replacement=not unique, weights=weights)

    # ------------------------------------------------------------------
    # spatial & geometric helpers
    # ------------------------------------------------------------------
    def point_in_circle(self, radius: float = 1.0) -> tuple[float, float]:
        """Returns a uniform random (x, y) coordinate inside a circle."""
        # Use sqrt to avoid radial clustering: r = R * sqrt(u)
        # Batch generate both values in single call to reduce lock acquisitions
        samples = self.get_floats(0.0, 1.0, 2)
        r = radius * math.sqrt(samples[0])
        theta = 2.0 * math.pi * samples[1]
        return (r * math.cos(theta), r * math.sin(theta))

    def point_on_circle(self, radius: float = 1.0) -> tuple[float, float]:
        """Returns a random (x, y) coordinate exactly on the circle's edge."""
        theta = self.get_float(0, 2.0 * math.pi)
        return (radius * math.cos(theta), radius * math.sin(theta))

    # ------------------------------------------------------------------
    # visual & color helpers
    # ------------------------------------------------------------------
    def color_rgb(self) -> tuple[int, int, int]:
        """Returns a random (R, G, B) tuple in 0-255 range."""
        return tuple(self.get_ints(0, 255, 3))

    def color_hex(self) -> str:
        """Returns a random color string in #RRGGBB format."""
        r, g, b = self.get_ints(0, 255, 3)
        return f"#{r:02x}{g:02x}{b:02x}"

    # ------------------------------------------------------------------
    # miscellaneous
    # ------------------------------------------------------------------
    def uuid(self, deterministic: bool = False) -> str:
        """Generates a UUID, deterministic based on RNG state if requested."""
        if not deterministic:
            return str(uuid.uuid4())

        with self._rng_lock:
            if _NP_INTEGERS_SUPPORTS_ENDPOINT:
                # endpoint=True path returns numbers 0..255 inclusive
                ints = self.rng.integers(0, 255, size=16, endpoint=True, dtype=np.uint8)
            else:
                # fallback produces 0..255 with high bound 256 (exclusive)
                ints = self.rng.integers(0, 256, size=16, dtype=np.uint8)
            b = bytearray(ints.tolist())
        if self.metrics:
            self.metrics.update("bits_consumed", 128)

        # Set variant/version bits per RFC 4122
        b[6] = (b[6] & 0x0F) | 0x40
        b[8] = (b[8] & 0x3F) | 0x80
        return str(uuid.UUID(bytes=bytes(b)))

    # ------------------------------------------------------------------
    # noise (SplitMix64 implementation)
    # ------------------------------------------------------------------
    def _hash_seed(self, *vals: int) -> int:
        """Hashes input integers with the internal noise seed.

        Note: Reads noise_seed under _rng_lock to avoid a tiny race with reset().
        """
        with self._rng_lock:
            seed = self.noise_seed
        for v in vals:
            seed = (seed * 6364136223846793005 + v + 1) & 0xFFFFFFFFFFFFFFFF
        return seed

    @staticmethod
    def _splitmix64(x: int) -> int:
        """Internal 64-bit mixer for noise generation."""
        x = (x + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9 & 0xFFFFFFFFFFFFFFFF
        x = (x ^ (x >> 27)) * 0x94D049BB133111EB & 0xFFFFFFFFFFFFFFFF
        return x ^ (x >> 31)

    def _rand_float_from_seed(self, seed: int) -> float:
        """Converts a hashed integer into a float in [-1.0, 1.0]."""
        v = self._splitmix64(seed)
        val = (v >> 11) / float(1 << 53)
        return val * 2.0 - 1.0

    def noise_1d(self, x: float, scale: float = 1.0, seed_offset: int = 0) -> float:
        """Deterministic 1D noise sample."""
        if scale <= 0:
            raise ValueError("scale must be positive")
        input_x = math.floor(x / scale)
        return self._rand_float_from_seed(self._hash_seed(input_x, seed_offset))

    def noise_2d(
        self, x: float, y: float, scale: float = 1.0, seed_offset: int = 0
    ) -> float:
        """Deterministic 2D noise sample."""
        if scale <= 0:
            raise ValueError("scale must be positive")
        input_x = math.floor(x / scale)
        input_y = math.floor(y / scale)
        return self._rand_float_from_seed(
            self._hash_seed(input_x, input_y, seed_offset)
        )

    # ------------------------------------------------------------------
    # state management (.npz binary serialization) + JSON compatibility
    # ------------------------------------------------------------------
    def _value_to_array(self, v: Any) -> np.ndarray:
        """Converts state values to numpy arrays for serialization."""
        if isinstance(v, np.ndarray):
            if v.dtype.kind == "O":
                raise ValueError("Cannot serialize object arrays without pickle.")
            return v
        if isinstance(v, (int, float, bool, np.generic)):
            return np.array(v)
        if isinstance(v, str):
            return np.array(v.encode("utf-8"), dtype="S")
        if isinstance(v, (bytes, bytearray)):
            return np.array(bytes(v), dtype="S")
        if isinstance(v, (list, tuple)):
            arr = np.asarray(v)
            if arr.dtype.kind == "O":
                if all(isinstance(x, str) for x in v):
                    return np.array([x.encode("utf-8") for x in v], dtype="S")
                raise ValueError("Cannot serialize sequence with objects.")
            return arr
        msg = f"Unsupported state leaf type: {type(v)!r}"
        raise ValueError(msg)

    def _array_to_value(self, arr: np.ndarray) -> Any:
        """Converts numpy arrays back into state values."""
        if arr.dtype.kind == "S":
            if arr.shape == ():
                return arr.tobytes().decode("utf-8")
            return [x.decode("utf-8") for x in arr.tolist()]
        if arr.shape == ():
            return arr.item()
        return arr

    def _flatten_state(self, obj: Any, prefix: str, out: Dict[str, np.ndarray]) -> None:
        """Recursively flattens state dict for .npz storage."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                key = f"{prefix}::{k}" if prefix else k
                self._flatten_state(v, key, out)
        else:
            out[prefix] = self._value_to_array(obj)

    def _get_raw_state(self) -> Dict[str, Any]:
        """Return the raw internal state (may contain numpy arrays)."""
        with self._rng_lock:
            return {
                "version": 1,
                "random_state": self.rng.bit_generator.state,
                "initial_seed": self.initial_seed,
                "noise_seed": self.noise_seed,
            }

    def _to_jsonable(self, obj: Any) -> Any:
        """Convert a structure containing numpy arrays/scalars into JSON-friendly types."""
        if isinstance(obj, dict):
            return {k: self._to_jsonable(v) for k, v in obj.items()}

        if isinstance(obj, (np.integer, np.floating, np.bool_, np.generic)):
            return obj.item()

        if isinstance(obj, np.ndarray):
            if obj.dtype.kind == "S":
                if obj.shape == ():
                    return obj.tobytes().decode("utf-8")
                return [x.decode("utf-8") for x in obj.tolist()]
            return obj.tolist()

        if isinstance(obj, (list, tuple)):
            return [self._to_jsonable(v) for v in obj]

        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj

        return str(obj)

    def get_state(self) -> Dict[str, Any]:
        """Returns a JSON-serializable snapshot of state."""
        raw = self._get_raw_state()
        return self._to_jsonable(raw)

    def set_state(self, state: Dict[str, Any]) -> None:
        """Restores the internal state. Accepts the JSON-friendly structure too."""
        with self._rng_lock:
            if "random_state" in state:
                try:
                    # BitGenerator.state assignment coerces lists back to arrays.
                    self.rng.bit_generator.state = state["random_state"]
                except Exception as e:
                    raise ValueError("Invalid RNG random_state structure") from e
            if "initial_seed" in state:
                self.initial_seed = state["initial_seed"]
            if "noise_seed" in state:
                self.noise_seed = state["noise_seed"]

    def save_state_to_file(self, filename: Path) -> None:
        """Save state. If filename ends with .json, write JSON; otherwise write .npz."""
        if filename.suffix.lower() == ".json":
            state = self.get_state()
            with filename.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            return

        state = self._get_raw_state()
        arrays: Dict[str, np.ndarray] = {}
        self._flatten_state(state, "", arrays)
        np.savez_compressed(filename, **arrays)

    def load_state_from_file(self, filename: Path) -> None:
        """Loads state from .npz or .json file (auto-detect by extension)."""
        if filename.suffix.lower() == ".json":
            with filename.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.set_state(loaded)
            return

        loaded: Dict[str, Any] = {}
        with np.load(filename, allow_pickle=False) as npz:
            for key in npz.files:
                arr = npz[key]
                parts = key.split("::")
                value = self._array_to_value(arr)
                d = loaded
                for p in parts[:-1]:
                    d = d.setdefault(p, {})
                d[parts[-1]] = value

        if "version" not in loaded or int(loaded["version"]) != 1:
            msg = f"Incompatible state version: {loaded.get('version')}"
            raise ValueError(msg)
        if "random_state" not in loaded:
            raise ValueError("Invalid state file: 'random_state' missing.")

        self.set_state(loaded)

    def get_metrics(self) -> Dict[str, Any] | None:
        """Returns metric snapshot if tracking is enabled."""
        if not self.metrics_enabled or not self.metrics:
            return None
        return self.metrics.get_metrics()

    def reset(
        self, seed: int | None = None, noise_seed: int | Literal["reset"] | None = None
    ) -> None:
        """Resets the engine with a new seed."""
        self.initial_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
        with self._rng_lock:
            self.rng = np.random.default_rng(self.initial_seed)
            if noise_seed == "reset" or noise_seed is None:
                self.noise_seed = self.initial_seed
            else:
                self.noise_seed = noise_seed
            self.weighted_choice_cache.clear()

        if self.metrics_enabled and self.metrics:
            self.metrics.stop()
            self.metrics = MetricsCollector()
            self.metrics.start()


__all__ = ["GameRNG", "MetricsCollector", "Distribution"]
