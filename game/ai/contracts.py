"""Shared row and perception contracts for production AI adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, TypeAlias, TypeGuard, runtime_checkable

import numpy as np
from numpy.typing import NDArray

EntityRow: TypeAlias = Mapping[str, object]
LegacyPerceptionMaps: TypeAlias = tuple[
    NDArray[np.float64], NDArray[np.float64], NDArray[np.bool_]
]
PrioritySignal: TypeAlias = tuple[
    Literal["visual", "audio", "scent", "memory"], tuple[int, int]
]


@runtime_checkable
class PerceptionFactLike(Protocol):
    """Minimal AI-facing perception fact contract used by adapters."""

    visible_targets: Sequence[Mapping[str, object]]
    heard_source: tuple[int, int] | None
    scent_position: tuple[int, int] | None
    last_known_position: tuple[int, int] | None


@runtime_checkable
class StructuredPerceptionLike(Protocol):
    """Minimal structured perception snapshot contract used by adapters."""

    entity_facts: Mapping[int, PerceptionFactLike]
    los_map: NDArray[np.bool_]
    debug_noise_map: NDArray[np.float64] | None
    debug_scent_map: NDArray[np.float64] | None


GOAPPerception: TypeAlias = StructuredPerceptionLike | LegacyPerceptionMaps | None


def row_int(row: EntityRow, key: str) -> int | None:
    """Return an integer field if present and already integer-like."""
    value = row.get(key)
    return value if isinstance(value, int) else None


def require_row_int(row: EntityRow, key: str) -> int:
    """Return a required integer field or raise a precise TypeError."""
    value = row_int(row, key)
    if value is None:
        raise TypeError(f"entity row missing integer field {key!r}")
    return value


def row_str(row: EntityRow, key: str) -> str | None:
    """Return a string field if present."""
    value = row.get(key)
    return value if isinstance(value, str) else None


def is_structured_perception(perception: object) -> TypeGuard[StructuredPerceptionLike]:
    """Return whether ``perception`` exposes the structured snapshot contract."""
    return hasattr(perception, "entity_facts") and hasattr(perception, "los_map")


def priority_signal(
    entity_id: int, perception: StructuredPerceptionLike | None
) -> PrioritySignal | None:
    """Return the highest-priority target signal for one entity."""
    if perception is None:
        return None

    fact = perception.entity_facts.get(entity_id)
    if fact is None:
        return None

    if fact.visible_targets:
        first = fact.visible_targets[0]
        x = row_int(first, "x")
        y = row_int(first, "y")
        if x is not None and y is not None:
            return "visual", (x, y)
    if fact.heard_source is not None:
        return "audio", fact.heard_source
    if fact.scent_position is not None:
        return "scent", fact.scent_position
    if fact.last_known_position is not None:
        return "memory", fact.last_known_position

    return None
