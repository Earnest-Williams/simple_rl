#!/usr/bin/env python
"""Standalone test script to verify savegame.py fixes.

This can be run directly without pytest to verify the improvements work.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np
import polars as pl

from utils.savegame import (
    SaveGameSerializationError,
    _make_json_serializable,
    _restore_numpy_if_list_like,
    load_game_state,
    save_game_state,
)


def test_lists_stay_lists() -> None:
    """Verify that lists remain lists (not converted to arrays)."""
    print("Testing: Lists should stay as lists...")
    obj = {"simple_list": [1, 2, 3], "nested": [[1, 2], [3, 4]]}
    serialized = _make_json_serializable(obj)
    restored = _restore_numpy_if_list_like(serialized)

    assert isinstance(restored["simple_list"], list), "List was converted to array!"
    assert isinstance(restored["nested"], list), "Nested list was converted!"
    assert isinstance(restored["nested"][0], list), "Inner list was converted!"
    print("✓ Lists correctly preserved")


def test_arrays_stay_arrays() -> None:
    """Verify that numpy arrays remain arrays with correct dtype."""
    print("Testing: NumPy arrays should stay as arrays...")
    obj = {
        "int_array": np.array([1, 2, 3], dtype=np.int32),
        "float_array": np.array([1.5, 2.5], dtype=np.float64),
    }
    serialized = _make_json_serializable(obj)
    restored = _restore_numpy_if_list_like(serialized)

    assert isinstance(restored["int_array"], np.ndarray), "Array became list!"
    assert (
        restored["int_array"].dtype == np.int32
    ), f"Dtype changed: {restored['int_array'].dtype}"
    assert isinstance(restored["float_array"], np.ndarray), "Float array became list!"
    print("✓ Arrays correctly preserved with proper dtypes")


def test_error_on_unserializable() -> None:
    """Verify that unserializable objects raise errors instead of returning None."""
    print("Testing: Unserializable objects should raise errors...")

    class CustomClass:
        pass

    obj = {"data": CustomClass()}

    try:
        _make_json_serializable(obj)
        assert False, "Should have raised SaveGameSerializationError!"
    except SaveGameSerializationError as e:
        assert "CustomClass" in str(e)
        print("✓ Proper error raised for unserializable object")


def test_tuples_preserved() -> None:
    """Verify that tuples are preserved."""
    print("Testing: Tuples should be preserved...")
    obj = {"coords": (10, 20, 30)}
    serialized = _make_json_serializable(obj)
    restored = _restore_numpy_if_list_like(serialized)

    assert isinstance(restored["coords"], tuple), "Tuple became list!"
    assert restored["coords"] == (10, 20, 30)
    print("✓ Tuples correctly preserved")


def test_full_roundtrip() -> None:
    """Test complete save/load cycle."""
    print("Testing: Full save/load round-trip...")

    with tempfile.TemporaryDirectory() as tmpdir:
        save_path = Path(tmpdir) / "test.sav"

        # Create test data
        mobs_df = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "x": [10, 20, 30],
                "health": [100.0, 75.5, 50.0],
            }
        )

        world_map_data = {
            "grid": np.array([[1, 2], [3, 4]], dtype=np.int32),
            "tiles": ["grass", "dirt", "stone"],  # List should stay list
            "metadata": {"discovered": True},
        }

        global_state = {
            "player_pos": [5, 10],  # List should stay list
            "stats": np.array([10, 20, 30], dtype=np.int64),  # Array should stay array
        }

        rng_state = {"seed": 12345}

        # Save
        save_game_state(
            save_path,
            mobs_df=mobs_df,
            world_map_data=world_map_data,
            global_state=global_state,
            rng_state=rng_state,
        )

        # Load
        loaded_mobs, loaded_world, loaded_global, loaded_rng = load_game_state(
            save_path
        )

        # Verify DataFrame
        assert loaded_mobs.shape == mobs_df.shape
        assert loaded_mobs["id"].to_list() == [1, 2, 3]

        # Verify arrays stayed arrays
        assert isinstance(loaded_world["grid"], np.ndarray)
        assert loaded_world["grid"].dtype == np.int32
        np.testing.assert_array_equal(loaded_world["grid"], np.array([[1, 2], [3, 4]]))

        # Verify lists stayed lists
        assert isinstance(loaded_world["tiles"], list)
        assert loaded_world["tiles"] == ["grass", "dirt", "stone"]

        assert isinstance(loaded_global["player_pos"], list)
        assert loaded_global["player_pos"] == [5, 10]

        # Verify arrays in global state
        assert isinstance(loaded_global["stats"], np.ndarray)
        assert loaded_global["stats"].dtype == np.int64

        print("✓ Full round-trip successful with correct types")


def test_ipc_error_handling() -> None:
    """Test that invalid IPC data raises clear errors."""
    print("Testing: Invalid IPC data should raise clear errors...")

    with tempfile.TemporaryDirectory() as tmpdir:
        import base64

        import orjson

        save_path = Path(tmpdir) / "bad.sav"

        # Create save file with invalid IPC data
        payload = {
            "schema_version": "1.0.0",
            "mobs_df_ipc_b64": base64.b64encode(b"not valid IPC data").decode("ascii"),
            "mobs_df_ipc_compressed": False,
            "world_map_data": {},
            "global_state": {},
            "rng_state": {},
        }
        save_path.write_bytes(orjson.dumps(payload))

        try:
            load_game_state(save_path)
            assert False, "Should have raised ValueError!"
        except ValueError as e:
            # Check that error message is clear
            error_msg = str(e).lower()
            assert (
                "polars" in error_msg or "ipc" in error_msg or "dataframe" in error_msg
            )
            print(f"✓ Clear error message: {e}")


def main() -> int:
    """Run all tests."""
    print("=" * 60)
    print("Running standalone savegame.py verification tests")
    print("=" * 60)
    print()

    try:
        test_lists_stay_lists()
        test_arrays_stay_arrays()
        test_error_on_unserializable()
        test_tuples_preserved()
        test_full_roundtrip()
        test_ipc_error_handling()

        print()
        print("=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print()
        print("Summary of fixes verified:")
        print("  1. ✓ Lists stay as lists (not converted to arrays)")
        print("  2. ✓ Arrays stay as arrays with correct dtypes")
        print("  3. ✓ Tuples are preserved")
        print("  4. ✓ Unserializable objects raise clear errors (not silent None)")
        print("  5. ✓ Invalid IPC data raises clear error messages")
        print("  6. ✓ Full save/load cycle works correctly")
        return 0

    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"✗ TEST FAILED: {e}")
        print("=" * 60)
        return 1
    except Exception as e:
        print()
        print("=" * 60)
        print(f"✗ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
