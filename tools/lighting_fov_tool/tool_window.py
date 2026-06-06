"""PySide6 window for the lighting/FOV tool with scene rendering and controls."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final

import numpy as np
import structlog
from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
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

from game.world.fov import compute_light_color_array
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

log = structlog.get_logger(__name__)

# Constants
DEFAULT_TILE_SIZE: Final[int] = 16
MIN_TILE_SIZE: Final[int] = 8
MAX_TILE_SIZE: Final[int] = 32

# Lighting constants
LIGHT_FACTOR_OUTSIDE_FOV: Final[float] = (
    0.0  # Light factor for tiles outside player's field of view
)
AMBIENT_INTENSITY: Final[float] = 0.30
LIGHT_EXPOSURE: Final[float] = 2.5
RENDER_DEBOUNCE_MS: Final[int] = 33

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
        self._intensity_slider.setTracking(False)
        self._intensity_label = QLabel(f"{config.intensity:.2f}")
        intensity_layout = QHBoxLayout()
        intensity_layout.addWidget(self._intensity_slider)
        intensity_layout.addWidget(self._intensity_label)
        intensity_widget = QWidget()
        intensity_widget.setLayout(intensity_layout)
        layout.addRow("Intensity:", intensity_widget)

        # Reset button
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._on_reset)
        layout.addRow("", reset_btn)

        self.setLayout(layout)

    def _on_color_changed(self, color: tuple[int, int, int]) -> None:
        """Handle color change."""
        self._config_state.set_light_color(self._light_name, color)
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
        self._tile_size = DEFAULT_TILE_SIZE

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
            f"Use Arrow Keys or WASD to move around and see lighting blending"
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
        self.setStyleSheet(
            """
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
            """
        )

    def _on_tile_size_changed(self, size: int) -> None:
        """Handle tile size change."""
        self._tile_size = size
        self._load_tileset()
        self._render_scene()

    def _on_config_changed(self) -> None:
        """Handle configuration change from any panel."""
        self._render_timer.start()

    def _on_reset_all(self) -> None:
        """Reset all configurations to original values."""
        self._config_state.reset_all_to_original()
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

        # Compute FOV from player position
        visible = self._compute_simple_fov(
            scene.player_pos[0], scene.player_pos[1], radius=12
        )

        # Compute lighting (base intensity and colored light)
        base_intensity, colored_light = self._compute_lighting(visible)

        # Render each tile
        for y in range(scene.height):
            for x in range(scene.width):
                element_type = ElementType(scene.tiles[y, x])
                elem_config = config.elements.get(element_type)
                if elem_config is None:
                    continue

                tile_id = elem_config.tile_id
                fg_color = np.array(elem_config.fg_color, dtype=np.float32)
                bg_color = np.array(elem_config.bg_color, dtype=np.float32)

                # Apply lighting only where player can see (within FOV)
                if visible[y, x]:
                    # Apply base intensity and add colored light for visible tiles
                    intensity = base_intensity[y, x]
                    light_rgb = colored_light[y, x]
                else:
                    # Tiles outside FOV are dark
                    intensity = LIGHT_FACTOR_OUTSIDE_FOV
                    light_rgb = np.zeros(3, dtype=np.float32)

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
                px = x * self._tile_size
                py = y * self._tile_size
                self._composite_tile(
                    output, px, py, tile_img, fg_lit, bg_lit, self._tile_size
                )

        # Mark player position
        px, py = scene.player_pos
        player_px = px * self._tile_size
        player_py = py * self._tile_size
        # Draw a simple @ marker
        self._draw_player_marker(output, player_px, player_py)

        # Mark light sources
        for ls in scene.light_sources:
            light_cfg = config.lights.get(ls.name)
            if light_cfg:
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

    def _compute_simple_fov(self, ox: int, oy: int, radius: int) -> np.ndarray:
        """Compute a simple circular FOV."""
        scene = self._scene
        visible = np.zeros((scene.height, scene.width), dtype=bool)

        for y in range(scene.height):
            for x in range(scene.width):
                dx = x - ox
                dy = y - oy
                dist_sq = dx * dx + dy * dy
                if dist_sq <= radius * radius and self._has_los(ox, oy, x, y):
                    visible[y, x] = True

        return visible

    def _has_los(self, x0: int, y0: int, x1: int, y1: int) -> bool:
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
                tile = scene.tiles[y, x]
                if tile in (ElementType.WALL, ElementType.PILLAR):
                    return False

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

    def _compute_lighting(self, visible: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Compute base intensity and RGB colored lighting for each tile.

        Light sources illuminate all tiles they can reach, independent of player FOV.
        The visible parameter is not used in lighting computation but kept for API compatibility.

        Returns:
            Tuple of (base_intensity, colored_light_rgb):
            - base_intensity: 2D float32 array of ambient lighting (height, width)
            - colored_light_rgb: 3D float32 array of colored light (height, width, 3)
        """
        scene = self._scene
        config = self._config_state

        # Base ambient lighting intensity
        base_intensity = np.full(
            (scene.height, scene.width), AMBIENT_INTENSITY, dtype=np.float32
        )

        # RGB colored light contributions (additive)
        colored_light = np.zeros((scene.height, scene.width, 3), dtype=np.float32)

        # Create opaque grid for FOV computation (walls and pillars block light)
        opaque_grid = np.zeros((scene.height, scene.width), dtype=bool)
        for y in range(scene.height):
            for x in range(scene.width):
                tile = scene.tiles[y, x]
                if tile in (ElementType.WALL, ElementType.PILLAR):
                    opaque_grid[y, x] = True

        # Add contribution from each light source using compute_light_color_array
        for ls in scene.light_sources:
            light_cfg = config.lights.get(ls.name)
            if light_cfg is None:
                continue

            # Use compute_light_color_array from fov module for colored lighting
            compute_light_color_array(
                origin_xy=(ls.x, ls.y),
                range_limit=light_cfg.radius,
                opaque_grid=opaque_grid,
                height_map=scene.height_map,
                ceiling_map=scene.ceiling_map,
                origin_height=0,
                target_rgb_array=colored_light,
                base_color_rgb=light_cfg.color,
            )

        # Apply exposure and clamp
        colored_light *= LIGHT_EXPOSURE
        np.clip(colored_light, 0.0, 255.0, out=colored_light)

        return base_intensity, colored_light

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
