"""Fixed dungeon scene layout for the lighting/FOV tool."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Final

import numpy as np


class ElementType(IntEnum):
    """Scene element types for the fixed dungeon layout."""

    WALL = 0
    FLOOR = 1
    PILLAR = 2
    HALLWAY_FLOOR = 3


@dataclass
class LightSourceDef:
    """Definition of a light source in the scene."""

    name: str
    x: int
    y: int
    radius: int
    color: tuple[int, int, int]
    intensity: float = 1.0


@dataclass
class SceneLayout:
    """Container for the fixed dungeon scene data."""

    width: int
    height: int
    tiles: np.ndarray  # 2D array of ElementType values
    height_map: np.ndarray  # 2D array of floor heights
    ceiling_map: np.ndarray  # 2D array of ceiling heights
    light_sources: list[LightSourceDef] = field(default_factory=list)
    player_pos: tuple[int, int] = (0, 0)


# Scene dimensions
SCENE_WIDTH: Final[int] = 40
SCENE_HEIGHT: Final[int] = 25

# Room dimensions and position
ROOM_X: Final[int] = 8
ROOM_Y: Final[int] = 5
ROOM_WIDTH: Final[int] = 20
ROOM_HEIGHT: Final[int] = 15

# Hallway dimensions
HALLWAY_WIDTH: Final[int] = 3


def create_fixed_scene() -> SceneLayout:
    """Create the fixed dungeon scene with room, pillars, hallways, and lights."""
    # Initialize with walls
    tiles = np.full((SCENE_HEIGHT, SCENE_WIDTH), ElementType.WALL, dtype=np.uint8)
    height_map = np.zeros((SCENE_HEIGHT, SCENE_WIDTH), dtype=np.int16)
    ceiling_map = np.full((SCENE_HEIGHT, SCENE_WIDTH), 10, dtype=np.int16)

    # Carve out the main room
    room_y_end = ROOM_Y + ROOM_HEIGHT
    room_x_end = ROOM_X + ROOM_WIDTH
    tiles[ROOM_Y:room_y_end, ROOM_X:room_x_end] = ElementType.FLOOR
    ceiling_map[ROOM_Y:room_y_end, ROOM_X:room_x_end] = 6

    # Add pillars (4 symmetrically placed)
    pillar_positions = [
        (ROOM_X + 4, ROOM_Y + 3),
        (ROOM_X + ROOM_WIDTH - 5, ROOM_Y + 3),
        (ROOM_X + 4, ROOM_Y + ROOM_HEIGHT - 4),
        (ROOM_X + ROOM_WIDTH - 5, ROOM_Y + ROOM_HEIGHT - 4),
    ]
    for px, py in pillar_positions:
        tiles[py, px] = ElementType.PILLAR
        height_map[py, px] = 3  # Pillars have some height

    # North hallway (extending upward from room center)
    hallway_n_x = ROOM_X + ROOM_WIDTH // 2 - HALLWAY_WIDTH // 2
    hallway_n_y_start = 0
    hallway_n_y_end = ROOM_Y
    for y in range(hallway_n_y_start, hallway_n_y_end):
        for x in range(hallway_n_x, hallway_n_x + HALLWAY_WIDTH):
            if 0 <= x < SCENE_WIDTH and 0 <= y < SCENE_HEIGHT:
                tiles[y, x] = ElementType.HALLWAY_FLOOR
                ceiling_map[y, x] = 4

    # East hallway (extending rightward from room center)
    hallway_e_x_start = room_x_end
    hallway_e_x_end = SCENE_WIDTH
    hallway_e_y = ROOM_Y + ROOM_HEIGHT // 2 - HALLWAY_WIDTH // 2
    for y in range(hallway_e_y, hallway_e_y + HALLWAY_WIDTH):
        for x in range(hallway_e_x_start, hallway_e_x_end):
            if 0 <= x < SCENE_WIDTH and 0 <= y < SCENE_HEIGHT:
                tiles[y, x] = ElementType.HALLWAY_FLOOR
                ceiling_map[y, x] = 4

    # Define light sources
    light_sources = [
        LightSourceDef(
            name="torch_nw",
            x=ROOM_X + 2,
            y=ROOM_Y + 2,
            radius=8,
            color=(255, 160, 60),
            intensity=1.0,
        ),
        LightSourceDef(
            name="torch_se",
            x=ROOM_X + ROOM_WIDTH - 3,
            y=ROOM_Y + ROOM_HEIGHT - 3,
            radius=8,
            color=(255, 160, 60),
            intensity=1.0,
        ),
        LightSourceDef(
            name="orb_center",
            x=ROOM_X + ROOM_WIDTH // 2,
            y=ROOM_Y + ROOM_HEIGHT // 2,
            radius=10,
            color=(160, 200, 255),
            intensity=0.8,
        ),
    ]

    # Player position (center of room)
    player_pos = (ROOM_X + ROOM_WIDTH // 2, ROOM_Y + ROOM_HEIGHT // 2)

    return SceneLayout(
        width=SCENE_WIDTH,
        height=SCENE_HEIGHT,
        tiles=tiles,
        height_map=height_map,
        ceiling_map=ceiling_map,
        light_sources=light_sources,
        player_pos=player_pos,
    )


def get_element_name(element_type: ElementType) -> str:
    """Get a human-readable name for an element type."""
    names: dict[ElementType, str] = {
        ElementType.WALL: "Wall",
        ElementType.FLOOR: "Floor",
        ElementType.PILLAR: "Pillar",
        ElementType.HALLWAY_FLOOR: "Hallway Floor",
    }
    return names.get(element_type, "Unknown")
