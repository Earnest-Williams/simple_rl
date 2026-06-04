from __future__ import annotations

from dataclasses import dataclass

from settlegen import Facility, Settlement


@dataclass(frozen=True, slots=True)
class SubsurfaceEntrance:
    id: int
    x: int
    y: int
    kind: str
    source_building_id: int | None
    target: str


_FACILITY_TARGETS: dict[Facility, tuple[str, str]] = {
    Facility.MINE: ("mine", "Dungeon"),
    Facility.QUARRY: ("quarry", "Dungeon"),
    Facility.ANCIENT_VAULT: ("vault", "Dungeon"),
    Facility.NECROPOLIS: ("catacombs", "Dungeon"),
    Facility.CEMETERY: ("catacombs", "Dungeon"),
}


def extract_entrances(settlement: Settlement) -> list[SubsurfaceEntrance]:
    entrances: list[SubsurfaceEntrance] = []
    for building in settlement.buildings:
        mapping = _FACILITY_TARGETS.get(building.facility)
        if mapping is None:
            continue
        kind, target = mapping
        x, y = building.rect.center
        entrances.append(
            SubsurfaceEntrance(
                id=len(entrances) + 1,
                x=int(x),
                y=int(y),
                kind=kind,
                source_building_id=int(building.id),
                target=target,
            )
        )
    return entrances
