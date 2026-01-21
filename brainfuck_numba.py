# brainfuck_numba.py
from __future__ import annotations

from dataclasses import dataclass
from multiprocessing import Pipe, get_context
from multiprocessing.connection import Connection
import resource
import time
from typing import Literal

import numpy as np

# Try to import numba explicitly; if missing we'll fall back.
try:
    from numba import njit  # type: ignore
    _NUMBA_AVAILABLE = True
except Exception:
    njit = None  # type: ignore
    _NUMBA_AVAILABLE = False


# Brainfuck command ASCII values
CMD_GT = ord('>')      # 62
CMD_LT = ord('<')      # 60
CMD_PLUS = ord('+')    # 43
CMD_MINUS = ord('-')   # 45
CMD_DOT = ord('.')     # 46
CMD_COMMA = ord(',')   # 44
CMD_LBRACKET = ord('[')  # 91
CMD_RBRACKET = ord(']')  # 93


@dataclass(frozen=True)
class BFResult:
    success: bool
    output: str
    error: str | None
    steps: int
    halted: bool


SandboxMode = Literal["auto", "always", "never"]
BFResultTuple = tuple[bool, str, str | None, int, bool]

_SANDBOX_STEP_THRESHOLD = 1_000_000
_DEFAULT_SANDBOX_CPU_SECONDS = 1
_DEFAULT_SANDBOX_WALL_TIME_S = 1.0
_DEFAULT_SANDBOX_MEMORY_BYTES = 256 * 1024 * 1024


# -----------------------
# Utilities (pure python)
# -----------------------
def sanitize(code: str) -> str:
    """Keep only Brainfuck command characters."""
    return "".join(c for c in code if c in "><+-.,[]")


def build_bracket_map(code: str) -> dict[int, int]:
    """
    Build bidirectional bracket mapping.

    Raises SyntaxError on unmatched brackets.
    """
    stack: list[int] = []
    mapping: dict[int, int] = {}
    for i, c in enumerate(code):
        if c == "[":
            stack.append(i)
        elif c == "]":
            if not stack:
                raise SyntaxError(f"Unmatched ']' at position {i}")
            opening = stack.pop()
            mapping[opening] = i
            mapping[i] = opening
    if stack:
        opening = stack.pop()
        raise SyntaxError(f"Unmatched '[' at position {opening}")
    return mapping


def _interpret_pure(
    code: str,
    input_bytes: bytes,
    tape: np.ndarray,
    bracket_map: dict[int, int],
    max_steps: int,
    wrap_pointer: bool,
    clamp_pointer: bool,
) -> tuple[str, int, bool, str | None]:
    """
    A safe, pure-Python interpreter loop. Returns:
      (output_str, steps_executed, halted_bool, error_or_None)
    """
    code_len = len(code)
    ip = 0
    ptr = 0
    input_pos = 0
    output_chars: list[str] = []
    steps = 0
    tape_len = int(tape.shape[0])
    tape_view = tape  # local alias

    try:
        while ip < code_len:
            if steps >= max_steps:
                return ("".join(output_chars), steps, False, "max_steps_exceeded")
            cmd = code[ip]

            if cmd == ">":
                if clamp_pointer:
                    ptr = min(ptr + 1, tape_len - 1)
                else:  # Default behavior is to wrap
                    ptr = (ptr + 1) % tape_len
                ip += 1

            elif cmd == "<":
                if clamp_pointer:
                    ptr = max(ptr - 1, 0)
                else:  # Default behavior is to wrap
                    ptr = (ptr - 1 + tape_len) % tape_len
                ip += 1

            elif cmd == "+":
                tape_view[ptr] = (int(tape_view[ptr]) + 1) & 0xFF
                ip += 1

            elif cmd == "-":
                tape_view[ptr] = (int(tape_view[ptr]) - 1) & 0xFF
                ip += 1

            elif cmd == ".":
                output_chars.append(chr(int(tape_view[ptr])))
                ip += 1

            elif cmd == ",":
                if input_pos < len(input_bytes):
                    tape_view[ptr] = int(input_bytes[input_pos]) & 0xFF
                    input_pos += 1
                else:
                    tape_view[ptr] = 0
                ip += 1

            elif cmd == "[":
                if tape_view[ptr] == 0:
                    ip = bracket_map[ip] + 1
                else:
                    ip += 1

            elif cmd == "]":
                if tape_view[ptr] != 0:
                    ip = bracket_map[ip] + 1
                else:
                    ip += 1

            else:
                # should not happen thanks to sanitize
                ip += 1

            steps += 1

    except Exception as exc:
        return ("".join(output_chars), steps, False, f"runtime_error: {exc}")

    return ("".join(output_chars), steps, True, None)


