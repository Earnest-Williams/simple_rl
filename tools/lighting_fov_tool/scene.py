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
class MonsterDef:
    """Definition of a simple sighted monster in the test scene."""

    name: str
    x: int
    y: int
    sight_radius: int = 12
    has_eyes: bool = True


@dataclass
class SceneLayout:
    """Container for the fixed dungeon scene data."""

    width: int
    height: int
    tiles: np.ndarray  # 2D array of ElementType values
    height_map: np.ndarray  # 2D array of floor heights
    ceiling_map: np.ndarray  # 2D array of ceiling heights
    light_sources: list[LightSourceDef] = field(default_factory=list)
    monsters: list[MonsterDef] = field(default_factory=list)
    player_pos: tuple[int, int] = (0, 0)


# Scene dimensions
SCENE_WIDTH: Final[int] = 60
SCENE_HEIGHT: Final[int] = 40


def create_fixed_scene() -> SceneLayout:
    """Create a complex dungeon scene with rooms, hallways, pillars, and lights."""
    # Initialize with walls
    tiles = np.full((SCENE_HEIGHT, SCENE_WIDTH), ElementType.WALL, dtype=np.uint8)
    height_map = np.zeros((SCENE_HEIGHT, SCENE_WIDTH), dtype=np.int16)
    ceiling_map = np.full((SCENE_HEIGHT, SCENE_WIDTH), 10, dtype=np.int16)

    # 1. Main Center Room
    tiles[12:28, 20:40] = ElementType.FLOOR
    ceiling_map[12:28, 20:40] = 6

    # 2. NW Room
    tiles[4:13, 4:16] = ElementType.FLOOR
    ceiling_map[4:13, 4:16] = 5

    # 3. SE Room
    tiles[26:36, 44:56] = ElementType.FLOOR
    ceiling_map[26:36, 44:56] = 5

    # 4. NE Room
    tiles[4:14, 40:54] = ElementType.FLOOR
    ceiling_map[4:14, 40:54] = 5

    # 5. SW Room
    tiles[25:35, 5:18] = ElementType.FLOOR
    ceiling_map[25:35, 5:18] = 5

    # Symmetrically distribute pillars
    pillar_positions = [
        # Center Room pillars
        (24, 16),
        (35, 16),
        (24, 23),
        (35, 23),
        # Room NW pillar
        (9, 8),
        # Room SE pillar
        (49, 30),
        # Room NE pillars
        (44, 8),
        (49, 8),
        # Room SW pillar
        (11, 29),
    ]

    for px, py in pillar_positions:
        if 0 <= px < SCENE_WIDTH and 0 <= py < SCENE_HEIGHT:
            tiles[py, px] = ElementType.PILLAR
            height_map[py, px] = 3

    # Carve Hallways: hallway floor, ceiling 4

    # HW1: NW to Center
    tiles[13:20, 9:12] = ElementType.HALLWAY_FLOOR
    tiles[17:20, 12:20] = ElementType.HALLWAY_FLOOR
    ceiling_map[13:20, 9:12] = 4
    ceiling_map[17:20, 12:20] = 4

    # HW2: NE to Center
    tiles[14:20, 46:49] = ElementType.HALLWAY_FLOOR
    tiles[17:20, 40:46] = ElementType.HALLWAY_FLOOR
    ceiling_map[14:20, 46:49] = 4
    ceiling_map[17:20, 40:46] = 4

    # HW3: SW to Center
    tiles[20:25, 10:13] = ElementType.HALLWAY_FLOOR
    tiles[20:23, 13:20] = ElementType.HALLWAY_FLOOR
    ceiling_map[20:25, 10:13] = 4
    ceiling_map[20:23, 13:20] = 4

    # HW4: SE to Center
    tiles[20:26, 48:51] = ElementType.HALLWAY_FLOOR
    tiles[20:23, 40:48] = ElementType.HALLWAY_FLOOR
    ceiling_map[20:26, 48:51] = 4
    ceiling_map[20:23, 40:48] = 4

    # HW5: NW to NE corridor across the top
    tiles[5:8, 16:40] = ElementType.HALLWAY_FLOOR
    ceiling_map[5:8, 16:40] = 4

    # HW6: SW to SE corridor across the bottom
    tiles[30:33, 18:44] = ElementType.HALLWAY_FLOOR
    ceiling_map[30:33, 18:44] = 4

    # HW7: Light bleed test corridor
    #
    # This is a controlled occlusion test:
    #
    #   x=1:2   left hallway with a light source
    #   x=3     solid wall separator for y=15..26
    #   x=4:5   right hallway that should remain dark
    #
    # A bottom access passage connects both test hallways to HW3 far below the
    # test light. That lets the player walk into either hallway without opening
    # a short path around the separator wall within the light's default radius.
    #
    # The light at (2, 19) should not illuminate the right hallway at x=4:5
    # unless the lighting/FOV implementation leaks through walls.
    tiles[15:28, 1:3] = ElementType.HALLWAY_FLOOR
    tiles[15:28, 4:6] = ElementType.HALLWAY_FLOOR
    ceiling_map[15:28, 1:3] = 4
    ceiling_map[15:28, 4:6] = 4

    # Access passage from the center/SW hallway network into both test hallways.
    tiles[24:28, 10:13] = ElementType.HALLWAY_FLOOR
    tiles[27:28, 1:13] = ElementType.HALLWAY_FLOOR
    ceiling_map[24:28, 10:13] = 4
    ceiling_map[27:28, 1:13] = 4

    # Define light sources
    light_sources = [
        LightSourceDef(
            name="orb_center",
            x=30,
            y=20,
            radius=8,
            color=(160, 200, 255),
            intensity=0.50,
        ),
        LightSourceDef(
            name="torch_nw",
            x=7,
            y=6,
            radius=7,
            color=(255, 160, 60),
            intensity=0.40,
        ),
        LightSourceDef(
            name="torch_se",
            x=52,
            y=32,
            radius=7,
            color=(255, 160, 60),
            intensity=0.40,
        ),
        LightSourceDef(
            name="brazier_ne",
            x=47,
            y=7,
            radius=7,
            color=(240, 100, 50),
            intensity=0.45,
        ),
        LightSourceDef(
            name="lantern_sw",
            x=11,
            y=27,
            radius=6,
            color=(200, 255, 200),
            intensity=0.35,
        ),
        LightSourceDef(
            name="bleed_test_light",
            x=2,
            y=19,
            radius=5,
            color=(255, 255, 255),
            intensity=0.75,
        ),
    ]

    # Player position: center of room
    player_pos = (30, 20)

    # Dummy sighted monster in the bottom-right room. This keeps nearby lights
    # active even when the player cannot see that room, so the tool can test
    # visibility-gated light emission from non-player observers.
    monsters = [
        MonsterDef(
            name="dummy_eyes",
            x=54,
            y=34,
            sight_radius=12,
            has_eyes=True,
        ),
    ]

    return SceneLayout(
        width=SCENE_WIDTH,
        height=SCENE_HEIGHT,
        tiles=tiles,
        height_map=height_map,
        ceiling_map=ceiling_map,
        light_sources=light_sources,
        monsters=monsters,
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
