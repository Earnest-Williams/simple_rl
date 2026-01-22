from dataclasses import dataclass
from typing import Callable, Dict, List, Sequence, Tuple

from magic.executor import (
    Art,
    ExecutionResult,
    Substance,
    Work,
    execute_work,
    register_handler,
)
from magic import executor
from magic.wards import Ward, Counterseal


class _EntityRegistryStub:
    """Minimal stand-in for ``EntityRegistry`` used in tests."""

    def __init__(self) -> None:
        self.components: Dict[int, Dict[str, object]] = {
            0: {"status_effects": [], "hp": 10}
        }

    def get_entity_component(
        self, entity_id: int, component: str
    ) -> object | None:  # pragma: no cover - trivial
        return self.components.get(entity_id, {}).get(component)

    def set_entity_component(
        self, entity_id: int, component: str, value: object
    ) -> bool:  # pragma: no cover - trivial
        self.components.setdefault(entity_id, {})[component] = value
        return True


@dataclass(frozen=True)
class _WorkStub:
    art: object
    substances: List[object]


class DummyGameState:
    """Lightweight stand-in for the real GameState.

    The magic executor expects a ``player_id`` attribute, resource lookup
    methods for seals, fonts, and vents, and some basic player resources.  This
    stub provides simple set-based implementations suitable for unit tests.
    """

    def __init__(
        self,
        *,
        seals: Sequence[str] = ("s",),
        fonts: Sequence[str] = ("f",),
        vents: Sequence[str] = ("v",),
    ) -> None:
        self.player_id = 0
        self._seals = set(seals)
        self._fonts = set(fonts)
        self._vents = set(vents)
        self.player_fuel = 10
        self.entity_registry = _EntityRegistryStub()

    def has_seal_tag(
        self, entity_id: int, tag: str
    ) -> bool:  # pragma: no cover - trivial
        return tag in self._seals

    def has_font_source(
        self, entity_id: int, source: str
    ) -> bool:  # pragma: no cover - trivial
        return source in self._fonts

    def has_vent_target(
        self, entity_id: int, target: str
    ) -> bool:  # pragma: no cover - trivial
        return target in self._vents


def make_basic_work(**kwargs: object) -> Work:
    """Helper to create a Work with mandatory validation fields populated."""
    defaults: Dict[str, object] = {
        "art": Art.CREATE,
        "substance": Substance.FIRE,
        "seals": ["s"],
        "fonts": ["f"],
        "vents": ["v"],
        "func": lambda: None,
    }
    defaults.update(kwargs)
    return Work(**defaults)


def test_seal_font_vent_verifications_pass_and_fail() -> None:
    """Each validation succeeds when resources exist and fails otherwise."""

    work = make_basic_work(seals=["alpha"], fonts=["beta"], vents=["gamma"])

    # All resources present: should pass
    gs_ok = DummyGameState(seals=("alpha",), fonts=("beta",), vents=("gamma",))
    assert executor._verify_seals(work, gs_ok)
    assert executor._verify_fonts(work, gs_ok)
    assert executor._verify_vents(work, gs_ok)
    result: ExecutionResult = execute_work(work, gs_ok)
    assert result.executed is True
    assert result.reason is None

    # Missing each resource should fail the respective check and execution
    gs_missing_seal = DummyGameState(seals=(), fonts=("beta",), vents=("gamma",))
    assert not executor._verify_seals(work, gs_missing_seal)
    result = execute_work(
        make_basic_work(seals=["alpha"], fonts=["beta"], vents=["gamma"]),
        gs_missing_seal,
    )
    assert result.executed is False
    assert result.reason == "seals_failed"

    gs_missing_font = DummyGameState(seals=("alpha",), fonts=(), vents=("gamma",))
    assert not executor._verify_fonts(work, gs_missing_font)
    result = execute_work(
        make_basic_work(seals=["alpha"], fonts=["beta"], vents=["gamma"]),
        gs_missing_font,
    )
    assert result.executed is False
    assert result.reason == "fonts_failed"

    gs_missing_vent = DummyGameState(seals=("alpha",), fonts=("beta",), vents=())
    assert not executor._verify_vents(work, gs_missing_vent)
    result = execute_work(
        make_basic_work(seals=["alpha"], fonts=["beta"], vents=["gamma"]),
        gs_missing_vent,
    )
    assert result.executed is False
    assert result.reason == "vents_failed"