# -----------------------
# Numba core (compiled)
# -----------------------
# Numba requires simple numpy arrays and numeric types only.
# We encode commands as integer ordinals (int32) and bracket map as int32 array
# of length code_len, with -1 for non-bracket positions.

_numba_core = None
if _NUMBA_AVAILABLE:
    # Implement the njit-compiled core loop. This function only uses
    # primitive types and numpy arrays; it returns numeric diagnostics.
    @njit(cache=True)
    def _numba_core(
        code_arr: np.ndarray,
        code_len: int,
        bracket_map_arr: np.ndarray,
        tape: np.ndarray,
        tape_len: int,
        input_arr: np.ndarray,
        input_len: int,
        output_arr: np.ndarray,
        max_output: int,
        max_steps: int,
        wrap_flag: int,
        clamp_flag: int,
    ) -> tuple[int, int, int, int]:
        # Return tuple: (steps, halted_flag(0/1), out_len, error_code)
        # error_code: 0 = OK, 1 = max_steps_exceeded, 2 = output_overflow, 3 = runtime_error
        ip = 0
        ptr = 0
        input_pos = 0
        out_len = 0
        steps = 0

        try:
            while ip < code_len:
                if steps >= max_steps:
                    return steps, 0, out_len, 1
                cmd = code_arr[ip]

                if cmd == CMD_GT:  # '>'
                    if clamp_flag == 1:
                        if ptr < tape_len - 1:
                            ptr += 1
                    else:  # Default behavior is to wrap
                        ptr = (ptr + 1) % tape_len
                    ip += 1

                elif cmd == CMD_LT:  # '<'
                    if clamp_flag == 1:
                        if ptr > 0:
                            ptr -= 1
                    else:  # Default behavior is to wrap
                        ptr = (ptr - 1 + tape_len) % tape_len
                    ip += 1

                elif cmd == CMD_PLUS:  # '+'
                    # uint8 wrap
                    tape[ptr] = (int(tape[ptr]) + 1) & 0xFF
                    ip += 1

                elif cmd == CMD_MINUS:  # '-'
                    tape[ptr] = (int(tape[ptr]) - 1) & 0xFF
                    ip += 1

                elif cmd == CMD_DOT:  # '.'
                    if out_len >= max_output:
                        return steps, 0, out_len, 2
                    # write raw byte value to output buffer (as int)
                    output_arr[out_len] = int(tape[ptr])
                    out_len += 1
                    ip += 1

                elif cmd == CMD_COMMA:  # ','
                    if input_pos < input_len:
                        tape[ptr] = int(input_arr[input_pos]) & 0xFF
                        input_pos += 1
                    else:
                        tape[ptr] = 0
                    ip += 1

                elif cmd == CMD_LBRACKET:  # '['
                    if tape[ptr] == 0:
                        # jump to matching ']' (bracket_map_arr[ip])
                        ip = bracket_map_arr[ip] + 1
                    else:
                        ip += 1

                elif cmd == CMD_RBRACKET:  # ']'
                    if tape[ptr] != 0:
                        ip = bracket_map_arr[ip] + 1
                    else:
                        ip += 1

                else:
                    # Shouldn't get here; skip
                    ip += 1

                steps += 1

        except Exception:
            # We can't produce Python exceptions from compiled code reliably for the caller,
            # return runtime error code.
            return steps, 0, out_len, 3

        # normal termination
        return steps, 1, out_len, 0


