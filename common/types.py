"""Shared type aliases for grid-based systems."""

from typing import TypeAlias

GridPosition: TypeAlias = tuple[int, int]
GridSize: TypeAlias = tuple[int, int]
GridOffset: TypeAlias = tuple[int, int]
QueueItem: TypeAlias = tuple[int, int, int]
Neighbors8: TypeAlias = tuple[tuple[int, int], ...]

__all__ = ["GridOffset", "GridPosition", "GridSize", "Neighbors8", "QueueItem"]
