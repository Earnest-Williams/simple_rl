"""Brainfuck step-budget handling: Numba results must not be re-run in Python."""

from __future__ import annotations

from typing import Final

import numpy as np
import pytest
from numpy.typing import NDArray

from magic import brainfuck_numba as bf

RUNAWAY_PROGRAM: Final[str] = ".+[]"  # prints cell 0, then loops forever
MAX_STEPS: Final[int] = 50_000


def test_numba_max_steps_result_is_returned_without_python_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail(*_args: object, **_kwargs: object) -> tuple[str, int, bool, str | None]:
        raise AssertionError("pure interpreter must not run after a Numba result")

    monkeypatch.setattr(bf, "_interpret_pure", _fail)
    result = bf.run_brainfuck(
        RUNAWAY_PROGRAM, max_steps=MAX_STEPS, deterministic=True, use_numba=True
    )
    assert result.error == "max_steps_exceeded"
    assert not result.success
    assert not result.halted
    assert result.steps == MAX_STEPS
    assert result.output == "\x00"


def test_numba_and_pure_agree_on_max_steps_outcome() -> None:
    jit = bf.run_brainfuck(
        RUNAWAY_PROGRAM, max_steps=MAX_STEPS, deterministic=True, use_numba=True
    )
    pure = bf.run_brainfuck(
        RUNAWAY_PROGRAM, max_steps=MAX_STEPS, deterministic=True, use_numba=False
    )
    assert (jit.success, jit.output, jit.error, jit.steps, jit.halted) == (
        pure.success,
        pure.output,
        pure.error,
        pure.steps,
        pure.halted,
    )


def test_pure_fallback_starts_from_clean_tape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_core = bf._run_numba_core

    def _dirty_failure(
        clean: str,
        input_bytes: bytes,
        tape: NDArray[np.uint8],
        bracket_map: dict[int, int],
        max_steps: int,
        wrap_pointer: bool,
        clamp_pointer: bool,
    ) -> tuple[str, int, bool, str | None]:
        real_core(
            clean,
            input_bytes,
            tape,
            bracket_map,
            max_steps,
            wrap_pointer,
            clamp_pointer,
        )
        return ("", 0, False, "output_buffer_overflow")

    monkeypatch.setattr(bf, "_run_numba_core", _dirty_failure)
    result = bf.run_brainfuck(
        RUNAWAY_PROGRAM, max_steps=MAX_STEPS, deterministic=True, use_numba=True
    )
    assert result.output == "\x00"


SANDBOX_JIT_STEPS: Final[int] = 10_000_000  # ~25 ms compiled; ~1.6 s CPU in pure Python
SANDBOX_KILL_STEPS: Final[int] = 60_000_000  # pure Python far beyond 1 s of CPU


def test_sandbox_runs_numba_core_within_cpu_budget() -> None:
    result = bf.run_brainfuck(
        "+[]",
        max_steps=SANDBOX_JIT_STEPS,
        use_numba=True,
        sandbox_mode="always",
        sandbox_wall_time_s=20.0,
        sandbox_cpu_time_s=1,
    )
    assert result.error == "max_steps_exceeded"
    assert result.steps == SANDBOX_JIT_STEPS


def test_sandbox_worker_killed_by_cpu_limit_reports_failure() -> None:
    result = bf.run_brainfuck(
        "+[]",
        max_steps=SANDBOX_KILL_STEPS,
        use_numba=False,
        sandbox_mode="always",
        sandbox_wall_time_s=20.0,
        sandbox_cpu_time_s=1,
    )
    assert result.error == "sandbox_execution_failed"
    assert not result.success
