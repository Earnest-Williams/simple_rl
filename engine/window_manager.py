# engine/window_manager.py
"""
Window manager for the roguelike game engine.
Handles display, input, tilesets, and rendering coordination.
"""
# Standard library imports
import json
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict
from typing import Dict as PyDict
from typing import List, Tuple

# Third-party imports
import numpy as np
from PIL import Image
from pydantic import TypeAdapter, ValidationError

# PySide6 imports
from PySide6.QtCore import QPoint, Qt, QRect, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QCursor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPalette,
    QPen,
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
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTabWidget,
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

NODE_TO_TILE_ADAPTER = TypeAdapter(Dict[int, Tuple[int, int]])

DEFAULT_MIN_TILE_SIZE = 4
DEFAULT_SCROLL_SCALE_DEBOUNCE_MS = 200
DEFAULT_RESIZE_DEBOUNCE_MS = 100
DEFAULT_INITIAL_WINDOW_WIDTH = 1024
DEFAULT_INITIAL_WINDOW_HEIGHT = 768


def tile_grid_to_qimage(tile_grid: np.ndarray, scale: int = 4) -> QImage:
    """Convert a numeric tile_grid into an RGB QImage with simple color mapping."""
    from common.constants import Material

    h: int
    w: int
    h, w = tile_grid.shape

    # Create an empty RGB array and fill with a default color
    rgb_array: np.ndarray = np.full((h, w, 3), (120, 120, 120), dtype=np.uint8)

    # Define color mapping for vectorized application
    color_map: PyDict[int, Tuple[int, int, int]] = {
        int(Material.SOLID_ROCK): (20, 20, 20),
        int(Material.CAVE_FLOOR): (220, 220, 220),
        int(Material.SHAFT_OPENING): (200, 150, 50),
        int(Material.CLIFF_EDGE): (80, 80, 80),
    }

    # Apply colors using vectorized boolean indexing, which is much faster than a Python loop
    mat_id: int
    color: Tuple[int, int, int]
    for mat_id, color in color_map.items():
        rgb_array[tile_grid == mat_id] = color

    # Create QImage from the numpy array. The .copy() is crucial to detach the QImage
    # from the numpy array's memory, preventing potential garbage collection issues.
    img: QImage = QImage(
        rgb_array.data, w, h, w * 3, QImage.Format.Format_RGB888
    ).copy()

    if scale != 1:
        return img.scaled(w * scale, h * scale)
    return img


class ClickableLabel(QLabel):
    """QLabel that emits a clicked signal with QPoint."""

    clicked = Signal(QPoint)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.pos())
        super().mousePressEvent(event)


