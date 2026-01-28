from __future__ import annotations

from lights_dev import constants
from utils.game_rng import GameRNG


class Entity:
    def __init__(
        self,
        x: int,
        y: int,
        light_radius: int = 0,
        light_level: int = 0,
        size_category: str = constants.DEFAULT_ENTITY_CATEGORY,
        base_color_rgb: tuple[int, int, int] = (0, 0, 0),
    ):
        self.x = x
        self.y = y
        self.light_radius = max(0, light_radius)
        self.light_level = light_level
        self.size_category = size_category
        self.base_color_rgb: tuple[int, int, int] = base_color_rgb

    @property
    def position(self) -> tuple[int, int]:
        return (self.x, self.y)


class Player(Entity):
    # Default torch radius lowered to 3 to match the desired player torch behavior.
    def __init__(self, x: int, y: int, light_radius: int = 3, light_level: int = 3):
        super().__init__(
            x, y, light_radius, light_level, "medium", constants.TORCH_COLOR_RGB
        )
        self.path: list[tuple[int, int]] = []
        self.path_index = 0

    def set_path(self, path: list[tuple[int, int]]) -> None:
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
        y: int,
        rng: GameRNG,
        light_radius: int = 16,
        light_level: int = 5,
        flicker: bool = False,
        base_color_rgb: tuple[int, int, int] = constants.ORB_COLOR_RGB,
    ):
        super().__init__(x, y, light_radius, light_level, "small", base_color_rgb)
        self.flicker = flicker
        self.original_radius = max(1, light_radius)
        self.rng = rng

    def update(self) -> None:
        if self.flicker and self.rng.get_float(0.0, 1.0) < 0.2:
            self.light_radius = self.rng.get_int(
                max(1, self.original_radius - 3), self.original_radius + 1
            )
        else:
            self.light_radius = self.original_radius
