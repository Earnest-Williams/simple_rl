# import sys
import json
import os
import warnings

# Suppress numpy overflow warnings that are expected with uint64 operations
warnings.filterwarnings(
    "ignore", category=RuntimeWarning, message="overflow encountered"
)

from PySide6 import QtCore, QtGui, QtWidgets

# Import the new dungeon_generator module
import dungeon_generator  # Import the new module
from utils.game_rng import GameRNG  # Import GameRNG from game_rng.py
from utils.game_rng import MetricsCollector
from scripting_engine import MacroManager  # Import MacroManager from our new module

# --- Configuration Constants ---
ROOM_MIN_SIZE = 3
ROOM_MAX_SIZE = 5
NUM_ROOMS = 12
DUNGEON_WIDTH = 40
DUNGEON_HEIGHT = 40
PLAYER_HP = 50
SKELETON_HP = 5
PLAYER_DAMAGE_RANGE = (1, 5)
SKELETON_DAMAGE_RANGE = (1, 3)
ROOM_GAP = 3

MOVE_DELTAS = {"w": (0, -1), "a": (-1, 0), "d": (1, 0), "x": (0, 1)}
ATTACK_DELTAS = {"q": (-1, -1), "e": (1, -1), "z": (-1, 1), "c": (1, 1)}

# --- Create a global GameRNG instance ---
GAME_SEED = 42  # Default seed value
game_rng = GameRNG(
    seed=GAME_SEED, generator="xorshift", metrics=True, default_int_type=int
)


# --- Entity Classes ---
class Entity:
    def __init__(self, x, y, hp, damage_range):
        self.x = x
        self.y = y
        self.hp = hp
        self.damage_range = damage_range

    def attack(self, target):
        # Use GameRNG instead of random
        damage = game_rng.get_int(self.damage_range[0], self.damage_range[1])
        target.hp -= damage
        return damage

    def is_alive(self):
        return self.hp > 0

    def to_dict(self):
        """Convert entity to dictionary for JSON serialization"""
        return {
            "x": self.x,
            "y": self.y,
            "hp": self.hp,
            "damage_range": list(self.damage_range),
        }


class Player(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, PLAYER_HP, PLAYER_DAMAGE_RANGE)

    def take_turn(self, command, dungeon, skeletons):
        command = command.lower()
        if command == "s":
            return "Player stands still."

        if command in MOVE_DELTAS:
            dx, dy = MOVE_DELTAS[command]
            new_x, new_y = self.x + dx, self.y + dy
            # Use the dungeon_generator is_valid_position function instead
            if not dungeon_generator.is_valid_position(dungeon, new_x, new_y):
                return "Cannot move there!"
            target = get_entity_at(new_x, new_y, skeletons)
            if target:
                damage = self.attack(target)
                msg = f"Player attacks skeleton at ({new_x}, {new_y}) for {damage} damage."
                if not target.is_alive():
                    msg += " Skeleton dies!"
                    skeletons.remove(target)
                return msg
            self.x, self.y = new_x, new_y
            return f"Player moves to ({new_x}, {new_y})."

        if command in ATTACK_DELTAS:
            dx, dy = ATTACK_DELTAS[command]
            target_x, target_y = self.x + dx, self.y + dy
            if not (0 <= target_x < DUNGEON_WIDTH and 0 <= target_y < DUNGEON_HEIGHT):
                return "That attack goes off into the void!"
            target = get_entity_at(target_x, target_y, skeletons)
            if target:
                damage = self.attack(target)
                msg = f"Player attacks skeleton at ({target_x}, {target_y}) for {damage} damage."
                if not target.is_alive():
                    msg += " Skeleton dies!"
                    skeletons.remove(target)
                return msg
            else:
                return "There's no enemy in that direction to attack."

        return "Invalid command."

    def to_dict(self):
        """Convert player to dictionary for JSON serialization"""
        data = super().to_dict()
        data["type"] = "player"
        return data

    @classmethod
    def from_dict(cls, data):
        """Create player from dictionary"""
        player = cls(data["x"], data["y"])
        player.hp = data["hp"]
        player.damage_range = tuple(data["damage_range"])
        return player


class Skeleton(Entity):
    def __init__(self, x, y):
        super().__init__(x, y, SKELETON_HP, SKELETON_DAMAGE_RANGE)

    def take_turn(self, player, dungeon, skeletons):
        if is_adjacent(self, player):
            damage = self.attack(player)
            return (
                f"Skeleton at ({self.x}, {self.y}) attacks player for {damage} damage."
            )
        # Use dungeon_generator's line_of_sight function instead
        if dungeon_generator.line_of_sight(dungeon, self.x, self.y, player.x, player.y):
            dx = 1 if player.x > self.x else -1 if player.x < self.x else 0
            dy = 1 if player.y > self.y else -1 if player.y < self.y else 0
            new_x, new_y = self.x + dx, self.y + dy
            if dungeon_generator.is_valid_position(
                dungeon, new_x, new_y
            ) and not get_entity_at(new_x, new_y, skeletons + [player]):
                self.x, self.y = new_x, new_y
                return f"Skeleton moves to ({new_x}, {new_y})."
        return ""

    def to_dict(self):
        """Convert skeleton to dictionary for JSON serialization"""
        data = super().to_dict()
        data["type"] = "skeleton"
        return data

    @classmethod
    def from_dict(cls, data):
        """Create skeleton from dictionary"""
        skeleton = cls(data["x"], data["y"])
        skeleton.hp = data["hp"]
        skeleton.damage_range = tuple(data["damage_range"])
        return skeleton


