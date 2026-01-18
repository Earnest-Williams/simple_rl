# engine/window_manager.py
"""
Window manager for the roguelike game engine.
Handles display, input, tilesets, and rendering coordination.
"""
# Standard library imports
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from typing import Dict as PyDict
from typing import List, Tuple

# Third-party imports
import numpy as np
from PIL import Image

# PySide6 imports
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QAction,
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QPalette,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QDockWidget,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# Modularized Imports
from engine.window_manager_modules.input_handler import InputHandler
from engine.window_manager_modules.tileset_manager import TilesetManager
from engine.window_manager_modules.ui_overlay_manager import UIOverlayManager
from engine.renderer import ViewportParams

# Type Checking
if TYPE_CHECKING:
    from engine.main_loop import MainLoop

# Logging Setup
import structlog
import threading

log = structlog.get_logger(__name__)

DEFAULT_MIN_TILE_SIZE = 4
DEFAULT_SCROLL_SCALE_DEBOUNCE_MS = 200
DEFAULT_RESIZE_DEBOUNCE_MS = 100
DEFAULT_INITIAL_WINDOW_WIDTH = 1024
DEFAULT_INITIAL_WINDOW_HEIGHT = 768


def tile_grid_to_qimage(tile_grid, scale=4):
    """Convert a numeric tile_grid into an RGB QImage with simple color mapping."""
    from common.constants import Material

    h, w = tile_grid.shape
    img = QImage(w, h, QImage.Format.Format_RGB888)

    # Simple color mapping for materials
    for y in range(h):
        for x in range(w):
            mat = int(tile_grid[y, x])
            if mat == int(Material.SOLID_ROCK):
                c = QColor(20, 20, 20)
            elif mat == int(Material.CAVE_FLOOR):
                c = QColor(220, 220, 220)
            elif mat == int(Material.SHAFT_OPENING):
                c = QColor(200, 150, 50)
            elif mat == int(Material.CLIFF_EDGE):
                c = QColor(80, 80, 80)
            else:
                c = QColor(120, 120, 120)
            img.setPixelColor(x, y, c)

    if scale != 1:
        return img.scaled(w * scale, h * scale)
    return img


class DiagnosticsDock(QDockWidget):
    """Diagnostics dock widget for exposing pipeline controls and visualization."""

    def __init__(self, parent=None):
        super().__init__("Diagnostics", parent)
        self.main = parent
        w = QWidget()
        self.setWidget(w)
        layout = QVBoxLayout()
        w.setLayout(layout)

        # Control form
        form = QFormLayout()
        self.seed_spin = QSpinBox()
        self.seed_spin.setRange(0, 2**31 - 1)
        self.seed_spin.setValue(1)
        self.max_nodes_spin = QSpinBox()
        self.max_nodes_spin.setRange(10, 2000)
        self.max_nodes_spin.setValue(400)
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(1, 500)
        self.max_depth_spin.setValue(50)
        self.ca_spin = QSpinBox()
        self.ca_spin.setRange(0, 32)
        self.ca_spin.setValue(8)
        form.addRow("Seed", self.seed_spin)
        form.addRow("Max nodes", self.max_nodes_spin)
        form.addRow("Max depth", self.max_depth_spin)
        form.addRow("CA iterations", self.ca_spin)

        layout.addLayout(form)

        # Run button
        self.run_btn = QPushButton("Run Pipeline")
        layout.addWidget(self.run_btn)

        # Image preview
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label, 1)

        # Log area
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        # Connect button
        self.run_btn.clicked.connect(self.on_run)

    def append_log(self, text):
        """Append text to the log area."""
        self.log.append(text)

    def on_run(self):
        """Handle Run Pipeline button click."""
        params = {
            "seed": int(self.seed_spin.value()),
            "max_nodes": int(self.max_nodes_spin.value()),
            "max_depth": int(self.max_depth_spin.value()),
            "ca_iterations": int(self.ca_spin.value()),
        }
        self.append_log(f"Starting run: {params}")
        # Run in a background thread
        t = threading.Thread(target=self._run_pipeline_thread, args=(params,), daemon=True)
        t.start()

    def _run_pipeline_thread(self, params):
        """Run the pipeline in a background thread."""
        try:
            from orchestrator import run_pipeline

            # Run the pipeline with specified parameters
            res = run_pipeline(
                seed=params["seed"],
                max_nodes=params["max_nodes"],
                max_depth=params["max_depth"],
                ca_iterations=params["ca_iterations"],
                output_file="tmp_shaped_map.arrow",
                grid_size=128,
                run_sim=False,
            )
            tile_grid = res.get("tile_grid")
            backbone_count = res.get("backbone_nodes")

            # Convert image on main thread
            img = tile_grid_to_qimage(tile_grid, scale=4)

            def ui_update():
                self.image_label.setPixmap(QPixmap.fromImage(img))
                self.append_log(
                    f"Done. Backbone nodes: {backbone_count}; tile grid: {tile_grid.shape}"
                )

            # Schedule update on main thread
            self.main.qt_invoke(ui_update)
        except Exception as e:
            log.error(f"Pipeline run failed: {e}", exc_info=True)

            def ui_err():
                self.append_log(f"Run failed: {e}")

            self.main.qt_invoke(ui_err)


