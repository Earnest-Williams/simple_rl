import structlog

from game.entities.components import Position
from game.game_state import GameState
from game.world.game_map import GameMap

log = structlog.get_logger()


def _find_cave_entry_point_near(
    gs: GameState, x: int, y: int
) -> tuple[int, int] | None:
    from game.expedition.resolvers import resolve_cave_metadata_at

    for dx, dy in (
        (0, 0),
        (-1, 0),
        (1, 0),
        (0, -1),
        (0, 1),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    ):
        nx = x + dx
        ny = y + dy
        if resolve_cave_metadata_at(gs, nx, ny):
            return nx, ny
    return None


def enter_cave_at(gs: GameState, x: int, y: int) -> bool:
    from game.expedition.resolvers import resolve_cave_metadata_at

    metadata = resolve_cave_metadata_at(gs, x, y)
    if not metadata:
        gs.add_message("There is no cave entrance here.", (150, 150, 150))
        return False

    expedition = getattr(gs, "expedition", None)
    if expedition is not None and not expedition.blockage_cleared:
        gs.add_message(
            "The blocked road must be cleared before the expedition can enter the cave.",
            (255, 200, 120),
        )
        return False

    cave_type = metadata.get("cave_type", "cave")
    seasonal_state = metadata.get("seasonal_state", "unknown season")
    flow_group = metadata.get("flow_group", "unknown")

    gs.add_message(
        f"Cave entered: {cave_type}, {seasonal_state} flow group {flow_group}.",
        (100, 255, 100),
    )

    # Backup overland state
    gs.overland_map_backup = gs.game_map
    gs.overland_player_pos_backup = gs.player_position

    # Create minimal interior
    new_map = GameMap(20, 20)
    new_map.create_test_room()

    spawn_x, spawn_y = 10, 10
    new_map.vertical_transitions.append(
        {"type": "exit_to_overland", "x": spawn_x, "y": spawn_y}
    )

    # Switch map in GameState
    gs.game_map = new_map
    gs._map_width = new_map.width
    gs._map_height = new_map.height
    gs.zone_manager.map_width = new_map.width
    gs.zone_manager.map_height = new_map.height
    gs.entity_registry.ensure_occupancy_shape(new_map.width, new_map.height)
    gs.entity_registry.rebuild_occupancy()
    gs._ensure_perception_arrays()

    gs.entity_registry.set_position(gs.player_id, Position(spawn_x, spawn_y))

    if hasattr(gs, "expedition") and gs.expedition:
        gs.expedition.cave_entered = True

    gs.update_fov()

    return True


def enter_cave_near(gs: GameState, x: int, y: int) -> bool:
    entry_point = _find_cave_entry_point_near(gs, x, y)
    if entry_point is None:
        gs.add_message("There is no cave entrance here.", (150, 150, 150))
        return False
    return enter_cave_at(gs, entry_point[0], entry_point[1])


def exit_cave(gs: GameState) -> bool:
    player_pos = gs.player_position
    if not player_pos:
        return False

    px, py = player_pos
    is_exit = False
    for transition in gs.game_map.vertical_transitions:
        if (
            transition.get("type") == "exit_to_overland"
            and transition.get("x") == px
            and transition.get("y") == py
        ):
            is_exit = True
            break

    if not is_exit:
        gs.add_message("There is no exit here.", (150, 150, 150))
        return False

    if not hasattr(gs, "overland_map_backup") or not gs.overland_map_backup:
        gs.add_message("Cannot find overland map to return to.", (255, 0, 0))
        return False

    gs.add_message("You return to the surface.", (100, 255, 100))

    # Restore overland state
    new_map = gs.overland_map_backup
    old_pos = gs.overland_player_pos_backup

    gs.game_map = new_map
    gs._map_width = new_map.width
    gs._map_height = new_map.height
    gs.zone_manager.map_width = new_map.width
    gs.zone_manager.map_height = new_map.height
    gs.entity_registry.ensure_occupancy_shape(new_map.width, new_map.height)
    gs.entity_registry.rebuild_occupancy()
    gs._ensure_perception_arrays()

    gs.entity_registry.set_position(gs.player_id, old_pos)

    # Clear backups
    gs.overland_map_backup = None
    gs.overland_player_pos_backup = None

    gs.update_fov()

    return True
