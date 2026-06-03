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
    entities: Mapping[str, Any] | Iterable[Mapping[str, Any]],
    *,
    game_state: GameState,
    rng: GameRNG,
    perception: Any | None,
    batch_size: int = 4,
    deterministic: bool = True,
) -> None:
    """Execute AI adapters for a batch of entities in parallel."""

    if not isinstance(entities, Iterable) or hasattr(entities, "get"):
        entity_rows = [entities]
    else:
        entity_rows = list(entities)

    if deterministic:
        entity_rows = sorted(
            entity_rows, key=lambda row: int(row.get("entity_id", 0) or 0)
        )

    def _invoke(row: Mapping[str, Any], local_rng: GameRNG) -> None:
        species = row.get("species")
        intelligence = row.get("intelligence")
        species_map = game_state.ai_config.get("species_mapping", {})
        goap_tiers = game_state.ai_config.get("intelligence_tiers", {})

        ai_type = row.get("ai_type")
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
            entity_id=row.get("entity_id"),
            plan_depth=plan_depth,
        )
        adapter(
            row,
            game_state,
            local_rng,
            perception,
            species=species,
            intelligence=intelligence,
        )

    def _invoke_with_rng(args: tuple[Mapping[str, Any], GameRNG]) -> None:
        row, local_rng = args
        _invoke(row, local_rng)

    seeds = [rng.get_int(0, 2**32 - 1) for _ in range(len(entity_rows))]
    if deterministic or batch_size <= 1:
        for row, seed in zip(entity_rows, seeds, strict=False):
            local_rng = GameRNG(seed=seed, metrics=False)
            _invoke(row, local_rng)
        return

    for i in range(0, len(entity_rows), batch_size):
        batch = entity_rows[i : i + batch_size]
        batch_seeds = seeds[i : i + batch_size]
        with ThreadPool(len(batch)) as pool:
            pool.map(
                _invoke_with_rng,
                [
                    (row, GameRNG(seed=seed, metrics=False))
                    for row, seed in zip(batch, batch_seeds, strict=False)
                ],
            )
