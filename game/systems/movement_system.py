"""Movement helper utilities.

This module exposes small helper functions for moving entities around the
game map.  The helpers centralise common checks such as map bounds and tile
walkability before delegating to the :class:`EntityRegistry` to update the
entity's position component.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from game.entities.components import Position
from game.perception_events import NoiseEvent

if TYPE_CHECKING:  # pragma: no cover - imported for type checking only
    from game.game_state import GameState


def try_move(entity_id: int, dx: int, dy: int, gs: GameState) -> bool:
    """Attempt to move an entity.

    Parameters
    ----------
    entity_id:
        The identifier of the entity to move.
    dx, dy:
        Delta values to apply to the entity's current position.
    gs:
        The active :class:`~game.game_state.GameState` instance which contains
        the map and entity registry.

    Returns
    -------
    bool
        ``True`` if the movement succeeded, ``False`` otherwise.

    Notes
    -----
    This helper only checks simple bounds and walkability rules.  Systems that
    require additional behaviour (e.g. falling, bump attacks) should perform
    those checks before calling this function.
    """

    entity_reg = gs.entity_registry
    game_map = gs.game_map

    current_pos = entity_reg.get_position(entity_id)
    if current_pos is None:
        return False

    x, y = current_pos
    dest_x, dest_y = x + dx, y + dy

    if not game_map.in_bounds(dest_x, dest_y):
        return False

    if not game_map.is_walkable(dest_x, dest_y):
        return False

    moved = entity_reg.set_position(entity_id, Position(dest_x, dest_y))
    if moved:
        # Moving entities generate gameplay noise at their destination. This is
        # intentionally a perception event, not an audio playback call.
        with contextlib.suppress(AttributeError):
            gs.noise_events.append(
                NoiseEvent(
                    x=dest_x,
                    y=dest_y,
                    intensity=10.0,
                    source_id=entity_id,
                    cause="movement",
                )
            )

        # Play movement sound effect if it's the player
        sound_manager = getattr(gs, "sound_manager", None)
        if entity_id == gs.player_id and sound_manager is not None:
            terrain_type = (
                gs.game_map.get_tile_type_name(dest_x, dest_y)
                if hasattr(gs.game_map, "get_tile_type_name")
                else "floor"
            )
            sound_context = {
                "entity": "player",
                "terrain": terrain_type,
                "position": (dest_x, dest_y),
            }
            sound_manager.handle_game_event("player_move", sound_context)
    return moved
