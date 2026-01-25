"""Tile and color configuration state management with change tracking."""

from dataclasses import dataclass, field
from typing import Final

from tools.lighting_fov_tool.scene import ElementType, LightSourceDef


@dataclass
class ElementConfig:
    """Visual configuration for a scene element type."""

    tile_name: str
    tile_id: int
    fg_color: tuple[int, int, int]
    bg_color: tuple[int, int, int]


@dataclass
class LightConfig:
    """Configuration for a light source."""

    color: tuple[int, int, int]
    radius: int
    intensity: float


@dataclass
class ConfigSnapshot:
    """Immutable snapshot of a configuration value for comparison."""

    tile_name: str
    tile_id: int
    fg_color: tuple[int, int, int]
    bg_color: tuple[int, int, int]


@dataclass
class LightConfigSnapshot:
    """Immutable snapshot of a light configuration."""

    color: tuple[int, int, int]
    radius: int
    intensity: float


# Default tile assignments for each element type
DEFAULT_ELEMENT_TILES: Final[dict[ElementType, str]] = {
    ElementType.WALL: "wall_stone_bricks",
    ElementType.FLOOR: "blank_tile_a",
    ElementType.PILLAR: "prop_pillar",
    ElementType.HALLWAY_FLOOR: "blank_tile_a",
}

# Default colors for each element type (fg_color, bg_color)
DEFAULT_ELEMENT_COLORS: Final[dict[ElementType, tuple[tuple[int, int, int], ...]]] = {
    ElementType.WALL: ((180, 180, 180), (30, 30, 50)),
    ElementType.FLOOR: ((200, 200, 200), (10, 10, 30)),
    ElementType.PILLAR: ((160, 140, 120), (20, 20, 40)),
    ElementType.HALLWAY_FLOOR: ((180, 180, 200), (15, 15, 35)),
}


def _get_tile_id_for_name(tile_name: str) -> int:
    """Look up tile ID from the glyph registry."""
    try:
        from engine.glyphs import tile_id_for

        result = tile_id_for(tile_name, None)
        return result if result is not None else 13  # fallback to blank_tile_a
    except ImportError:
        # Fallback tile IDs if engine not available
        fallback_ids: dict[str, int] = {
            "wall_stone_bricks": 38,
            "blank_tile_a": 13,
            "prop_pillar": 103,
        }
        return fallback_ids.get(tile_name, 13)


