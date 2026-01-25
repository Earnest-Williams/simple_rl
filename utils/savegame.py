from __future__ import annotations

import base64
import datetime
import gzip
import io
import itertools
import sys
from pathlib import Path
from typing import Any

import numpy as np
import orjson
import polars as pl

SchemaVersion = str


class SaveGameSerializationError(Exception):
    """Raised when an object cannot be serialized to the save format."""

    pass


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert Python/NumPy objects to JSON-serializable forms.

    Preserves type information to allow lossless round-trip serialization:
    - numpy arrays are marked with __ndarray__ metadata
    - lists remain lists
    - bytes are base64-encoded with marker
    - tuples are converted to lists (with marker for restoration)

    Raises:
        SaveGameSerializationError: If object cannot be serialized
    """
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if isinstance(obj, bytes):
        return {"__bytes_b64__": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, np.ndarray):
        # Preserve numpy array type with explicit marker
        return {
            "__ndarray__": obj.tolist(),
            "dtype": str(obj.dtype),
            "shape": list(obj.shape),
        }
    if isinstance(obj, dict):
        # Optimize: only convert key to string if not already a string
        return {
            (k if isinstance(k, str) else str(k)): _make_json_serializable(v)
            for k, v in obj.items()
        }
    if isinstance(obj, tuple):
        # Mark tuples for restoration
        return {"__tuple__": [_make_json_serializable(v) for v in obj]}
    if isinstance(obj, list):
        return [_make_json_serializable(v) for v in obj]

    # Explicit error instead of silent None conversion
    raise SaveGameSerializationError(
        f"Cannot serialize object of type {type(obj).__name__}: {repr(obj)[:100]}"
    )


def _restore_numpy_if_list_like(obj: Any) -> Any:
    """Restore objects from JSON-serializable forms with proper type preservation.

    Uses explicit markers to distinguish:
    - numpy arrays (__ndarray__ marker)
    - bytes (__bytes_b64__ marker)
    - tuples (__tuple__ marker)
    - plain lists (no marker, stay as lists)

    This ensures lossless round-trip serialization.
    """
    if isinstance(obj, dict):
        # Check for special type markers
        if "__bytes_b64__" in obj and len(obj) == 1:
            return base64.b64decode(obj["__bytes_b64__"])

        if "__ndarray__" in obj and "dtype" in obj and "shape" in obj:
            # Restore numpy array with original dtype and shape
            arr = np.array(obj["__ndarray__"], dtype=obj["dtype"])
            return arr.reshape(obj["shape"])

        if "__tuple__" in obj and len(obj) == 1:
            # Restore tuple
            return tuple(_restore_numpy_if_list_like(v) for v in obj["__tuple__"])

        # Regular dict - process recursively
        return {k: _restore_numpy_if_list_like(v) for k, v in obj.items()}

    if isinstance(obj, list):
        # Lists stay as lists - process elements recursively
        return [_restore_numpy_if_list_like(v) for v in obj]

    return obj


def _parse_major_version(schema_version: SchemaVersion) -> int:
    """Extract major version (leading integer) from semver-like string."""
    if len(schema_version) == 0:
        raise ValueError("Invalid schema_version ''")
    major_str = "".join(itertools.takewhile(str.isdigit, schema_version))
    if not major_str:
        raise ValueError(f"Invalid schema_version '{schema_version}'")
    return int(major_str)


def save_game_state(
    path: Path | str,
    *,
    mobs_df: pl.DataFrame,
    world_map_data: dict[str, Any],
    global_state: dict[str, Any],
    rng_state: dict[str, Any],
    schema_version: SchemaVersion = "1.0.0",
    compress_ipc: bool = False,
) -> None:
    """Save complete game state to a single JSON file.

    Args:
        path: Destination path for save file.
        mobs_df: Polars DataFrame with mobs/entities state.
        world_map_data: Mapping of world arrays/values (NumPy arrays permitted).
        global_state: Arbitrary JSON-serializable global state (player pos, flags).
        rng_state: RNG state representation.
        schema_version: Save schema version. Bump major on breaking changes.
        compress_ipc: If True, gzips the IPC bytes before base64 encoding.

    Raises:
        SaveGameSerializationError: If any data cannot be serialized.
    """
    dest = Path(path)

    # Serialize DataFrame to IPC format
    # Note: Using BytesIO is necessary as write_ipc needs a file-like object
    buf = io.BytesIO()
    mobs_df.write_ipc(buf)
    ipc_bytes = buf.getvalue()

    # Conditionally compress (creates a copy if enabled)
    if compress_ipc:
        ipc_bytes = gzip.compress(ipc_bytes, compresslevel=6)
        ipc_compressed = True
    else:
        ipc_compressed = False

    # Base64 encode for JSON embedding
    ipc_b64 = base64.b64encode(ipc_bytes).decode("ascii")

    # Serialize complex objects (may raise SaveGameSerializationError)
    json_world = _make_json_serializable(world_map_data)
    json_global = _make_json_serializable(global_state)
    json_rng = _make_json_serializable(rng_state)

    created_iso = datetime.datetime.now(datetime.UTC).isoformat()
    payload: dict[str, Any] = {
        "schema_version": schema_version,
        "created_iso": created_iso,
        "polars_version": pl.__version__,
        "python_version": sys.version.splitlines()[0],
        "mobs_df_ipc_b64": ipc_b64,
        "mobs_df_ipc_compressed": ipc_compressed,
        "world_map_data": json_world,
        "global_state": json_global,
        "rng_state": json_rng,
    }

    # Atomic write: write to temp file then rename
    temp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        temp.write_bytes(orjson.dumps(payload))
        temp.replace(dest)
    except Exception:
        # Clean up temp file if write/rename fails
        if temp.exists():
            temp.unlink()
        raise


def load_game_state(
    path: Path | str,
    expected_schema_version: SchemaVersion = "1.0.0",
) -> tuple[pl.DataFrame, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load a save written by `save_game_state`.

    Performs a major-version check to avoid silently loading incompatible saves.

    Args:
        path: Path to the save file to load.
        expected_schema_version: Expected schema version (major version must match).

    Returns:
        (mobs_df, world_map_data, global_state, rng_state)

    Raises:
        FileNotFoundError: If save file doesn't exist.
        ValueError: If save file is corrupted or has incompatible schema.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Save file not found: {src}")

    # Load and parse JSON
    try:
        raw = src.read_bytes()
        state = orjson.loads(raw)
    except orjson.JSONDecodeError as e:
        raise ValueError(f"Save file is not valid JSON: {e}") from e

    if not isinstance(state, dict):
        raise ValueError("Save file content must be a JSON object.")
    if "schema_version" not in state:
        raise ValueError("Save file missing 'schema_version' key.")

    # Validate schema version
    file_ver = state["schema_version"]
    if not isinstance(file_ver, str):
        raise ValueError("Save file 'schema_version' must be a string.")
    if _parse_major_version(file_ver) != _parse_major_version(expected_schema_version):
        raise ValueError(
            "Incompatible save schema version: "
            f"file={file_ver} expected={expected_schema_version}"
        )

    # Decode and decompress IPC data
    ipc_b64 = state.get("mobs_df_ipc_b64")
    if not isinstance(ipc_b64, str):
        raise ValueError("Save file 'mobs_df_ipc_b64' must be a string.")

    try:
        ipc_bytes = base64.b64decode(ipc_b64)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding in 'mobs_df_ipc_b64': {e}") from e

    if state.get("mobs_df_ipc_compressed", False):
        try:
            ipc_bytes = gzip.decompress(ipc_bytes)
        except gzip.BadGzipFile as e:
            raise ValueError(f"Corrupted gzip data in save file: {e}") from e

    # Load Polars DataFrame with validation
    try:
        mobs_df = pl.read_ipc(io.BytesIO(ipc_bytes))
    except Exception as e:
        raise ValueError(
            "Failed to load Polars DataFrame from IPC data. "
            "File may be corrupted or created with incompatible Polars version. "
            f"Error: {e}"
        ) from e

    # Load and validate other state components
    raw_world = state.get("world_map_data", {})
    raw_global = state.get("global_state", {})
    raw_rng = state.get("rng_state", {})

    if not isinstance(raw_world, dict):
        raise ValueError("Save file 'world_map_data' must be an object.")
    if not isinstance(raw_global, dict):
        raise ValueError("Save file 'global_state' must be an object.")
    if not isinstance(raw_rng, dict):
        raise ValueError("Save file 'rng_state' must be an object.")

    # Restore Python/NumPy objects from JSON representations
    world_map_data = _restore_numpy_if_list_like(raw_world)
    global_state = _restore_numpy_if_list_like(raw_global)
    rng_state = _restore_numpy_if_list_like(raw_rng)

    # Final type validation (in case restoration changed types unexpectedly)
    if not isinstance(world_map_data, dict):
        raise ValueError("Restored 'world_map_data' is not a dict.")
    if not isinstance(global_state, dict):
        raise ValueError("Restored 'global_state' is not a dict.")
    if not isinstance(rng_state, dict):
        raise ValueError("Restored 'rng_state' is not a dict.")

    return mobs_df, world_map_data, global_state, rng_state
