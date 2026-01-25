"""AI package providing adapters for different decision systems.

This package exposes helper functions that select the appropriate
AI routine for a given entity. The goal is to allow the game to mix
multiple AI implementations (e.g. GOAP for monsters and community
simulation for townsfolk) within the same simulation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from . import (
    bird,
    community,
    goap,
    insect,
    mammal,
    ml_policy,
    plant,
    reptile,
    simple,
    strategy,
)

if TYPE_CHECKING:  # pragma: no cover - for type checking
    pass

log = structlog.get_logger()

# Mapping from ai_type string to the adapter function that will
# execute a turn for entities of that type.
ADAPTERS: dict[str, Callable] = {
    "goap": goap.take_turn,
    "community": community.take_turn,
    "simple": simple.take_turn,
    "ml_policy": ml_policy.take_turn,
    "strategy": strategy.dispatch_strategy,
    "insect": insect.take_turn,
    "bird": bird.take_turn,
    "mammal": mammal.take_turn,
    "reptile": reptile.take_turn,
    "plant": plant.take_turn,
}


def get_adapter(ai_type: str) -> Callable:
    """Return the adapter function for the given ai_type.

    Unknown types default to the GOAP adapter so that new entity
    definitions do not cause crashes if misconfigured.
    """
    adapter = ADAPTERS.get(ai_type, goap.take_turn)
    if adapter is goap.take_turn and ai_type not in ADAPTERS:
        log.debug("Unknown ai_type, defaulting to GOAP", ai_type=ai_type)
    return adapter
