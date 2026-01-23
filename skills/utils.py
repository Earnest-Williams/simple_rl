"""Numba warmup and serialization utilities.

Handles JIT compilation warmup and msgpack-based save/load.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import msgpack
import numpy as np
import polars as pl

from skills.effects import (
    calculate_combat_bonuses,
    calculate_magic_bonuses,
    calculate_total_damage_multiplier,
)
from skills.progression import (
    batch_calculate_levels,
    calculate_level_from_xp,
    calculate_xp_for_level,
    calculate_xp_to_next_level,
)


def numba_warmup() -> None:
    """Warmup all Numba JIT functions to avoid first-call compilation spikes.

    Call this during game startup (dev/debug mode) or in CI.
    Production should pre-compile during build.

    Compilation overhead: ~200-500ms total for all functions.
    Subsequent calls: <1μs each.
    """
    # XP progression functions
    _ = calculate_xp_for_level(10, 0)
    _ = calculate_level_from_xp(2750, 0)
    _ = calculate_xp_to_next_level(2000, 0)

    # Batch operations
    test_xp: np.ndarray = np.array([100, 500, 1000, 2750], dtype=np.uint32)
    test_apt: np.ndarray = np.array([0, 2, -2, 0], dtype=np.int8)
    _ = batch_calculate_levels(test_xp, test_apt)

    # Combat bonuses
    _ = calculate_combat_bonuses(10, 15, 8, 12, 6, 10)
    _ = calculate_total_damage_multiplier(10, 15)

    # Magic bonuses
    _ = calculate_magic_bonuses(15, 12, 5, 1.0, 2.0)

    print("Numba JIT warmup complete (all functions compiled)")


def serialize_skills(skills_df: pl.DataFrame) -> bytes:
    """Serialize skills DataFrame to msgpack format.

    Compatible with EntityRegistry save format.
    ~10× faster than JSON, ~5× smaller than pickle.

    Args:
        skills_df: Polars DataFrame with skill data

    Returns:
        msgpack-encoded bytes
    """
    # Convert to dict of arrays for compact packing
    data: dict[str, Any] = {
        "entity_id": skills_df["entity_id"].to_numpy().astype(np.uint32),
        "skill": skills_df["skill"].to_numpy().astype(np.uint8),
        "level": skills_df["level"].to_numpy().astype(np.uint8),
        "xp": skills_df["xp"].to_numpy().astype(np.uint32),
        "aptitude": skills_df["aptitude"].to_numpy().astype(np.int8),
        "weight": skills_df["weight"].to_numpy().astype(np.float32),
        "training_state": skills_df["training_state"].to_numpy().astype(np.uint8),
        "target_level": _serialize_nullable_u8(skills_df["target_level"]),
        "usage_count": skills_df["usage_count"].to_numpy().astype(np.uint32),
    }

    packed: bytes = msgpack.packb(data, use_bin_type=True)
    return packed


def deserialize_skills(data: bytes) -> pl.DataFrame:
    """Deserialize msgpack bytes to Polars DataFrame.

    Args:
        data: msgpack-encoded skill data

    Returns:
        Reconstructed Polars DataFrame
    """
    unpacked: dict[str, Any] = msgpack.unpackb(data, raw=False)

    return pl.DataFrame(
        {
            "entity_id": pl.Series(unpacked["entity_id"], dtype=pl.UInt32),
            "skill": pl.Series(unpacked["skill"], dtype=pl.UInt8),
            "level": pl.Series(unpacked["level"], dtype=pl.UInt8),
            "xp": pl.Series(unpacked["xp"], dtype=pl.UInt32),
            "aptitude": pl.Series(unpacked["aptitude"], dtype=pl.Int8),
            "weight": pl.Series(unpacked["weight"], dtype=pl.Float32),
            "training_state": pl.Series(unpacked["training_state"], dtype=pl.UInt8),
            "target_level": _deserialize_nullable_u8(unpacked["target_level"]),
            "usage_count": pl.Series(unpacked["usage_count"], dtype=pl.UInt32),
        }
    )


def save_skills_to_file(skills_df: pl.DataFrame, save_path: Path) -> None:
    """Save skills DataFrame to file.

    Args:
        skills_df: Skills to save
        save_path: Destination file path
    """
    packed: bytes = serialize_skills(skills_df)
    save_path.write_bytes(packed)


def load_skills_from_file(save_path: Path) -> pl.DataFrame:
    """Load skills DataFrame from file.

    Args:
        save_path: Source file path

    Returns:
        Loaded skills DataFrame
    """
    packed: bytes = save_path.read_bytes()
    return deserialize_skills(packed)


def _serialize_nullable_u8(series: pl.Series) -> list[int | None]:
    """Serialize nullable UInt8 series to list.

    Args:
        series: Polars series with nullable UInt8

    Returns:
        List with None for null values
    """
    result: list[int | None] = []

    for val in series:
        if val is None:
            result.append(None)
        else:
            result.append(int(val))

    return result


def _deserialize_nullable_u8(values: list[int | None]) -> pl.Series:
    """Deserialize nullable UInt8 list to series.

    Args:
        values: List with None for null values

    Returns:
        Polars series with nullable UInt8
    """
    return pl.Series(values, dtype=pl.UInt8)


def integrate_with_registry_save(
    registry_save_dict: dict[str, Any],
    skills_df: pl.DataFrame,
) -> dict[str, Any]:
    """Integrate skills into EntityRegistry save dict.

    Args:
        registry_save_dict: Existing registry save data
        skills_df: Skills DataFrame to include

    Returns:
        Updated save dict with skills_table_v1 key
    """
    registry_save_dict["skills_table_v1"] = serialize_skills(skills_df)
    return registry_save_dict


def extract_from_registry_save(
    registry_save_dict: dict[str, Any],
) -> pl.DataFrame | None:
    """Extract skills from EntityRegistry save dict.

    Validates schema after loading to fail fast on corrupted saves.

    Args:
        registry_save_dict: Registry save data

    Returns:
        Skills DataFrame or None if not present

    Raises:
        ValueError: If loaded data doesn't match expected schema
    """
    if "skills_table_v1" not in registry_save_dict:
        return None

    skills_df = deserialize_skills(registry_save_dict["skills_table_v1"])

    # Validate schema matches expected columns
    from skills.registry_integration import SKILL_TABLE_SCHEMA

    expected_cols = set(SKILL_TABLE_SCHEMA.keys())
    actual_cols = set(skills_df.columns)

    if expected_cols != actual_cols:
        missing = expected_cols - actual_cols
        extra = actual_cols - expected_cols
        raise ValueError(f"Skills schema mismatch. Missing: {missing}, Extra: {extra}")

    return skills_df


def integrate_with_registry_save_dual_mode(
    registry_save_dict: dict[str, Any],
    skills_df: pl.DataFrame,
    legacy_skills: dict[int, dict[Any, Any]] | None = None,
) -> dict[str, Any]:
    """Integrate skills into save dict with dual-mode compatibility.

    Writes both vectorized skills_table_v1 and legacy format for
    backward compatibility during migration window.

    Args:
        registry_save_dict: Existing registry save data
        skills_df: Skills DataFrame to include
        legacy_skills: Optional legacy dict format for backward compat

    Returns:
        Updated save dict with both formats
    """
    # Always write vectorized format
    registry_save_dict["skills_table_v1"] = serialize_skills(skills_df)

    # Optionally write legacy format for clients not yet migrated
    if legacy_skills is not None:
        registry_save_dict["legacy_skills"] = legacy_skills

    return registry_save_dict


def benchmark_serialization(n_entities: int = 10000) -> None:
    """Benchmark save/load performance.

    Args:
        n_entities: Number of entities to test
    """
    import timeit

    # Generate test data
    from skills.models import Skill

    rows: list[dict[str, int | float | None]] = []

    for entity_id in range(n_entities):
        for skill in Skill:
            rows.append(
                {
                    "entity_id": entity_id,
                    "skill": skill.value,
                    "level": 10,
                    "xp": 2750,
                    "aptitude": 0,
                    "weight": 1.0,
                    "training_state": 1,
                    "target_level": None,
                    "usage_count": 100,
                }
            )

    from skills.registry_integration import SKILL_TABLE_SCHEMA

    test_df = pl.DataFrame(rows, schema=SKILL_TABLE_SCHEMA)

    # Benchmark serialization
    def run_serialize() -> None:
        _ = serialize_skills(test_df)

    serialize_time: float = timeit.timeit(run_serialize, number=10) / 10
    print(f"Serialization: {serialize_time*1000:.1f}ms for {n_entities} entities")

    # Benchmark deserialization
    packed = serialize_skills(test_df)

    def run_deserialize() -> None:
        _ = deserialize_skills(packed)

    deserialize_time: float = timeit.timeit(run_deserialize, number=10) / 10
    print(f"Deserialization: {deserialize_time*1000:.1f}ms for {n_entities} entities")

    # Size
    size_mb: float = len(packed) / (1024 * 1024)
    print(f"Size: {size_mb:.2f} MB for {n_entities} entities")


if __name__ == "__main__":
    # Run warmup
    numba_warmup()

    # Benchmark
    benchmark_serialization(n_entities=10000)