# --- Utility Functions ---
def is_adjacent(e1, e2):
    return abs(e1.x - e2.x) <= 1 and abs(e1.y - e2.y) <= 1


def get_entity_at(x, y, entities):
    return next((e for e in entities if e.x == x and e.y == y), None)


def get_dungeon_string(dungeon, player, skeletons):
    # Use dungeon_generator's function with our entities
    entities = {"player": player, "enemies": skeletons}
    return dungeon_generator.get_dungeon_string(dungeon, entities)


# --- Game State Class ---
class GameState:
    def __init__(self):
        self.new_game()

    def new_game(self, seed=None):
        # Reset RNG with a new seed if provided
        global game_rng
        if seed is not None:
            game_rng.reset(seed)
        else:
            # Generate a seed using system entropy if available, else time
            try:
                new_seed = int.from_bytes(os.urandom(8), "big")
            except (AttributeError, NotImplementedError):
                import time

                new_seed = int(time.time() * 1000)
            game_rng.reset(new_seed)

        self.seed = game_rng.initial_seed  # Store the seed for save/load functionality

        # Use the dungeon_generator module to create the dungeon
        self.dungeon, self.room_data = dungeon_generator.create_dungeon(
            width=DUNGEON_WIDTH,
            height=DUNGEON_HEIGHT,
            num_rooms=NUM_ROOMS,
            min_room_size=ROOM_MIN_SIZE,
            max_room_size=ROOM_MAX_SIZE,
            room_gap=ROOM_GAP,
            rng=game_rng,
        )

        # Place player in the center of the first room
        if self.room_data:
            self.player = Player(*self.room_data[0][1])
        else:
            # Handle no rooms created - place player somewhere default
            print("Warning: No rooms created. Placing player at default location.")
            self.player = Player(DUNGEON_WIDTH // 2, DUNGEON_HEIGHT // 2)
            # Ensure the default location is walkable
            if self.dungeon[self.player.y][self.player.x] == "#":
                self.dungeon[self.player.y][self.player.x] = "."
            self.room_data = []  # Ensure room_data is empty list

        self.skeletons = []

        # Generate skeletons using GameRNG, only if rooms exist
        for room, _ in self.room_data:
            # Use GameRNG for number of skeletons
            skeleton_count = game_rng.get_int(1, 3)

            for _ in range(skeleton_count):
                # Use dungeon_generator to find empty positions
                position = dungeon_generator.find_empty_position(
                    self.dungeon, room, game_rng
                )
                if position:
                    sx, sy = position
                    # Check position is not occupied
                    if not get_entity_at(sx, sy, self.skeletons + [self.player]):
                        self.skeletons.append(Skeleton(sx, sy))

        self.messages = ["New game started. Seed: " + str(self.seed)]

    def process_turn(self, command):
        if not isinstance(command, str) or not command:
            return "Invalid command."

        # Process only the first character of the command
        if command:
            player_command = command[0]
            # Ensure player is alive before taking turn
            if not self.player.is_alive():
                return self.get_display_text()  # Game already over

            msg = self.player.take_turn(player_command, self.dungeon, self.skeletons)
            if msg:
                self.messages.append(msg)

            # Check if player action ended the game (killed last skeleton)
            if not self.skeletons:
                self.messages.append("All skeletons are dead. You win!")
                return self.get_display_text()

            # Use GameRNG to decide which skeletons act first (introduces variety)
            skeleton_indices = list(range(len(self.skeletons)))
            game_rng.shuffle(skeleton_indices)
            shuffled_indices = skeleton_indices  # Now contains the shuffled values

            for idx in shuffled_indices:
                # Check if index is still valid and skeleton is alive
                if idx < len(self.skeletons):
                    s = self.skeletons[idx]
                    if s.is_alive():
                        smsg = s.take_turn(self.player, self.dungeon, self.skeletons)
                        if smsg:
                            self.messages.append(smsg)

                        # Check if skeleton action ended the game
                        if not self.player.is_alive():
                            self.messages.append("You have been slain!")
                            break  # No need for other skeletons to act

            # Final check after all turns
            if (
                not self.player.is_alive()
                and "You have been slain!" not in self.messages[-2:]
            ):
                self.messages.append("You have been slain!")
            elif (
                not self.skeletons
                and "All skeletons are dead." not in self.messages[-2:]
            ):
                self.messages.append("All skeletons are dead. You win!")

        return self.get_display_text()

    def get_display_text(self):
        dungeon_str = get_dungeon_string(self.dungeon, self.player, self.skeletons)
        # Add RNG metrics to display
        metrics_str = ""
        if game_rng.metrics_enabled:
            metrics = game_rng.get_metrics()
            if metrics and "stats" in metrics:  # Check if metrics are available
                # Format stats robustly, handle potential missing keys or None values
                ops = metrics["stats"].get("operations_per_second")
                bits = metrics["stats"].get("bits_per_second")
                ops_str = f"{ops:.1f}/s" if ops is not None else "N/A"
                bits_str = f"{bits:.1f}/s" if bits is not None else "N/A"
                metrics_str = f"\nRNG Metrics: Ops: {ops_str}, Bits: {bits_str}"

        # Ensure messages list isn't accessed with negative index if empty
        last_messages = self.messages[-5:] if len(self.messages) >= 5 else self.messages

        return (
            f"Player HP: {self.player.hp}\nSeed: {self.seed}{metrics_str}\n"
            + dungeon_str
            + "\n\n"
            + "\n".join(last_messages)
        )

    def is_game_over(self):
        return not self.player.is_alive() or not self.skeletons

    def to_dict(self):
        """Convert game state to dictionary for serialization"""
        # Make sure room_data is serializable (list of tuples)
        serializable_room_data = []
        if hasattr(self, "room_data"):
            serializable_room_data = [
                {"room": list(room), "center": list(center)}
                for room, center in self.room_data
            ]

        data = {
            "seed": self.seed,
            "rng_state": game_rng.get_state(),  # Get current RNG state for saving
            "dungeon": [row[:] for row in self.dungeon],
            "player": self.player.to_dict(),
            "skeletons": [s.to_dict() for s in self.skeletons],
            "messages": self.messages.copy(),
            "room_data": serializable_room_data,  # Add room_data
        }
        return data

    @classmethod
    def from_dict(cls, data):
        """Create game state from dictionary"""
        # Basic validation
        required_keys = [
            "seed",
            "rng_state",
            "dungeon",
            "player",
            "skeletons",
            "messages",
            "room_data",
        ]
        if not all(key in data for key in required_keys):
            raise ValueError("Invalid save data format: Missing required keys.")

        # Reset RNG with saved state before creating anything else
        global game_rng
        try:
            game_rng.set_state(data["rng_state"])
        except Exception as e:
            raise ValueError(f"Failed to set RNG state: {e}")

        state = cls.__new__(cls)  # Create instance without calling __init__

        state.seed = data["seed"]
        state.dungeon = data["dungeon"]
        state.player = Player.from_dict(data["player"])
        state.skeletons = [Skeleton.from_dict(s) for s in data["skeletons"]]
        state.messages = data["messages"].copy()

        # Reconstruct room_data from list of dicts back to list of tuples
        state.room_data = [
            (tuple(rd["room"]), tuple(rd["center"])) for rd in data["room_data"]
        ]

        # Link the macro manager if it exists in MainWindow
        # This might be better handled in MainWindow.load_game
        # if hasattr(MainWindow, 'instance') and MainWindow.instance:
        #    MainWindow.instance.macro_manager.game_state = state

        return state


# --- Main Window ---
class MainWindow(QtWidgets.QMainWindow):
    # Keep track of the instance for potential access (e.g., by GameState.from_dict)
    # This is generally not ideal, consider dependency injection or signals/slots
    instance = None

    def __init__(self):
        super().__init__()
        MainWindow.instance = self  # Assign instance

        self.setWindowTitle("Enhanced Roguelike with GameRNG, Macros & EBF")
        self.resize(800, 700)

        # Initialize GameState first
        self.game_state = GameState()
        # Then initialize MacroManager, passing the game_state
        self.macro_manager = MacroManager(game_state=self.game_state)

        self.setup_ui()
        self.apply_dark_mode()
        self.update_display()  # Initial display update

    def setup_ui(self):
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        # Create a main layout for the central widget
        main_layout = QtWidgets.QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create a splitter for resizable panes
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        main_layout.addWidget(self.splitter)

        # Game display - top pane
        self.display_edit = QtWidgets.QPlainTextEdit(readOnly=True)
        self.display_edit.setFont(QtGui.QFont("Courier New", 10))
        self.splitter.addWidget(self.display_edit)

        # Command tab widget - bottom pane
        bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QVBoxLayout(bottom_widget)
        self.splitter.addWidget(bottom_widget)

        self.command_tabs = QtWidgets.QTabWidget()
        bottom_layout.addWidget(self.command_tabs)

        # Game command tab
        game_tab = QtWidgets.QWidget()
        game_layout = QtWidgets.QVBoxLayout(game_tab)
        self.game_input = QtWidgets.QLineEdit()
        self.game_input.setPlaceholderText("Enter game commands (e.g. wasd, qezc, s)")
        self.game_input.returnPressed.connect(self.handle_game_command)
        game_layout.addWidget(self.game_input)
        self.command_tabs.addTab(game_tab, "Game Commands")

        # Macro tab
        macro_tab = QtWidgets.QWidget()
        macro_layout = QtWidgets.QVBoxLayout(macro_tab)
        self.macro_input = QtWidgets.QLineEdit()
        self.macro_input.setPlaceholderText(
            "Define: !m=wasd;s or Execute: !m or game cmds"
        )
        self.macro_input.returnPressed.connect(self.update_macro_command)
        macro_layout.addWidget(self.macro_input)

        self.macro_list = QtWidgets.QListWidget()
        macro_layout.addWidget(self.macro_list)
        self.command_tabs.addTab(macro_tab, "Macros")

        # EBF tab
        ebf_tab = QtWidgets.QWidget()
        ebf_layout = QtWidgets.QVBoxLayout(ebf_tab)
        self.ebf_input = QtWidgets.QTextEdit()
        self.ebf_input.setPlaceholderText("Enter Brainfuck code here")
        ebf_layout.addWidget(self.ebf_input)

        # Add error display area for Brainfuck
        self.ebf_error = QtWidgets.QLabel("")
        self.ebf_error.setStyleSheet("color: red;")
        self.ebf_error.setWordWrap(True)
        ebf_layout.addWidget(self.ebf_error)

        ebf_button = QtWidgets.QPushButton("Run Brainfuck")
        ebf_button.clicked.connect(self.handle_ebf_command)
        ebf_layout.addWidget(ebf_button)
        self.command_tabs.addTab(ebf_tab, "Brainfuck")

        # Add RNG tab for GameRNG controls and statistics
        rng_tab = QtWidgets.QWidget()
        rng_layout = QtWidgets.QVBoxLayout(rng_tab)

        # Seed input
        seed_layout = QtWidgets.QHBoxLayout()
        seed_layout.addWidget(QtWidgets.QLabel("RNG Seed:"))
        self.seed_input = QtWidgets.QLineEdit()
        # Ensure game_state exists before accessing seed
        if self.game_state:
            self.seed_input.setText(str(self.game_state.seed))
        seed_layout.addWidget(self.seed_input)
        reseed_button = QtWidgets.QPushButton("Apply Seed & New Game")
        reseed_button.clicked.connect(self.reseed_game)
        seed_layout.addWidget(reseed_button)
        rng_layout.addLayout(seed_layout)

        # RNG statistics
        self.rng_stats = QtWidgets.QTextEdit()
        self.rng_stats.setReadOnly(True)
        rng_layout.addWidget(self.rng_stats)

        # Update stats button
        update_stats_button = QtWidgets.QPushButton("Update RNG Statistics")
        update_stats_button.clicked.connect(self.update_rng_stats)
        rng_layout.addWidget(update_stats_button)

        # Test RNG button
        test_rng_button = QtWidgets.QPushButton("Run RNG Self-Tests")
        test_rng_button.clicked.connect(self.run_rng_tests)
        rng_layout.addWidget(test_rng_button)

        self.command_tabs.addTab(rng_tab, "RNG Controls")

        # Set initial splitter sizes - give more space to the game display
        self.splitter.setSizes([700, 200])  # Roughly 78% top, 22% bottom

        self.setup_menu()
        self.update_macro_list()
        self.update_rng_stats()

    def setup_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("File")

        new_action = QtGui.QAction("New Game", self)
        new_action.triggered.connect(self.new_game)
        file_menu.addAction(new_action)

        save_action = QtGui.QAction("Save Game", self)
        save_action.triggered.connect(self.save_game)
        file_menu.addAction(save_action)

        load_action = QtGui.QAction("Load Game", self)
        load_action.triggered.connect(self.load_game)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QtGui.QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Add Macro menu
        macro_menu = menubar.addMenu("Macros")

        save_macros_action = QtGui.QAction("Save Macros", self)
        # Connect to the method that should exist now
        save_macros_action.triggered.connect(self.save_macros)
        macro_menu.addAction(save_macros_action)

        load_macros_action = QtGui.QAction("Load Macros", self)
        # Connect to the method that should exist now
        load_macros_action.triggered.connect(self.load_macros)
        macro_menu.addAction(load_macros_action)

        # Add RNG menu
        rng_menu = menubar.addMenu("RNG")

        toggle_metrics_action = QtGui.QAction("Toggle Metrics", self)
        toggle_metrics_action.triggered.connect(self.toggle_rng_metrics)
        rng_menu.addAction(toggle_metrics_action)

        rng_menu.addSeparator()

        save_rng_state_action = QtGui.QAction("Save RNG State", self)
        save_rng_state_action.triggered.connect(self.save_rng_state)
        rng_menu.addAction(save_rng_state_action)

        load_rng_state_action = QtGui.QAction("Load RNG State", self)
        load_rng_state_action.triggered.connect(self.load_rng_state)
        rng_menu.addAction(load_rng_state_action)

    def apply_dark_mode(self):
        # Using a common dark theme style
        self.setStyleSheet(
            """
        QWidget { 
            background-color: #2b2b2b; 
            color: #d3d3d3; 
            border: 0px; /* Prevent borders on widgets */
        }
        QMainWindow {
             background-color: #2b2b2b; 
        }
        QMenuBar { 
            background-color: #3c3f41; 
            color: #d3d3d3; 
        }
        QMenuBar::item:selected { 
            background-color: #4f5254; 
        }
        QMenu { 
            background-color: #3c3f41; 
            color: #d3d3d3; 
            border: 1px solid #4f5254;
        }
        QMenu::item:selected { 
            background-color: #4f5254; 
        }
        QLineEdit, QPlainTextEdit, QTextEdit { 
            background-color: #3c3f41; 
            color: #d3d3d3; 
            border: 1px solid #4f5254;
            padding: 2px;
        }
        QPlainTextEdit[readOnly="true"], QTextEdit[readOnly="true"] {
            background-color: #333333; /* Slightly different for readonly */
            border: 1px solid #444444;
        }
        QTabWidget::pane { 
            border: 1px solid #4f5254; 
            background-color: #2b2b2b;
        }
        QTabBar::tab { 
            background-color: #3c3f41; 
            color: #b0b0b0; 
            padding: 8px 20px;
            border: 1px solid #4f5254;
            border-bottom: none; /* Tab looks connected to pane */
        }
        QTabBar::tab:selected { 
            background-color: #4f5254; 
            color: #d3d3d3; 
            font-weight: bold;
        }
        QTabBar::tab:!selected {
             margin-top: 2px; /* Push non-selected tabs down slightly */
        }
        QListWidget { 
            background-color: #3c3f41; 
            color: #d3d3d3; 
            border: 1px solid #4f5254;
        }
        QListWidget::item:selected {
             background-color: #4f5254;
        }
        QPushButton { 
            background-color: #4f5254; 
            color: #d3d3d3; 
            border: 1px solid #5f6163;
            padding: 5px 10px;
            min-width: 60px; /* Ensure buttons have some width */
        }
        QPushButton:hover { 
            background-color: #5f6163; 
        }
        QPushButton:pressed {
             background-color: #4a4d4f;
        }
        QLabel {
             border: none; /* Ensure labels don't have borders unless intended */
        }
        QScrollBar:vertical {
            border: 1px solid #4f5254;
            background: #3c3f41;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #5f6163;
            min-height: 20px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px; /* Hide arrows */
            background: none;
        }
        
        /* Splitter handle styling */
        QSplitter::handle {
            background-color: #4f5254;
            height: 2px;
        }
        QSplitter::handle:hover {
            background-color: #7f8487;
        }
        QSplitter::handle:pressed {
            background-color: #a0a0a0;
        }
        """
        )

    def keyPressEvent(self, event):
        # Handle game keys if no input widget has focus, regardless of current tab
        if (
            not self.game_input.hasFocus()
            and not self.macro_input.hasFocus()
            and not self.ebf_input.hasFocus()
            and not self.seed_input.hasFocus()
            and not self.rng_stats.hasFocus()
        ):

            key = event.text().lower()
            if key in "wasdqexzcs":  # Include 's' for stand still
                self.run_game_command(key)
            elif key == "\r" or key == "\n":  # Allow Enter key in game display area
                self.run_game_command("s")  # Treat Enter as "stand still" or next turn
        else:
            # Let the parent class handle the event for text input fields
            super().keyPressEvent(event)

    def run_game_command(self, cmd):
        # Ensure game state exists and game is not over
        if not self.game_state or self.game_state.is_game_over():
            return  # Do nothing if game ended or not initialized

        if not cmd:
            return

        display_text = self.game_state.process_turn(cmd)
        self.update_display(display_text)  # Use the correct update method
        self.update_rng_stats()  # Update RNG stats after each turn

        if self.game_state.is_game_over():
            self.game_input.setEnabled(False)  # Disable input on game over

    def handle_ebf_command(self):
        code = self.ebf_input.toPlainText().strip()
        if code:
            # Clear previous error
            self.ebf_error.setText("")

            # Use the macro manager to process the line (handles BF execution)
            result = self.macro_manager.process_line(code)

            # Check if the result is an error dictionary
            if isinstance(result, dict) and result.get("is_error"):
                self.ebf_error.setText(result.get("error", "Unknown Brainfuck error"))
                # Optionally update main display to show current game state even on BF error
                self.update_display()
            else:
                # If BF produced game commands, process_line executed them and returned display text
                self.update_display(
                    result
                )  # Update display with output/final game state
                self.update_rng_stats()  # Update RNG stats after BF execution

    def reseed_game(self):
        """Apply a new seed and start a new game"""
        try:
            new_seed_text = self.seed_input.text().strip()
            if not new_seed_text:
                # If input is empty, generate a new random seed
                new_seed = int.from_bytes(os.urandom(8), "big")
                print(f"Generated new seed: {new_seed}")
            else:
                new_seed = int(new_seed_text)

            # Start a new game with the specified or generated seed
            self.game_state.new_game(seed=new_seed)

            # Ensure macro manager points to the new game state
            self.macro_manager.game_state = self.game_state

            self.game_input.setEnabled(True)  # Ensure input is enabled for new game
            self.seed_input.setText(
                str(self.game_state.seed)
            )  # Update display with actual seed used
            self.update_display()
            self.update_rng_stats()
            QtWidgets.QMessageBox.information(
                self,
                "New Game Started",
                f"New game started with seed: {self.game_state.seed}",
            )
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Seed",
                "Seed must be a valid integer or empty for random.",
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to start new game: {e}"
            )

    def update_macro_list(self):
        self.macro_list.clear()
        # Check if macro_manager and its macros exist
        if (
            hasattr(self, "macro_manager")
            and self.macro_manager
            and hasattr(self.macro_manager, "macros")
        ):
            for name, sequence in self.macro_manager.macros.items():
                self.macro_list.addItem(f"{name} = {sequence}")

    def new_game(self):
        """Starts a new game with a randomly generated seed"""
        # Generate a new seed using system entropy if possible
        try:
            seed = int.from_bytes(os.urandom(8), "big")
        except (AttributeError, NotImplementedError):
            import time

            seed = int(time.time() * 1000)

        self.game_state.new_game(seed=seed)

        # Ensure macro manager points to the new game state
        self.macro_manager.game_state = self.game_state

        self.seed_input.setText(str(self.game_state.seed))  # Update seed display
        self.game_input.setEnabled(True)  # Ensure input enabled
        self.update_display()
        self.update_rng_stats()
        print(f"Started new game with seed: {seed}")  # Log seed

    def save_game(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Game", "", "Game Files (*.json)"
        )
        if fn:
            try:
                # Get the combined game and RNG state dictionary
                data = self.game_state.to_dict()

                # Add macro state if needed (optional, depends if you want macros saved with game)
                # data['macros'] = self.macro_manager.macros

                with open(fn, "w") as f:
                    # Use default=int to handle potential NumPy integers in RNG state
                    json.dump(data, f, indent=2, default=int)

                QtWidgets.QMessageBox.information(
                    self, "Save Game", f"Game saved successfully to:\n{fn}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to save game: {e}"
                )

    def load_game(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Game", "", "Game Files (*.json)"
        )
        if fn:
            try:
                with open(fn, "r") as f:
                    data = json.load(f)

                # Basic validation (as defined in previous fix)
                if "game_state" not in data or "rng_state" not in data:
                    # Compatibility check for older saves without separate game_state key
                    if all(
                        k in data
                        for k in [
                            "seed",
                            "rng_state",
                            "dungeon",
                            "player",
                            "skeletons",
                            "messages",
                        ]
                    ):
                        print("Attempting to load older save format...")
                        game_state_data = data  # Assume the whole dict is game_state
                    else:
                        raise ValueError("Invalid save file format.")
                else:
                    # Newer format with 'game_state' key
                    game_state_data = data["game_state"]

                # Load game state (GameState.from_dict handles RNG state restoration)
                self.game_state = GameState.from_dict(game_state_data)

                # Crucially, update the macro manager's reference to the new game state
                self.macro_manager.game_state = self.game_state

                # Load macros if they were saved with the game state (optional)
                # if 'macros' in data:
                #    self.macro_manager.macros = data['macros']
                #    self.update_macro_list()

                # Update UI
                self.game_input.setEnabled(
                    not self.game_state.is_game_over()
                )  # Disable input if loaded game is over
                self.seed_input.setText(str(self.game_state.seed))
                self.update_display()
                self.update_rng_stats()
                # Ensure macro list is updated if macros were loaded separately or with game
                self.update_macro_list()

                QtWidgets.QMessageBox.information(
                    self, "Load Game", f"Game loaded successfully from:\n{fn}"
                )

            except Exception as e:

                # print(f"Load game error: {e}\n{traceback.format_exc()}") # Detailed error for debugging
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to load game: {e}"
                )
                # Optionally, start a new game on load failure
                # self.new_game()

    def save_macros(self):
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save Macros", "", "Macro Files (*.json)"
        )
        if fn:
            try:
                with open(fn, "w") as f:
                    # Save the macros from the manager instance
                    json.dump(self.macro_manager.macros, f, indent=2)
                QtWidgets.QMessageBox.information(
                    self, "Save Macros", f"Macros saved successfully to:\n{fn}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to save macros: {e}"
                )

    def load_macros(self):
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load Macros", "", "Macro Files (*.json)"
        )
        if fn:
            try:
                with open(fn, "r") as f:
                    loaded_macros = json.load(f)

                if not isinstance(loaded_macros, dict):
                    raise ValueError(
                        "Invalid macro file format. Expected a JSON object."
                    )

                # Replace current macros with loaded ones
                self.macro_manager.macros = loaded_macros
                self.update_macro_list()  # Update the UI list
                QtWidgets.QMessageBox.information(
                    self, "Load Macros", f"Macros loaded successfully from:\n{fn}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to load macros: {e}"
                )

    def update_display(self, text=None):
        """Updates the main display text area."""
        # Ensure game_state is valid before trying to display
        if not hasattr(self, "game_state") or not self.game_state:
            self.display_edit.setPlainText("Error: Game state not initialized.")
            return

        try:
            if text is not None:
                # Ensure text passed (e.g. from macro manager) is a string
                display_content = str(text)
            else:
                # Otherwise, get the standard display text from game_state
                display_content = self.game_state.get_display_text()

            self.display_edit.setPlainText(display_content)
        except Exception as e:
            # Fallback if getting display text fails
            # print(f"Error updating display: {e}") # Log error
            self.display_edit.setPlainText(f"Error generating display:\n{e}")

        # Optional: Auto-scroll to the bottom
        # Use QTimer.singleShot to ensure scroll happens after text is rendered
        QtCore.QTimer.singleShot(
            0,
            lambda: self.display_edit.verticalScrollBar().setValue(
                self.display_edit.verticalScrollBar().maximum()
            ),
        )

    def update_rng_stats(self) -> None:
        """Update the RNG statistics display"""
        # Check game_rng exists and metrics are enabled/available
        if hasattr(game_rng, "metrics_enabled") and game_rng.metrics_enabled:
            metrics = game_rng.get_metrics()
            if metrics and "stats" in metrics and "metrics" in metrics:
                try:
                    # Format key metrics nicely, check for None before formatting
                    stats = metrics.get("stats", {})
                    metrics_data = metrics.get("metrics", {})
                    buffer_data = metrics.get("buffer", {})
                    ops = stats.get("operations_per_second")
                    bits = stats.get("bits_per_second")

                    vals = metrics_data.get("values_generated")
                    if vals is None:
                        ints_generated = metrics_data.get("integers_generated")
                        floats_generated = metrics_data.get("floats_generated")
                        if ints_generated is not None or floats_generated is not None:
                            vals = (ints_generated or 0) + (floats_generated or 0)

                    bits_used = metrics_data.get("bits_used")
                    if bits_used is None:
                        bits_used = metrics_data.get("bits_consumed")

                    buf_size = buffer_data.get("buffer_size")
                    buf_cap = buffer_data.get("buffer_capacity")
                    w_choices = metrics_data.get("weighted_choices", 0)

                    stats_text = "RNG Metrics:\n"
                    # Check if game_state exists for seed
                    current_seed = (
                        self.game_state.seed if hasattr(self, "game_state") else "N/A"
                    )
                    stats_text += f"- Current Seed: {current_seed}\n"
                    stats_text += (
                        f"- Operations/sec: {ops:.1f}\n"
                        if ops is not None
                        else "- Operations/sec: N/A\n"
                    )
                    stats_text += (
                        f"- Bits/sec: {bits:.1f}\n"
                        if bits is not None
                        else "- Bits/sec: N/A\n"
                    )
                    stats_text += (
                        f"- Values Generated: {vals}\n"
                        if vals is not None
                        else "- Values Generated: N/A\n"
                    )
                    stats_text += (
                        f"- Bits Used: {bits_used}\n"
                        if bits_used is not None
                        else "- Bits Used: N/A\n"
                    )
                    stats_text += (
                        f"- Buffer Size: {buf_size} / {buf_cap}\n"
                        if buf_size is not None and buf_cap is not None
                        else "- Buffer Size: N/A\n"
                    )

                    generator_type = getattr(game_rng, "generator_type", "N/A")
                    stats_text += f"\nGenerator Type: {generator_type}\n"

                    if w_choices > 0:
                        stats_text += f"Weighted Choices: {w_choices}\n"

                    self.rng_stats.setText(stats_text)
                    return  # Exit after successful update
                except Exception:
                    # print(f"Error formatting RNG stats: {e}") # Log error
                    self.rng_stats.setText("Error updating RNG stats.")
                    return  # Exit on error

        # If metrics disabled or unavailable
        self.rng_stats.setText(
            "RNG Metrics Disabled or Unavailable\nEnable via RNG menu."
        )

    def run_rng_tests(self):
        """Run statistical tests on the RNG"""
        # Run tests without affecting the game state
        try:
            current_state = game_rng.get_state()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to get current RNG state: {e}"
            )
            return

        try:
            # Run basic tests by default, can add options for more extensive tests
            test_results = game_rng.run_self_tests(level="basic")

            # Format test results
            results_text = "RNG Self-Test Results:\n\n"

            # Add test status
            all_passed = test_results.get("all_tests_passed", False)
            results_text += f"All Tests Passed: {'Yes' if all_passed else 'No'}\n\n"

            # Add details for each test, handling potential missing keys
            for key, value in test_results.items():
                if key != "all_tests_passed":
                    if key.endswith("_ok"):
                        test_name = key[:-3].replace("_", " ").title()
                        results_text += (
                            f"- {test_name}: {'PASS' if value else 'FAIL'}\n"
                        )
                    else:
                        # Format numeric values nicely
                        test_name = key.replace("_", " ").title()
                        if isinstance(value, float):
                            results_text += f"- {test_name}: {value:.4f}\n"
                        else:
                            results_text += f"- {test_name}: {value}\n"

            # Show test results in a larger message box
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowTitle("RNG Test Results")
            msg_box.setText(results_text)
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box.exec()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Failed to run RNG self-tests: {e}"
            )
        finally:
            # Restore the original RNG state robustly
            try:
                game_rng.set_state(current_state)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "RNG State Error",
                    f"Could not restore RNG state after tests: {e}",
                )

    def toggle_rng_metrics(self):
        """Toggle RNG metrics collection on/off"""

        global game_rng  # Ensure we modify the global instance

        # Ensure game_rng object exists and has the necessary attributes
        if not hasattr(game_rng, "metrics_enabled"):
            QtWidgets.QMessageBox.warning(
                self,
                "RNG Error",
                "GameRNG object not properly initialized for metrics.",
            )
            return

        game_rng.metrics_enabled = not game_rng.metrics_enabled

        msg = ""
        try:
            if game_rng.metrics_enabled:
                # Re-initialize metrics if needed or start if stopped
                if not hasattr(game_rng, "metrics") or game_rng.metrics is None:
                    # Assuming MetricsCollector is available globally or imported
                    game_rng.metrics = MetricsCollector()
                # Ensure start method exists before calling
                if hasattr(game_rng.metrics, "start"):
                    game_rng.metrics.start()
                msg = "RNG metrics collection enabled."
            else:
                # Stop metrics if they exist and are running
                if hasattr(game_rng, "metrics") and game_rng.metrics is not None:
                    # Ensure stop method exists
                    if hasattr(game_rng.metrics, "stop"):
                        game_rng.metrics.stop()
                msg = "RNG metrics collection disabled."
        except Exception as e:
            msg = f"Error toggling metrics: {e}"
            # Optionally revert the toggle on error
            # game_rng.metrics_enabled = not game_rng.metrics_enabled

        self.update_rng_stats()  # Update display regardless of success/failure
        QtWidgets.QMessageBox.information(self, "RNG Metrics", msg)

    def save_rng_state(self):
        """Save RNG state to a file"""
        fn, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save RNG State", "", "RNG State Files (*.rng)"
        )
        if fn:
            try:
                # Ensure save_state_to_file method exists
                if not hasattr(game_rng, "save_state_to_file"):
                    raise AttributeError(
                        "GameRNG object does not have 'save_state_to_file' method."
                    )

                game_rng.save_state_to_file(fn)
                QtWidgets.QMessageBox.information(
                    self, "Save RNG State", f"RNG state saved successfully to:\n{fn}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to save RNG state: {e}"
                )

    def load_rng_state(self):
        """Load RNG state from a file"""
        fn, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load RNG State", "", "RNG State Files (*.rng)"
        )
        if fn:
            try:
                # Ensure load_state_from_file method exists
                if not hasattr(game_rng, "load_state_from_file"):
                    raise AttributeError(
                        "GameRNG object does not have 'load_state_from_file' method."
                    )

                game_rng.load_state_from_file(fn)

                # Update the seed input to reflect the loaded state's *initial* seed
                if hasattr(game_rng, "initial_seed"):
                    self.seed_input.setText(str(game_rng.initial_seed))
                else:
                    # If initial_seed isn't tracked, maybe clear or use current game seed?
                    self.seed_input.setText(str(self.game_state.seed))

                self.update_rng_stats()
                QtWidgets.QMessageBox.information(
                    self,
                    "Load RNG State",
                    f"RNG state loaded successfully from:\n{fn}.\nNote: This only loads the RNG, not the full game state.",
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    self, "Error", f"Failed to load RNG state: {e}"
                )

    def update_macro_command(self):
        """Handle text entered in the macro input line"""
        text = self.macro_input.text().strip()
        if text:
            # Process the line using MacroManager
            result = self.macro_manager.process_line(text)

            # Check if the result indicates an error
            if isinstance(result, dict) and result.get("is_error"):
                # Display error in the main display or a dedicated status bar/label
                self.update_display(f"Error: {result.get('error', 'Unknown error')}")
            else:
                # For macro definitions, just show a status message and don't replace game display
                if text.startswith("!") and "=" in text:
                    # Create a status message without replacing game display
                    if isinstance(result, str) and result.startswith("Defined macro"):
                        # Add to messages list in game_state instead of replacing display
                        if self.game_state and hasattr(self.game_state, "messages"):
                            self.game_state.messages.append(result)
                            self.update_display()  # Update to refresh messages list
                        else:
                            # Fallback if game_state is not available
                            QtWidgets.QMessageBox.information(
                                self, "Macro Defined", result
                            )
                    else:
                        # For other operations that aren't definitions, update display
                        self.update_display(result)
                else:
                    # If it's not a macro definition, update the display with the game state
                    self.update_display(result)

            self.macro_input.clear()
            self.update_macro_list()  # Update list if definition changed
            self.update_rng_stats()  # Update RNG stats if game commands were executed

    def handle_game_command(self):
        """Handle text entered in the game command input line"""
        text = self.game_input.text().strip()

        # Check if it's a macro (starts with !)
        if text.startswith("!"):
            # Execute the macro using MacroManager
            result = self.macro_manager.process_line(text)

            # Update the game display with the result
            if isinstance(result, dict) and result.get("is_error"):
                self.update_display(f"Error: {result.get('error', 'Unknown error')}")
            else:
                self.update_display(result)

            self.game_input.clear()
            self.update_rng_stats()
            return

        # Original logic for individual character commands
        for char in text.lower():
            if char in "wasdqexzcs":  # Valid game commands including 's'
                self.run_game_command(char)
                # Stop processing sequence if game ends
                if self.game_state and self.game_state.is_game_over():
                    break
            # Allow other characters? Or ignore? Currently ignores.

        self.game_input.clear()


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    # Ensure exceptions are caught and displayed if GUI fails early
    try:
        window = MainWindow()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(f"Critical error during application startup: {e}")
        # Try to show a basic message box if possible
        try:
            error_dialog = QtWidgets.QMessageBox()
            error_dialog.setIcon(QtWidgets.QMessageBox.Critical)
            error_dialog.setText("Application Startup Error")
            error_dialog.setInformativeText(str(e))
            error_dialog.setWindowTitle("Critical Error")
            error_dialog.exec()
        except Exception as diag_e:
            print(f"Could not display error dialog: {diag_e}")
        sys.exit(1)  # Exit with error code
