"""
Dungeon Generator Module - Create procedural dungeons with connected rooms

This module provides functionality for creating grid-based dungeons with
customizable room parameters and connections between rooms.
"""

import warnings

# Suppress numpy overflow warnings that are expected with uint64 operations
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="overflow encountered"
)


def rooms_overlap(r1, r2, gap=3):
    """
    Check if two rooms overlap, including a specified gap between them.

    Args:
        r1 (tuple): First room as (x, y, width, height)
        r2 (tuple): Second room as (x, y, width, height)
        gap (int): Minimum gap to maintain between rooms

    Returns:
        bool: True if rooms overlap or are too close, False otherwise
    """
    x1, y1, w1, h1 = r1
    x2, y2, w2, h2 = r2
    return not (
        x1 + w1 + gap <= x2
        or x2 + w2 + gap <= x1
        or y1 + h1 + gap <= y2
        or y2 + h2 + gap <= y1
    )


def create_dungeon(
    width, height, num_rooms, min_room_size, max_room_size, room_gap, rng
):
    """
    Create a procedurally generated dungeon with rooms and connecting hallways.

    Args:
        width (int): Width of the dungeon
        height (int): Height of the dungeon
        num_rooms (int): Target number of rooms to generate
        min_room_size (int): Minimum room width/height
        max_room_size (int): Maximum room width/height
        room_gap (int): Minimum spacing between rooms
        rng: Random number generator object with get_int method

    Returns:
        tuple: (dungeon grid, room_data)
            - dungeon grid is a 2D array where '.' is floor and '#' is wall
            - room_data is a list of tuples, each containing (room, center)
                where room is (x, y, width, height) and center is (x, y)
    """
    dungeon = [["#"] * width for _ in range(height)]
    rooms, centers = [], []
    attempts = 0

    while (
        len(rooms) < num_rooms and attempts < 1000
    ):  # Limit attempts to prevent infinite loops
        # Generate room dimensions
        w = rng.get_int(min_room_size, max_room_size)
        h = rng.get_int(min_room_size, max_room_size)

        # Ensure coordinates are within bounds, leaving border space
        x = rng.get_int(1, width - w - 1)
        y = rng.get_int(1, height - h - 1)

        new_room = (x, y, w, h)

        # Check overlap with existing rooms
        is_overlapping = False
        for other in rooms:
            if rooms_overlap(new_room, other, room_gap):
                is_overlapping = True
                break

        if is_overlapping:
            attempts += 1
            continue

        # Carve the room
        for i in range(y, y + h):
            for j in range(x, x + w):
                dungeon[i][j] = "."

        rooms.append(new_room)
        centers.append((x + w // 2, y + h // 2))
        attempts = 0  # Reset attempts after successful placement

    # Handle case where not enough rooms were placed
    if len(rooms) < num_rooms:
        print(f"Warning: Only placed {len(rooms)} out of {num_rooms} desired rooms.")

    room_data = list(zip(rooms, centers))

    if room_data:  # Only connect rooms if any were created
        connect_rooms(dungeon, room_data)

    return dungeon, room_data


def create_hallway(dungeon, start, end):
    """
    Create a hallway between two points using an L-shaped connector.

    Args:
        dungeon (list): 2D dungeon grid
        start (tuple): Starting coordinates (x, y)
        end (tuple): Ending coordinates (x, y)
    """
    x1, y1 = start
    x2, y2 = end

    # Horizontal segment first
    for x in range(min(x1, x2), max(x1, x2) + 1):
        if 0 <= y1 < len(dungeon) and 0 <= x < len(dungeon[0]):
            dungeon[y1][x] = "."

    # Vertical segment second
    for y in range(min(y1, y2), max(y1, y2) + 1):
        if 0 <= y < len(dungeon) and 0 <= x2 < len(dungeon[0]):
            dungeon[y][x2] = "."


def connect_rooms(dungeon, room_data):
    """
    Connect rooms with L-shaped hallways.

    Args:
        dungeon (list): 2D dungeon grid
        room_data (list): List of (room, center) tuples
    """
    # Sort centers by x then y to connect nearest first
    sorted_centers = sorted([center for _, center in room_data])

    if len(sorted_centers) > 1:
        for i in range(len(sorted_centers) - 1):
            create_hallway(dungeon, sorted_centers[i], sorted_centers[i + 1])

        # Optional: Add some extra connections for more loops
        # Uncomment to add additional connections
        # for _ in range(len(sorted_centers) // 4):  # Add ~25% extra connections
        #     idx1 = rng.get_int(0, len(sorted_centers)-1)
        #     idx2 = rng.get_int(0, len(sorted_centers)-1)
        #     if idx1 != idx2:
        #         create_hallway(dungeon, sorted_centers[idx1], sorted_centers[idx2])


def get_dungeon_string(dungeon, entities=None):
    """
    Convert dungeon to a displayable string, optionally with entities.

    Args:
        dungeon (list): 2D dungeon grid
        entities (dict, optional): Dictionary of entities keyed by type
            with format {'player': player_obj, 'enemies': [enemy_objs]}

    Returns:
        str: String representation of the dungeon with entities
    """
    display = [row[:] for row in dungeon]

    if entities:
        # Add player if it exists
        player = entities.get("player")
        if player and hasattr(player, "x") and hasattr(player, "y"):
            if 0 <= player.y < len(display) and 0 <= player.x < len(display[0]):
                display[player.y][player.x] = "@"

        # Add enemies if they exist
        enemies = entities.get("enemies", [])
        for enemy in enemies:
            if hasattr(enemy, "is_alive") and enemy.is_alive():
                if 0 <= enemy.y < len(display) and 0 <= enemy.x < len(display[0]):
                    display[enemy.y][enemy.x] = "S"  # Assuming 'S' for skeletons

    return "\n".join("".join(row) for row in display)


def is_valid_position(dungeon, x, y):
    """
    Check if a position is valid and walkable.

    Args:
        dungeon (list): 2D dungeon grid
        x (int): X coordinate
        y (int): Y coordinate

    Returns:
        bool: True if position is valid and walkable
    """
    return 0 <= y < len(dungeon) and 0 <= x < len(dungeon[0]) and dungeon[y][x] == "."


def find_empty_position(dungeon, room, rng):
    """
    Find a random empty position within a room.

    Args:
        dungeon (list): 2D dungeon grid
        room (tuple): Room as (x, y, width, height)
        rng: Random number generator object with get_int method

    Returns:
        tuple: (x, y) position or None if no empty position found
    """
    x, y, w, h = room
    attempts = 10

    for _ in range(attempts):
        pos_x = rng.get_int(x, x + w - 1)
        pos_y = rng.get_int(y, y + h - 1)

        if is_valid_position(dungeon, pos_x, pos_y):
            return pos_x, pos_y

    return None  # No empty position found


def line_of_sight(dungeon, x0, y0, x1, y1):
    """
    Check if there's a clear line of sight between two points.

    Args:
        dungeon (list): 2D dungeon grid
        x0, y0 (int): Starting coordinates
        x1, y1 (int): Ending coordinates

    Returns:
        bool: True if there's a clear line of sight
    """
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    x, y = int(x0), int(y0)
    sx, sy = (1 if x1 > x0 else -1), (1 if y1 > y0 else -1)

    if dx > dy:
        err = dx / 2.0  # Use float division
        while x != x1:
            if dungeon[y][x] == "#":
                return False
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0  # Use float division
        while y != y1:
            if dungeon[y][x] == "#":
                return False
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy

    # Final check at destination
    return dungeon[int(y)][int(x)] != "#"