def test_execute_work_blocked_by_ward_without_counterseal() -> None:
    work = make_basic_work()
    ward = Ward(arts={Art.CREATE})
    counterseal = Counterseal(arts={Art.DESTROY})  # does not match the ward
    result: ExecutionResult = execute_work(
        work, DummyGameState(), wards=[ward], counterseals=[counterseal]
    )
    assert result.executed is False
    assert result.reason == "blocked_by_ward"


def test_ward_blocks_with_normalized_art_and_substance_names() -> None:
    ward: Ward = Ward(arts={"create"}, substances={"fire"})
    work: Work = make_basic_work(art=Art.CREATE, substance=Substance.FIRE)
    assert ward.blocks(work)

    string_work: _WorkStub = _WorkStub(art="CREATE", substances=["FIRE"])
    enum_ward: Ward = Ward(arts={Art.CREATE}, substances={Substance.FIRE})
    assert enum_ward.blocks(string_work)


def test_friction_increases_and_triggers_thresholds(monkeypatch) -> None:
    calls: List[str] = []

    def recorder(name: str) -> Callable[[Work, DummyGameState], None]:
        def _rec(work: Work, ctx: DummyGameState) -> None:
            calls.append(name)

        return _rec

    monkeypatch.setattr(executor, "_handle_quiver", recorder("quiver"))
    monkeypatch.setattr(executor, "_handle_warp", recorder("warp"))
    monkeypatch.setattr(executor, "_handle_shiver", recorder("shiver"))
    monkeypatch.setattr(executor, "_handle_backlash", recorder("backlash"))

    work = make_basic_work(
        quiver_threshold=1,
        warp_threshold=2,
        shiver_threshold=3,
        backlash_threshold=4,
    )
    gs = DummyGameState()

    frictions: List[float] = []
    for _ in range(4):
        result: ExecutionResult = execute_work(work, gs)
        assert result.executed is True
        assert result.reason is None
        frictions.append(work.friction)

    assert frictions == [1.0, 2.0, 3.0, 0.0]
    assert calls == ["quiver", "warp", "shiver", "backlash"]


def test_threshold_handlers_modify_state_and_emit_events(monkeypatch) -> None:
    """Threshold effects update GameState and fire registered callbacks."""

    # Reset callback registry
    monkeypatch.setattr(
        executor,
        "FRICTION_CALLBACKS",
        {"quiver": [], "warp": [], "shiver": [], "backlash": []},
    )

    events: List[str] = []
    for evt in ("quiver", "warp", "shiver", "backlash"):
        executor.register_friction_callback(
            evt, lambda w, c, e=evt: events.append(e)
        )

    work = make_basic_work(
        quiver_threshold=1,
        warp_threshold=2,
        shiver_threshold=3,
        backlash_threshold=4,
    )
    gs = DummyGameState()

    expected_fuel = [9, 7, 4, 0]
    expected_events = [
        ["quiver"],
        ["quiver", "warp"],
        ["quiver", "warp", "shiver"],
        ["quiver", "warp", "shiver", "backlash"],
    ]
    expected_statuses = [
        ["quivering"],
        ["quivering", "warped"],
        ["quivering", "warped", "shivering"],
        ["quivering", "warped", "shivering", "backlash"],
    ]

    for idx in range(4):
        result: ExecutionResult = execute_work(work, gs)
        assert result.executed is True
        assert result.reason is None
        assert gs.player_fuel == expected_fuel[idx]
        statuses = gs.entity_registry.get_entity_component(
            gs.player_id, "status_effects"
        )
        assert [s["id"] for s in statuses] == expected_statuses[idx]
        assert events == expected_events[idx]

    # Backlash also drains HP
    hp = gs.entity_registry.get_entity_component(gs.player_id, "hp")
    assert hp == 9


def test_registered_handlers_are_invoked(monkeypatch) -> None:
    called: List[Tuple[Work, DummyGameState]] = []
    monkeypatch.setattr(executor, "EFFECT_HANDLERS", {})

    def handler(work: Work, state: DummyGameState) -> None:
        called.append((work, state))

    register_handler(Art.DESTROY, Substance.WATER, handler)

    work = make_basic_work(art=Art.DESTROY, substance=Substance.WATER, func=None)
    gs = DummyGameState()
    result: ExecutionResult = execute_work(work, gs)

    assert result.executed is True
    assert result.reason is None
    assert called == [(work, gs)]


def test_game_effects_register_existing_handlers(monkeypatch) -> None:
    monkeypatch.setattr(executor, "EFFECT_HANDLERS", {})

    import importlib
    import game.effects

    importlib.reload(game.effects)

    assert (Art.CREATE, Substance.WATER) in executor.EFFECT_HANDLERS
