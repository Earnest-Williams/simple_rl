from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ExpeditionState:
    survey_completed: bool = False
    route_revealed: bool = False
    blockage_cleared: bool = False
    cave_entered: bool = False
    discovery_recorded: bool = False
    returned_to_port: bool = False
    loop_completed: bool = False
    active_objective_id: str | None = None
    discovery_ids: set[str] = field(default_factory=set)
