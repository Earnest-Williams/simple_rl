from __future__ import annotations

from pathlib import Path

from worldgen.chunk_cache import (
    chunk_cache_path,
    compute_chunk_cache_key,
    ensure_chunk_cache_dir,
)
from worldgen.metadata import build_world_meta


def test_chunk_cache_key_is_stable_and_parameter_sensitive() -> None:
    meta = build_world_meta(
        world_seed=123,
        n=8,
        planet_radius_m=1_000.0,
        elev_quantum_m=0.5,
        global_tunables_hash="global",
        chunk_tunables_hash="chunk",
    )

    first_key = compute_chunk_cache_key(
        meta,
        face=1,
        i0=2,
        j0=3,
        width=4,
        height=5,
        detail_cells_per_sim=6,
    )
    second_key = compute_chunk_cache_key(
        meta,
        face=1,
        i0=2,
        j0=3,
        width=4,
        height=5,
        detail_cells_per_sim=6,
    )
    changed_key = compute_chunk_cache_key(
        meta,
        face=1,
        i0=2,
        j0=3,
        width=4,
        height=5,
        detail_cells_per_sim=7,
    )

    assert first_key == second_key
    assert first_key.startswith("sha256:")
    assert first_key != changed_key


def test_chunk_cache_path_and_directory_creation(tmp_path: Path) -> None:
    ensure_chunk_cache_dir(tmp_path)

    cache_dir = tmp_path / "chunk_cache"
    path = chunk_cache_path(tmp_path, key="sha256:abc")

    assert cache_dir.is_dir()
    assert path == cache_dir / "sha256:abc.json"