@dataclass
class TileConfigState:
    """Manages tile/color configuration state with change tracking."""

    elements: dict[ElementType, ElementConfig] = field(default_factory=dict)
    lights: dict[str, LightConfig] = field(default_factory=dict)

    # Original values for comparison
    _original_elements: dict[ElementType, ConfigSnapshot] = field(default_factory=dict)
    _original_lights: dict[str, LightConfigSnapshot] = field(default_factory=dict)

    def initialize_defaults(
        self, light_sources: list[LightSourceDef] | None = None
    ) -> None:
        """Initialize configuration with default values."""
        # Initialize element configs
        for element_type in ElementType:
            tile_name = DEFAULT_ELEMENT_TILES.get(element_type, "blank_tile_a")
            tile_id = _get_tile_id_for_name(tile_name)
            colors = DEFAULT_ELEMENT_COLORS.get(
                element_type, ((200, 200, 200), (20, 20, 20))
            )
            fg_color = colors[0]
            bg_color = colors[1] if len(colors) > 1 else (20, 20, 20)

            config = ElementConfig(
                tile_name=tile_name,
                tile_id=tile_id,
                fg_color=fg_color,
                bg_color=bg_color,
            )
            self.elements[element_type] = config
            self._original_elements[element_type] = ConfigSnapshot(
                tile_name=tile_name,
                tile_id=tile_id,
                fg_color=fg_color,
                bg_color=bg_color,
            )

        # Initialize light configs from scene light sources
        if light_sources:
            for ls in light_sources:
                light_cfg = LightConfig(
                    color=ls.color,
                    radius=ls.radius,
                    intensity=ls.intensity,
                )
                self.lights[ls.name] = light_cfg
                self._original_lights[ls.name] = LightConfigSnapshot(
                    color=ls.color,
                    radius=ls.radius,
                    intensity=ls.intensity,
                )

    def set_element_tile(self, element_type: ElementType, tile_name: str) -> None:
        """Set the tile for an element type."""
        if element_type not in self.elements:
            return
        tile_id = _get_tile_id_for_name(tile_name)
        self.elements[element_type].tile_name = tile_name
        self.elements[element_type].tile_id = tile_id

    def set_element_fg_color(
        self, element_type: ElementType, color: tuple[int, int, int]
    ) -> None:
        """Set the foreground color for an element type."""
        if element_type not in self.elements:
            return
        self.elements[element_type].fg_color = color

    def set_element_bg_color(
        self, element_type: ElementType, color: tuple[int, int, int]
    ) -> None:
        """Set the background color for an element type."""
        if element_type not in self.elements:
            return
        self.elements[element_type].bg_color = color

    def set_light_color(self, light_name: str, color: tuple[int, int, int]) -> None:
        """Set the color for a light source."""
        if light_name not in self.lights:
            return
        self.lights[light_name].color = color

    def set_light_radius(self, light_name: str, radius: int) -> None:
        """Set the radius for a light source."""
        if light_name not in self.lights:
            return
        self.lights[light_name].radius = max(1, radius)

    def set_light_intensity(self, light_name: str, intensity: float) -> None:
        """Set the intensity for a light source."""
        if light_name not in self.lights:
            return
        self.lights[light_name].intensity = max(0.0, min(1.0, intensity))

    def reset_element_to_original(self, element_type: ElementType) -> None:
        """Reset an element's configuration to its original values."""
        if element_type not in self._original_elements:
            return
        original = self._original_elements[element_type]
        self.elements[element_type] = ElementConfig(
            tile_name=original.tile_name,
            tile_id=original.tile_id,
            fg_color=original.fg_color,
            bg_color=original.bg_color,
        )

    def reset_light_to_original(self, light_name: str) -> None:
        """Reset a light's configuration to its original values."""
        if light_name not in self._original_lights:
            return
        original = self._original_lights[light_name]
        self.lights[light_name] = LightConfig(
            color=original.color,
            radius=original.radius,
            intensity=original.intensity,
        )

    def reset_all_to_original(self) -> None:
        """Reset all configurations to original values."""
        for element_type in self._original_elements:
            self.reset_element_to_original(element_type)
        for light_name in self._original_lights:
            self.reset_light_to_original(light_name)

    def is_element_changed(self, element_type: ElementType) -> bool:
        """Check if an element's configuration differs from original."""
        if (
            element_type not in self.elements
            or element_type not in self._original_elements
        ):
            return False
        current = self.elements[element_type]
        original = self._original_elements[element_type]
        return (
            current.tile_name != original.tile_name
            or current.fg_color != original.fg_color
            or current.bg_color != original.bg_color
        )

    def is_light_changed(self, light_name: str) -> bool:
        """Check if a light's configuration differs from original."""
        if light_name not in self.lights or light_name not in self._original_lights:
            return False
        current = self.lights[light_name]
        original = self._original_lights[light_name]
        return (
            current.color != original.color
            or current.radius != original.radius
            or abs(current.intensity - original.intensity) > 0.001
        )

    def get_element_original(self, element_type: ElementType) -> ConfigSnapshot | None:
        """Get the original configuration for an element."""
        return self._original_elements.get(element_type)

    def get_light_original(self, light_name: str) -> LightConfigSnapshot | None:
        """Get the original configuration for a light."""
        return self._original_lights.get(light_name)

    def get_all_changes(
        self,
    ) -> dict[
        str,
        list[
            tuple[
                str,
                ElementConfig | LightConfig,
                ConfigSnapshot | LightConfigSnapshot | None,
            ]
        ],
    ]:
        """Get all changed configurations with their originals."""
        changes: dict[
            str,
            list[
                tuple[
                    str,
                    ElementConfig | LightConfig,
                    ConfigSnapshot | LightConfigSnapshot | None,
                ]
            ],
        ] = {
            "elements": [],
            "lights": [],
        }

        for element_type, config in self.elements.items():
            if self.is_element_changed(element_type):
                original = self.get_element_original(element_type)
                changes["elements"].append((element_type.name, config, original))

        for light_name, config in self.lights.items():
            if self.is_light_changed(light_name):
                original = self.get_light_original(light_name)
                changes["lights"].append((light_name, config, original))

        return changes
