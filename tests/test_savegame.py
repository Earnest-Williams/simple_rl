"""Comprehensive tests for utils/savegame.py module.

Tests correctness of serialization/deserialization and proper error handling.
"""
from __future__ import annotations

import base64
import gzip
import io
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import polars as pl
import pytest

from utils.savegame import (
    SaveGameSerializationError,
    _make_json_serializable,
    _restore_numpy_if_list_like,
    load_game_state,
    save_game_state,
)


class TestRoundTripSerialization:
    """Test that serialization preserves types correctly."""

    def test_primitives(self) -> None:
        """Primitives should round-trip perfectly."""
        obj = {
            "str": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None,
        }
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)
        assert restored == obj

    def test_numpy_scalars(self) -> None:
        """NumPy scalars should convert to Python types."""
        obj = {
            "np_int": np.int64(42),
            "np_float": np.float32(3.14),
            "np_bool": np.bool_(True),
        }
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)
        assert restored["np_int"] == 42
        assert isinstance(restored["np_int"], int)
        assert abs(restored["np_float"] - 3.14) < 0.01
        assert isinstance(restored["np_float"], float)
        assert restored["np_bool"] is True
        assert isinstance(restored["np_bool"], bool)

    def test_lists_stay_lists(self) -> None:
        """Lists should remain lists, not become numpy arrays."""
        obj = {"simple_list": [1, 2, 3], "empty_list": [], "nested_list": [[1, 2], [3, 4]]}
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["simple_list"], list)
        assert restored["simple_list"] == [1, 2, 3]

        assert isinstance(restored["empty_list"], list)
        assert restored["empty_list"] == []

        assert isinstance(restored["nested_list"], list)
        assert restored["nested_list"] == [[1, 2], [3, 4]]

    def test_numpy_arrays_stay_arrays(self) -> None:
        """NumPy arrays should remain arrays with correct dtype."""
        obj = {
            "int_array": np.array([1, 2, 3], dtype=np.int32),
            "float_array": np.array([1.5, 2.5], dtype=np.float64),
            "2d_array": np.array([[1, 2], [3, 4]], dtype=np.int64),
            "empty_array": np.array([]),
        }
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["int_array"], np.ndarray)
        assert restored["int_array"].dtype == np.int32
        np.testing.assert_array_equal(restored["int_array"], np.array([1, 2, 3]))

        assert isinstance(restored["float_array"], np.ndarray)
        assert restored["float_array"].dtype == np.float64
        np.testing.assert_array_almost_equal(restored["float_array"], np.array([1.5, 2.5]))

        assert isinstance(restored["2d_array"], np.ndarray)
        assert restored["2d_array"].shape == (2, 2)
        np.testing.assert_array_equal(restored["2d_array"], np.array([[1, 2], [3, 4]]))

        assert isinstance(restored["empty_array"], np.ndarray)
        assert len(restored["empty_array"]) == 0

    def test_bytes_roundtrip(self) -> None:
        """Bytes should be preserved."""
        obj = {"data": b"hello\x00world"}
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["data"], bytes)
        assert restored["data"] == b"hello\x00world"

    def test_tuples_roundtrip(self) -> None:
        """Tuples should be preserved."""
        obj = {"coords": (10, 20, 30), "empty": ()}
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["coords"], tuple)
        assert restored["coords"] == (10, 20, 30)

        assert isinstance(restored["empty"], tuple)
        assert restored["empty"] == ()

    def test_nested_structures(self) -> None:
        """Complex nested structures should preserve types."""
        obj = {
            "level1": {
                "level2": {
                    "list": [1, 2, 3],
                    "array": np.array([4, 5, 6]),
                    "nested_list": [[7, 8], [9, 10]],
                }
            }
        }
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["level1"]["level2"]["list"], list)
        assert isinstance(restored["level1"]["level2"]["array"], np.ndarray)
        assert isinstance(restored["level1"]["level2"]["nested_list"], list)

    def test_list_of_dicts(self) -> None:
        """Lists containing dicts should stay as lists."""
        obj = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["items"], list)
        assert len(restored["items"]) == 3
        assert all(isinstance(item, dict) for item in restored["items"])
        assert restored["items"][0]["id"] == 1

    def test_mixed_list_types(self) -> None:
        """Lists with mixed types should be preserved."""
        obj = {"mixed": [1, "two", 3.0, None]}
        serialized = _make_json_serializable(obj)
        restored = _restore_numpy_if_list_like(serialized)

        assert isinstance(restored["mixed"], list)
        assert restored["mixed"] == [1, "two", 3.0, None]