class NodeInspectorDock(QDockWidget):
    """Docked inspector for backbone nodes: summary, generator steps, children, JSON."""

    main: "WindowManager"
    layout: QVBoxLayout
    header: QLabel
    children_label: QLabel
    children_container: QWidget
    children_layout: QVBoxLayout
    tabs: QTabWidget
    summary: QTextEdit
    steps_list: QListWidget
    json_view: QPlainTextEdit
    _current_node_id: int | None
    _generator_steps: List[Dict[str, Any]] | None
    _augmented_node_map: Dict[str | int, Any] | None
    navigate_callback: Callable[[int], None] | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Node Inspector", parent)
        self.main = parent  # type: ignore
        w = QWidget()
        self.setWidget(w)
        self.layout = QVBoxLayout()
        w.setLayout(self.layout)

        self.header = QLabel("No node selected")
        self.layout.addWidget(self.header)

        self.children_label = QLabel("Children:")
        self.layout.addWidget(self.children_label)
        self.children_container = QWidget()
        self.children_layout = QVBoxLayout()
        self.children_container.setLayout(self.children_layout)
        self.layout.addWidget(self.children_container)

        self.tabs = QTabWidget()
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.steps_list = QListWidget()
        self.json_view = QPlainTextEdit()
        self.json_view.setReadOnly(True)

        self.tabs.addTab(self.summary, "Summary")
        self.tabs.addTab(self.steps_list, "Generator Steps")
        self.tabs.addTab(self.json_view, "JSON")
        self.layout.addWidget(self.tabs)

        self._current_node_id = None
        self._generator_steps = None
        self._augmented_node_map = None
        self.navigate_callback = None

    def display_node(
        self,
        node_id: int,
        node_dict: Dict[str, Any],
        generator_steps: List[Dict[str, Any]] | None,
        augmented_node_map: Dict[str | int, Any] | None,
    ) -> None:
        """Populate the inspector with a node's details."""
        self._current_node_id = node_id
        self._generator_steps = generator_steps or []
        self._augmented_node_map = augmented_node_map or {}

        self.header.setText(f"Node {node_id}")
        keys = [
            "id",
            "parent_id",
            "children_ids",
            "node_type",
            "degree",
            "path_depth",
            "path_length_from_root",
            "depth_m",
            "segment_length_xy",
            "segment_incline_deg",
        ]
        lines = []
        for key in keys:
            if key in node_dict:
                lines.append(f"{key}: {node_dict.get(key)}")
        other_keys = sorted([key for key in node_dict.keys() if key not in keys])
        for key in other_keys:
            lines.append(f"{key}: {node_dict.get(key)}")
        self.summary.setPlainText("\n".join(lines))

        while self.children_layout.count():
            widget = self.children_layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
        children = node_dict.get("children_ids") or []
        if not children:
            self.children_layout.addWidget(QLabel("(no children)"))
        else:
            for child_id in children:
                child_id_int: int | None = None
                if isinstance(child_id, (int, np.integer)):
                    child_id_int = int(child_id)
                elif isinstance(child_id, str) and child_id.lstrip("-").isdigit():
                    child_id_int = int(child_id)
                btn = QPushButton(f"Child {child_id}")

                def on_child_clicked(
                    checked: bool = False, child_id: int | None = child_id_int
                ) -> None:
                    if child_id is None:
                        return
                    if self.navigate_callback:
                        self.navigate_callback(child_id)

                btn.clicked.connect(on_child_clicked)
                self.children_layout.addWidget(btn)

        self.steps_list.clear()
        for idx, step in enumerate(self._generator_steps or []):
            if isinstance(step, dict):
                desc = step.get("desc", "")
                vars_obj = step.get("vars", "")
                vars_str = str(vars_obj)
            else:
                desc = str(step)
                vars_str = ""
            text = f"{idx}: {desc}  —  {vars_str}"
            item = QListWidgetItem(text)
            if str(node_id) in vars_str:
                item.setBackground(QColor(255, 250, 200))
            self.steps_list.addItem(item)

        self.json_view.setPlainText(
            orjson.dumps(node_dict, option=orjson.OPT_INDENT_2).decode()
        )


