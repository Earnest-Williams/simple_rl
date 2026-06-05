from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from enum import IntEnum

import numpy as np

from .config import (
    BuildingMaterial,
    Facility,
    MagicMode,
    SettlementConfig,
    SettlementState,
)


class TerrainCode(IntEnum):
    VOID = 0
    GRASS = 1
    FOREST = 2
    DENSE_FOREST = 3
    FARMLAND = 4
    ORCHARD = 5
    PASTURE = 6
    HILL = 7
    MOUNTAIN = 8
    ROAD = 9
    PLAZA = 10
    WATER = 11
    DEEP_WATER = 12
    SHORE = 13
    MARSH = 14
    SWAMP = 15
    BRIDGE = 16
    WALL = 17
    PALISADE = 18
    GATE = 19
    BUILDING = 20
    RUIN = 21
    CEMETERY = 22
    DOCK = 23
    DYKE = 24
    MAGIC = 25
    FIELD = 26
    EMPTY_LOT = 27
    MOAT = 28


TERRAIN_NAMES = {code.value: code.name.lower() for code in TerrainCode}


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    @property
    def area(self) -> int:
        return self.w * self.h

    def expanded(self, margin: int, width: int, height: int) -> Rect:
        x = max(0, self.x - margin)
        y = max(0, self.y - margin)
        x2 = min(width, self.x2 + margin)
        y2 = min(height, self.y2 + margin)
        return Rect(x, y, x2 - x, y2 - y)

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.w, self.h)


@dataclass
class District:
    id: int
    kind: str
    center: tuple[int, int]
    radius: int
    wealth: str
    tags: tuple[str, ...] = tuple()


@dataclass
class RoadSegment:
    id: int
    kind: str
    points: list[tuple[int, int]]
    tags: tuple[str, ...] = tuple()


@dataclass
class Building:
    id: int
    facility: Facility
    rect: Rect
    material: BuildingMaterial
    state: SettlementState
    district_id: int | None = None
    occupants: int = 0
    workers: int = 0
    quality: float = 0.5
    magic: MagicMode | None = None
    name: str | None = None
    tags: tuple[str, ...] = tuple()
    meta: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class MagicSite:
    kind: str
    location: tuple[int, int]
    radius: int
    intensity: float
    tags: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class FailedFacility:
    """A facility that was requested but could not be placed."""

    facility: str
    reason: str


@dataclass(frozen=True)
class GenerationReport:
    """Typed report of facility placement outcomes.

    This is the stable contract for downstream consumers that need to know
    what was requested, what was placed, and what failed (with reason codes).
    """

    requested_facilities: tuple[str, ...]
    placed_facilities: tuple[str, ...]
    failed_facilities: tuple[FailedFacility, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_facilities": list(self.requested_facilities),
            "placed_facilities": list(self.placed_facilities),
            "failed_facilities": {
                f.facility: f.reason for f in self.failed_facilities
            },
        }


@dataclass
class Settlement:
    config: SettlementConfig
    seed: int
    name: str
    terrain: np.ndarray
    overlay: np.ndarray
    districts: list[District]
    roads: list[RoadSegment]
    buildings: list[Building]
    gates: list[tuple[int, int]]
    docks: list[tuple[int, int]]
    magic_sites: list[MagicSite]
    population: int
    generation_report: GenerationReport
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def width(self) -> int:
        return int(self.terrain.shape[1])

    @property
    def height(self) -> int:
        return int(self.terrain.shape[0])

    def tile_summary(self) -> dict[str, int]:
        combined = self.combined_grid()
        values, counts = np.unique(combined, return_counts=True)
        return {
            TERRAIN_NAMES.get(int(v), str(int(v))): int(c)
            for v, c in zip(values, counts, strict=False)
        }

    def facility_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for building in self.buildings:
            counts[building.facility.value] = counts.get(building.facility.value, 0) + 1
        return counts

    def combined_grid(self) -> np.ndarray:
        """Return a single render/use grid with overlay taking precedence."""
        return np.where(
            self.overlay != TerrainCode.VOID, self.overlay, self.terrain
        ).astype(np.int16)

    def iter_building_records(self) -> Iterable[dict[str, str | int | float | None]]:
        for b in self.buildings:
            yield {
                "id": b.id,
                "facility": b.facility.value,
                "x": b.rect.x,
                "y": b.rect.y,
                "w": b.rect.w,
                "h": b.rect.h,
                "area": b.rect.area,
                "center_x": b.rect.center[0],
                "center_y": b.rect.center[1],
                "material": b.material.value,
                "state": b.state.value,
                "district_id": b.district_id,
                "occupants": b.occupants,
                "workers": b.workers,
                "quality": round(float(b.quality), 4),
                "magic": b.magic.value if b.magic else None,
                "name": b.name,
                "tags": ";".join(b.tags),
            }

    def to_dict(self, include_grids: bool = False) -> dict[str, object]:
        data: dict[str, object] = {
            "name": self.name,
            "seed": self.seed,
            "population": self.population,
            "width": self.width,
            "height": self.height,
            "config": _serialize(self.config),
            "districts": [_serialize(d) for d in self.districts],
            "roads": [_serialize(r) for r in self.roads],
            "buildings": [_serialize(b) for b in self.buildings],
            "gates": self.gates,
            "docks": self.docks,
            "magic_sites": [_serialize(m) for m in self.magic_sites],
            "metadata": self.metadata,
            "facility_counts": self.facility_counts(),
            "tile_summary": self.tile_summary(),
        }
        if include_grids:
            data["terrain"] = self.terrain.astype(int).tolist()
            data["overlay"] = self.overlay.astype(int).tolist()
        return data


def _serialize(value: object) -> object:
    if hasattr(value, "value") and not isinstance(value, IntEnum):
        return value.value
    if isinstance(value, Rect):
        return {"x": value.x, "y": value.y, "w": value.w, "h": value.h}
    if hasattr(value, "__dataclass_fields__"):
        from typing import Any, cast

        out = asdict(cast(Any, value))
        return _serialize(out)
    if isinstance(value, dict):
        return {k: _serialize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_serialize(v) for v in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value