class TestErrorHandling:
    """Test that proper errors are raised for invalid inputs."""

    def test_unserializable_object_raises_error(self) -> None:
        """Non-serializable objects should raise SaveGameSerializationError."""

        class CustomClass:
            pass

        obj = {"custom": CustomClass()}

        with pytest.raises(SaveGameSerializationError) as exc_info:
            _make_json_serializable(obj)

        assert "CustomClass" in str(exc_info.value)

    def test_corrupted_json_raises_clear_error(self, tmp_path: Path) -> None:
        """Corrupted JSON should raise clear error."""
        save_path = tmp_path / "corrupted.json"
        save_path.write_bytes(b"not valid json {{{")

        with pytest.raises(ValueError) as exc_info:
            load_game_state(save_path)

        assert "not valid JSON" in str(exc_info.value)

    def test_invalid_base64_raises_clear_error(self, tmp_path: Path) -> None:
        """Invalid base64 in IPC field should raise clear error."""
        save_path = tmp_path / "bad_b64.json"
        payload = {
            "schema_version": "1.0.0",
            "mobs_df_ipc_b64": "not valid base64!!!",
            "mobs_df_ipc_compressed": False,
            "world_map_data": {},
            "global_state": {},
            "rng_state": {},
        }
        save_path.write_bytes(orjson.dumps(payload))

        with pytest.raises(ValueError) as exc_info:
            load_game_state(save_path)

        assert "base64" in str(exc_info.value).lower()

    def test_corrupted_gzip_raises_clear_error(self, tmp_path: Path) -> None:
        """Corrupted gzip data should raise clear error."""
        save_path = tmp_path / "bad_gzip.json"
        payload = {
            "schema_version": "1.0.0",
            "mobs_df_ipc_b64": base64.b64encode(b"not gzip data").decode("ascii"),
            "mobs_df_ipc_compressed": True,
            "world_map_data": {},
            "global_state": {},
            "rng_state": {},
        }
        save_path.write_bytes(orjson.dumps(payload))

        with pytest.raises(ValueError) as exc_info:
            load_game_state(save_path)

        assert "gzip" in str(exc_info.value).lower()

    def test_invalid_ipc_raises_clear_error(self, tmp_path: Path) -> None:
        """Invalid IPC data should raise clear error."""
        save_path = tmp_path / "bad_ipc.json"
        payload = {
            "schema_version": "1.0.0",
            "mobs_df_ipc_b64": base64.b64encode(b"not ipc data").decode("ascii"),
            "mobs_df_ipc_compressed": False,
            "world_map_data": {},
            "global_state": {},
            "rng_state": {},
        }
        save_path.write_bytes(orjson.dumps(payload))

        with pytest.raises(ValueError) as exc_info:
            load_game_state(save_path)

        assert "Polars DataFrame" in str(exc_info.value) or "IPC" in str(exc_info.value)

    def test_missing_file_raises_clear_error(self, tmp_path: Path) -> None:
        """Missing file should raise FileNotFoundError."""
        save_path = tmp_path / "doesnt_exist.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            load_game_state(save_path)

        assert "not found" in str(exc_info.value).lower()

    def test_schema_version_mismatch_raises_error(self, tmp_path: Path) -> None:
        """Incompatible schema version should raise error."""
        save_path = tmp_path / "v2.json"
        df = pl.DataFrame({"id": [1, 2]})

        save_game_state(
            save_path,
            mobs_df=df,
            world_map_data={},
            global_state={},
            rng_state={},
            schema_version="2.0.0",
        )

        with pytest.raises(ValueError) as exc_info:
            load_game_state(save_path, expected_schema_version="1.0.0")

        assert "Incompatible" in str(exc_info.value)
        assert "2.0.0" in str(exc_info.value)