# -----------------------
# Numba-wrapper and driver
# -----------------------
def _run_numba_core(
    clean: str,
    input_bytes: bytes,
    tape: np.ndarray,
    bracket_map: dict[int, int],
    max_steps: int,
    wrap_pointer: bool,
    clamp_pointer: bool,
) -> tuple[str, int, bool, str | None]:
    """
    Prepare arrays and call the njit core. Reconstruct output string from output buffer.
    Returns: (output_str, steps, halted_bool, error_or_None)
    """
    # convert code to int32 ordinals
    code_len = len(clean)
    if code_len == 0:
        return ("", 0, True, None)

    code_arr = np.frombuffer(clean.encode("ascii"), dtype=np.uint8).astype(np.int32)

    # bracket map as int32 array, -1 for non-bracket positions
    bracket_map_arr = np.full(code_len, -1, dtype=np.int32)
    if bracket_map:
        indices = np.array(list(bracket_map.keys()), dtype=np.int32)
        values = np.array(list(bracket_map.values()), dtype=np.int32)
        bracket_map_arr[indices] = values

    tape_len = int(tape.shape[0])

    # input arr
    input_arr = np.frombuffer(input_bytes, dtype=np.uint8).astype(np.int32)
    input_len = int(input_arr.shape[0])

    # output buffer (store byte ordinals). Reserve reasonable size:
    # Worst case: output cannot exceed max_steps; but that's huge. Instead reserve smaller:
    # choose min(max_steps, 1_000_000) as safety but make it dynamic if needed.
    max_output = min(max_steps, 1_000_000)
    output_arr = np.zeros(max_output, dtype=np.int32)

    wrap_flag = 1 if wrap_pointer else 0
    clamp_flag = 1 if clamp_pointer else 0

    if not _NUMBA_AVAILABLE or _numba_core is None:
        raise RuntimeError("Numba core not available")

    try:
        steps, halted_flag, out_len, error_code = _numba_core(
            code_arr,
            code_len,
            bracket_map_arr,
            tape,
            tape_len,
            input_arr,
            input_len,
            output_arr,
            max_output,
            max_steps,
            wrap_flag,
            clamp_flag,
        )
    except Exception as exc:
        # Compilation / runtime error: propagate to caller for fallback
        raise RuntimeError(f"Numba execution failed: {exc}")

    # reconstruct output string from output buffer
    if out_len > 0:
        output_str = output_arr[:out_len].astype(np.uint8).tobytes().decode("latin1")
    else:
        output_str = ""

    if error_code != 0:
        if error_code == 1:
            return (output_str, int(steps), False, "max_steps_exceeded")
        if error_code == 2:
            return (output_str, int(steps), False, "output_buffer_overflow")
        return (output_str, int(steps), False, "numba_runtime_error")

    return (output_str, int(steps), bool(halted_flag), None)


def _apply_resource_limits(cpu_time_s: int, memory_bytes: int) -> None:
    if cpu_time_s > 0 and hasattr(resource, "RLIMIT_CPU"):
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_s, cpu_time_s))
    if memory_bytes > 0 and hasattr(resource, "RLIMIT_AS"):
        resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))


def _run_brainfuck_internal(
    code: str,
    input_data: str = "",
    *,
    tape_size: int = 30_000,
    max_steps: int = 10_000_000,
    wrap_pointer: bool = True,
    clamp_pointer: bool = False,
    use_numba: bool | None = None,
) -> BFResult:
    """
    Run brainfuck code with an explicit Numba backend attempt.

    If use_numba is True we insist on trying numba; if False we skip it.
    If None we auto-decide based on availability and I/O presence.
    """
    clean = sanitize(code)
    try:
        bracket_map = build_bracket_map(clean)
    except SyntaxError as e:
        return BFResult(success=False, output="", error=str(e), steps=0, halted=False)

    try:
        tape = np.zeros(tape_size, dtype=np.uint8)
    except Exception as exc:
        return BFResult(success=False, output="", error=f"tape_init_error: {exc}", steps=0, halted=False)

    # prepare input bytes: UTF-8 with replacement to avoid exceptions
    input_bytes = input_data.encode("utf-8", errors="replace")

    # decide about numba
    has_io = ("." in clean) or ("," in clean)
    if use_numba is None:
        use_numba = _NUMBA_AVAILABLE and (not has_io) and (len(clean) > 200 and clean.count("[") > 2)

    if use_numba and _NUMBA_AVAILABLE:
        try:
            out, steps, halted, error = _run_numba_core(clean, input_bytes, tape, bracket_map, max_steps, wrap_pointer, clamp_pointer)
            if error is None:
                return BFResult(success=True, output=out, error=None, steps=steps, halted=halted)
            else:
                # Numba executed but returned an error; fall through to pure interpreter fallback.
                # We return fallback result below.
                pass
        except Exception as exc:
            # Numba compile/runtime failure: log-ish fallback by returning fallback result
            # Caller can inspect error message if needed.
            numba_err = str(exc)
            # Fall back to pure interpreter (safe)
            out, steps, halted, error = _interpret_pure(clean, input_bytes, tape, bracket_map, max_steps, wrap_pointer, clamp_pointer)
            if error is None:
                return BFResult(success=True, output=out, error=None, steps=steps, halted=halted)
            else:
                # Both numba and pure failed
                return BFResult(success=False, output=out, error=f"numba_error: {numba_err}; pure_error: {error}", steps=steps, halted=halted)

    # Fallback: pure interpreter
    out, steps, halted, error = _interpret_pure(clean, input_bytes, tape, bracket_map, max_steps, wrap_pointer, clamp_pointer)
    return BFResult(success=(error is None), output=out, error=error, steps=steps, halted=halted)


