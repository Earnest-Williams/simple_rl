from __future__ import annotations

import math
from typing import Final

from lights_dev import constants
from utils.game_rng import GameRNG


DEFAULT_ENTITY_HEIGHT: Final[float] = 1.0
DEFAULT_LIGHT_RADIUS: Final[int] = 0
DEFAULT_LIGHT_LEVEL: Final[int] = 0
DEFAULT_PLAYER_LIGHT_RADIUS: Final[int] = 3
DEFAULT_PLAYER_LIGHT_LEVEL: Final[int] = 3
DEFAULT_LIGHT_SOURCE_RADIUS: Final[int] = 16
DEFAULT_LIGHT_SOURCE_LEVEL: Final[int] = 5
OMNIDIRECTIONAL_CONE_ANGLE: Final[float] = 2 * math.pi


class Entity:
    def __init__(
        self,
        x: int,
        *,
        y: int,
        light_radius: int = DEFAULT_LIGHT_RADIUS,
        light_level: int = DEFAULT_LIGHT_LEVEL,
        size_category: str = constants.DEFAULT_ENTITY_CATEGORY,
        base_color_rgb: Tuple[int, int, int] = (0, 0, 0),
        height: float = DEFAULT_ENTITY_HEIGHT,
    ) -> None:
        self.x = x
        self.y = y
        self.light_radius = max(0, light_radius)
        self.light_level = light_level
        self.size_category = size_category
        self.base_color_rgb: Tuple[int, int, int] = base_color_rgb
        self.height: float = float(height)

    @property
    def position(self) -> Tuple[int, int]:
        return (self.x, self.y)


class Player(Entity):
    def __init__(
        self,
        x: int,
        *,
        y: int,
        light_radius: int = DEFAULT_PLAYER_LIGHT_RADIUS,
        light_level: int = DEFAULT_PLAYER_LIGHT_LEVEL,
        height: float = DEFAULT_ENTITY_HEIGHT,
    ) -> None:
        super().__init__(
            x,
            y=y,
            light_radius=light_radius,
            light_level=light_level,
            size_category="medium",
            base_color_rgb=constants.TORCH_COLOR_RGB,
            height=height,
        )
        self.path: List[Tuple[int, int]] = []
        self.path_index = 0

    def set_path(self, path: List[Tuple[int, int]]) -> None:
        self.path = path
        self.path_index = 0

    def move(self) -> bool:
        if not self.path or self.path_index >= len(self.path):
            return False
        self.x, self.y = self.path[self.path_index]
        self.path_index += 1
        return True


class LightSource(Entity):
    def __init__(
        self,
        x: int,
        *,
        y: int,
        rng: GameRNG,
        light_radius: int = DEFAULT_LIGHT_SOURCE_RADIUS,
        light_level: int = DEFAULT_LIGHT_SOURCE_LEVEL,
        flicker: bool = False,
        base_color_rgb: Tuple[int, int, int] = constants.ORB_COLOR_RGB,
        height: float = DEFAULT_ENTITY_HEIGHT,
        direction: float | None = None,
        cone_angle: float = OMNIDIRECTIONAL_CONE_ANGLE,
    ) -> None:
        super().__init__(
            x,
            y=y,
            light_radius=light_radius,
            light_level=light_level,
            size_category="small",
            base_color_rgb=base_color_rgb,
            height=height,
        )
        self.flicker = flicker
        self.original_radius = max(1, light_radius)
        self.rng = rng
        self.direction = direction
        self.cone_angle = cone_angle

    def update(self) -> None:
        if self.flicker and self.rng.get_float(0.0, 1.0) < 0.2:
            self.light_radius = self.rng.get_int(
                max(1, self.original_radius - 3), self.original_radius + 1
            )
        else:
            self.light_radius = self.original_radius
