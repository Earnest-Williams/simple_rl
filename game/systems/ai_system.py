"""Central AI dispatch system.

This module exposes :func:`dispatch_ai` which selects an appropriate AI
adapter for an entity based on its metadata.  Adapters must implement the
``take_turn(entity_row, game_state, rng, perception)`` interface so the game
can mix multiple decision making systems.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from multiprocessing.dummy import Pool as ThreadPool
from typing import TYPE_CHECKING, Any

import structlog

from game.ai import get_adapter, goap
from utils.game_rng import GameRNG

if TYPE_CHECKING:  # pragma: no cover - type checking only
    import numpy as np

    from game.game_state import GameState
    from utils.game_rng import GameRNG

log = structlog.get_logger()


def dispatch_ai(
    entities: int | Mapping[str, Any] | Iterable[int | Mapping[str, Any]],
    *,
    game_state: GameState,
    rng: GameRNG,
    perception: Any | None,
    batch_size: int = 4,
    deterministic: bool = True,
) -> None:
    """Execute AI adapters for a batch of entities in parallel by their IDs."""

    if isinstance(entities, int):
        entity_ids = [entities]
    elif isinstance(entities, Mapping):
        entity_ids = [int(entities["entity_id"])]
    elif isinstance(entities, Iterable):
        entity_ids = []
        for e in entities:
            if isinstance(e, Mapping):
                entity_ids.append(int(e["entity_id"]))
            else:
                entity_ids.append(int(e))
    else:
        entity_ids = [int(entities)]

    if deterministic:
        entity_ids.sort()

    def _invoke(entity_id: int, local_rng: GameRNG) -> None:
        registry = game_state.entity_registry
        species = registry.species_of(entity_id)
        intelligence = registry.intelligence_of(entity_id)
        species_map = game_state.ai_config.get("species_mapping", {})
        goap_tiers = game_state.ai_config.get("intelligence_tiers", {})

        ai_type = registry.ai_type_of(entity_id)
        plan_depth = None
        if not ai_type:
            if species and species in species_map:
                ai_type = species_map[species]
            elif intelligence is not None:
                ai_type = "goap"
        if not ai_type:
            ai_type = game_state.ai_config.get("default", "goap")

        adapter = get_adapter(ai_type)
        if adapter is goap.take_turn:
            if intelligence is not None:
                plan_depth = goap_tiers.get(intelligence, intelligence)
            if plan_depth is None:
                plan_depth = 1
            adapter = goap.get_goap_adapter(plan_depth)
        log.debug(
            "Dispatching AI",
            ai_type=ai_type,
            species=species,
            intelligence=intelligence,
            entity_id=entity_id,
            plan_depth=plan_depth,
        )
        adapter(
            entity_id,
            game_state,
            local_rng,
            perception,
            species=species,
            intelligence=intelligence,
        )

    def _invoke_with_rng(args: tuple[int, GameRNG]) -> None:
        entity_id, local_rng = args
        _invoke(entity_id, local_rng)

    seeds = [rng.get_int(0, 2**32 - 1) for _ in range(len(entity_ids))]
    if deterministic or batch_size <= 1:
        for entity_id, seed in zip(entity_ids, seeds, strict=False):
            local_rng = GameRNG(seed=seed, metrics=False)
            _invoke(entity_id, local_rng)
        return

    for i in range(0, len(entity_ids), batch_size):
        batch = entity_ids[i : i + batch_size]
        batch_seeds = seeds[i : i + batch_size]
        with ThreadPool(len(batch)) as pool:
            pool.map(
                _invoke_with_rng,
                [
                    (entity_id, GameRNG(seed=seed, metrics=False))
                    for entity_id, seed in zip(batch, batch_seeds, strict=False)
                ],
            )