def _sandbox_worker(
    code: str,
    input_data: str,
    tape_size: int,
    max_steps: int,
    wrap_pointer: bool,
    clamp_pointer: bool,
    use_numba: bool | None,
    cpu_time_s: int,
    memory_bytes: int,
    conn: Connection,
) -> None:
    _apply_resource_limits(cpu_time_s, memory_bytes)
    result = _run_brainfuck_internal(
        code,
        input_data,
        tape_size=tape_size,
        max_steps=max_steps,
        wrap_pointer=wrap_pointer,
        clamp_pointer=clamp_pointer,
        use_numba=use_numba,
    )
    payload: BFResultTuple = (
        result.success,
        result.output,
        result.error,
        result.steps,
        result.halted,
    )
    conn.send(payload)
    conn.close()


def _should_use_sandbox(clean_code: str, max_steps: int, mode: SandboxMode) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if max_steps >= _SANDBOX_STEP_THRESHOLD:
        return True
    return len(clean_code) >= _SANDBOX_STEP_THRESHOLD


def _run_brainfuck_sandboxed(
    code: str,
    input_data: str,
    *,
    tape_size: int,
    max_steps: int,
    wrap_pointer: bool,
    clamp_pointer: bool,
    use_numba: bool | None,
    wall_time_s: float,
    cpu_time_s: int,
    memory_bytes: int,
) -> BFResult:
    if wall_time_s <= 0.0:
        return BFResult(
            success=False,
            output="",
            error="sandbox_invalid_wall_time",
            steps=0,
            halted=False,
        )
    if cpu_time_s <= 0:
        return BFResult(
            success=False,
            output="",
            error="sandbox_invalid_cpu_limit",
            steps=0,
            halted=False,
        )
    if memory_bytes <= 0:
        return BFResult(
            success=False,
            output="",
            error="sandbox_invalid_memory_limit",
            steps=0,
            halted=False,
        )

    parent_conn, child_conn = Pipe(duplex=False)
    ctx = get_context("spawn")
    process = ctx.Process(
        target=_sandbox_worker,
        args=(
            code,
            input_data,
            tape_size,
            max_steps,
            wrap_pointer,
            clamp_pointer,
            use_numba,
            cpu_time_s,
            memory_bytes,
            child_conn,
        ),
    )
    process.start()
    child_conn.close()

    deadline = time.monotonic() + wall_time_s
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            break
        if parent_conn.poll(remaining):
            result_tuple = parent_conn.recv()
            process.join(timeout=0.1)
            return BFResult(
                success=result_tuple[0],
                output=result_tuple[1],
                error=result_tuple[2],
                steps=result_tuple[3],
                halted=result_tuple[4],
            )
        if not process.is_alive():
            break

    if parent_conn.poll(0.0):
        result_tuple = parent_conn.recv()
        process.join(timeout=0.1)
        return BFResult(
            success=result_tuple[0],
            output=result_tuple[1],
            error=result_tuple[2],
            steps=result_tuple[3],
            halted=result_tuple[4],
        )
    if not process.is_alive():
        process.join(timeout=0.1)
        return BFResult(
            success=False,
            output="",
            error="sandbox_execution_failed",
            steps=0,
            halted=False,
        )

    process.terminate()
    process.join(timeout=0.1)
    return BFResult(
        success=False,
        output="",
        error="sandbox_timeout",
        steps=0,
        halted=False,
    )


def run_brainfuck(
    code: str,
    input_data: str = "",
    *,
    tape_size: int = 30_000,
    max_steps: int = 10_000_000,
    wrap_pointer: bool = True,
    clamp_pointer: bool = False,
    use_numba: bool | None = None,
    sandbox_mode: SandboxMode = "auto",
    sandbox_wall_time_s: float = _DEFAULT_SANDBOX_WALL_TIME_S,
    sandbox_cpu_time_s: int = _DEFAULT_SANDBOX_CPU_SECONDS,
    sandbox_memory_bytes: int = _DEFAULT_SANDBOX_MEMORY_BYTES,
) -> BFResult:
    """
    Run brainfuck code with an explicit Numba backend attempt.

    If use_numba is True we insist on trying numba; if False we skip it.
    If None we auto-decide based on availability and I/O presence.
    """
    clean = sanitize(code)
    if _should_use_sandbox(clean, max_steps, sandbox_mode):
        return _run_brainfuck_sandboxed(
            code,
            input_data,
            tape_size=tape_size,
            max_steps=max_steps,
            wrap_pointer=wrap_pointer,
            clamp_pointer=clamp_pointer,
            use_numba=use_numba,
            wall_time_s=sandbox_wall_time_s,
            cpu_time_s=sandbox_cpu_time_s,
            memory_bytes=sandbox_memory_bytes,
        )
    return _run_brainfuck_internal(
        code,
        input_data,
        tape_size=tape_size,
        max_steps=max_steps,
        wrap_pointer=wrap_pointer,
        clamp_pointer=clamp_pointer,
        use_numba=use_numba,
    )
