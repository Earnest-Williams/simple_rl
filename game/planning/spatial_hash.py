from __future__ import annotations

from collections import defaultdict


class SpatialHashTable:
    def __init__(self, cell_size: int = 10) -> None:
        self.cell_size = cell_size
        self.grid: defaultdict[tuple[int, int], list[tuple[int, int, int, str]]] = (
            defaultdict(list)
        )

    def clear(self) -> None:
        self.grid.clear()

    def insert(self, entity_id: int, x: int, y: int, kind: str) -> None:
        self.grid[(x // self.cell_size, y // self.cell_size)].append(
            (entity_id, x, y, kind)
        )

    def query_radius(
        self, center: tuple[int, int], radius: int, kind: str | None = None
    ) -> list[tuple[int, int, int]]:
        cx, cy = center
        min_cell_x = (cx - radius) // self.cell_size
        max_cell_x = (cx + radius) // self.cell_size
        min_cell_y = (cy - radius) // self.cell_size
        max_cell_y = (cy + radius) // self.cell_size

        results: list[tuple[int, int, int]] = []
        for cell_x in range(min_cell_x, max_cell_x + 1):
            for cell_y in range(min_cell_y, max_cell_y + 1):
                items = self.grid.get((cell_x, cell_y), [])
                if kind is None:
                    # Return all items regardless of kind
                    for entity_id, x, y, _ in items:
                        results.append((entity_id, x, y))
                else:
                    # Filter by the specified kind
                    for entity_id, x, y, entity_kind in items:
                        if entity_kind == kind:
                            results.append((entity_id, x, y))
        return results
