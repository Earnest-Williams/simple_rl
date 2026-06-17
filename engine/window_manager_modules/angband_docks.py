# engine/window_manager_modules/angband_docks.py
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from engine.window_manager import WindowManager
    from game.game_state import GameState

class CharacterStatusDock(QDockWidget):
    def __init__(self, parent: WindowManager) -> None:
        super().__init__("Character Status", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setObjectName("CharacterStatusDock")
        
        self.container = QWidget()
        self.container.setFixedWidth(280)
        self.layout = QVBoxLayout()
        self.container.setLayout(self.layout)
        
        self.status_label = QLabel("Loading...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Font styling
        font = QFont("Courier", 11)
        self.status_label.setFont(font)
        
        self.layout.addWidget(self.status_label)
        self.layout.addStretch(1)
        
        self.setWidget(self.container)

    def update_ui(self, gs: GameState) -> None:
        if not gs:
            return
            
        pos = gs.player_position
        x, y = pos if pos else (0, 0)
        
        hp_text = "Unknown"
        # Try to get HP from registry
        if hasattr(gs, 'entity_registry'):
            hp = gs.entity_registry.get_entity_component(gs.player_id, "hp")
            max_hp = gs.entity_registry.get_entity_component(gs.player_id, "max_hp")
            if hp is not None and max_hp is not None:
                hp_text = f"{hp}/{max_hp}"
        
        text = f"<b>Level:</b> 1<br>" \
               f"<b>Turn:</b> {gs.turn_count}<br>" \
               f"<b>Pos:</b> ({x}, {y})<br>" \
               f"<b>Fuel:</b> {gs.player_fuel}/{gs.player_max_fuel}<br>" \
               f"<b>HP:</b> {hp_text}<br>"
               
        self.status_label.setText(text)


class MessageLogDock(QDockWidget):
    def __init__(self, parent: WindowManager) -> None:
        super().__init__("Message Log", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setObjectName("MessageLogDock")
        
        self.container = QWidget()
        self.layout = QVBoxLayout()
        self.container.setLayout(self.layout)
        
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setFont(QFont("Courier", 11))
        # Remove borders for a cleaner look
        self.log_widget.setStyleSheet("QTextEdit { border: none; }")
        
        self.layout.addWidget(self.log_widget)
        
        self.setWidget(self.container)
        self._last_message_count = 0

    def update_ui(self, gs: GameState) -> None:
        if not gs or not gs.message_log:
            return
            
        current_count = len(gs.message_log)
        if current_count > self._last_message_count:
            # Append new messages
            for i in range(self._last_message_count, current_count):
                msg, color = gs.message_log[i]
                hex_color = "#{:02x}{:02x}{:02x}".format(*color)
                html_msg = f'<span style="color: {hex_color};">{msg}</span>'
                self.log_widget.append(html_msg)
            
            self._last_message_count = current_count


class TileInspectorDock(QDockWidget):
    def __init__(self, parent: WindowManager) -> None:
        super().__init__("Tile Inspector", parent)
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        self.setObjectName("TileInspectorDock")
        
        self.container = QWidget()
        self.container.setFixedWidth(280)
        self.layout = QVBoxLayout()
        self.container.setLayout(self.layout)
        
        self.info_label = QLabel("Hover over a tile...")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.info_label.setFont(QFont("Courier", 11))
        self.info_label.setWordWrap(True)
        
        self.layout.addWidget(self.info_label)
        self.layout.addStretch(1)
        self.setWidget(self.container)
        
        self._last_tile_coords = (-1, -1)

    def update_tile_info(self, gs: GameState, x: int, y: int) -> None:
        if not gs or not gs.game_map:
            return
            
        if (x, y) == self._last_tile_coords:
            return
            
        self._last_tile_coords = (x, y)
        
        if not gs.game_map.in_bounds(x, y):
            self.info_label.setText("Out of bounds")
            return
            
        if not gs.game_map.visible[y, x] and not gs.game_map.explored[y, x]:
            self.info_label.setText(f"<b>Tile:</b> ({x}, {y})<br>Unexplored")
            return
            
        # Get tile name
        tile_id = gs.game_map.tiles[y, x]
        from game.world.game_map import TILE_NAME_TO_ID
        tile_name = "Unknown"
        for name, tid in TILE_NAME_TO_ID.items():
            if tid == tile_id:
                tile_name = name.capitalize()
                break
        
        # Check metadata
        md = getattr(gs.game_map, "overland_metadata", None)
        md_text = ""
        if md:
            from common.constants import Material
            mat = md.material_grid[y, x]
            mat_name = "Unknown"
            for m in Material:
                if int(m) == int(mat):
                    mat_name = m.name
                    break
            
            from worldgen.overland.schema import Wetness
            wet = md.wetness_grid[y, x]
            wet_name = "Unknown"
            for w in Wetness:
                if int(w) == int(wet):
                    wet_name = w.name
                    break
                    
            md_text = f"<br><b>Material:</b> {mat_name}<br><b>Wetness:</b> {wet_name}"
            
        # Entities
        entities_text = ""
        if hasattr(gs, 'entity_registry'):
            occupant_id = gs.entity_registry.get_blocking_entity_at(x, y)
            if occupant_id is not None:
                name = gs.entity_registry.get_entity_component(occupant_id, "name")
                if name:
                    entities_text = f"<br><b>Occupant:</b> {name}"
                else:
                    entities_text = f"<br><b>Occupant ID:</b> {occupant_id}"
                    
            if gs.player_position and x == gs.player_position.x and y == gs.player_position.y:
                entities_text = "<br><b>Occupant:</b> You!"
                
        text = f"<b>Tile:</b> ({x}, {y})<br><b>Type:</b> {tile_name}{md_text}{entities_text}"
        self.info_label.setText(text)
