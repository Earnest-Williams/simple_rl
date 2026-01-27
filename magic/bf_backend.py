from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from common.tuning import BF_MAX_STEPS, BF_TAPE_SIZE


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
        deterministic: bool = False,
        tape_size: int = BF_TAPE_SIZE,
        max_steps: int = BF_MAX_STEPS,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult: ...


class _BaseBackend(BFBackend):
    _USE_NUMBA: bool | None

    def run(
        self,
        code: str,
        input_data: str = "",
        *,
        deterministic: bool = False,
        tape_size: int = BF_TAPE_SIZE,
        max_steps: int = BF_MAX_STEPS,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult:
        from magic import brainfuck_numba as bf_numba

        bf_result: bf_numba.BFResult = bf_numba.run_brainfuck(
            code,
            input_data=input_data,
            deterministic=deterministic,
            tape_size=tape_size,
            max_steps=max_steps,
            wrap_pointer=wrap_pointer,
            clamp_pointer=clamp_pointer,
            use_numba=self._USE_NUMBA,
        )
        return BFResult(
            success=bf_result.success,
            output=bf_result.output,
            error=bf_result.error,
            steps=bf_result.steps,
            halted=bf_result.halted,
        )


class NumbaBackend(_BaseBackend):
    """Brainfuck backend that attempts to use the Numba JIT."""

    _USE_NUMBA: bool | None = True


class PureBackend(_BaseBackend):
    """Brainfuck backend that uses the pure Python interpreter."""

    _USE_NUMBA: bool | None = False


class JitBackend(BFBackend):
    """Brainfuck backend that uses the numba core and refuses I/O."""

    @staticmethod
    def supports_code(code: str) -> bool:
        return "." not in code and "," not in code

    def run(
        self,
        code: str,
        input_data: str = "",
        *,
        deterministic: bool = False,
        tape_size: int = BF_TAPE_SIZE,
        max_steps: int = BF_MAX_STEPS,
        wrap_pointer: bool = True,
        clamp_pointer: bool = False,
    ) -> BFResult:
        _ = deterministic
        if not self.supports_code(code):
            return BFResult(False, "", "jit_refuses_io", 0, False)

        from magic import brainfuck_numba as bf_numba

        return bf_numba._run_numba_core_internal(
            code,
            input_data,
            tape_size=tape_size,
            max_steps=max_steps,
            wrap_pointer=wrap_pointer,
            clamp_pointer=clamp_pointer,
        )
