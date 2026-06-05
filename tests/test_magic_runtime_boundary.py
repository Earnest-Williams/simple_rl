from __future__ import annotations

import magic
from magic import Art, Substance
from magic.executor import EFFECT_HANDLERS, ExecutionResult, Work, execute_work
from magic.models import Work as ModelWork


class DummyGameState:
    player_id = 1

    def __init__(self) -> None:
        self.handled: list[tuple[Art, Substance]] = []

    def has_seal_tag(self, entity_id: int, tag: str) -> bool:
        return entity_id == self.player_id and tag == "known_seal"

    def has_font_source(self, entity_id: int, tag: str) -> bool:
        return entity_id == self.player_id and tag == "known_font"

    def has_vent_target(self, entity_id: int, tag: str) -> bool:
        return entity_id == self.player_id and tag == "known_vent"


def test_top_level_magic_work_exports_runtime_work_without_hiding_model_work() -> None:
    assert magic.Work is Work
    assert magic.ModelWork is ModelWork
    assert magic.Art is Art
    assert magic.Substance is Substance


def test_execute_work_runs_registered_handler_and_updates_friction() -> None:
    context = DummyGameState()
    work = Work(
        art=Art.PERCEIVE,
        substance=Substance.SPIRIT,
        seals=["known_seal"],
        fonts=["known_font"],
        vents=["known_vent"],
    )

    original_handler = EFFECT_HANDLERS.get((work.art, work.substance))

    def handler(executed_work: Work, game_state: DummyGameState) -> None:
        game_state.handled.append((executed_work.art, executed_work.substance))

    EFFECT_HANDLERS[(work.art, work.substance)] = handler
    try:
        result = execute_work(work, context)  # type: ignore[arg-type]
    finally:
        if original_handler is None:
            EFFECT_HANDLERS.pop((work.art, work.substance), None)
        else:
            EFFECT_HANDLERS[(work.art, work.substance)] = original_handler

    assert result == ExecutionResult(True)
    assert context.handled == [(Art.PERCEIVE, Substance.SPIRIT)]
    assert work.friction == 1.0


def test_execute_work_reports_missing_runtime_requirement() -> None:
    context = DummyGameState()
    work = Work(
        art=Art.PERCEIVE,
        substance=Substance.SPIRIT,
        seals=["missing_seal"],
    )

    result = execute_work(work, context)  # type: ignore[arg-type]

    assert result == ExecutionResult(False, "seals_failed")
