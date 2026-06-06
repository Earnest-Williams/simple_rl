"""PySide6 window for the lighting/FOV tool with scene rendering and controls."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final, Literal
import math

import numpy as np
import structlog
from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from engine.render_lighting import LightContributionCache, collapse_premult_rgba_to_rgb
from tools.lighting_fov_tool.exporter import (
    export_configuration,
    get_default_export_path,
)
from tools.lighting_fov_tool.scene import (
    ElementType,
    create_fixed_scene,
    get_element_name,
)
from tools.lighting_fov_tool.tile_config import TileConfigState

if TYPE_CHECKING:
    pass

LightingBackend = Literal["Fast Diffuse", "Production Side-Aware", "Unified Preview", "Raw Heatmap"]

log = structlog.get_logger(__name__)

# Constants
DEFAULT_TILE_SIZE: Final[int] = 16
MIN_TILE_SIZE: Final[int] = 8
MAX_TILE_SIZE: Final[int] = 32

# Lighting constants
AMBIENT_INTENSITY: Final[float] = 0.30
RENDER_DEBOUNCE_MS: Final[int] = 33
PLAYER_SIGHT_RADIUS: Final[int] = 12
DEFAULT_OBSERVER_SIGHT_RADIUS: Final[int] = 12
FAST_DIFFUSE_BACKEND: Final[LightingBackend] = "Fast Diffuse"
PRODUCTION_SIDE_AWARE_BACKEND: Final[LightingBackend] = "Production Side-Aware"
UNIFIED_PREVIEW_BACKEND: Final[LightingBackend] = "Unified Preview"
RAW_HEATMAP_BACKEND: Final[LightingBackend] = "Raw Heatmap"

# Available tiles for selection (subset of glyphs.yaml)
AVAILABLE_TILES: Final[dict[str, int]] = {
    "blank_tile_a": 13,
    "blank_tile_b": 37,
    "wall_stone_bricks": 38,
    "wall_wood_planks": 45,
    "debris_rubble": 39,
    "floor_purple": 40,
    "prop_pillar": 103,
    "prop_boulder_large": 11,
    "prop_obelisk_purple": 10,
    "terrain_pebbles": 2,
    "terrain_mound": 8,
    "autotile_stone_solid": 46,
    "door_wood_closed": 51,
    "door_stone_closed": 53,
    "effect_fire_1": 18,
    "effect_fire_2": 19,
}


@dataclass(frozen=True)
class ToolLightSource:
    """Configured light source passed to renderer-facing lighting backends."""

    name: str
    x: int
    y: int
    radius: int
    color: tuple[int, int, int]
    intensity: float

@dataclass
class LightRuntimeResult:
    """Combines light configuration with its pre-computed reach and FOV outputs."""

    source: ToolLightSource
    reach_mask: np.ndarray
    visible_out: np.ndarray
    dist_out: np.ndarray
    side_bits_out: np.ndarray
    visibility_out: np.ndarray
    active: bool = False
    reached_observer_visible_cells: int = 0
    emitter_seen_by_observer: bool = False
    shape_mask: np.ndarray | None = None


@dataclass(frozen=True)
class ToolObserver:
    """Sight source that can activate lights for rendering."""

    name: str
    x: int
    y: int
    sight_radius: int


class ColorButton(QPushButton):
    """Button that displays and allows selection of a color."""

    color_changed = Signal(tuple)

    def __init__(
        self, initial_color: tuple[int, int, int], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._color = initial_color
        self._update_style()
        self.clicked.connect(self._on_clicked)
        self.setFixedSize(60, 25)

    def _update_style(self) -> None:
        """Update button style to show current color."""
        r, g, b = self._color
        # Calculate contrasting text color
        luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255
        text_color = "black" if luminance > 0.5 else "white"
        self.setStyleSheet(
            f"background-color: rgb({r}, {g}, {b}); color: {text_color}; "
            "border: 1px solid #555;"
        )
        self.setText(f"#{r:02x}{g:02x}{b:02x}")

    def _on_clicked(self) -> None:
        """Open color picker dialog."""
        current = QColor(*self._color)
        color = QColorDialog.getColor(current, self, "Select Color")
        if color.isValid():
            new_color = (color.red(), color.green(), color.blue())
            self._color = new_color
            self._update_style()
            self.color_changed.emit(new_color)

    def set_color(self, color: tuple[int, int, int]) -> None:
        """Set the button's color."""
        self._color = color
        self._update_style()

    def get_color(self) -> tuple[int, int, int]:
        """Get the button's current color."""
        return self._color


class ElementConfigPanel(QGroupBox):
    """Panel for configuring a single element type."""

    config_changed = Signal()

    def __init__(
        self,
        element_type: ElementType,
        config_state: TileConfigState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(get_element_name(element_type), parent)
        self._element_type = element_type
        self._config_state = config_state
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QFormLayout()
        layout.setContentsMargins(5, 10, 5, 5)

        config = self._config_state.elements.get(self._element_type)
        if config is None:
            return

        # Tile selector
        self._tile_combo = QComboBox()
        for tile_name in sorted(AVAILABLE_TILES.keys()):
            self._tile_combo.addItem(tile_name)
        current_idx = self._tile_combo.findText(config.tile_name)
        if current_idx >= 0:
            self._tile_combo.setCurrentIndex(current_idx)
        self._tile_combo.currentTextChanged.connect(self._on_tile_changed)
        layout.addRow("Tile:", self._tile_combo)

        # Foreground color
        self._fg_button = ColorButton(config.fg_color)
        self._fg_button.color_changed.connect(self._on_fg_changed)
        layout.addRow("FG Color:", self._fg_button)

        # Background color
        self._bg_button = ColorButton(config.bg_color)
        self._bg_button.color_changed.connect(self._on_bg_changed)
        layout.addRow("BG Color:", self._bg_button)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset)
        layout.addRow("", reset_btn)

        self.setLayout(layout)

    def _on_tile_changed(self, tile_name: str) -> None:
        """Handle tile selection change."""
        self._config_state.set_element_tile(self._element_type, tile_name)
        self.config_changed.emit()

    def _on_fg_changed(self, color: tuple[int, int, int]) -> None:
        """Handle foreground color change."""
        self._config_state.set_element_fg_color(self._element_type, color)
        self.config_changed.emit()

    def _on_bg_changed(self, color: tuple[int, int, int]) -> None:
        """Handle background color change."""
        self._config_state.set_element_bg_color(self._element_type, color)
        self.config_changed.emit()

    def _on_reset(self) -> None:
        """Reset this element to original values."""
        self._config_state.reset_element_to_original(self._element_type)
        self._refresh_ui()
        self.config_changed.emit()

    def _refresh_ui(self) -> None:
        """Refresh UI to match current config state."""
        config = self._config_state.elements.get(self._element_type)
        if config is None:
            return
        idx = self._tile_combo.findText(config.tile_name)
        if idx >= 0:
            self._tile_combo.blockSignals(True)
            self._tile_combo.setCurrentIndex(idx)
            self._tile_combo.blockSignals(False)
        self._fg_button.set_color(config.fg_color)
        self._bg_button.set_color(config.bg_color)


