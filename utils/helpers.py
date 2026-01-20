# utils/helpers.py
from __future__ import annotations

import re

import structlog

log = structlog.get_logger(__name__)

try:
    from utils.game_rng import GameRNG
except Exception as e:  # pragma: no cover - critical import failure
    log.critical("GameRNG type could not be imported", error=str(e))
    raise

# --- Dice Rolling Utility (Moved from effects.handlers) ---
DICE_PATTERN = re.compile(r"(\d+)?d(\d+)(?:([+-])(\d+))?", re.IGNORECASE)


def _is_int_literal(value: str) -> bool:
    if not value:
        return False
    stripped = value
    if stripped[0] in "+-":
        stripped = stripped[1:]
    return stripped.isdigit()


# Make it a public function
def roll_dice(dice_str: str | None, rng: GameRNG | None) -> int:
    """
    Rolls dice based on a string format (e.g., "1d6", "2d4+1").
    Requires a :class:`GameRNG` instance and raises ``ValueError`` if ``rng`` is
    ``None``.
    """
    if not dice_str:
        return 0
    if rng is None:
        log.error("Dice roll attempted without RNG instance!")
        raise ValueError("RNG instance is required for roll_dice.")

    if _is_int_literal(dice_str):
        return int(dice_str)

    match = DICE_PATTERN.match(dice_str)
    if match:
        num_dice_str, sides_str, operator, bonus_str = match.groups()
        num_dice = int(num_dice_str) if num_dice_str else 1
        sides = int(sides_str)
        bonus = int(f"{operator}{bonus_str}") if operator and bonus_str else 0
        if sides <= 0:
            return bonus
        if num_dice <= 0:
            return bonus
        # Use the passed RNG instance
        try:
            rng_get_int = rng.get_int
            roll_total = 0
            for _ in range(num_dice):
                roll_total += rng_get_int(1, sides)
            return roll_total + bonus
        except AttributeError:
            log.error(
                "Passed rng object does not have expected 'get_int' method.",
                rng_type=type(rng),
            )
            raise  # Re-raise the error as this is unexpected
        except Exception as e:
            log.error("Error during RNG dice roll", error=str(e), exc_info=True)
            raise  # Re-raise other RNG errors

    log.error("Invalid dice string format", dice_str=dice_str)
    return 0
