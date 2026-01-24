from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict

import orjson

from worldgen.metadata import WorldMeta


def compute_chunk_cache_key(
    meta: WorldMeta,
    *,
    face: int,
    i0: int,
    j0: int,
    width: int,
    height: int,
    detail_cells_per_sim: int,
) -> str:
    """Return a stable sha256 cache key for a chunk request."""
    payload: Dict[str, object] = {
        "global_tunables_hash": meta.global_tunables_hash,
        "chunk_tunables_hash": meta.chunk_tunables_hash,
        "world_seed": int(meta.world_seed),
        "N": int(meta.N),
        "face": int(face),
        "i0": int(i0),
        "j0": int(j0),
        "width": int(width),
        "height": int(height),
        "detail_cells_per_sim": int(detail_cells_per_sim),
    }
    blob: bytes = orjson.dumps(payload, option=orjson.OPT_SORT_KEYS)
    digest: str = hashlib.sha256(blob).hexdigest()
    return f"sha256:{digest}"


def chunk_cache_path(out_dir: Path, *, key: str) -> Path:
    return out_dir / "chunk_cache" / f"{key}.json"


def ensure_chunk_cache_dir(out_dir: Path) -> None:
    cache_dir: Path = out_dir / "chunk_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
