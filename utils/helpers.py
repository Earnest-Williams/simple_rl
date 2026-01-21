# utils/helpers.py
from __future__ import annotations

from typing import Literal

import structlog
from pydantic import BaseModel, field_validator, ValidationError

log = structlog.get_logger(__name__)

try:
    from utils.game_rng import GameRNG
except Exception as e:  # pragma: no cover - critical import failure
    log.critical("GameRNG type could not be imported", error=str(e))
    raise


class DiceRoll(BaseModel):
    """Pydantic model for dice roll notation (e.g., '2d6+3', 'd20', '3d8-2')."""

    num_dice: int = 1
    sides: int
    modifier: int = 0

    @field_validator("num_dice", "sides")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v < 0:
            raise ValueError("Number of dice and sides must be non-negative")
        return v

    @classmethod
    def from_string(cls, dice_str: str) -> DiceRoll:
        """
        Parse dice notation string into a DiceRoll model.

        Supported formats:
        - "1d6" -> 1 die with 6 sides
        - "2d4+1" -> 2 dice with 4 sides, +1 modifier
        - "d20" -> 1 die with 20 sides (num_dice defaults to 1)
        - "3d8-2" -> 3 dice with 8 sides, -2 modifier

        Raises:
            ValueError: If the string doesn't match dice notation format
        """
        dice_str = dice_str.strip().lower()

        # Handle modifier (+/- at the end)
        modifier = 0
        if "+" in dice_str:
            parts = dice_str.split("+")
            if len(parts) != 2:
                raise ValueError(f"Invalid dice notation: {dice_str}")
            dice_str = parts[0]
            modifier = int(parts[1])
        elif "-" in dice_str and dice_str.rfind("-") > 0:
            # Only split on - if it's not at the start (negative modifier)
            idx = dice_str.rfind("-")
            modifier_part = dice_str[idx:]
            dice_str = dice_str[:idx]
            modifier = int(modifier_part)

        # Parse the XdY part
        if "d" not in dice_str:
            raise ValueError(f"Invalid dice notation (missing 'd'): {dice_str}")

        parts = dice_str.split("d")
        if len(parts) != 2:
            raise ValueError(f"Invalid dice notation: {dice_str}")

        num_dice_str, sides_str = parts

        # Handle optional number of dice (defaults to 1)
        if num_dice_str == "":
            num_dice = 1
        else:
            try:
                num_dice = int(num_dice_str)
            except ValueError:
                raise ValueError(f"Invalid number of dice: {num_dice_str}")

        # Parse sides
        if not sides_str:
            raise ValueError("Dice sides cannot be empty")
        try:
            sides = int(sides_str)
        except ValueError:
            raise ValueError(f"Invalid number of sides: {sides_str}")

        return cls(num_dice=num_dice, sides=sides, modifier=modifier)

    def roll(self, rng: GameRNG) -> int:
        """
        Execute the dice roll using the provided RNG.

        Args:
            rng: GameRNG instance for deterministic rolling

        Returns:
            Total roll result including modifier
        """
        if self.sides <= 0:
            return self.modifier
        if self.num_dice <= 0:
            return self.modifier

        total = 0
        for _ in range(self.num_dice):
            total += rng.get_int(1, self.sides)
        return total + self.modifier


def _is_int_literal(value: str) -> bool:
    """Check if a string is an integer literal."""
    if not value:
        return False
    stripped = value.strip()
    if stripped[0] in "+-":
        stripped = stripped[1:]
    return stripped.isdigit()


def roll_dice(dice_str: str | None, rng: GameRNG | None) -> int:
    """
    Rolls dice based on a string format (e.g., "1d6", "2d4+1").
    Requires a :class:`GameRNG` instance and raises ``ValueError`` if ``rng`` is
    ``None``.

    This function now uses Pydantic validation instead of regex for better
    error handling and compliance with AGENTS.md Section 1.6.
    """
    if not dice_str:
        return 0
    if rng is None:
        log.error("Dice roll attempted without RNG instance!")
        raise ValueError("RNG instance is required for roll_dice.")

    # Check for plain integer literal first
    if _is_int_literal(dice_str):
        return int(dice_str)

    # Parse using Pydantic model
    try:
        dice_roll = DiceRoll.from_string(dice_str)
        return dice_roll.roll(rng)
    except (ValueError, ValidationError) as e:
        log.error("Invalid dice string format", dice_str=dice_str, error=str(e))
        return 0
    except AttributeError:
        log.error(
            "Passed rng object does not have expected 'get_int' method.",
            rng_type=type(rng),
        )
        raise
    except Exception as e:
        log.error("Error during dice roll", error=str(e), exc_info=True)
        raise