class TestFullRoundTrip:
    """Test complete save/load cycle."""

    def test_basic_roundtrip(self, tmp_path: Path) -> None:
        """Basic save and load should work."""
        save_path = tmp_path / "game.sav"

        mobs_df = pl.DataFrame(
            {
                "id": [1, 2, 3],
                "x": [10, 20, 30],
                "y": [100, 200, 300],
                "health": [100.0, 75.5, 50.0],
            }
        )

        world_map_data = {
            "grid": np.array([[1, 2], [3, 4]], dtype=np.int32),
            "tiles": ["grass", "dirt", "stone"],
        }

        global_state = {"player_pos": [5, 10], "turn": 42}

        rng_state = {"seed": 12345}

        save_game_state(
            save_path,
            mobs_df=mobs_df,
            world_map_data=world_map_data,
            global_state=global_state,
            rng_state=rng_state,
        )

        assert save_path.exists()

        loaded_mobs, loaded_world, loaded_global, loaded_rng = load_game_state(save_path)

        # Check DataFrame
        assert loaded_mobs.shape == mobs_df.shape
        assert loaded_mobs["id"].to_list() == [1, 2, 3]

        # Check world map data
        assert isinstance(loaded_world["grid"], np.ndarray)
        np.testing.assert_array_equal(loaded_world["grid"], np.array([[1, 2], [3, 4]]))
        assert isinstance(loaded_world["tiles"], list)
        assert loaded_world["tiles"] == ["grass", "dirt", "stone"]

        # Check global state
        assert isinstance(loaded_global["player_pos"], list)
        assert loaded_global["player_pos"] == [5, 10]
        assert loaded_global["turn"] == 42

        # Check RNG state
        assert loaded_rng["seed"] == 12345

    def test_roundtrip_with_compression(self, tmp_path: Path) -> None:
        """Save/load with compression should work."""
        save_path = tmp_path / "game_compressed.sav"

        mobs_df = pl.DataFrame({"id": list(range(100)), "value": list(range(100))})

        save_game_state(
            save_path,
            mobs_df=mobs_df,
            world_map_data={},
            global_state={},
            rng_state={},
            compress_ipc=True,
        )

        loaded_mobs, _, _, _ = load_game_state(save_path)

        assert loaded_mobs.shape == mobs_df.shape
        assert loaded_mobs["id"].to_list() == list(range(100))

    def test_complex_nested_data(self, tmp_path: Path) -> None:
        """Complex nested structures should round-trip correctly."""
        save_path = tmp_path / "complex.sav"

        mobs_df = pl.DataFrame({"id": [1]})

        world_map_data = {
            "zones": {
                "zone1": {
                    "tiles": np.array([[1, 2, 3], [4, 5, 6]]),
                    "metadata": {"name": "Forest", "discovered": True},
                },
                "zone2": {
                    "tiles": np.array([[7, 8], [9, 10]]),
                    "metadata": {"name": "Cave", "discovered": False},
                },
            },
            "special_locations": [(10, 20), (30, 40)],
        }

        global_state = {
            "inventory": [
                {"item": "sword", "count": 1},
                {"item": "potion", "count": 5},
            ],
            "stats": np.array([10, 20, 30], dtype=np.int64),
        }

        save_game_state(
            save_path,
            mobs_df=mobs_df,
            world_map_data=world_map_data,
            global_state=global_state,
            rng_state={},
        )

        _, loaded_world, loaded_global, _ = load_game_state(save_path)

        # Check nested numpy arrays
        assert isinstance(loaded_world["zones"]["zone1"]["tiles"], np.ndarray)
        np.testing.assert_array_equal(
            loaded_world["zones"]["zone1"]["tiles"], np.array([[1, 2, 3], [4, 5, 6]])
        )

        # Check nested dicts
        assert loaded_world["zones"]["zone1"]["metadata"]["name"] == "Forest"

        # Check tuples
        assert isinstance(loaded_world["special_locations"], list)
        assert all(isinstance(loc, tuple) for loc in loaded_world["special_locations"])
        assert loaded_world["special_locations"][0] == (10, 20)

        # Check list of dicts
        assert isinstance(loaded_global["inventory"], list)
        assert loaded_global["inventory"][0]["item"] == "sword"

        # Check arrays in global state
        assert isinstance(loaded_global["stats"], np.ndarray)
        np.testing.assert_array_equal(loaded_global["stats"], np.array([10, 20, 30]))

    def test_empty_structures(self, tmp_path: Path) -> None:
        """Empty lists and arrays should be handled correctly."""
        save_path = tmp_path / "empty.sav"

        mobs_df = pl.DataFrame({"id": []})

        world_map_data = {
            "empty_list": [],
            "empty_array": np.array([]),
            "empty_dict": {},
        }

        save_game_state(
            save_path,
            mobs_df=mobs_df,
            world_map_data=world_map_data,
            global_state={},
            rng_state={},
        )

        _, loaded_world, _, _ = load_game_state(save_path)

        assert isinstance(loaded_world["empty_list"], list)
        assert len(loaded_world["empty_list"]) == 0

        assert isinstance(loaded_world["empty_array"], np.ndarray)
        assert len(loaded_world["empty_array"]) == 0

        assert isinstance(loaded_world["empty_dict"], dict)
        assert len(loaded_world["empty_dict"]) == 0

    def test_atomic_write_cleanup_on_error(self, tmp_path: Path) -> None:
        """If write fails, temp file should be cleaned up."""
        save_path = tmp_path / "test.sav"

        # Create a read-only directory to force write failure
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_path = readonly_dir / "test.sav"

        # Make directory read-only (this might not work on all systems)
        try:
            readonly_dir.chmod(0o444)

            mobs_df = pl.DataFrame({"id": [1]})

            with pytest.raises((PermissionError, OSError)):
                save_game_state(
                    readonly_path,
                    mobs_df=mobs_df,
                    world_map_data={},
                    global_state={},
                    rng_state={},
                )

            # Cleanup should have happened - no .tmp files
            tmp_files = list(readonly_dir.glob("*.tmp"))
            assert len(tmp_files) == 0

        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)


