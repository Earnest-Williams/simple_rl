"""Surface chunk coordinates and deterministic chunk identity.

Implements Phase 1 of ``docs/Surface Map Plan.md``: pure chunk coordinate
transforms, stable chunk identifiers, and process-stable seed derivation for
the character-scale playable surface layer.

The surface play space is divided into square chunks of configurable size
(``S_c``, default 64 character-scale tiles). Chunks are stacked 2D planes:
the global vertical coordinate maps directly onto the vertical chunk
coordinate (``C_z = Z_g``) and the local vertical coordinate is always zero
(``Z_l = 0``). ``C_z`` levels are reserved for major structural plane
changes such as cave layers, dungeon levels, or separate building floors.
Tactical verticality inside one viewport (bridges, rooftops, low walls) is
expressed per tile via a local elevation offset ``H_t`` stored on tiles,
never through chunk coordinates.

All functions are pure and deterministic: no Python ``hash()``, no
randomness, no global state, no filesystem access.
"""

from __future__ import annotations

import hashlib
from typing import Final, NamedTuple

DEFAULT_CHUNK_SIZE: Final[int] = 64
"""Default chunk dimension ``S_c`` in character-scale tiles."""

CHUNK_ID_PREFIX: Final[str] = "chunk"

_CHUNK_SEED_MODULUS: Final[int] = 2**32


class ChunkCoord(NamedTuple):
    """Chunk-space coordinate of one stacked 2D plane chunk."""

    cx: int
    cy: int
    cz: int


class LocalCoord(NamedTuple):
    """Tile offset within its chunk; ``z`` is always 0 on stacked planes."""

    x: int
    y: int
    z: int


class GlobalCoord(NamedTuple):
    """Absolute character-scale tile coordinate."""

    x: int
    y: int
    z: int


def _validate_chunk_size(chunk_size: int) -> None:
    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")


def chunk_coordinates(
    x: int,
    y: int,
    z: int = 0,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> ChunkCoord:
    """Return the chunk coordinate containing global tile ``(x, y, z)``.

    Uses floor division so negative global coordinates map to the chunk on
    the correct side of the origin (``-1 // 64 == -1``).
    """
    _validate_chunk_size(chunk_size)
    return ChunkCoord(cx=x // chunk_size, cy=y // chunk_size, cz=z)


def global_to_local(
    x: int,
    y: int,
    z: int = 0,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> LocalCoord:
    """Return the local tile offset of ``(x, y, z)`` within its chunk.

    The global ``z`` selects the stacked plane; the local vertical
    coordinate is always 0 because each chunk is a single logical layer.
    """
    _validate_chunk_size(chunk_size)
    return LocalCoord(x=x % chunk_size, y=y % chunk_size, z=0)


def local_to_global(
    cx: int,
    cy: int,
    cz: int,
    local_x: int,
    local_y: int,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> GlobalCoord:
    """Return the global tile coordinate of a chunk-local tile.

    Raises ``ValueError`` if a local offset falls outside the chunk.
    """
    _validate_chunk_size(chunk_size)
    if not 0 <= local_x < chunk_size:
        raise ValueError(f"local_x must be in [0, {chunk_size}), got {local_x}")
    if not 0 <= local_y < chunk_size:
        raise ValueError(f"local_y must be in [0, {chunk_size}), got {local_y}")
    return GlobalCoord(
        x=cx * chunk_size + local_x,
        y=cy * chunk_size + local_y,
        z=cz,
    )


def chunk_id(cx: int, cy: int, cz: int) -> str:
    """Return the stable chunk identifier string, e.g. ``chunk_3_-2_0``."""
    return f"{CHUNK_ID_PREFIX}_{cx}_{cy}_{cz}"


def chunk_id_for_tile(
    x: int,
    y: int,
    z: int = 0,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> str:
    """Return the chunk identifier containing global tile ``(x, y, z)``."""
    coord = chunk_coordinates(x, y, z, chunk_size=chunk_size)
    return chunk_id(cx=coord.cx, cy=coord.cy, cz=coord.cz)


def derive_chunk_seed(
    world_seed: int | str,
    cx: int,
    cy: int,
    cz: int,
    *,
    content_version: int,
    generation_version: int,
) -> int:
    """Return the process-stable generation seed for a chunk.

    Derives a 32-bit seed from SHA-256 over the world seed, the chunk
    coordinates, and the content/generator version identifiers. Identical
    inputs always produce identical seeds in every process; any changed
    input produces a different seed. This deliberately avoids Python's
    process-randomized ``hash()`` (see ``docs/ADR/0001-canonical-rng.md``
    for the repo-wide determinism policy).
    """
    seed_bytes = (
        f"{world_seed}:{cx}:{cy}:{cz}"
        f":{content_version}:{generation_version}"
    ).encode("utf-8")
    return int(hashlib.sha256(seed_bytes).hexdigest(), 16) % _CHUNK_SEED_MODULUS


__all__ = [
    "CHUNK_ID_PREFIX",
    "ChunkCoord",
    "DEFAULT_CHUNK_SIZE",
    "GlobalCoord",
    "LocalCoord",
    "chunk_coordinates",
    "chunk_id",
    "chunk_id_for_tile",
    "derive_chunk_seed",
    "global_to_local",
    "local_to_global",
]
