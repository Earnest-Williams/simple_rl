"""
Scripting Engine - A module for script processing and command automation

This module provides tools for processing game commands, defining macros,
and interpreting scripts. It includes:
- MacroManager: Handles defining, expanding, and executing command macros
- BrainfuckRunner: A simple Brainfuck interpreter for script execution
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Literal, Protocol, TypedDict

from magic.brainfuck_numba import BFResult, run_brainfuck

_MACRO_TOKEN: re.Pattern[str] = re.compile(r"(!\w+)")
MacroExpansionReason = Literal[
    "char_limit_exceeded",
    "depth_exceeded",
    "recursion_detected",
]


@dataclass(frozen=True)
class MacroExpansionError(Exception):
    reason: MacroExpansionReason
    macro_name: str | None = None

    def __str__(self) -> str:
        if self.reason == "recursion_detected" and self.macro_name is not None:
            return f"{self.reason}:{self.macro_name}"
        return self.reason


class GameStateProtocol(Protocol):
    def is_game_over(self) -> bool:
        ...

    def get_display_text(self) -> str:
        ...

    def process_turn(self, command: str) -> str:
        ...


class BFRunSuccess(TypedDict):
    success: Literal[True]
    output: str


class BFRunFailure(TypedDict):
    success: Literal[False]
    error: str


BFRunResult = BFRunSuccess | BFRunFailure


class ErrorResult(TypedDict):
    error: str
    is_error: bool


class BrainfuckRunner:
    """
    A simple and efficient Brainfuck interpreter with optional JIT compilation.
    """

    def __init__(self, tape_size: int = 30000) -> None:
        """
        Initialize the Brainfuck interpreter.

        Args:
            tape_size (int): Size of the virtual memory tape
        """
        self.tape_size: int = tape_size
        # Remove self.output state, run should return output directly

    def run(
        self, code: str, input_data: str = "", jit: bool | None = None
    ) -> BFRunResult:
        """
        Execute Brainfuck code and return the result.

        Args:
            code (str): The Brainfuck code to execute
            input_data (str): Input data to feed to the ',' command
            jit (bool or None): Whether to use JIT compilation (None = auto-detect)

        Returns:
            dict: A dictionary with 'success' status and 'output' or 'error'
        """
        try:
            bf_result: BFResult = run_brainfuck(
                code,
                input_data=input_data,
                tape_size=self.tape_size,
                use_numba=jit,
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        if bf_result.success:
            return {"success": True, "output": bf_result.output}

        error_message = bf_result.error or "unknown_brainfuck_error"
        return {"success": False, "error": error_message}


class MacroManager:
    """
    Manages the definition, expansion, and execution of command macros.
    Also handles Brainfuck code execution through integration with BrainfuckRunner.
    """

    def __init__(self, game_state: GameStateProtocol | None = None) -> None:
        """
        Initialize the MacroManager.

        Args:
            game_state: Reference to the game state for command execution
        """
        self.macros: Dict[str, str] = {}
        self.game_state: GameStateProtocol | None = (
            game_state  # Ensure this is updated if game_state changes (e.g., on load)
        )
        self.bf_runner: BrainfuckRunner = BrainfuckRunner()

    def define(self, name: str, sequence: str) -> str:
        """
        Define a new macro with the given name and command sequence.

        Args:
            name (str): The macro name (must start with !)
            sequence (str): The command sequence for this macro

        Returns:
            str: Confirmation message or error message
        """
        # Add basic validation for macro names
        if not re.match(r"^!\w+$", name):
            error_message = (
                f"Error: Invalid macro name '{name}'. Must start with ! and "
                "contain only letters, numbers, or _."
            )
            return error_message
        self.macros[name] = sequence
        return f"Defined macro {name} = {sequence}"

    def expand_macros(self, text: str, expansion_limit: int = 10) -> str:
        """
        Expand all macros in the given text, with limits to prevent infinite recursion.

        Args:
            text (str): The text containing macros to expand
            expansion_limit (int): Maximum recursive expansion depth

        Returns:
            str: The text with all macros expanded
        """
        return self.expand_macros_strict(
            text,
            max_depth=expansion_limit,
            max_chars=50_000,
        )

    def expand_macros_strict(
        self,
        text: str,
        max_depth: int = 20,
        max_chars: int = 50_000,
    ) -> str:
        """
        Expand macros using depth-first traversal with recursion detection.

        Args:
            text (str): The text containing macros to expand
            max_depth (int): Maximum recursive expansion depth
            max_chars (int): Maximum total expanded character count

        Returns:
            str: The text with all macros expanded
        """
        if max_depth < 0:
            raise ValueError("max_depth must be >= 0.")
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0.")

        def _append_text(
            out_parts: list[str],
            text_part: str,
            char_count: int,
        ) -> int:
            if not text_part:
                return char_count
            new_count: int = char_count + len(text_part)
            if new_count > max_chars:
                raise MacroExpansionError("char_limit_exceeded")
            out_parts.append(text_part)
            return new_count

        def _expand_segment(
            seg: str,
            path: list[str],
            depth: int,
            char_count: int,
        ) -> tuple[str, int]:
            if depth > max_depth:
                raise MacroExpansionError("depth_exceeded")
            out_parts: list[str] = []
            pos: int = 0
            for match in _MACRO_TOKEN.finditer(seg):
                start: int
                end: int
                start, end = match.span()
                char_count = _append_text(out_parts, seg[pos:start], char_count)

                token: str = match.group(1)
                if token in path:
                    raise MacroExpansionError("recursion_detected", token)
                if token not in self.macros:
                    char_count = _append_text(out_parts, token, char_count)
                else:
                    path.append(token)
                    expanded: str
                    expanded, char_count = _expand_segment(
                        self.macros[token],
                        path,
                        depth + 1,
                        char_count,
                    )
                    path.pop()
                    out_parts.append(expanded)
                pos = end

            char_count = _append_text(out_parts, seg[pos:], char_count)
            return "".join(out_parts), char_count

        expanded_text: str
        expanded_text, _ = _expand_segment(text, [], 0, 0)
        return expanded_text

    def execute_command_sequence(self, command_string: str) -> str:
        """
        Execute a sequence of game commands.

        Args:
            command_string (str): The command string to execute

        Returns:
            str: The game state display text after execution
        """
        # Split by semicolons to handle command sequences
        command_groups: list[str] = [
            cmd.strip() for cmd in command_string.split(";") if cmd.strip()
        ]
        outputs: list[str] = []

        # Ensure game_state is valid before processing
        if self.game_state is None:
            return "Error: Game state not available."

        for group in command_groups:
            # Process each character in the command group individually
            for char in group:
                if not char:
                    continue

                # Each single character is a valid game command
                # Check game over before processing turn
                if self.game_state.is_game_over():
                    outputs.append(self.game_state.get_display_text())
                    break  # Stop processing sequence if game ended

                result: str = self.game_state.process_turn(char)
                outputs.append(
                    result
                )  # Append the display text returned by process_turn

            # If game ended, break the outer loop too
            if self.game_state.is_game_over():
                break

        # Return the final display state text
        return outputs[-1] if outputs else "No valid commands executed."

    def process_line(self, line: str) -> str | ErrorResult:
        """
        Process a line of input, which could be a macro definition, macro execution,
        Brainfuck code, or direct game commands.

        Args:
            line (str): The input line to process

        Returns:
            str or dict: The result of processing (usually display text or error info)
        """
        line = line.strip()

        # Define a new macro
        if line.startswith("!") and "=" in line:
            # Ensure correct splitting, handle potential '=' in sequence
            parts: list[str] = line.split("=", 1)
            if len(parts) == 2:
                name: str
                seq: str
                name, seq = map(str.strip, parts)
                if name.startswith("!"):  # Validate name starts with !
                    return self.define(name, seq)
                else:
                    return "Error: Macro name must start with '!'"
            else:  # Handle case like "!foo=" or just "!foo"
                return "Error: Invalid macro definition format. Use !name=sequence"

        # Expand potential macros in the line first
        # Limit expansion depth to prevent infinite loops
        try:
            expanded_line: str = self.expand_macros(line, expansion_limit=10)
        except Exception as exc:
            return f"Error during macro expansion: {exc}"

        # Execute a macro (check if the fully expanded line is just a known macro name)
        if expanded_line.startswith("!") and expanded_line in self.macros:
            # This case might be redundant if expand_macros handles it,
            # but could be kept for clarity or direct single macro execution.
            # We re-expand here in case the macro itself contains other macros.
            final_sequence: str = self.expand_macros(
                self.macros[expanded_line], expansion_limit=10
            )
            return self.execute_command_sequence(final_sequence)

        # Check if the expanded line looks like Brainfuck code
        # Use a stricter check: must contain BF chars and potentially brackets
        is_bf_chars: bool = set(expanded_line) <= set("><+-.,[]")
        has_brackets: bool = "[" in expanded_line and "]" in expanded_line
        likely_bf: bool = is_bf_chars or has_brackets  # Adjust logic as needed

        if likely_bf and len(expanded_line) > 0:  # Check length > 0
            try:
                # Execute Brainfuck code
                # Pass empty string "" as default input for now
                result: BFRunResult = self.bf_runner.run(
                    expanded_line, input_data=""
                )

                if result["success"]:
                    bf_output: str = result["output"]
                    if bf_output:
                        # Convert Brainfuck output to game commands
                        # Note: BF output might not be valid game commands!
                        print(f"Brainfuck output: {bf_output}")  # Log BF output
                        return self.execute_command_sequence(bf_output)
                    else:
                        return "Brainfuck program executed with no command output."
                else:
                    # Return dict for clearer error handling in UI
                    return {
                        "error": f"Brainfuck Error: {result['error']}",
                        "is_error": True,
                    }
            except Exception as exc:

                # print(
                #     f"Error processing Brainfuck line: {e}\n{traceback.format_exc()}"
                # )
                return {
                    "error": f"Brainfuck Processing Error: {exc}",
                    "is_error": True,
                }

        # Otherwise, assume it's a sequence of game commands
        else:
            return self.execute_command_sequence(expanded_line)