class TestPerformanceOptimizations:
    """Test that performance optimizations are in place."""

    def test_string_keys_not_reconverted(self) -> None:
        """String keys should not be unnecessarily converted."""
        obj = {"already_string": 123, 456: "int_key"}
        serialized = _make_json_serializable(obj)

        # Both keys should be strings in output
        assert "already_string" in serialized
        assert "456" in serialized

    def test_compression_reduces_file_size(self, tmp_path: Path) -> None:
        """Compression should reduce file size for large DataFrames."""
        # Create a large DataFrame with repetitive data (compresses well)
        mobs_df = pl.DataFrame(
            {
                "id": list(range(1000)),
                "type": ["monster"] * 1000,  # Repetitive
                "x": [0] * 1000,  # Very repetitive
                "y": [0] * 1000,
            }
        )

        uncompressed_path = tmp_path / "uncompressed.sav"
        compressed_path = tmp_path / "compressed.sav"

        save_game_state(
            uncompressed_path,
            mobs_df=mobs_df,
            world_map_data={},
            global_state={},
            rng_state={},
            compress_ipc=False,
        )

        save_game_state(
            compressed_path,
            mobs_df=mobs_df,
            world_map_data={},
            global_state={},
            rng_state={},
            compress_ipc=True,
        )

        uncompressed_size = uncompressed_path.stat().st_size
        compressed_size = compressed_path.stat().st_size

        # Compressed should be smaller (at least 10% smaller for this repetitive data)
        assert compressed_size < uncompressed_size * 0.9
