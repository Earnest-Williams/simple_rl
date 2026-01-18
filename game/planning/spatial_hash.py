from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, List, Tuple


class SpatialHashTable:
    def __init__(self, cell_size: int = 10) -> None:
        self.cell_size = cell_size
        self.grid: DefaultDict[Tuple[int, int, str], List[Tuple[int, int, int]]] = (
            defaultdict(list)
        )

    def clear(self) -> None:
        self.grid.clear()

    def insert(self, entity_id: int, x: int, y: int, kind: str) -> None:
        self.grid[(x // self.cell_size, y // self.cell_size, kind)].append(
            (entity_id, x, y)
        )

    def query_radius(
        self, center: Tuple[int, int], radius: int, kind: str | None = None
    ) -> List[Tuple[int, int, int]]:
        cx, cy = center
        min_cell_x = (cx - radius) // self.cell_size
        max_cell_x = (cx + radius) // self.cell_size
        min_cell_y = (cy - radius) // self.cell_size
        max_cell_y = (cy + radius) // self.cell_size

        results: List[Tuple[int, int, int]] = []
        if kind is None:
            for key, items in self.grid.items():
                cell_x, cell_y, _ = key
                if (
                    min_cell_x <= cell_x <= max_cell_x
                    and min_cell_y <= cell_y <= max_cell_y
                ):
                    results.extend(items)
            return results

        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                results.extend(self.grid.get((cell_x, cell_y, kind), []))
        return results
