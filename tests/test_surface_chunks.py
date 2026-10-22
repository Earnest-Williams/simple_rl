"""Tests for surface chunk coordinates and chunk identity (Phase 1).

Covers docs/Surface Map Plan.md Phase 1: 3D coordinate edge cases, chunk id
formatting, and SHA-256 seed stability.
"""

from __future__ import annotations

import pytest

from game.world.surface_chunks import (
    DEFAULT_CHUNK_SIZE,
    chunk_coordinates,
    chunk_id,
    chunk_id_for_tile,
    derive_chunk_seed,
    global_to_local,
    local_to_global,
)


def test_surface_coordinate_transforms() -> None:
    # Origin and chunk interior.
    assert chunk_coordinates(0, 0) == (0, 0, 0)
    assert global_to_local(0, 0) == (0, 0, 0)
    assert chunk_coordinates(5, 7) == (0, 0, 0)
    assert global_to_local(5, 7) == (5, 7, 0)

    # Chunk boundaries with the default 64-tile chunk size.
    assert chunk_coordinates(63, 63) == (0, 0, 0)
    assert global_to_local(63, 63) == (63, 63, 0)
    assert chunk_coordinates(64, 0) == (1, 0, 0)
    assert global_to_local(64, 0) == (0, 0, 0)
    assert chunk_coordinates(128, 191) == (2, 2, 0)

    # Negative coordinates use floor division, not truncation.
    assert chunk_coordinates(-1, 0) == (-1, 0, 0)
    assert global_to_local(-1, 0) == (DEFAULT_CHUNK_SIZE - 1, 0, 0)
    assert chunk_coordinates(-64, -1) == (-1, -1, 0)
    assert global_to_local(-64, -1) == (0, DEFAULT_CHUNK_SIZE - 1, 0)

    # Round trip: global -> chunk + local -> global is identity.
    for gx, gy in [
        (0, 0),
        (5, 7),
        (63, 63),
        (64, 64),
        (127, 1),
        (-1, -1),
        (-65, 63),
        (-128, -129),
    ]:
        coord = chunk_coordinates(gx, gy)
        local = global_to_local(gx, gy)
        assert coord.cx * DEFAULT_CHUNK_SIZE + local.x == gx
        assert coord.cy * DEFAULT_CHUNK_SIZE + local.y == gy
        restored = local_to_global(coord.cx, coord.cy, coord.cz, local.x, local.y)
        assert restored == (gx, gy, 0)

    # Configurable chunk size.
    assert chunk_coordinates(65, 5, chunk_size=16) == (4, 0, 0)
    assert global_to_local(65, 5, chunk_size=16) == (1, 5, 0)


def test_surface_z_axis_coordinates() -> None:
    # Stacked planes: C_z equals the global z, local z is always 0.
    for gz in (0, 1, 7, -3):
        coord = chunk_coordinates(10, 20, gz)
        assert coord.cz == gz
        local = global_to_local(10, 20, gz)
        assert local.z == 0
        restored = local_to_global(coord.cx, coord.cy, coord.cz, local.x, local.y)
        assert restored == (10, 20, gz)

    # Different plane layers never share a chunk identity.
    assert chunk_coordinates(10, 20, 1) != chunk_coordinates(10, 20, 2)
    assert chunk_id(0, 0, 1) != chunk_id(0, 0, 2)


def test_surface_chunk_id_format() -> None:
    assert chunk_id(3, -2, 0) == "chunk_3_-2_0"
    assert chunk_id(0, 0, 0) == "chunk_0_0_0"
    assert chunk_id(-1, -1, 4) == "chunk_-1_-1_4"
    assert chunk_id_for_tile(200, -1, 5) == "chunk_3_-1_5"
    assert chunk_id_for_tile(-1, -1) == "chunk_-1_-1_0"


def test_surface_seed_determinism() -> None:
    kwargs = {"content_version": 1, "generation_version": 2}

    # Identical inputs always produce identical seeds.
    first = derive_chunk_seed("lost-continent", 3, -2, 0, **kwargs)
    assert first == derive_chunk_seed("lost-continent", 3, -2, 0, **kwargs)
    assert first == derive_chunk_seed("lost-continent", 3, -2, 0, **kwargs)

    # Seeds are 32-bit unsigned integers.
    assert 0 <= first < 2**32

    # Any changed input changes the seed.
    assert first != derive_chunk_seed("other-world", 3, -2, 0, **kwargs)
    assert first != derive_chunk_seed("lost-continent", 4, -2, 0, **kwargs)
    assert first != derive_chunk_seed("lost-continent", 3, -1, 0, **kwargs)
    assert first != derive_chunk_seed("lost-continent", 3, -2, 1, **kwargs)
    assert first != derive_chunk_seed(
        "lost-continent", 3, -2, 0, content_version=2, generation_version=2
    )
    assert first != derive_chunk_seed(
        "lost-continent", 3, -2, 0, content_version=1, generation_version=3
    )

    # The seed formula stringifies the world seed, so int 42 and str "42"
    # interpolate identically. Document that explicitly.
    numeric = derive_chunk_seed(42, 3, -2, 0, **kwargs)
    assert numeric == derive_chunk_seed(42, 3, -2, 0, **kwargs)
    assert numeric == derive_chunk_seed("42", 3, -2, 0, **kwargs)
    assert numeric != derive_chunk_seed(43, 3, -2, 0, **kwargs)

    # Negative chunk coordinates remain deterministic and distinct.
    neg = derive_chunk_seed("lost-continent", -1, -1, -1, **kwargs)
    assert neg == derive_chunk_seed("lost-continent", -1, -1, -1, **kwargs)
    assert neg != first


def test_surface_invalid_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_coordinates(0, 0, chunk_size=0)
    with pytest.raises(ValueError):
        global_to_local(0, 0, chunk_size=-64)
    with pytest.raises(ValueError):
        local_to_global(0, 0, 0, 0, 0, chunk_size=0)


def test_surface_local_offsets_out_of_range() -> None:
    with pytest.raises(ValueError):
        local_to_global(0, 0, 0, -1, 0)
    with pytest.raises(ValueError):
        local_to_global(0, 0, 0, 0, DEFAULT_CHUNK_SIZE)
    with pytest.raises(ValueError):
        local_to_global(0, 0, 0, 0, 64, chunk_size=8)
