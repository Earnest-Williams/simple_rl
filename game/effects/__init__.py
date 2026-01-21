"""Package initialization for game effects.

On import this module registers any handlers defined in
``ART_SUBSTANCE_DISPATCHER`` with the ``magic.executor`` subsystem.  This
ensures that magical Works can resolve their effect functions before
execution.
"""

from typing import Any, Callable

from .handlers import ART_SUBSTANCE_DISPATCHER
from magic.executor import register_handler


def _adapt_handler(handler: Callable[[dict[str, Any], dict[str, Any]], None]) -> Callable[[Any, Any], None]:
    """Wrap legacy handlers to match ``(Work, GameState)`` signature."""

    def wrapper(work: Any, game_state: Any) -> None:
        context = {"game_state": game_state}
        handler(context, {})

    return wrapper


# Populate the magic executor's registry with all known art/substance mappings
for (art, substance), handler in ART_SUBSTANCE_DISPATCHER.items():
    register_handler(art, substance, _adapt_handler(handler))