class DiagnosticsDock(QDockWidget):
    """Diagnostics dock widget for exposing pipeline controls and visualization."""

    main: "WindowManager"
    seed_spin: QSpinBox
    max_nodes_spin: QSpinBox
    max_depth_spin: QSpinBox
    ca_spin: QSpinBox
    run_btn: QPushButton
    overlay_btn: QPushButton
    dump_core_btn: QPushButton
    dump_processed_btn: QPushButton
    image_label: ClickableLabel
    log: QTextEdit
    _last_run_results: PyDict[str, Any] | None
    node_tile_coords: PyDict[int, Tuple[int, int]]
    preview_scale: int
    overlay_enabled: bool
    _node_inspector: "NodeInspectorDock" | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Diagnostics", parent)
        self.main = parent  # type: ignore
        self._last_run_results = None
        self.node_tile_coords = {}
        self.preview_scale = 4
        self.overlay_enabled = True
        self._node_inspector = None
        w: QWidget = QWidget()
        self.setWidget(w)
        layout: QVBoxLayout = QVBoxLayout()
        w.setLayout(layout)

        # Control form
        form: QFormLayout = QFormLayout()
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

        # Run button and overlay toggle
        btn_row = QHBoxLayout()
        self.run_btn = QPushButton("Run Pipeline")
        btn_row.addWidget(self.run_btn)
        self.overlay_btn = QPushButton("Overlay: ON")
        self.overlay_btn.setCheckable(True)
        self.overlay_btn.setChecked(True)
        btn_row.addWidget(self.overlay_btn)
        layout.addLayout(btn_row)

        # Dump buttons
        dump_row = QHBoxLayout()
        self.dump_core_btn = QPushButton("Dump core_gen.json")
        self.dump_processed_btn = QPushButton("Dump processed_cave.json")
        dump_row.addWidget(self.dump_core_btn)
        dump_row.addWidget(self.dump_processed_btn)
        layout.addLayout(dump_row)

        # Image preview
        self.image_label = ClickableLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label, 1)

        # Log area
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)

        # Connect button
        self.run_btn.clicked.connect(self.on_run)
        self.overlay_btn.clicked.connect(self.on_toggle_overlay)
        self.dump_core_btn.clicked.connect(self.on_dump_core)
        self.dump_processed_btn.clicked.connect(self.on_dump_processed)
        self.image_label.clicked.connect(self.on_image_clicked)

    def append_log(self, text: str) -> None:
        """Append text to the log area."""
        self.log.append(text)

    def on_toggle_overlay(self) -> None:
        self.overlay_enabled = self.overlay_btn.isChecked()
        text = "Overlay: ON" if self.overlay_enabled else "Overlay: OFF"
        self.overlay_btn.setText(text)
        if self._last_run_results is None:
            return
        tile_grid = self._last_run_results.get("tile_grid")
        if isinstance(tile_grid, np.ndarray):
            self._update_preview_with_overlay(tile_grid)

    def on_dump_core(self) -> None:
        if self._last_run_results is None:
            self.append_log("No run results to dump.")
            return
        raw = self._last_run_results.get("raw_backbone")
        if not isinstance(raw, dict):
            self.append_log("No raw_backbone present in results.")
            return
        out_path = Path.cwd() / "diagnostics_core_gen.json"
        with out_path.open("w", encoding="utf-8") as output_file:
            json.dump(raw, output_file, indent=2)
        self.append_log(f"Wrote raw backbone to: {out_path}")

    def on_dump_processed(self) -> None:
        if self._last_run_results is None:
            self.append_log("No run results to dump.")
            return
        proc = self._last_run_results.get("augmented_nodes")
        if not isinstance(proc, list):
            self.append_log("No augmented_nodes present in results.")
            return
        out_path = Path.cwd() / "diagnostics_processed_cave.json"
        with out_path.open("w", encoding="utf-8") as output_file:
            json.dump({"nodes": proc}, output_file, indent=2)
        self.append_log(f"Wrote processed cave to: {out_path}")

    def on_run(self) -> None:
        """Handle Run Pipeline button click."""
        params: PyDict[str, int] = {
            "seed": self.seed_spin.value(),
            "max_nodes": self.max_nodes_spin.value(),
            "max_depth": self.max_depth_spin.value(),
            "ca_iterations": self.ca_spin.value(),
        }
        self.append_log(f"Starting run: {params}")
        # Run in a background thread
        t: threading.Thread = threading.Thread(
            target=self._run_pipeline_thread, args=(params,), daemon=True
        )
        t.start()

    def _run_pipeline_thread(self, params: PyDict[str, int]) -> None:
        """Run the pipeline in a background thread."""
        from orchestrator import run_pipeline

        try:
            # Run the pipeline with specified parameters
            res: PyDict[str, Any] = run_pipeline(
                seed=params["seed"],
                max_nodes=params["max_nodes"],
                max_depth=params["max_depth"],
                ca_iterations=params["ca_iterations"],
                output_file="tmp_shaped_map.arrow",
                grid_size=128,
                run_sim=False,
            )
            tile_grid_obj = res.get("tile_grid")
            if not isinstance(tile_grid_obj, np.ndarray):
                raise RuntimeError("Pipeline did not return a tile grid array.")
            tile_grid: np.ndarray = tile_grid_obj

            backbone_value = res.get("backbone_nodes")
            if not isinstance(backbone_value, (int, np.integer)):
                raise RuntimeError("Pipeline did not return a backbone count.")
            backbone_count = int(backbone_value)

            self._last_run_results = res
            node_to_tile_obj = res.get("node_to_tile")
            if isinstance(node_to_tile_obj, dict) and node_to_tile_obj:
                try:
                    node_tile_coords = NODE_TO_TILE_ADAPTER.validate_python(
                        node_to_tile_obj
                    )
                    self.node_tile_coords = node_tile_coords
                except ValidationError as exc:
                    log.exception("Invalid node_to_tile mapping: %s", exc)
                    self.node_tile_coords = {}
            else:
                augmented_nodes = res.get("augmented_nodes")
                if isinstance(augmented_nodes, list):
                    self.node_tile_coords = self._map_nodes_to_tile_coords(
                        augmented_nodes, tile_grid.shape
                    )
                else:
                    self.node_tile_coords = {}

            # Convert image on main thread
            img: QImage = tile_grid_to_qimage(tile_grid, scale=self.preview_scale)

            def ui_update() -> None:
                self.append_log(
                    "Done. Backbone nodes: "
                    f"{backbone_count}; tile grid: {tile_grid.shape}"
                )
                if self.overlay_enabled and self.node_tile_coords:
                    pix = self._image_with_overlay(
                        img,
                        self.node_tile_coords,
                        highlight_node=None,
                    )
                    self.image_label.setPixmap(pix)
                else:
                    self.image_label.setPixmap(QPixmap.fromImage(img))

            # Schedule update on main thread
            self.main.qt_invoke(ui_update)
        except Exception as e:
            log.error(f"Pipeline run failed: {e}", exc_info=True)

            def ui_err() -> None:
                self.append_log(f"Run failed: {e}")

            self.main.qt_invoke(ui_err)

    def _update_preview_with_overlay(self, tile_grid: np.ndarray) -> None:
        img = tile_grid_to_qimage(tile_grid, scale=self.preview_scale)
        if self.overlay_enabled and self.node_tile_coords:
            pix = self._image_with_overlay(
                img,
                self.node_tile_coords,
                highlight_node=None,
            )
            self.image_label.setPixmap(pix)
            return
        self.image_label.setPixmap(QPixmap.fromImage(img))

    def _map_nodes_to_tile_coords(
        self,
        augmented_nodes: List[PyDict[str, Any]],
        tile_shape: Tuple[int, int],
    ) -> PyDict[int, Tuple[int, int]]:
        """Map processor node x/y values to tile (row,col) using normalization."""
        xs = [
            float(node.get("x", 0.0))
            for node in augmented_nodes
            if node.get("x") is not None
        ]
        ys = [
            float(node.get("y", 0.0))
            for node in augmented_nodes
            if node.get("y") is not None
        ]
        if not xs or not ys:
            return {}
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        dx = max(1e-6, max_x - min_x)
        dy = max(1e-6, max_y - min_y)
        h, w = tile_shape
        mapping: PyDict[int, Tuple[int, int]] = {}
        for node in augmented_nodes:
            node_id = node.get("id")
            if node_id is None:
                continue
            nx = float(node.get("x", 0.0))
            ny = float(node.get("y", 0.0))
            col = int(round((nx - min_x) / dx * (w - 1)))
            row = int(round((ny - min_y) / dy * (h - 1)))
            col = max(0, min(w - 1, col))
            row = max(0, min(h - 1, row))
            mapping[int(node_id)] = (row, col)
        return mapping

    def _image_with_overlay(
        self,
        base_img: QImage,
        node_tile_coords: PyDict[int, Tuple[int, int]],
        highlight_node: int | None,
    ) -> QPixmap:
        """Return a QPixmap built from base_img with backbone overlay drawn on top."""
        img = base_img.copy()
        painter = QPainter(img)
        alpha = 200
        pen = QPen(QColor(220, 50, 50, alpha))
        pen.setWidth(max(1, int(self.preview_scale / 2)))
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(50, 200, 50, 150)))

        augmented_nodes = []
        if self._last_run_results is not None:
            nodes_obj = self._last_run_results.get("augmented_nodes")
            if isinstance(nodes_obj, list):
                augmented_nodes = nodes_obj
        for node in augmented_nodes:
            node_id = node.get("id")
            parent_id = node.get("parent_id")
            if node_id is None or parent_id is None:
                continue
            if node_id not in node_tile_coords:
                continue
            if parent_id not in node_tile_coords:
                continue
            row0, col0 = node_tile_coords[node_id]
            row1, col1 = node_tile_coords[parent_id]
            x0 = int(col0 * self.preview_scale + self.preview_scale / 2)
            y0 = int(row0 * self.preview_scale + self.preview_scale / 2)
            x1 = int(col1 * self.preview_scale + self.preview_scale / 2)
            y1 = int(row1 * self.preview_scale + self.preview_scale / 2)
            painter.drawLine(x0, y0, x1, y1)

        for node_id, (row, col) in node_tile_coords.items():
            x = int(col * self.preview_scale + self.preview_scale / 2)
            y = int(row * self.preview_scale + self.preview_scale / 2)
            radius = max(2, int(self.preview_scale / 1.5))
            if highlight_node is not None and node_id == highlight_node:
                painter.setBrush(QBrush(QColor(255, 200, 0, 220)))
                painter.setPen(
                    QPen(
                        QColor(255, 200, 0, 220),
                        max(1, int(self.preview_scale / 1.5)),
                    )
                )
            else:
                painter.setBrush(QBrush(QColor(50, 200, 50, 200)))
                painter.setPen(QPen(QColor(10, 10, 10, 200)))
            painter.drawEllipse(QPoint(x, y), radius, radius)

        painter.end()
        return QPixmap.fromImage(img)

    def show_node_in_inspector(self, node_id: int) -> None:
        """Open/activate the NodeInspectorDock and show node details."""
        if self._last_run_results is None:
            return
        augmented_map_obj = self._last_run_results.get("augmented_node_map")
        if not isinstance(augmented_map_obj, dict):
            self.append_log("No augmented_node_map present in results.")
            return
        node = augmented_map_obj.get(node_id)
        if node is None:
            node = augmented_map_obj.get(str(node_id))
        if not isinstance(node, dict):
            self.append_log(f"Node {node_id} not found in augmented_node_map.")
            return
        if self._node_inspector is None:
            self._node_inspector = NodeInspectorDock(parent=self.main)
            self._node_inspector.navigate_callback = self.show_node_in_inspector
            self.main.addDockWidget(
                Qt.DockWidgetArea.RightDockWidgetArea, self._node_inspector
            )
        steps_obj = self._last_run_results.get("generator_steps")
        steps: List[Dict[str, Any]]
        if isinstance(steps_obj, list):
            steps = steps_obj
        else:
            steps = []
        self._node_inspector.display_node(node_id, node, steps, augmented_map_obj)
        tile_grid_obj = self._last_run_results.get("tile_grid")
        if isinstance(tile_grid_obj, np.ndarray) and self.node_tile_coords:
            img = tile_grid_to_qimage(tile_grid_obj, scale=self.preview_scale)
            pix = self._image_with_overlay(
                img, self.node_tile_coords, highlight_node=node_id
            )
            self.image_label.setPixmap(pix)

    def on_image_clicked(self, pos: QPoint) -> None:
        """Handle clicks on the preview image to inspect nearest backbone node."""
        if self._last_run_results is None:
            return
        if not self.node_tile_coords:
            self.append_log("No backbone nodes available for inspection.")
            return

        x = int(pos.x() / max(1, self.preview_scale))
        y = int(pos.y() / max(1, self.preview_scale))

        best_nid: int | None = None
        best_dist: float | None = None
        for node_id, (row, col) in self.node_tile_coords.items():
            dx = col - x
            dy = row - y
            dist = math.hypot(dx, dy)
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_nid = node_id

        threshold = 6.0
        if best_nid is None or best_dist is None or best_dist > threshold:
            self.append_log(f"No backbone node within {threshold} tiles of ({y}, {x}).")
            return

        self.show_node_in_inspector(best_nid)


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
        self._px_idx: Tuple[np.ndarray, np.ndarray] | None = None
        self._last_frame_image: Image.Image | None = None
        self._cached_frame: QPixmap | None = None
        self._frame_dirty: bool = True
        self._last_viewport_params: ViewportParams | None = None

        # Diagnostics dock widget
        self._diagnostics_dock: DiagnosticsDock | None = None

        # UI Setup
        self.setWindowTitle("Basic Roguelike")
        self.resize(DEFAULT_INITIAL_WINDOW_WIDTH, DEFAULT_INITIAL_WINDOW_HEIGHT)

        # Central widget with layout
        central_widget: QWidget = QWidget()
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

        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.update_frame_if_dirty)
        self.frame_timer.start(16)

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

            max_h = vp_pixel_h
            max_w = vp_pixel_w
            if self._px_idx is not None:
                max_h = max(max_h, self._px_idx[0].shape[0])
                max_w = max(max_w, self._px_idx[1].shape[1])
            if (
                self._px_idx is None
                or self._px_idx[0].shape[0] < vp_pixel_h
                or self._px_idx[1].shape[1] < vp_pixel_w
            ):
                self._px_idx = np.indices((max_h, max_w), dtype=np.int16)
            px_y = self._px_idx[0][:vp_pixel_h, :vp_pixel_w]
            px_x = self._px_idx[1][:vp_pixel_h, :vp_pixel_w]
            tile_coord_y = (px_y // current_tile_h).astype(np.int16)
            tile_coord_x = (px_x // current_tile_w).astype(np.int16)

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
        diag_menu: QMenu = QMenu("Diagnostics", self)
        open_diag: QAction = QAction("Open Diagnostics", self)
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

    def _get_viewport_params(self) -> ViewportParams | None:
        return self._last_viewport_params

    def _pil_to_qpixmap(self, image: Image.Image) -> QPixmap:
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        img_data = image.tobytes("raw", "RGBA")
        qimage = QImage(
            img_data,
            image.width,
            image.height,
            QImage.Format.Format_RGBA8888,
        ).copy()
        return QPixmap.fromImage(qimage)

    def get_pixmap(self) -> QPixmap:
        if self._cached_frame is not None and not self._frame_dirty:
            return self._cached_frame
        if self._last_frame_image is None:
            return QPixmap()
        pixmap = self._pil_to_qpixmap(self._last_frame_image)
        self._cached_frame = pixmap
        self._frame_dirty = False
        return pixmap

    def update_frame_if_dirty(self) -> None:
        if not self._frame_dirty:
            return
        self.update_frame()

    def _blit_partial_to_backing_store(
        self, partial_image: Image.Image, rect: QRect
    ) -> None:
        if self._last_frame_image is None:
            return
        if partial_image.mode != "RGBA":
            partial_image = partial_image.convert("RGBA")
        self._last_frame_image.paste(partial_image, (rect.x(), rect.y()))
        self._frame_dirty = True

    def update_frame_partial(self, dirty_rects: List[QRect]) -> None:
        if not dirty_rects or self.main_loop is None:
            return
        viewport_params = self._get_viewport_params()
        if viewport_params is None:
            return
        render_region = getattr(self.main_loop, "render_region", None)
        if render_region is None:
            log.debug("render_region not available on main loop")
            return
        for rect in dirty_rects:
            partial_image = render_region(rect, viewport_params)
            if partial_image is None:
                continue
            self._blit_partial_to_backing_store(partial_image, rect)
        pixmap = self.get_pixmap()
        self.label.setPixmap(pixmap)

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
            frame_image = self.main_loop.update_console(gs, viewport_params)
        except Exception as render_err:
            log.error(f"Frame render failed: {render_err}", exc_info=True)
            self.label.setText("Render Error")
            return

        if frame_image is None:
            log.warning("render_frame returned None")
            self.label.clear()
            return

        self._last_viewport_params = viewport_params

        # Apply overlays
        try:
            frame_image = self.ui_overlay_manager.render_overlays(
                frame_image, gs, self.main_loop
            )
        except Exception as overlay_err:
            log.error(f"Overlay application failed: {overlay_err}")

        if frame_image is not None:
            self._last_frame_image = frame_image
            self._frame_dirty = True
        pixmap = self.get_pixmap()
        self.label.setFixedSize(frame_image.width, frame_image.height)
        self.label.setPixmap(pixmap)

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
                self._frame_dirty = True
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

    def qt_invoke(self, callable_fn: Callable[[], None]) -> None:
        """Schedule a callable to run on the main Qt thread."""
        QTimer.singleShot(0, callable_fn)

    def show_diagnostics_dock(self) -> None:
        """Create and show the diagnostics dock widget."""
        if self._diagnostics_dock:
            self._diagnostics_dock.raise_()
            return
        self._diagnostics_dock = DiagnosticsDock(parent=self)
        self.addDockWidget(
            Qt.DockWidgetArea.RightDockWidgetArea, self._diagnostics_dock
        )
