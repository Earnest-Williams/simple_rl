from __future__ import annotations

import base64
import datetime
import io
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import orjson
import polars as pl

SchemaVersion = str


def _make_json_serializable(obj: Any) -> Any:
    """Recursively convert non-JSON types to JSON-safe forms."""
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, bytes):
        encoded = base64.b64encode(obj).decode("ascii")
        return {"__bytes_b64__": encoded}
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (np.integer, np.floating, np.bool_)):
        return obj.item()
    if isinstance(obj, dict):
        return {str(k): _make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_json_serializable(v) for v in obj]
    return str(obj)


def _restore_numpy_if_list_like(obj: Any) -> Any:
    """Restore list-like values to numpy arrays when appropriate."""
    if isinstance(obj, dict):
        if "__bytes_b64__" in obj and len(obj) == 1:
            encoded = obj["__bytes_b64__"]
            if isinstance(encoded, str):
                return base64.b64decode(encoded)
        return {k: _restore_numpy_if_list_like(v) for k, v in obj.items()}
    if isinstance(obj, list):
        if len(obj) == 0:
            return np.array([])
        first = obj[0]
        if isinstance(first, dict):
            return [_restore_numpy_if_list_like(v) for v in obj]
        try:
            return np.array(obj)
        except (TypeError, ValueError):
            return [_restore_numpy_if_list_like(v) for v in obj]
    return obj


def _parse_major_version(schema_version: SchemaVersion) -> int:
    """Return the major version number for a semver-like string."""
    parts = schema_version.split(".")
    if len(parts) == 0:
        raise ValueError(f"Invalid schema_version '{schema_version}'")
    major = parts[0]
    if not major.isdigit():
        raise ValueError(f"Invalid schema_version '{schema_version}'")
    return int(major)


def save_game_state(
    path: Path | str,
    *,
    mobs_df: pl.DataFrame,
    world_map_data: Dict[str, Any],
    global_state: Dict[str, Any],
    rng_state: Dict[str, Any],
    schema_version: SchemaVersion = "1.0.0",
) -> None:
    """Save the complete game state to disk in a JSON wrapper."""
    dest = Path(path)

    buf = io.BytesIO()
    mobs_df.write_ipc(buf)
    ipc_bytes = buf.getvalue()
    ipc_b64 = base64.b64encode(ipc_bytes).decode("ascii")

    json_world = _make_json_serializable(world_map_data)
    json_global = _make_json_serializable(global_state)
    json_rng = _make_json_serializable(rng_state)

    created_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    payload: Dict[str, Any] = {
        "schema_version": schema_version,
        "created_iso": created_iso,
        "mobs_df_ipc_b64": ipc_b64,
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
    """Load game state saved by save_game_state with schema version checking."""
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"Save file not found: {src}")

    raw = src.read_bytes()
    state = orjson.loads(raw)

    if not isinstance(state, dict):
        raise ValueError("Save file content must be a JSON object.")
    if "schema_version" not in state:
        raise ValueError("Save file missing 'schema_version' key.")
    if "mobs_df_ipc_b64" not in state:
        raise ValueError("Save file missing 'mobs_df_ipc_b64' key.")

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
    mobs_df = pl.read_ipc(io.BytesIO(ipc_bytes))

    raw_world = state.get("world_map_data", {})
    raw_global = state.get("global_state", {})
    raw_rng = state.get("rng_state", {})

    if isinstance(raw_world, dict):
        world_map_data = {k: _restore_numpy_if_list_like(v) for k, v in raw_world.items()}
    else:
        world_map_data = raw_world
    if isinstance(raw_global, dict):
        global_state = _restore_numpy_if_list_like(raw_global)
    else:
        global_state = raw_global
    if isinstance(raw_rng, dict):
        rng_state = _restore_numpy_if_list_like(raw_rng)
    else:
        rng_state = raw_rng

    if not isinstance(world_map_data, dict):
        raise ValueError("Save file 'world_map_data' must be an object.")
    if not isinstance(global_state, dict):
        raise ValueError("Save file 'global_state' must be an object.")
    if not isinstance(rng_state, dict):
        raise ValueError("Save file 'rng_state' must be an object.")

    return mobs_df, world_map_data, global_state, rng_state
