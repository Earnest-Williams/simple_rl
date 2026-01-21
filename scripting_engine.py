"""
Scripting Engine - A module for script processing and command automation

This module provides tools for processing game commands, defining macros,
and interpreting scripts. It includes:
- MacroManager: Handles defining, expanding, and executing command macros
- BrainfuckRunner: A simple Brainfuck interpreter for script execution
"""

from __future__ import annotations

import re
from typing import Dict, Literal, Protocol, TypedDict

from magic.brainfuck_numba import BFResult, run_brainfuck


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
        # Prevent infinite recursion more robustly
        pattern: re.Pattern[str] = re.compile(r"!\w+")
        expanded_text: str = text
        depth: int = 0
        seen_macros: set[str] = set()  # Track macros used in current expansion chain

        while depth < expansion_limit:
            found_macro: bool = False
            current_expansion: str = ""
            last_end: int = 0

            for match in pattern.finditer(expanded_text):
                macro_name: str = match.group(0)
                start: int
                end: int
                start, end = match.span()

                # Append text before the macro
                current_expansion += expanded_text[last_end:start]

                if macro_name in seen_macros:
                    # Prevent direct recursion within this expansion path
                    warning_message = (
                        f"Warning: Detected recursion for macro {macro_name}. "
                        "Stopping expansion here."
                    )
                    print(warning_message)  # TODO: Replace with logging.warning
                    current_expansion += macro_name  # Keep the macro name as is
                elif macro_name in self.macros:
                    # Expand the macro
                    replacement: str = self.macros[macro_name]
                    current_expansion += replacement
                    found_macro = True
                    # We could add 'macro_name' to seen_macros here for stricter
                    # recursion check, but simple depth limit might be enough.
                else:
                    # Macro not found, keep it as is
                    current_expansion += macro_name

                last_end = end

            # Append any remaining text after the last macro
            current_expansion += expanded_text[last_end:]

            if not found_macro:
                # No more macros found in this pass
                break

            expanded_text = current_expansion
            depth += 1
            seen_macros.clear()  # Reset seen set for the next level of expansion.

        if depth >= expansion_limit:
            print(f"Warning: Macro expansion reached depth limit ({expansion_limit}).")

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
