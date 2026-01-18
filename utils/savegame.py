from __future__ import annotations

import base64
import datetime
import gzip
import io
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import orjson
import polars as pl

SchemaVersion = str


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert Python/NumPy objects to JSON-serializable forms."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if isinstance(obj, bytes):
        return {"__bytes_b64__": base64.b64encode(obj).decode("ascii")}
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    try:
        return str(obj)
    except Exception:
        return None


def _restore_numpy_if_list_like(obj: Any) -> Any:
    """Restore lists to numpy arrays for grid-like objects where appropriate.

    Heuristic:
    * If obj is a dict, process recursively.
    * If obj is a list:
        - If empty -> np.array([])
        - If first element is a dict -> return list-of-dicts (preserve)
        - Otherwise -> try np.array(list)
    * If obj is a special bytes marker -> decode.
    """
    if isinstance(obj, dict):
        if "__bytes_b64__" in obj and len(obj) == 1:
            return base64.b64decode(obj["__bytes_b64__"])
        return {k: _restore_numpy_if_list_like(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) == 0:
            return np.array([])
        first = obj[0]
        if isinstance(first, dict):
            return [_restore_numpy_if_list_like(v) for v in obj]
        try:
            return np.array(obj)
        except Exception:
            return [_restore_numpy_if_list_like(v) for v in obj]
    return obj


def _parse_major_version(schema_version: SchemaVersion) -> int:
    """Extract major version (leading integer) from semver-like string."""
    if len(schema_version) == 0:
        raise ValueError("Invalid schema_version ''")
    digits: List[str] = []
    for char in schema_version:
        if char.isdigit():
            digits.append(char)
        else:
            break
    if not digits:
        raise ValueError(f"Invalid schema_version '{schema_version}'")
    return int("".join(digits))


def save_game_state(
    path: Path | str,
    *,
    mobs_df: pl.DataFrame,
    world_map_data: Dict[str, Any],
    global_state: Dict[str, Any],
    rng_state: Dict[str, Any],
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
    """
    dest = Path(path)

    buf = io.BytesIO()
    mobs_df.write_ipc(buf)
    ipc_bytes = buf.getvalue()

    if compress_ipc:
        ipc_bytes = gzip.compress(ipc_bytes)
        ipc_compressed = True
    else:
        ipc_compressed = False

    ipc_b64 = base64.b64encode(ipc_bytes).decode("ascii")

    json_world = _make_json_serializable(world_map_data)
    json_global = _make_json_serializable(global_state)
    json_rng = _make_json_serializable(rng_state)

    payload: Dict[str, Any] = {
        "schema_version": schema_version,
        "created_iso": datetime.datetime.utcnow().isoformat() + "Z",
        "polars_version": pl.__version__,
        "python_version": sys.version.splitlines()[0],
        "mobs_df_ipc_b64": ipc_b64,
        "mobs_df_ipc_compressed": ipc_compressed,
        "world_map_data": json_world,
        "global_state": json_global,
        "rng_state": json_rng,
    }

    temp = dest.with_suffix(dest.suffix + ".tmp")
    temp.write_bytes(orjson.dumps(payload))
    temp.replace(dest)


def load_game_state(
    path: Path | str,
    expected_schema_version: SchemaVersion = "1.0.0",
) -> Tuple[pl.DataFrame, Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Load a save written by `save_game_state`.

    Performs a major-version check to avoid silently loading incompatible saves.

    Returns:
        (mobs_df, world_map_data, global_state, rng_state)
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Save file not found: {src}")
    raw = src.read_bytes()
    state = orjson.loads(raw)

    if not isinstance(state, dict):
        raise ValueError("Save file content must be a JSON object.")
    if "schema_version" not in state:
        raise ValueError("Save file missing 'schema_version' key.")

    file_ver = state["schema_version"]
    if not isinstance(file_ver, str):
        raise ValueError("Save file 'schema_version' must be a string.")
    if _parse_major_version(file_ver) != _parse_major_version(expected_schema_version):
        raise ValueError(
            "Incompatible save schema version: "
            f"file={file_ver} expected={expected_schema_version}"
        )

    ipc_b64 = state["mobs_df_ipc_b64"]
    if not isinstance(ipc_b64, str):
        raise ValueError("Save file 'mobs_df_ipc_b64' must be a string.")
    ipc_bytes = base64.b64decode(ipc_b64)
    if state.get("mobs_df_ipc_compressed", False):
        ipc_bytes = gzip.decompress(ipc_bytes)

    mobs_df = pl.read_ipc(io.BytesIO(ipc_bytes))

    raw_world = state.get("world_map_data", {})
    raw_global = state.get("global_state", {})
    raw_rng = state.get("rng_state", {})

    if not isinstance(raw_world, dict):
        raise ValueError("Save file 'world_map_data' must be an object.")
    if not isinstance(raw_global, dict):
        raise ValueError("Save file 'global_state' must be an object.")
    if not isinstance(raw_rng, dict):
        raise ValueError("Save file 'rng_state' must be an object.")

    world_map_data = {k: _restore_numpy_if_list_like(v) for k, v in raw_world.items()}
    global_state = _restore_numpy_if_list_like(raw_global)
    rng_state = _restore_numpy_if_list_like(raw_rng)

    if not isinstance(global_state, dict):
        raise ValueError("Save file 'global_state' must be an object.")
    if not isinstance(rng_state, dict):
        raise ValueError("Save file 'rng_state' must be an object.")

    return mobs_df, world_map_data, global_state, rng_state
