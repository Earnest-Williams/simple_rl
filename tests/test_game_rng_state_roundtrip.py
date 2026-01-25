from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from utils.game_rng import GameRNG


def _draw_sequence(rng: GameRNG, count: int) -> list[int]:
    return [rng.get_int(0, 10) for _ in range(count)]


def _contains_large_int(obj: Any, max_uint64: int) -> bool:
    if isinstance(obj, dict):
        return any(_contains_large_int(v, max_uint64) for v in obj.values())
    if isinstance(obj, list | tuple):
        return any(_contains_large_int(v, max_uint64) for v in obj)
    if isinstance(obj, np.ndarray):
        return obj.dtype.kind == "O" or (
            obj.dtype.kind in {"i", "u"} and obj.itemsize > 8
        )
    if isinstance(obj, np.integer):
        obj = int(obj)
    if isinstance(obj, int):
        return obj < 0 or obj > max_uint64
    return False


def test_rng_state_roundtrip(tmp_path: Path) -> None:
    rng = GameRNG(seed=123, metrics=False)
    _ = [rng.get_float() for _ in range(5)]
    state = rng.get_state()

    seq1 = _draw_sequence(rng, 20)
    rng.set_state(state)
    seq2 = _draw_sequence(rng, 20)

    assert seq1 == seq2

    json_path = tmp_path / "rng_state.json"
    rng.set_state(state)
    rng.save_state_to_file(str(json_path))
    rng_json = GameRNG(seed=0, metrics=False)
    rng_json.load_state_from_file(str(json_path))
    seq3 = _draw_sequence(rng_json, 20)
    assert seq1 == seq3

    raw_state = rng._get_raw_state()
    max_uint64 = int(np.iinfo(np.uint64).max)
    if _contains_large_int(raw_state, max_uint64):
        pytest.skip("npz round-trip unsupported when RNG state contains large ints")

    npz_path = tmp_path / "rng_state.npz"
    rng.set_state(state)
    rng.save_state_to_file(str(npz_path))
    rng_npz = GameRNG(seed=0, metrics=False)
    rng_npz.load_state_from_file(str(npz_path))
    seq4 = _draw_sequence(rng_npz, 20)
    assert seq1 == seq4
