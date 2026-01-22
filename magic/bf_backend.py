from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class BFResult:
    success: bool
    output: str
    error: str | None
    steps: int
    halted: bool


class BFBackend(ABC):
    @abstractmethod
    def run(
        self,
        code: str,
        input_data: str = "",
        *,
        tape_size: int = 30_000,
        max_steps: int = 10_000_000,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult:
        ...


class NumbaBackend(BFBackend):
    def run(
        self,
        code: str,
        input_data: str = "",
        *,
        tape_size: int = 30_000,
        max_steps: int = 10_000_000,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult:
        from magic import brainfuck_numba as bf_numba

        bf_result: bf_numba.BFResult = bf_numba.run_brainfuck(
            code,
            input_data=input_data,
            tape_size=tape_size,
            max_steps=max_steps,
            wrap_pointer=wrap_pointer,
            clamp_pointer=clamp_pointer,
        )
        return BFResult(
            success=bf_result.success,
            output=bf_result.output,
            error=bf_result.error,
            steps=bf_result.steps,
            halted=bf_result.halted,
        )


class PureBackend(BFBackend):
    def run(
        self,
        code: str,
        input_data: str = "",
        *,
        tape_size: int = 30_000,
        max_steps: int = 10_000_000,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult:
        from magic import brainfuck_numba as bf_numba

        bf_result: bf_numba.BFResult = bf_numba.run_brainfuck(
            code,
            input_data=input_data,
            tape_size=tape_size,
            max_steps=max_steps,
            wrap_pointer=wrap_pointer,
            clamp_pointer=clamp_pointer,
            use_numba=False,
        )
        return BFResult(
            success=bf_result.success,
            output=bf_result.output,
            error=bf_result.error,
            steps=bf_result.steps,
            halted=bf_result.halted,
        )