class WindowManager(QMainWindow):
    def __init__(
        self,
        app_config: PyDict[str, Any],
        keybindings_config: PyDict[str, Any],
        initial_tileset_path: str,
        initial_tile_width: int,
        initial_tile_height: int,
        map_width: int,
        map_height: int,
        min_tile_size_cfg: int = DEFAULT_MIN_TILE_SIZE,
        scroll_debounce_cfg: int = DEFAULT_SCROLL_SCALE_DEBOUNCE_MS,
        resize_debounce_cfg: int = DEFAULT_RESIZE_DEBOUNCE_MS,
        overlay_config_path: str | Path | None = None,
    ):
        super().__init__()
        self.app_config = app_config
        self.keybindings_config = keybindings_config
        log.info("Initializing WindowManager...")

        self.min_tile_size = min_tile_size_cfg
        self.scroll_debounce_ms = scroll_debounce_cfg
        self.resize_debounce_ms = resize_debounce_cfg
        self.map_width = map_width
        self.map_height = map_height

        # Instantiate TilesetManager
        self.tileset_manager = TilesetManager(
            initial_tileset_path=initial_tileset_path,
            initial_tile_width=initial_tile_width,
            initial_tile_height=initial_tile_height,
            min_tile_size_cfg=min_tile_size_cfg,
        )

        # FIXED: Improved cache management
        self._render_coord_cache: PyDict[str, np.ndarray] = {}
        self._cached_vp_pixel_dims: Tuple[int, int] | None = None
        self._cached_tile_dims: Tuple[int, int] | None = None
        self._cache_generation: int = 0
        self._last_tileset_change: int = 0

        # UI Setup
        self.setWindowTitle("Basic Roguelike")
        self.resize(DEFAULT_INITIAL_WINDOW_WIDTH, DEFAULT_INITIAL_WINDOW_HEIGHT)

        # Central widget with layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        central_widget.setLayout(self.layout)

        # Menu bar (QMainWindow manages its own menu bar)
        self.menu_bar = self.menuBar()

        # Dark color scheme
        self.setStyleSheet(
            """
            QWidget {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QMenuBar {
                background-color: #2a2a2a;
            }
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
            }
        """
        )

        # Scroll area for game display
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.layout.addWidget(self.scroll_area)

        # Main display label
        self.label = QLabel()
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.label)

        # State
        self.main_loop: MainLoop | None = None
        self.viewport_width: int = 0
        self.viewport_height: int = 0
        self.window_width = self.width()
        self.window_height = self.height()

        # Build menus
        self.build_menus()

        # Timers
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(self.resize_debounce_ms)
        self._resize_timer.timeout.connect(self.update_frame)

        self._pending_tile_size_change: int = 0
        self._scroll_scale_timer = QTimer(self)
        self._scroll_scale_timer.setSingleShot(True)
        self._scroll_scale_timer.setInterval(self.scroll_debounce_ms)
        self._scroll_scale_timer.timeout.connect(self._apply_scroll_scaling)

        # Active keybindings
        self.active_keybinding_sets: List[str] = ["common", "numpad"]
        for default_set in ("modern", "arrows"):
            if default_set not in self.active_keybinding_sets:
                self.active_keybinding_sets.append(default_set)
        log.info("Active keybinding sets", sets=self.active_keybinding_sets)

        # Instantiate other handlers
        self.input_handler = InputHandler(self.keybindings_config, self)

        # Overlay config
        default_overlay_cfg = self.app_config.get(
            "overlay_config", "config/overlays.toml"
        )
        overlays_path = (
            Path(overlay_config_path)
            if overlay_config_path is not None
            else Path(default_overlay_cfg)
        ).resolve()
        self.ui_overlay_manager = UIOverlayManager(self, overlays_path)

        log.debug("WindowManager __init__ complete")

    @staticmethod
    def lerp_color(color1: tuple, color2: tuple, t: float) -> tuple:
        """Linearly interpolate between two RGB colors."""
        t = max(0.0, min(1.0, t))
        r = int(color1[0] + (color2[0] - color1[0]) * t)
        g = int(color1[1] + (color2[1] - color1[1]) * t)
        b = int(color1[2] + (color2[2] - color1[2]) * t)
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return (r, g, b)

    def _update_render_coordinate_cache(self) -> None:
        """FIXED: Update render coordinate cache with better invalidation tracking."""
        if not hasattr(self, "viewport_width") or not hasattr(self, "viewport_height"):
            log.warning("Viewport dimensions not set, skipping cache update")
            return

        vp_pixel_w = self.viewport_width * self.tileset_manager.tile_width
        vp_pixel_h = self.viewport_height * self.tileset_manager.tile_height
        current_tile_w = self.tileset_manager.tile_width
        current_tile_h = self.tileset_manager.tile_height
        current_tile_dims = (current_tile_w, current_tile_h)
        current_vp_pixel_dims = (vp_pixel_w, vp_pixel_h)

        # FIXED: Check if tileset has changed
        tileset_change = getattr(self.tileset_manager, "_change_counter", 0)
        cache_needs_update = (
            self._cached_vp_pixel_dims != current_vp_pixel_dims
            or self._cached_tile_dims != current_tile_dims
            or not self._render_coord_cache
            or self._last_tileset_change != tileset_change
        )

        if not cache_needs_update:
            return

        log.info(
            "Updating render coordinate cache",
            vp_pixel_dims=current_vp_pixel_dims,
            tile_dims=current_tile_dims,
            generation=self._cache_generation + 1,
        )

        start_time = time.perf_counter()
        try:
            # Validate dimensions
            if vp_pixel_h <= 0 or vp_pixel_w <= 0:
                raise ValueError(
                    f"Invalid viewport pixel dimensions: {vp_pixel_w}x{vp_pixel_h}"
                )
            if current_tile_h <= 0 or current_tile_w <= 0:
                raise ValueError(
                    f"Invalid tile dimensions: {current_tile_w}x{current_tile_h}"
                )

            # FIXED: Check memory requirements
            estimated_memory = vp_pixel_h * vp_pixel_w * 2 * 2  # 2 arrays, 2 bytes each
            if estimated_memory > 100_000_000:  # 100MB limit
                log.warning(f"Cache would require {estimated_memory/1e6:.1f}MB")

            # Create coordinate mapping arrays
            px_y_indices, px_x_indices = np.indices(
                (vp_pixel_h, vp_pixel_w), dtype=np.int16
            )
            tile_coord_y = (px_y_indices // current_tile_h).astype(np.int16)
            tile_coord_x = (px_x_indices // current_tile_w).astype(np.int16)

            # FIXED: Validate results
            if tile_coord_y.max() >= self.viewport_height:
                log.warning(
                    f"Y coordinate overflow: max={tile_coord_y.max()}, height={self.viewport_height}"
                )
            if tile_coord_x.max() >= self.viewport_width:
                log.warning(
                    f"X coordinate overflow: max={tile_coord_x.max()}, width={self.viewport_width}"
                )

            # Store cache
            self._render_coord_cache = {
                "tile_coord_y": tile_coord_y,
                "tile_coord_x": tile_coord_x,
                "generation": self._cache_generation,
            }
            self._cached_vp_pixel_dims = current_vp_pixel_dims
            self._cached_tile_dims = current_tile_dims
            self._last_tileset_change = tileset_change
            self._cache_generation += 1

            log.debug(
                "Cache update complete",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                coord_shapes=(tile_coord_y.shape, tile_coord_x.shape),
                generation=self._cache_generation,
            )

        except (ValueError, MemoryError) as e:
            log.error(f"Failed to update coordinate cache: {e}", exc_info=True)
            self._render_coord_cache = {}
            self._cached_vp_pixel_dims = None
            self._cached_tile_dims = None
        except Exception as e:
            log.error(f"Unexpected error updating cache: {e}", exc_info=True)
            self.invalidate_render_cache()

    def invalidate_render_cache(self) -> None:
        """FIXED: Invalidate all render-related caches."""
        log.info("Invalidating all render caches")
        self._render_coord_cache = {}
        self._cached_vp_pixel_dims = None
        self._cached_tile_dims = None
        self._cache_generation += 1

        # Also invalidate tileset cache if needed
        if hasattr(self, "tileset_manager"):
            self.tileset_manager.invalidate_cache()

    def build_menus(self) -> None:
        log.debug("Building menus...")
        tileset_menu = QMenu("Tileset", self)
        try:
            script_dir = Path(__file__).parent.resolve()
            project_root = script_dir.parent
        except NameError:
            project_root = Path(".")

        # PNG tileset option
        png_path_str = str(project_root / "fonts" / "classic_roguelike_sliced")
        use_png_action = QAction("Use PNG Tileset (8x8 base)", self)
        use_png_action.triggered.connect(
            lambda: self.handle_load_tileset_action(png_path_str, 8, 8)
        )
        tileset_menu.addAction(use_png_action)

        # SVG tileset option
        svg_path_str = str(project_root / "fonts" / "classic_roguelike_sliced_svgs")
        initial_svg_render_size = 16
        use_svg_action = QAction(f"Use SVG Tileset (@{initial_svg_render_size}x)", self)
        use_svg_action.triggered.connect(
            lambda: self.handle_load_tileset_action(
                svg_path_str, initial_svg_render_size, initial_svg_render_size
            )
        )
        tileset_menu.addAction(use_svg_action)
        self.menu_bar.addMenu(tileset_menu)

        # Diagnostics menu
        diag_menu = QMenu("Diagnostics", self)
        open_diag = QAction("Open Diagnostics", self)
        open_diag.triggered.connect(lambda: self.show_diagnostics_dock())
        diag_menu.addAction(open_diag)
        self.menu_bar.addMenu(diag_menu)

        log.debug("Menus built")

    def handle_load_tileset_action(self, folder: str, width: int, height: int) -> None:
        """FIXED: Callback for menu actions with proper cache invalidation."""
        success = self.tileset_manager.load_new_tileset(folder, width, height)
        if success:
            # FIXED: Force complete cache rebuild
            self.tileset_manager._change_counter = (
                getattr(self.tileset_manager, "_change_counter", 0) + 1
            )
            self.invalidate_render_cache()
            self._update_render_coordinate_cache()
            self.update_frame()
        else:
            QMessageBox.critical(
                self, "Tileset Error", f"Failed to load tileset from:\n{folder}"
            )

    def set_main_loop(self, main_loop: "MainLoop") -> None:
        self.main_loop = main_loop
        log.info("MainLoop instance set in WindowManager")
        QTimer.singleShot(0, self.update_frame)

    def resizeEvent(self, event: QResizeEvent) -> None:
        log.debug("Resize event detected", new_size=event.size())
        # FIXED: Handle resize with cache management
        old_width = self.window_width
        old_height = self.window_height
        new_width = event.size().width()
        new_height = event.size().height()

        if new_width != old_width or new_height != old_height:
            self.window_width = new_width
            self.window_height = new_height

            # Calculate new viewport
            if hasattr(self, "tileset_manager"):
                old_vp_width = self.viewport_width
                old_vp_height = self.viewport_height
                self.viewport_width = new_width // max(
                    1, self.tileset_manager.tile_width
                )
                self.viewport_height = new_height // max(
                    1, self.tileset_manager.tile_height
                )

                # Check if viewport actually changed
                if (
                    self.viewport_width != old_vp_width
                    or self.viewport_height != old_vp_height
                ):
                    log.debug(
                        f"Viewport changed: {old_vp_width}x{old_vp_height} -> {self.viewport_width}x{self.viewport_height}"
                    )
                    self._update_render_coordinate_cache()

        self._resize_timer.start()
        super().resizeEvent(event)

    def update_frame(self) -> None:
        """Updates and redraws the main display label."""
        frame_start_time = time.perf_counter()

        if (
            not self.main_loop
            or not self.main_loop.game_state
            or not self.tileset_manager
            or not self.isVisible()
        ):
            log.debug("Skipping frame update: Components not ready")
            return

        # Use scroll area viewport size for calculations
        viewport_w = self.scroll_area.viewport().width()
        viewport_h = self.scroll_area.viewport().height()
        current_tile_w = self.tileset_manager.tile_width
        current_tile_h = self.tileset_manager.tile_height

        if (
            viewport_w <= 0
            or viewport_h <= 0
            or current_tile_w <= 0
            or current_tile_h <= 0
        ):
            log.warning("Skipping frame: Invalid dimensions")
            self.label.clear()
            return

        gs = self.main_loop.game_state

        # Calculate visible tiles based on viewport size
        visible_cols = max(1, viewport_w // current_tile_w)
        visible_rows = max(1, viewport_h // current_tile_h)

        # Calculate camera/viewport position based on player
        player_pos = gs.player_position
        cam_x, cam_y = (
            player_pos if player_pos else (gs.map_width // 2, gs.map_height // 2)
        )

        # Calculate viewport tile coordinates
        render_cols = min(visible_cols, gs.map_width)
        render_rows = min(visible_rows, gs.map_height)
        viewport_tile_x = max(
            0, min(cam_x - render_cols // 2, gs.map_width - render_cols)
        )
        viewport_tile_y = max(
            0, min(cam_y - render_rows // 2, gs.map_height - render_rows)
        )

        # Calculate actual number of tiles to render
        vp_render_tile_w = min(render_cols, gs.map_width - viewport_tile_x)
        vp_render_tile_h = min(render_rows, gs.map_height - viewport_tile_y)

        if vp_render_tile_w <= 0 or vp_render_tile_h <= 0:
            log.warning("Calculated viewport tile dimensions are invalid")
            self.label.clear()
            return

        # Store viewport dimensions
        self.viewport_width = vp_render_tile_w
        self.viewport_height = vp_render_tile_h

        # Calculate pixel size
        output_pixel_w = vp_render_tile_w * current_tile_w
        output_pixel_h = vp_render_tile_h * current_tile_h

        # Update coordinate cache if necessary
        try:
            self._update_render_coordinate_cache()
        except Exception as cache_err:
            log.error(f"Render coordinate cache update failed: {cache_err}")
            self.label.setText("Cache Error")
            return

        # Get render data from tileset manager
        tileset_render_data = self.tileset_manager.get_render_data()
        if (
            not tileset_render_data
            or tileset_render_data.get("max_defined_tile_id", -1) < 0
        ):
            log.error("Invalid render data from TilesetManager")
            self.label.setText("Tileset Error")
            return

        # Create viewport params
        viewport_params = ViewportParams(
            viewport_x=viewport_tile_x,
            viewport_y=viewport_tile_y,
            viewport_width=vp_render_tile_w,
            viewport_height=vp_render_tile_h,
            tile_arrays=tileset_render_data["tile_arrays"],
            tile_fg_colors=tileset_render_data["tile_fg_colors"],
            tile_bg_colors=tileset_render_data["tile_bg_colors"],
            tile_indices_render=tileset_render_data["tile_indices_render"],
            max_defined_tile_id=tileset_render_data["max_defined_tile_id"],
            tile_w=tileset_render_data["tile_w"],
            tile_h=tileset_render_data["tile_h"],
            coord_arrays=self._render_coord_cache,
        )

        # Render the frame
        try:
            frame_image = self.main_loop.render_frame(viewport_params)
        except Exception as render_err:
            log.error(f"Frame render failed: {render_err}", exc_info=True)
            self.label.setText("Render Error")
            return

        if frame_image is None:
            log.warning("render_frame returned None")
            self.label.clear()
            return

        # Apply overlays
        try:
            frame_image = self.ui_overlay_manager.apply_overlays(
                frame_image, gs, viewport_params
            )
        except Exception as overlay_err:
            log.error(f"Overlay application failed: {overlay_err}")

        # Convert PIL to QPixmap
        try:
            if hasattr(frame_image, "tobytes"):
                img_data = frame_image.tobytes("raw", "RGBA")
            else:
                img_data = frame_image.tostring("raw", "RGBA")

            qimage = QImage(
                img_data,
                frame_image.width,
                frame_image.height,
                QImage.Format.Format_RGBA8888,
            )
            pixmap = QPixmap.fromImage(qimage)

            # Set label size and pixmap
            self.label.setFixedSize(frame_image.width, frame_image.height)
            self.label.setPixmap(pixmap)

        except Exception as convert_err:
            log.error(f"Image conversion failed: {convert_err}")
            self.label.setText("Display Error")
            return

        # Log frame timing
        frame_duration = (time.perf_counter() - frame_start_time) * 1000
        if frame_duration > 100:
            log.warning(f"Slow frame: {frame_duration:.1f}ms")

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.main_loop:
            action = self.input_handler.process_key_event(
                event, self.active_keybinding_sets
            )
            if action:
                log.debug(f"Action triggered: {action}")
                self.main_loop.handle_action(action)
                self.update_frame()
        super().keyPressEvent(event)

    def show_help_dialog(self) -> None:
        help_text = "Roguelike Controls:\n\n"
        help_text += "Movement: Arrow keys, Numpad, or HJKL\n"
        help_text += "Wait: Period (.)\n"
        help_text += "Pickup: G\n"
        help_text += "Inventory: I\n"
        help_text += "Drop: D\n"
        help_text += "Use: U\n"
        help_text += "Equip: E\n"
        help_text += "Look: L\n"
        help_text += "Zoom: Ctrl+Scroll\n"
        help_text += "Quit: Escape"

        QMessageBox.information(self, "Help", help_text)

    def closeEvent(self, event) -> None:
        log.info("Window close event")
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.quit()

    def ui_return_to_player_turn(self) -> None:
        if self.main_loop and self.main_loop.game_state:
            self.main_loop.game_state.change_ui_state("PLAYER_TURN")
            self.ui_overlay_manager.reset_inventory_state()
            self.update_frame()

    def ui_show_help_dialog(self) -> None:
        self.show_help_dialog()

    def ui_quit_game(self) -> None:
        """Handle quit game action."""
        log.info("Quit game requested")
        app_instance = QApplication.instance()
        if app_instance:
            app_instance.quit()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.main_loop:
            return

        modifiers = event.modifiers()
        angle_delta = event.angleDelta()

        if modifiers & Qt.KeyboardModifier.ControlModifier:  # Zooming
            delta_y = angle_delta.y()
            change = 1 if delta_y > 0 else -1 if delta_y < 0 else 0
            if change != 0:
                self._pending_tile_size_change += change
                self._scroll_scale_timer.start(self.scroll_debounce_ms)
        else:
            super().wheelEvent(event)

    def _apply_scroll_scaling(self) -> None:
        """Applies pending zoom changes."""
        if not hasattr(self, "scroll_area") or not self.scroll_area:
            log.error("_apply_scroll_scaling called without scroll_area")
            self._pending_tile_size_change = 0
            return

        if (
            not self.main_loop
            or self._pending_tile_size_change == 0
            or not self.tileset_manager
        ):
            return

        viewport_widget = self.scroll_area.viewport()
        if not viewport_widget:
            log.warning("Scroll area viewport missing for zoom")
            self._pending_tile_size_change = 0
            return

        # Calculate zoom
        h_bar = self.scroll_area.horizontalScrollBar()
        v_bar = self.scroll_area.verticalScrollBar()
        mouse_pos_in_viewport = viewport_widget.mapFromGlobal(QCursor.pos())
        content_x_at_mouse_before = h_bar.value() + mouse_pos_in_viewport.x()
        content_y_at_mouse_before = v_bar.value() + mouse_pos_in_viewport.y()

        old_tile_w = self.tileset_manager.tile_width
        old_tile_h = self.tileset_manager.tile_height

        if old_tile_w <= 0 or old_tile_h <= 0:
            log.error("Old tile size invalid")
            return

        grid_x_at_mouse = content_x_at_mouse_before / old_tile_w
        grid_y_at_mouse = content_y_at_mouse_before / old_tile_h

        target_width = old_tile_w + self._pending_tile_size_change
        target_height = old_tile_h + self._pending_tile_size_change
        min_sz = self.min_tile_size
        max_sz = self.app_config.get("max_tile_size", 64)
        new_width = max(min_sz, min(target_width, max_sz))
        new_height = max(min_sz, min(target_height, max_sz))

        accumulated_change = self._pending_tile_size_change
        self._pending_tile_size_change = 0

        if new_width != old_tile_w or new_height != old_tile_h:
            log.info(
                f"Applying zoom: {old_tile_w}x{old_tile_h} -> {new_width}x{new_height}"
            )

            success = self.tileset_manager.load_new_tileset(
                self.tileset_manager.current_tileset_path, new_width, new_height
            )

            if success:
                # FIXED: Proper cache invalidation after zoom
                self.invalidate_render_cache()
                self._update_render_coordinate_cache()

                def recenter_view_after_zoom():
                    QApplication.processEvents()
                    current_h_bar = self.scroll_area.horizontalScrollBar()
                    current_v_bar = self.scroll_area.verticalScrollBar()
                    new_content_x_at_grid = (
                        grid_x_at_mouse * self.tileset_manager.tile_width
                    )
                    new_content_y_at_grid = (
                        grid_y_at_mouse * self.tileset_manager.tile_height
                    )
                    current_h_bar.setValue(
                        int(new_content_x_at_grid - mouse_pos_in_viewport.x())
                    )
                    current_v_bar.setValue(
                        int(new_content_y_at_grid - mouse_pos_in_viewport.y())
                    )
                    log.debug("Recentered view after zoom")

                QTimer.singleShot(0, recenter_view_after_zoom)
                self.update_frame()
            else:
                log.error("Zoom failed - tileset failed to load new size")
        else:
            log.debug("Zoom resulted in no size change")

    def qt_invoke(self, callable_fn):
        """Schedule a callable to run on the main Qt thread."""
        QTimer.singleShot(0, callable_fn)

    def show_diagnostics_dock(self):
        """Create and show the diagnostics dock widget."""
        if hasattr(self, "_diagnostics_dock") and self._diagnostics_dock:
            self._diagnostics_dock.raise_()
            return
        self._diagnostics_dock = DiagnosticsDock(parent=self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self._diagnostics_dock)