class LightConfigPanel(QGroupBox):
    """Panel for configuring a single light source."""

    config_changed = Signal()

    def __init__(
        self,
        light_name: str,
        config_state: TileConfigState,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(f"Light: {light_name}", parent)
        self._light_name = light_name
        self._config_state = config_state
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the panel UI."""
        layout = QFormLayout()
        layout.setContentsMargins(5, 10, 5, 5)

        config = self._config_state.lights.get(self._light_name)
        if config is None:
            return

        # Light color
        self._color_button = ColorButton(config.color)
        self._color_button.color_changed.connect(self._on_color_changed)
        layout.addRow("Color:", self._color_button)

        # Shape selector
        self._shape_combo = QComboBox()
        self._shape_combo.addItems(["circle", "cone", "beam"])
        self._shape_combo.setCurrentText(config.shape)
        self._shape_combo.currentTextChanged.connect(self._on_shape_changed)
        layout.addRow("Shape:", self._shape_combo)

        # Radius
        self._radius_spin = QSpinBox()
        self._radius_spin.setRange(1, 20)
        self._radius_spin.setValue(config.radius)
        self._radius_spin.valueChanged.connect(self._on_radius_changed)
        layout.addRow("Radius:", self._radius_spin)

        # Intensity slider
        self._intensity_slider = QSlider(Qt.Orientation.Horizontal)
        self._intensity_slider.setRange(0, 100)
        self._intensity_slider.setValue(int(config.intensity * 100))
        self._intensity_slider.valueChanged.connect(self._on_intensity_changed)
        self._intensity_label = QLabel(f"{config.intensity:.2f}")
        intensity_layout = QHBoxLayout()
        intensity_layout.addWidget(self._intensity_slider)
        intensity_layout.addWidget(self._intensity_label)
        intensity_widget = QWidget()
        intensity_widget.setLayout(intensity_layout)
        layout.addRow("Intensity:", intensity_widget)

        # Direction slider (0 to 360 degrees)
        self._direction_slider = QSlider(Qt.Orientation.Horizontal)
        self._direction_slider.setRange(0, 360)
        self._direction_slider.setValue(int(math.degrees(config.direction)) % 360)
        self._direction_slider.valueChanged.connect(self._on_direction_changed)
        self._direction_label = QLabel(f"{int(math.degrees(config.direction)) % 360}°")
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(self._direction_slider)
        dir_layout.addWidget(self._direction_label)
        self._dir_widget = QWidget()
        self._dir_widget.setLayout(dir_layout)
        layout.addRow("Direction:", self._dir_widget)

        # Cone Angle slider (5 to 360 degrees)
        self._cone_angle_slider = QSlider(Qt.Orientation.Horizontal)
        self._cone_angle_slider.setRange(5, 360)
        self._cone_angle_slider.setValue(int(math.degrees(config.cone_angle)))
        self._cone_angle_slider.valueChanged.connect(self._on_cone_angle_changed)
        self._cone_angle_label = QLabel(f"{int(math.degrees(config.cone_angle))}°")
        cone_layout = QHBoxLayout()
        cone_layout.addWidget(self._cone_angle_slider)
        cone_layout.addWidget(self._cone_angle_label)
        self._cone_widget = QWidget()
        self._cone_widget.setLayout(cone_layout)
        layout.addRow("Cone Angle:", self._cone_widget)

        # Beam Width (double spinbox)
        self._beam_width_spin = QDoubleSpinBox()
        self._beam_width_spin.setRange(0.5, 10.0)
        self._beam_width_spin.setSingleStep(0.5)
        self._beam_width_spin.setValue(config.beam_width)
        self._beam_width_spin.valueChanged.connect(self._on_beam_width_changed)
        layout.addRow("Beam Width:", self._beam_width_spin)

        # Beam Length (spinbox)
        self._beam_length_spin = QSpinBox()
        self._beam_length_spin.setRange(1, 30)
        self._beam_length_spin.setValue(config.beam_length)
        self._beam_length_spin.valueChanged.connect(self._on_beam_length_changed)
        layout.addRow("Beam Length:", self._beam_length_spin)

        # Softness slider (0 to 100)
        self._softness_slider = QSlider(Qt.Orientation.Horizontal)
        self._softness_slider.setRange(0, 100)
        self._softness_slider.setValue(int(config.softness * 100))
        self._softness_slider.valueChanged.connect(self._on_softness_changed)
        self._softness_label = QLabel(f"{config.softness:.2f}")
        soft_layout = QHBoxLayout()
        soft_layout.addWidget(self._softness_slider)
        soft_layout.addWidget(self._softness_label)
        self._soft_widget = QWidget()
        self._soft_widget.setLayout(soft_layout)
        layout.addRow("Softness:", self._soft_widget)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset)
        layout.addRow("", reset_btn)

        self.setLayout(layout)
        self._update_visibility()

    def _update_visibility(self) -> None:
        """Dynamically show/hide controls based on selected light shape."""
        shape = self._shape_combo.currentText()
        is_circle = shape == "circle"
        is_cone = shape == "cone"
        is_beam = shape == "beam"

        # Direction
        self._dir_widget.setVisible(is_cone or is_beam)
        self.layout().labelForField(self._dir_widget).setVisible(is_cone or is_beam)

        # Cone Angle
        self._cone_widget.setVisible(is_cone)
        self.layout().labelForField(self._cone_widget).setVisible(is_cone)

        # Beam Width
        self._beam_width_spin.setVisible(is_beam)
        self.layout().labelForField(self._beam_width_spin).setVisible(is_beam)

        # Beam Length
        self._beam_length_spin.setVisible(is_beam)
        self.layout().labelForField(self._beam_length_spin).setVisible(is_beam)

        # Softness
        self._soft_widget.setVisible(is_cone or is_beam)
        self.layout().labelForField(self._soft_widget).setVisible(is_cone or is_beam)

        # Radius (hidden for beam)
        self._radius_spin.setVisible(is_circle or is_cone)
        self.layout().labelForField(self._radius_spin).setVisible(is_circle or is_cone)

    def _on_color_changed(self, color: tuple[int, int, int]) -> None:
        """Handle color change."""
        self._config_state.set_light_color(self._light_name, color)
        self.config_changed.emit()

    def _on_shape_changed(self, shape: str) -> None:
        """Handle shape selection change."""
        self._config_state.set_light_shape(self._light_name, shape)
        self._update_visibility()
        self.config_changed.emit()

    def _on_radius_changed(self, radius: int) -> None:
        """Handle radius change."""
        self._config_state.set_light_radius(self._light_name, radius)
        self.config_changed.emit()

    def _on_intensity_changed(self, value: int) -> None:
        """Handle intensity change."""
        intensity = value / 100.0
        self._intensity_label.setText(f"{intensity:.2f}")
        self._config_state.set_light_intensity(self._light_name, intensity)
        self.config_changed.emit()

    def _on_direction_changed(self, value: int) -> None:
        """Handle direction change (convert from degrees to radians)."""
        rad = math.radians(value)
        self._direction_label.setText(f"{value}°")
        self._config_state.set_light_direction(self._light_name, rad)
        self.config_changed.emit()

    def _on_cone_angle_changed(self, value: int) -> None:
        """Handle cone angle change (convert from degrees to radians)."""
        rad = math.radians(value)
        self._cone_angle_label.setText(f"{value}°")
        self._config_state.set_light_cone_angle(self._light_name, rad)
        self.config_changed.emit()

    def _on_beam_width_changed(self, value: float) -> None:
        """Handle beam width change."""
        self._config_state.set_light_beam_width(self._light_name, value)
        self.config_changed.emit()

    def _on_beam_length_changed(self, value: int) -> None:
        """Handle beam length change."""
        self._config_state.set_light_beam_length(self._light_name, value)
        self.config_changed.emit()

    def _on_softness_changed(self, value: int) -> None:
        """Handle softness change."""
        softness = value / 100.0
        self._softness_label.setText(f"{softness:.2f}")
        self._config_state.set_light_softness(self._light_name, softness)
        self.config_changed.emit()

    def _on_reset(self) -> None:
        """Reset this light to original values."""
        self._config_state.reset_light_to_original(self._light_name)
        self._refresh_ui()
        self.config_changed.emit()

    def _refresh_ui(self) -> None:
        """Refresh UI to match current config state."""
        config = self._config_state.lights.get(self._light_name)
        if config is None:
            return
        self._color_button.set_color(config.color)
        
        self._radius_spin.blockSignals(True)
        self._radius_spin.setValue(config.radius)
        self._radius_spin.blockSignals(False)
        
        self._intensity_slider.blockSignals(True)
        self._intensity_slider.setValue(int(config.intensity * 100))
        self._intensity_slider.blockSignals(False)
        self._intensity_label.setText(f"{config.intensity:.2f}")

        # Refresh shape fields
        self._shape_combo.blockSignals(True)
        self._shape_combo.setCurrentText(config.shape)
        self._shape_combo.blockSignals(False)

        self._direction_slider.blockSignals(True)
        self._direction_slider.setValue(int(math.degrees(config.direction)) % 360)
        self._direction_slider.blockSignals(False)
        self._direction_label.setText(f"{int(math.degrees(config.direction)) % 360}°")

        self._cone_angle_slider.blockSignals(True)
        self._cone_angle_slider.setValue(int(math.degrees(config.cone_angle)))
        self._cone_angle_slider.blockSignals(False)
        self._cone_angle_label.setText(f"{int(math.degrees(config.cone_angle))}°")

        self._beam_width_spin.blockSignals(True)
        self._beam_width_spin.setValue(config.beam_width)
        self._beam_width_spin.blockSignals(False)

        self._beam_length_spin.blockSignals(True)
        self._beam_length_spin.setValue(config.beam_length)
        self._beam_length_spin.blockSignals(False)

        self._softness_slider.blockSignals(True)
        self._softness_slider.setValue(int(config.softness * 100))
        self._softness_slider.blockSignals(False)
        self._softness_label.setText(f"{config.softness:.2f}")

        self._update_visibility()


class LightingFovToolWindow(QMainWindow):
    """Main window for the lighting/FOV tool."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lighting/FOV Tool")
        self.resize(1200, 800)

        # Initialize state
        self._scene = create_fixed_scene()
        self._config_state = TileConfigState()
        self._config_state.initialize_defaults(self._scene.light_sources)

        # Load default configuration
        from tools.lighting_fov_tool.exporter import load_configuration
        default_config_path = Path(__file__).parent / "default_config.txt"
        if default_config_path.exists():
            load_configuration(self._config_state, default_config_path)
            self._config_state.mark_current_as_original()

        # Cached geometry grids
        self._opaque_grid = None
        self._transparency_grid = None

        # Caches
        self._blocker_revision: int = 0
        self._observer_fov_cache: dict[tuple[str, int, int, int], tuple[int, np.ndarray]] = {}
        self._light_reach_cache: dict[tuple[str, int, int, int, float], tuple[int, LightRuntimeResult]] = {}

        # Blending weights for unified preview
        self._diffuse_weight = 1.0
        self._side_weight = 1.0

        self._tile_size = DEFAULT_TILE_SIZE
        self._lighting_backend: LightingBackend = "Fast Diffuse"
        self._production_light_cache = LightContributionCache(
            self._scene.height, self._scene.width
        )

        # Debug visualization toggles
        self._show_full_light_field = False
        self._show_hidden_light_sources = False
        self._use_los_for_debug_radial = True

        # Lights are only emitted when at least part of their light field is
        # visible to a sighted observer. The observer does not need LOS to the
        # emitter tile itself.
        self._active_light_names: set[str] = set()

        # Set up render debounce timer
        self._render_timer = QTimer(self)
        self._render_timer.setSingleShot(True)
        self._render_timer.setInterval(RENDER_DEBOUNCE_MS)
        self._render_timer.timeout.connect(self._render_scene)

        # Load tileset
        self._tiles: dict[int, np.ndarray] = {}
        self._load_tileset()

        # Set up UI
        self._setup_ui()

        # Enable keyboard focus for movement
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # Initial render
        QTimer.singleShot(100, self._render_scene)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """Handle keyboard input for camera movement."""
        key = event.key()

        # Map keys to movement deltas
        dx, dy = 0, 0
        if key in (Qt.Key.Key_Up, Qt.Key.Key_W):
            dy = -1
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_S):
            dy = 1
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_A):
            dx = -1
        elif key in (Qt.Key.Key_Right, Qt.Key.Key_D):
            dx = 1
        else:
            super().keyPressEvent(event)
            return

        # Try to move player
        current_x, current_y = self._scene.player_pos
        new_x = current_x + dx
        new_y = current_y + dy

        # Check bounds
        if not (0 <= new_x < self._scene.width and 0 <= new_y < self._scene.height):
            return

        # Check if tile is walkable (not wall or pillar)
        tile_type = ElementType(self._scene.tiles[new_y, new_x])
        if tile_type in (ElementType.WALL, ElementType.PILLAR):
            return

        # Update player position
        self._scene.player_pos = (new_x, new_y)
        self._update_status_label()
        self._render_scene()

    def _update_status_label(self) -> None:
        """Update the status label with current player position and instructions."""
        px, py = self._scene.player_pos
        self._status_label.setText(
            f"Player Position: ({px}, {py}) | "
            "Use Arrow Keys or WASD to move around, including into the "
            "left-side light-bleed test hallways"
        )

    def _load_tileset(self) -> None:
        """Load the tileset images."""
        try:
            from engine.tileset_loader import load_tiles

            project_root = Path(__file__).parent.parent.parent
            tileset_path = project_root / "fonts" / "classic_roguelike_sliced_svgs"
            tiles_dict, _ = load_tiles(
                str(tileset_path), self._tile_size, self._tile_size
            )
            # Convert PIL Images to numpy arrays
            for tile_id, img in tiles_dict.items():
                if img.mode != "RGBA":
                    img = img.convert("RGBA")
                self._tiles[tile_id] = np.array(img, dtype=np.uint8)
            log.info("Tileset loaded", count=len(self._tiles))
        except Exception as e:
            log.error("Failed to load tileset", error=str(e))
            # Create placeholder tiles
            placeholder = np.full(
                (self._tile_size, self._tile_size, 4), 128, dtype=np.uint8
            )
            placeholder[:, :, 3] = 255
            for tile_id in AVAILABLE_TILES.values():
                self._tiles[tile_id] = placeholder.copy()

    def _setup_ui(self) -> None:
        """Set up the main window UI."""
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Scene display
        scene_widget = QWidget()
        scene_layout = QVBoxLayout()
        scene_layout.setContentsMargins(5, 5, 5, 5)

        # Scene label in scroll area
        self._scene_label = QLabel()
        self._scene_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self._scene_label)
        scroll_area.setWidgetResizable(False)
        scene_layout.addWidget(scroll_area, 1)

        # Status label with movement instructions
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._update_status_label()
        scene_layout.addWidget(self._status_label)

        # Tile size control
        size_layout = QHBoxLayout()
        size_layout.addWidget(QLabel("Tile Size:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(MIN_TILE_SIZE, MAX_TILE_SIZE)
        self._size_spin.setValue(self._tile_size)
        self._size_spin.valueChanged.connect(self._on_tile_size_changed)
        size_layout.addWidget(self._size_spin)
        size_layout.addStretch()
        scene_layout.addLayout(size_layout)

        scene_widget.setLayout(scene_layout)
        splitter.addWidget(scene_widget)

        # Right side: Control panels in scroll area
        controls_scroll = QScrollArea()
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setMinimumWidth(300)

        controls_widget = QWidget()
        controls_layout = QVBoxLayout()
        controls_layout.setContentsMargins(5, 5, 5, 5)

        # Element config panels
        elements_group = QGroupBox("Tile Elements")
        elements_layout = QVBoxLayout()
        self._element_panels: list[ElementConfigPanel] = []
        for element_type in ElementType:
            panel = ElementConfigPanel(element_type, self._config_state)
            panel.config_changed.connect(self._on_config_changed)
            self._element_panels.append(panel)
            elements_layout.addWidget(panel)
        elements_group.setLayout(elements_layout)
        controls_layout.addWidget(elements_group)

        # Light config panels
        lights_group = QGroupBox("Light Sources")
        lights_layout = QVBoxLayout()
        self._light_panels: list[LightConfigPanel] = []
        for light_name in sorted(self._config_state.lights.keys()):
            panel = LightConfigPanel(light_name, self._config_state)
            panel.config_changed.connect(self._on_config_changed)
            self._light_panels.append(panel)
            lights_layout.addWidget(panel)
        lights_group.setLayout(lights_layout)
        controls_layout.addWidget(lights_group)

        # Action buttons
        actions_group = QGroupBox("Actions")
        actions_layout = QVBoxLayout()

        backend_layout = QFormLayout()
        self._lighting_backend_combo = QComboBox()
        self._lighting_backend_combo.addItem(FAST_DIFFUSE_BACKEND)
        self._lighting_backend_combo.addItem(PRODUCTION_SIDE_AWARE_BACKEND)
        self._lighting_backend_combo.addItem(UNIFIED_PREVIEW_BACKEND)
        self._lighting_backend_combo.addItem(RAW_HEATMAP_BACKEND)
        self._lighting_backend_combo.setCurrentText(self._lighting_backend)
        self._lighting_backend_combo.currentTextChanged.connect(
            self._on_lighting_backend_changed
        )
        backend_layout.addRow("Lighting Backend:", self._lighting_backend_combo)
        actions_layout.addLayout(backend_layout)

        # Unified Preview weights layout
        self._weights_group = QGroupBox("Unified Blending Weights")
        weights_layout = QFormLayout()

        self._diffuse_weight_slider = QSlider(Qt.Orientation.Horizontal)
        self._diffuse_weight_slider.setRange(0, 200)  # 0.0 to 2.0
        self._diffuse_weight_slider.setValue(int(self._diffuse_weight * 100))
        self._diffuse_weight_slider.valueChanged.connect(self._on_diffuse_weight_changed)
        self._diffuse_weight_label = QLabel(f"{self._diffuse_weight:.2f}")
        diffuse_w_layout = QHBoxLayout()
        diffuse_w_layout.addWidget(self._diffuse_weight_slider)
        diffuse_w_layout.addWidget(self._diffuse_weight_label)
        diffuse_w_widget = QWidget()
        diffuse_w_widget.setLayout(diffuse_w_layout)
        weights_layout.addRow("Diffuse Wash:", diffuse_w_widget)

        self._side_weight_slider = QSlider(Qt.Orientation.Horizontal)
        self._side_weight_slider.setRange(0, 200)  # 0.0 to 2.0
        self._side_weight_slider.setValue(int(self._side_weight * 100))
        self._side_weight_slider.valueChanged.connect(self._on_side_weight_changed)
        self._side_weight_label = QLabel(f"{self._side_weight:.2f}")
        side_w_layout = QHBoxLayout()
        side_w_layout.addWidget(self._side_weight_slider)
        side_w_layout.addWidget(self._side_weight_label)
        side_w_widget = QWidget()
        side_w_widget.setLayout(side_w_layout)
        weights_layout.addRow("Side Highlights:", side_w_widget)

        self._weights_group.setLayout(weights_layout)
        self._weights_group.setVisible(self._lighting_backend == UNIFIED_PREVIEW_BACKEND)
        actions_layout.addWidget(self._weights_group)

        # Debug visualization options
        debug_group = QGroupBox("Debug Visualization")
        debug_layout = QVBoxLayout()

        self._show_full_light_checkbox = QPushButton()
        self._show_full_light_checkbox.setCheckable(True)
        self._show_full_light_checkbox.setChecked(self._show_full_light_field)
        self._show_full_light_checkbox.clicked.connect(self._on_debug_toggle_changed)
        debug_layout.addWidget(self._show_full_light_checkbox)

        self._show_hidden_lights_checkbox = QPushButton()
        self._show_hidden_lights_checkbox.setCheckable(True)
        self._show_hidden_lights_checkbox.setChecked(self._show_hidden_light_sources)
        self._show_hidden_lights_checkbox.clicked.connect(self._on_debug_toggle_changed)
        debug_layout.addWidget(self._show_hidden_lights_checkbox)

        self._use_los_radial_checkbox = QPushButton()
        self._use_los_radial_checkbox.setCheckable(True)
        self._use_los_radial_checkbox.setChecked(self._use_los_for_debug_radial)
        self._use_los_radial_checkbox.clicked.connect(self._on_debug_toggle_changed)
        debug_layout.addWidget(self._use_los_radial_checkbox)

        self._set_debug_toggle_texts()

        debug_group.setLayout(debug_layout)
        actions_layout.addWidget(debug_group)

        reset_all_btn = QPushButton("Reset All to Original")
        reset_all_btn.clicked.connect(self._on_reset_all)
        actions_layout.addWidget(reset_all_btn)

        export_btn = QPushButton("Export Configuration...")
        export_btn.clicked.connect(self._on_export)
        actions_layout.addWidget(export_btn)

        actions_group.setLayout(actions_layout)
        controls_layout.addWidget(actions_group)

        controls_layout.addStretch()
        controls_widget.setLayout(controls_layout)
        controls_scroll.setWidget(controls_widget)
        splitter.addWidget(controls_scroll)

        # Set splitter sizes
        splitter.setSizes([800, 400])

        self.setCentralWidget(splitter)

        # Dark style
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QGroupBox {
                border: 1px solid #444;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 3px;
            }
            QPushButton {
                background-color: #333;
                border: 1px solid #555;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #444;
            }
            QComboBox, QSpinBox {
                background-color: #333;
                border: 1px solid #555;
                padding: 3px;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #333;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #666;
                width: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QScrollArea {
                border: none;
            }
            """)

    def _on_tile_size_changed(self, size: int) -> None:
        """Handle tile size change."""
        self._tile_size = size
        self._load_tileset()
        self._render_scene()

    def _on_config_changed(self) -> None:
        """Handle configuration change from any panel."""
        self._render_timer.start()

    def _on_lighting_backend_changed(self, backend_name: str) -> None:
        """Switch between debug and production lighting backends."""
        if backend_name not in (FAST_DIFFUSE_BACKEND, PRODUCTION_SIDE_AWARE_BACKEND, UNIFIED_PREVIEW_BACKEND, RAW_HEATMAP_BACKEND):
            log.warning("Ignoring unknown lighting backend", backend=backend_name)
            return

        self._lighting_backend = backend_name
        self._weights_group.setVisible(backend_name == UNIFIED_PREVIEW_BACKEND)
        self._render_scene()

    def _on_diffuse_weight_changed(self, value: int) -> None:
        """Handle diffuse weight slider change."""
        self._diffuse_weight = value / 100.0
        self._diffuse_weight_label.setText(f"{self._diffuse_weight:.2f}")
        self._render_scene()

    def _on_side_weight_changed(self, value: int) -> None:
        """Handle side weight slider change."""
        self._side_weight = value / 100.0
        self._side_weight_label.setText(f"{self._side_weight:.2f}")
        self._render_scene()

    def _set_debug_toggle_texts(self) -> None:
        """Set the text for all debug toggle buttons based on current state."""
        self._show_full_light_checkbox.setText(
            f"Show full light field: {'ON' if self._show_full_light_field else 'OFF'}"
        )
        self._show_hidden_lights_checkbox.setText(
            f"Show hidden emitters: {'ON' if self._show_hidden_light_sources else 'OFF'}"
        )
        self._use_los_radial_checkbox.setText(
            f"Use LOS for debug radial: {'ON' if self._use_los_for_debug_radial else 'OFF'}"
        )

    def _on_debug_toggle_changed(self) -> None:
        """Handle debug visualization toggle changes."""
        sender = self.sender()
        if sender is self._show_full_light_checkbox:
            self._show_full_light_field = self._show_full_light_checkbox.isChecked()
        elif sender is self._show_hidden_lights_checkbox:
            self._show_hidden_light_sources = (
                self._show_hidden_lights_checkbox.isChecked()
            )
        elif sender is self._use_los_radial_checkbox:
            self._use_los_for_debug_radial = self._use_los_radial_checkbox.isChecked()

        self._set_debug_toggle_texts()
        self._render_scene()

    def _on_reset_all(self) -> None:
        """Reset all configurations to original values."""
        self._config_state.reset_all_to_original()
        self._blocker_revision += 1
        # Refresh all panels
        for panel in self._element_panels:
            panel._refresh_ui()
        for panel in self._light_panels:
            panel._refresh_ui()
        self._render_scene()

    def _on_export(self) -> None:
        """Export configuration to file."""
        default_path = get_default_export_path()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Configuration",
            str(default_path),
            "Text Files (*.txt);;All Files (*)",
        )
        if not file_path:
            return

        try:
            export_configuration(self._config_state, Path(file_path))
            QMessageBox.information(
                self, "Export Complete", f"Configuration exported to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Export Error", f"Failed to export configuration:\n{e}"
            )

    def _render_scene(self) -> None:
        """Render the scene with current configuration."""
        scene = self._scene
        config = self._config_state

        # Create output image
        img_width = scene.width * self._tile_size
        img_height = scene.height * self._tile_size
        output = np.zeros((img_height, img_width, 4), dtype=np.uint8)
        output[:, :, 3] = 255  # Full alpha

        # Compute observer visibility once
        visible = self._compute_observer_visible_mask()

        # Compute runtime results for all lights, identifying which are active
        light_results = self._compute_frame_light_results(visible)

        # Compute lighting from emitters that are active
        base_intensity, colored_light = self._compute_lighting(light_results)

        # Render each tile
        for y in range(scene.height):
            for x in range(scene.width):
                # Apply lighting: show full light field for tuning (not clipped by player FOV)
                if self._show_full_light_field:
                    light_rgb = colored_light[y, x]
                    intensity = base_intensity[y, x]
                else:
                    is_visible = visible[y, x]
                    if is_visible:
                        light_rgb = colored_light[y, x]
                        intensity = base_intensity[y, x]
                    else:
                        light_rgb = np.zeros(3, dtype=np.float32)
                        intensity = 0.05

                px = x * self._tile_size
                py = y * self._tile_size

                if self._lighting_backend == RAW_HEATMAP_BACKEND:
                    output[py : py + self._tile_size, px : px + self._tile_size, :3] = light_rgb.clip(0, 255).astype(np.uint8)
                    continue

                element_type = ElementType(scene.tiles[y, x])
                elem_config = config.elements.get(element_type)
                if elem_config is None:
                    continue

                tile_id = elem_config.tile_id
                fg_color = np.array(elem_config.fg_color, dtype=np.float32)
                bg_color = np.array(elem_config.bg_color, dtype=np.float32)

                # Apply lighting: (base_color * intensity) + colored_light
                fg_lit = (
                    (fg_color * intensity + light_rgb).clip(0, 255).astype(np.uint8)
                )
                bg_lit = (
                    (bg_color * intensity + light_rgb).clip(0, 255).astype(np.uint8)
                )

                # Get tile image
                tile_img = self._tiles.get(tile_id)
                if tile_img is None:
                    tile_img = self._tiles.get(13)  # Fallback to blank
                if tile_img is None:
                    continue

                # Composite tile onto output
                self._composite_tile(
                    output, px, py, tile_img, fg_lit, bg_lit, self._tile_size
                )

        # Mark player position
        px, py = scene.player_pos
        player_px = px * self._tile_size
        player_py = py * self._tile_size
        # Draw a simple @ marker
        self._draw_player_marker(output, player_px, player_py)

        # Mark dummy sighted monsters.
        for monster in scene.monsters:
            if not monster.has_eyes:
                continue

            h, w = visible.shape
            is_visible = (
                0 <= monster.y < h
                and 0 <= monster.x < w
                and visible[monster.y, monster.x]
            )
            if self._show_full_light_field or is_visible:
                mx = monster.x * self._tile_size
                my = monster.y * self._tile_size
                self._draw_monster_marker(output, mx, my)

        # Mark light sources
        for ls in scene.light_sources:
            res = next((r for r in light_results if r.source.name == ls.name), None)
            if res is None:
                continue

            light_cfg = config.lights.get(ls.name)
            if light_cfg is None:
                continue

            is_visible = res.emitter_seen_by_observer
            is_active = res.active
            should_hide_marker = (
                not self._show_full_light_field
                and not self._show_hidden_light_sources
                and not is_visible
            )
            if should_hide_marker or (not is_active and not self._show_hidden_light_sources):
                continue

            lx = ls.x * self._tile_size + self._tile_size // 2
            ly = ls.y * self._tile_size + self._tile_size // 2
            self._draw_light_marker(output, lx, ly, light_cfg.color)

        # Convert to QPixmap and display
        img = Image.fromarray(output, "RGBA")
        qimage = QImage(
            img.tobytes(), img.width, img.height, QImage.Format.Format_RGBA8888
        )
        pixmap = QPixmap.fromImage(qimage)
        self._scene_label.setPixmap(pixmap)
        self._scene_label.setFixedSize(pixmap.size())

    def _compute_simple_fov(self, opaque_grid: np.ndarray, ox: int, oy: int, radius: int) -> np.ndarray:
        """Compute a simple circular FOV."""
        scene = self._scene
        visible = np.zeros((scene.height, scene.width), dtype=bool)

        for y in range(scene.height):
            for x in range(scene.width):
                dx = x - ox
                dy = y - oy
                dist_sq = dx * dx + dy * dy
                if dist_sq <= radius * radius and self._has_los(opaque_grid, ox, oy, x, y):
                    visible[y, x] = True

        return visible

    def _has_los(self, opaque_grid: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> bool:
        """Simple line of sight check using Bresenham."""
        scene = self._scene
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        while True:
            if x == x1 and y == y1:
                return True
            # Check if current tile blocks light (walls and pillars)
            if (x, y) != (x0, y0):
                if opaque_grid[y, x]:
                    return False

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def _compute_lighting(self, light_results: list[LightRuntimeResult]) -> tuple[np.ndarray, np.ndarray]:
        """Compute base intensity and RGB lighting for active visible emitters."""
        scene = self._scene

        base_intensity = np.full(
            (scene.height, scene.width), AMBIENT_INTENSITY, dtype=np.float32
        )

        active_lights = [r for r in light_results if r.active]

        if self._lighting_backend == FAST_DIFFUSE_BACKEND:
            colored_light = np.zeros((scene.height, scene.width, 3), dtype=np.float32)
            opaque_grid, transparency_grid = self._get_cached_geometry_grids()
            for light_res in active_lights:
                self._accumulate_fast_diffuse_light(
                    colored_light,
                    light_res=light_res,
                    opaque_grid=opaque_grid,
                    transparency_grid=transparency_grid,
                )
            # Match 2.0 tool exposure of previous debug radial backend
            colored_light *= 2.0
        elif self._lighting_backend == PRODUCTION_SIDE_AWARE_BACKEND:
            colored_light = self._compute_production_cache_lighting(active_lights)
        elif self._lighting_backend in (UNIFIED_PREVIEW_BACKEND, RAW_HEATMAP_BACKEND):
            diffuse_rgb, side_rgba = self._compute_unified_lighting(active_lights)
            side_rgb = collapse_premult_rgba_to_rgb(side_rgba)
            colored_light = diffuse_rgb * self._diffuse_weight + side_rgb * self._side_weight
        else:
            colored_light = np.zeros((scene.height, scene.width, 3), dtype=np.float32)

        np.clip(colored_light, 0.0, 255.0, out=colored_light)

        lit_mask = np.any(colored_light > 1.0, axis=2)
        log.info(
            "light stats",
            backend=self._lighting_backend,
            max=float(colored_light.max()),
            mean=float(colored_light.mean()),
            lit_tiles=int(lit_mask.sum()),
            total_tiles=int(scene.width * scene.height),
        )

        return base_intensity, colored_light

    def _compute_production_cache_lighting(self, active_lights: list[LightRuntimeResult]) -> np.ndarray:
        """Compute colored light with the renderer-facing contribution cache."""
        scene = self._scene
        light_sources = [r.source for r in active_lights]
        if not light_sources:
            return np.zeros((scene.height, scene.width, 3), dtype=np.float32)

        opaque_grid, _ = self._get_cached_geometry_grids()
        colored_light = self._production_light_cache.update(
            light_sources,
            opaque_grid,
            scene_seq=0,
            height_map=scene.height_map,
            ceiling_map=scene.ceiling_map,
        )
        return colored_light.astype(np.float32, copy=True)

    def _get_cached_geometry_grids(self) -> tuple[np.ndarray, np.ndarray]:
        """Get or compute cached grids of opaque and transparent cells."""
        if self._opaque_grid is None or self._transparency_grid is None:
            scene = self._scene
            self._opaque_grid = (scene.tiles == ElementType.WALL) | (
                scene.tiles == ElementType.PILLAR
            )
            self._transparency_grid = (1.0 - self._opaque_grid).astype(np.float32)
        return self._opaque_grid, self._transparency_grid

    def _get_observers(self) -> list[ToolObserver]:
        """Return all sighted entities that can activate visible light emitters."""
        player_x, player_y = self._scene.player_pos
        observers = [
            ToolObserver(
                name="player",
                x=player_x,
                y=player_y,
                sight_radius=PLAYER_SIGHT_RADIUS,
            )
        ]

        for monster in self._scene.monsters:
            if not monster.has_eyes:
                continue

            observers.append(
                ToolObserver(
                    name=monster.name,
                    x=monster.x,
                    y=monster.y,
                    sight_radius=monster.sight_radius,
                )
            )

        return observers

    def _compute_observer_visible_mask(self) -> np.ndarray:
        """Return all cells visible to the player or a sighted monster."""
        scene = self._scene
        observer_visible = np.zeros((scene.height, scene.width), dtype=bool)

        opaque_grid, transparency_grid = self._get_cached_geometry_grids()
        for observer in self._get_observers():
            cache_key = (observer.name, observer.x, observer.y, observer.sight_radius)
            if cache_key in self._observer_fov_cache:
                rev, mask = self._observer_fov_cache[cache_key]
                if rev == self._blocker_revision:
                    observer_visible |= mask
                    continue

            _, visible_out, _, _, _ = self._compute_point_fov_mask(
                observer.x, observer.y, observer.sight_radius, opaque_grid, transparency_grid
            )
            mask = visible_out != 0
            self._observer_fov_cache[cache_key] = (self._blocker_revision, mask)
            observer_visible |= mask

        return observer_visible

    def _compute_point_fov_mask(
        self,
        origin_x: int,
        origin_y: int,
        radius: int,
        opaque_grid: np.ndarray,
        transparency_grid: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Compute FOV from a point, returning (reach_mask, visible_out, dist_out, side_bits_out, visibility_out)."""
        scene = self._scene
        if radius <= 0:
            zeros = np.zeros((scene.height, scene.width), dtype=bool)
            return zeros, zeros.astype(np.uint8), zeros.astype(np.int32), zeros.astype(np.uint8), zeros.astype(np.float32)

        if not (0 <= origin_x < scene.width and 0 <= origin_y < scene.height):
            zeros = np.zeros((scene.height, scene.width), dtype=bool)
            return zeros, zeros.astype(np.uint8), zeros.astype(np.int32), zeros.astype(np.uint8), zeros.astype(np.float32)

        if not self._use_los_for_debug_radial:
            y_coords, x_coords = np.ogrid[0:scene.height, 0:scene.width]
            dx = x_coords - origin_x
            dy = y_coords - origin_y
            dist_sq = dx * dx + dy * dy
            mask = dist_sq <= radius * radius
            dist_out = dist_sq.astype(np.int32)
            visible_out = mask.astype(np.uint8)
            return mask, visible_out, dist_out, np.zeros_like(visible_out), np.ones_like(dist_out, dtype=np.float32)

        visible_out = np.zeros((scene.height, scene.width), dtype=np.uint8)
        dist_out = -np.ones((scene.height, scene.width), dtype=np.int32)
        side_bits_out = np.zeros((scene.height, scene.width), dtype=np.uint8)
        visibility_out = np.zeros((scene.height, scene.width), dtype=np.float32)

        cell_mask = np.full((scene.height, scene.width), 0xFFFFFFFF, dtype=np.uint32)
        channels = 0xFFFFFFFF

        from game.world.light_fov import compute_fov_all_octants
        from engine.render_lighting import _precompute_geometry_blockers

        if scene.height_map is not None and scene.ceiling_map is not None:
            origin_height = int(scene.height_map[origin_y, origin_x])
            opaque_u8, transparency_f32 = _precompute_geometry_blockers(
                opaque_grid,
                scene.height_map,
                scene.ceiling_map,
                origin_x,
                origin_y,
                origin_height,
            )
        else:
            opaque_u8 = opaque_grid.astype(np.uint8)
            transparency_f32 = transparency_grid.astype(np.float32)

        compute_fov_all_octants(
            opaque_u8,
            transparency_f32,
            cell_mask,
            channels,
            visible_out,
            dist_out,
            side_bits_out,
            visibility_out,
            origin_x,
            origin_y,
            radius,
        )

        return visible_out != 0, visible_out, dist_out, side_bits_out, visibility_out

    def _compute_light_reach_mask(
        self,
        light_source: ToolLightSource,
        opaque_grid: np.ndarray,
        transparency_grid: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return cached FOV results for a light using the current debug LOS mode."""
        if light_source.intensity <= 0.0:
            scene = self._scene
            zeros = np.zeros((scene.height, scene.width), dtype=bool)
            return zeros, zeros.astype(np.uint8), zeros.astype(np.int32), zeros.astype(np.uint8), zeros.astype(np.float32)
        return self._compute_point_fov_mask(light_source.x, light_source.y, light_source.radius, opaque_grid, transparency_grid)

    def _get_configured_light_sources(self) -> list[ToolLightSource]:
        """Return scene light definitions overlaid with current UI configuration."""
        light_sources: list[ToolLightSource] = []
        for light_source in self._scene.light_sources:
            light_cfg = self._config_state.lights.get(light_source.name)
            if light_cfg is None:
                continue

            light_sources.append(
                ToolLightSource(
                    name=light_source.name,
                    x=light_source.x,
                    y=light_source.y,
                    radius=light_cfg.radius,
                    color=light_cfg.color,
                    intensity=light_cfg.intensity,
                )
            )
        return light_sources

    def _compute_frame_light_results(self, observer_visible: np.ndarray) -> list[LightRuntimeResult]:
        """Return lights with computed shape masks and activation state."""
        light_results: list[LightRuntimeResult] = []
        active_light_names: set[str] = set()

        if not bool(np.any(observer_visible)):
            self._active_light_names = active_light_names
            return light_results

        opaque_grid, transparency_grid = self._get_cached_geometry_grids()
        for light_source in self._get_configured_light_sources():
            if light_source.radius <= 0 or light_source.intensity <= 0.0:
                continue

            cache_key = (light_source.name, light_source.x, light_source.y, light_source.radius, light_source.intensity)
            if cache_key in self._light_reach_cache:
                rev, res = self._light_reach_cache[cache_key]
                if rev == self._blocker_revision:
                    light_res = res
                else:
                    light_res = None
            else:
                light_res = None

            if light_res is None:
                reach_mask, visible_out, dist_out, side_bits_out, visibility_out = self._compute_light_reach_mask(
                    light_source,
                    opaque_grid,
                    transparency_grid,
                )
                light_res = LightRuntimeResult(
                    source=light_source,
                    reach_mask=reach_mask,
                    visible_out=visible_out,
                    dist_out=dist_out,
                    side_bits_out=side_bits_out,
                    visibility_out=visibility_out,
                )
                self._light_reach_cache[cache_key] = (self._blocker_revision, light_res)

            light_cfg = self._config_state.lights.get(light_source.name)
            if light_cfg is not None:
                shape_mask = self._get_light_shape_mask(light_res, light_cfg)
            else:
                shape_mask = np.ones_like(light_res.reach_mask, dtype=np.float32)

            effective_reach = light_res.reach_mask & (shape_mask > 0.0)

            light_res.shape_mask = shape_mask
            light_res.active = bool(np.any(effective_reach & observer_visible))
            light_res.reached_observer_visible_cells = int(np.count_nonzero(effective_reach & observer_visible))
            
            h, w = observer_visible.shape
            if 0 <= light_source.y < h and 0 <= light_source.x < w:
                light_res.emitter_seen_by_observer = bool(observer_visible[light_source.y, light_source.x])
            else:
                light_res.emitter_seen_by_observer = False

            if light_res.active:
                active_light_names.add(light_source.name)

            light_results.append(light_res)

        self._active_light_names = active_light_names
        return light_results

    def _accumulate_fast_diffuse_light(
        self,
        target: np.ndarray,
        *,
        light_res: LightRuntimeResult,
        opaque_grid: np.ndarray,
        transparency_grid: np.ndarray,
    ) -> None:
        """Compute visible tiles once using production FOV function, then apply NumPy falloff."""
        if light_res.source.radius <= 0 or light_res.source.intensity <= 0.0:
            return

        valid = light_res.reach_mask
        visibility_out = light_res.visibility_out

        falloff = light_res.shape_mask if light_res.shape_mask is not None else np.zeros_like(valid, dtype=np.float32)

        if self._use_los_for_debug_radial:
            falloff = falloff * visibility_out

        target += falloff[..., None] * np.array(light_res.source.color, dtype=np.float32) * light_res.source.intensity

    def _get_light_shape_mask(self, light_res: LightRuntimeResult, light_cfg) -> np.ndarray:
        """Compute the post-shape effective mask for a light."""
        scene = self._scene
        shape = getattr(light_cfg, "shape", "circle")
        direction = getattr(light_cfg, "direction", 0.0)
        cone_angle = getattr(light_cfg, "cone_angle", 6.283185307179586)
        beam_width = getattr(light_cfg, "beam_width", 1.0)
        beam_length = getattr(light_cfg, "beam_length", 8)
        softness = getattr(light_cfg, "softness", 0.0)

        origin_x, origin_y = light_res.source.x, light_res.source.y
        radius = light_res.source.radius
        valid = light_res.reach_mask
        dist_out = light_res.dist_out

        y_coords, x_coords = np.ogrid[0:scene.height, 0:scene.width]
        dx = x_coords - origin_x
        dy = y_coords - origin_y

        shape_mask = np.zeros_like(valid, dtype=np.float32)

        if shape == "circle":
            dist = np.sqrt(np.maximum(dist_out, 0).astype(np.float32))
            falloff = np.where(valid, 1.0 - dist / float(radius), 0.0)
            shape_mask = np.clip(falloff, 0.0, 1.0)

        elif shape == "cone":
            dist = np.sqrt(np.maximum(dist_out, 0).astype(np.float32))
            falloff = np.where(valid, 1.0 - dist / float(radius), 0.0)
            falloff = np.clip(falloff, 0.0, 1.0)

            angle = np.arctan2(dy, dx)
            diff = (angle - direction + np.pi) % (2 * np.pi) - np.pi
            abs_diff = np.abs(diff)

            half_angle = cone_angle / 2.0
            if softness > 0.0:
                inner_angle = half_angle * (1.0 - softness)
                cone_factor = np.where(
                    abs_diff <= inner_angle,
                    1.0,
                    np.where(
                        abs_diff > half_angle,
                        0.0,
                        1.0 - (abs_diff - inner_angle) / (half_angle - inner_angle + 1e-9)
                    )
                )
            else:
                cone_factor = np.where(abs_diff <= half_angle, 1.0, 0.0)

            shape_mask = falloff * cone_factor

        elif shape == "beam":
            cos_dir = np.cos(direction)
            sin_dir = np.sin(direction)

            p = dx * cos_dir + dy * sin_dir
            d_perp = np.abs(-dx * sin_dir + dy * cos_dir)

            half_width = beam_width / 2.0

            in_length = (p >= 0.0) & (p <= beam_length)

            if softness > 0.0:
                inner_width = half_width * (1.0 - softness)
                perp_factor = np.where(
                    d_perp <= inner_width,
                    1.0,
                    np.where(
                        d_perp > half_width,
                        0.0,
                        1.0 - (d_perp - inner_width) / (half_width - inner_width + 1e-9)
                    )
                )
                inner_length = beam_length * (1.0 - softness)
                length_factor = np.where(
                    p <= inner_length,
                    1.0,
                    np.where(
                        p > beam_length,
                        0.0,
                        1.0 - (p - inner_length) / (beam_length - inner_length + 1e-9)
                    )
                )
            else:
                perp_factor = np.where(d_perp <= half_width, 1.0, 0.0)
                length_factor = 1.0

            beam_factor = np.where(valid & in_length, perp_factor * length_factor, 0.0)
            falloff = np.where(valid & in_length, 1.0 - p / float(beam_length), 0.0)
            falloff = np.clip(falloff, 0.0, 1.0)

            shape_mask = falloff * beam_factor

        return shape_mask

    def _compute_unified_lighting(self, active_lights: list[LightRuntimeResult]) -> tuple[np.ndarray, np.ndarray]:
        """Compute both diffuse wash and side highlights from a single visibility run per light."""
        scene = self._scene
        diffuse_rgb = np.zeros((scene.height, scene.width, 3), dtype=np.float32)
        side_rgba = np.zeros((scene.height, scene.width, 8, 4), dtype=np.float32)

        opaque_grid, transparency_grid = self._get_cached_geometry_grids()

        for light_res in active_lights:
            color = np.array(light_res.source.color, dtype=np.float32)
            intensity = light_res.source.intensity

            shape_mask = light_res.shape_mask if light_res.shape_mask is not None else np.zeros_like(light_res.reach_mask, dtype=np.float32)
            visibility_out = light_res.visibility_out
            side_bits_out = light_res.side_bits_out

            # Combine shape mask with JIT shadowcasting transmittance (visibility)
            atten = shape_mask * visibility_out * intensity

            # Walkable floors get diffuse Wash RGB
            walkable = ~opaque_grid
            diffuse_rgb += (atten * walkable)[..., None] * color

            # Walls/pillars get Side Highlights RGBA
            for side_idx in range(8):
                side_bit = 1 << side_idx
                has_side = (side_bits_out & side_bit) != 0

                side_atten = atten * has_side
                side_rgba[..., side_idx, 0:3] += side_atten[..., None] * color
                side_rgba[..., side_idx, 3] += side_atten * 255.0

        return diffuse_rgb, side_rgba

    def _composite_tile(
        self,
        output: np.ndarray,
        px: int,
        py: int,
        tile: np.ndarray,
        fg_color: np.ndarray,
        bg_color: np.ndarray,
        size: int,
    ) -> None:
        """Composite a tile onto the output image with color tinting."""
        # Ensure tile is the right size
        if tile.shape[0] != size or tile.shape[1] != size:
            return

        # Fill background
        output[py : py + size, px : px + size, :3] = bg_color

        # Apply foreground with tile alpha
        tile_alpha = tile[:, :, 3:4].astype(np.float32) / 255.0
        tile_rgb = tile[:, :, :3].astype(np.float32)

        # Tint tile with foreground color (multiply blend)
        fg_float = fg_color.astype(np.float32)
        tinted = (tile_rgb * fg_float / 255.0).clip(0, 255)

        # Blend with background using alpha
        bg_section = output[py : py + size, px : px + size, :3].astype(np.float32)
        blended = bg_section * (1 - tile_alpha) + tinted * tile_alpha
        output[py : py + size, px : px + size, :3] = blended.astype(np.uint8)

    def _draw_player_marker(self, output: np.ndarray, px: int, py: int) -> None:
        """Draw a simple player marker at the given pixel position."""
        size = self._tile_size
        # Draw a yellow-ish @ symbol area
        cx = px + size // 2
        cy = py + size // 2
        radius = size // 3
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    x = cx + dx
                    y = cy + dy
                    if 0 <= x < output.shape[1] and 0 <= y < output.shape[0]:
                        output[y, x, :3] = [255, 255, 100]

    def _draw_monster_marker(self, output: np.ndarray, px: int, py: int) -> None:
        """Draw a simple dummy monster marker at the given pixel position."""
        size = self._tile_size
        left = px + size // 4
        right = px + (size * 3) // 4
        cy = py + size // 2
        radius = max(2, size // 4)

        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    x = px + size // 2 + dx
                    y = cy + dy
                    if 0 <= x < output.shape[1] and 0 <= y < output.shape[0]:
                        output[y, x, :3] = [180, 80, 220]

        for eye_x in (left, right):
            if 0 <= eye_x < output.shape[1] and 0 <= cy < output.shape[0]:
                output[cy, eye_x, :3] = [255, 255, 255]

    def _draw_light_marker(
        self, output: np.ndarray, cx: int, cy: int, color: tuple[int, int, int]
    ) -> None:
        """Draw a small marker for a light source."""
        radius = 3
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx * dx + dy * dy <= radius * radius:
                    x = cx + dx
                    y = cy + dy
                    if 0 <= x < output.shape[1] and 0 <= y < output.shape[0]:
                        # Blend with existing
                        output[y, x, :3] = [
                            min(255, int(output[y, x, 0]) + color[0] // 2),
                            min(255, int(output[y, x, 1]) + color[1] // 2),
                            min(255, int(output[y, x, 2]) + color[2] // 2),
                        ]
