# Repository File Manifest

This document provides a comprehensive inventory of all files in the Simple RL repository, including their purpose, imports, constants, and magic numbers.

## Table Format

For each file, the following information is provided:
- **File**: Path relative to repository root
- **Purpose**: What the file does
- **Imports**: External dependencies and their purpose
- **Constants/Magic Numbers**: Hardcoded values and their purpose

---

## Root Level Files

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `main.py` | Legacy wrapper entrypoint - delegates to orchestrator.main() | `orchestrator.main` - Canonical pipeline entrypoint | None |
| `orchestrator.py` | Canonical pipeline entrypoint for dungeon generation, world initialization, and simulation | `argparse` - CLI argument parsing<br>`json` - JSON handling<br>`logging` - Logging framework<br>`os`, `sys` - System operations<br>`time` - Timestamp generation<br>`pathlib.Path` - Filesystem paths<br>`typing.Any` - Type hints<br>`numpy as np` - Numerical arrays<br>`orjson` - Fast JSON serialization<br>`polars as pl` - DataFrame operations<br>`pydantic` - Data validation<br>`scipy.spatial.KDTree` - Spatial indexing<br>`auto.simulation` - Simulation constants and classes<br>`Dungeon` (core, processor, shaper) - Cave generation pipeline<br>`engine.render_lighting.apply_memory_fade` - Lighting effects<br>`skills.utils.numba_warmup` - JIT warmup<br>`utils.game_rng.GameRNG` - Deterministic RNG<br>`utils.shaped_map.load_shaped_map_as_arrays` - Map loading | `DEFAULT_SEED` - int(time.time() * 1000) - Default RNG seed<br>`DEFAULT_MAX_NODES` - 400 - Max nodes in cave graph<br>`DEFAULT_MAX_DEPTH` - 50 - Max depth of cave generation<br>`DEFAULT_CA_ITERATIONS` - 8 - Cellular automata iterations<br>`DEFAULT_OUTPUT_FILE` - "generated_dungeon.arrow" - Output filename<br>`DEFAULT_GRID_SIZE` - 128 - Grid dimensions<br>`-1` - Sentinel value for unassigned node IDs<br>`0.0` - Default height value<br>`200` - Default max simulation turns<br>`50_000` - Max expanded macro characters<br>`10` - Default expansion limit |
| `brainfuck_numba.py` | Numba-accelerated Brainfuck interpreter with sandboxing support | `resource` - Resource limits<br>`time` - Timing operations<br>`dataclasses.dataclass` - Data structures<br>`multiprocessing` (Pipe, get_context, Connection) - Process isolation<br>`typing.Literal` - Type hints<br>`numpy as np` - Array operations<br>`numba.njit` - JIT compilation | `CMD_GT` - 62 (ord('>')) - Move pointer right<br>`CMD_LT` - 60 (ord('<')) - Move pointer left<br>`CMD_PLUS` - 43 (ord('+')) - Increment cell<br>`CMD_MINUS` - 45 (ord('-')) - Decrement cell<br>`CMD_DOT` - 46 (ord('.')) - Output cell<br>`CMD_COMMA` - 44 (ord(',')) - Input to cell<br>`CMD_LBRACKET` - 91 (ord('[')) - Loop start<br>`CMD_RBRACKET` - 93 (ord(']')) - Loop end<br>`_SANDBOX_STEP_THRESHOLD` - 1,000,000 - Steps before sandboxing<br>`_DEFAULT_SANDBOX_CPU_SECONDS` - 1 - CPU time limit<br>`_DEFAULT_SANDBOX_WALL_TIME_S` - 1.0 - Wall time limit<br>`_DEFAULT_SANDBOX_MEMORY_BYTES` - 256 * 1024 * 1024 - Memory limit (256MB)<br>`30_000` - Default tape size<br>`10_000_000` - Default max steps<br>`0xFF` - 255 - Byte mask for cell values<br>`1_000_000` - Max output buffer size |
| `scripting_engine.py` | Script processing, macro expansion, and Brainfuck integration for game commands | `re` - Regular expressions<br>`dataclasses.dataclass` - Data structures<br>`typing` (Literal, Protocol, TypedDict) - Type hints<br>`structlog` - Structured logging<br>`magic.bf_backend` (BFBackend, BFResult, JitBackend, NumbaBackend, PureBackend) - Brainfuck backends | `_MACRO_TOKEN` - Regex `r"!\w+"` - Matches macro tokens<br>`_MACRO_NAME` - Regex `r"^!\w+$"` - Validates macro names<br>`BF_CHARS` - set `"><+-.,[]"` - Valid Brainfuck characters<br>`_MIN_BF_LEN` - 3 - Minimum Brainfuck code length<br>`MAX_MACROS` - 1024 - Maximum number of macros<br>`MAX_DEF_LEN` - 4096 - Maximum macro definition length<br>`30000` - Default tape size for BF<br>`10` - Default macro expansion depth limit<br>`20` - Strict expansion max depth<br>`50_000` - Max expanded character count<br>`4` - Minimum BF characters for auto-detection |
| `pyproject.toml` | Python project configuration for build, dependencies, and development tools | None (TOML configuration file) | `requires-python` - ">=3.11" - Minimum Python version<br>`line-length` - 88 - Max line length for black/ruff<br>`target-version` - py311 - Python version for tools<br>`1.8.0` - Pinned mypy version<br>`24.1.0` - Pinned black version<br>`0.1.14` - Pinned ruff version |
| `requirements.txt` | Frozen pip dependencies (generated from conda environment) | None (dependency list) | None (file lists installed packages with versions) |
| `environment.yml` | Conda environment specification for reproducible setup | None (YAML configuration) | `python` - 3.11 - Python version<br>`numpy` - >=1.24 - Numerical arrays<br>`polars` - >=0.20 - DataFrames<br>`numba` - >=0.57 - JIT compilation<br>And other version specifications |

---

## ai/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `ai/__init__.py` | Empty AI package initialization file | None | None |
| `ai/v9.py` | Agent-based farming simulation core with trait-driven agents, habit system, fatigue/illness/memory management, skill progression, and adaptive planning | `collections` (defaultdict, deque)<br>`collections.abc.Callable`<br>`typing.Any`<br>`numpy as np`<br>`utils.game_rng.GameRNG` | `PLOT_STATUS_MAP` - {"growing": 1, "ready": 2, "empty": 0}<br>`CROPS` - Dict with peas, mushrooms specs (energy: 3.0, nutrients)<br>`WATER_CONTAINERS` - {"pot": {"size": 2.0}}<br>`16.0` - Initial energy<br>`100.0` - Max health<br>`24.0` - Day length<br>`0.5` - Trait variance<br>`0.2` - Habit prune threshold<br>`250` - Behavior memory maxlen<br>`2.0` - Endurance base<br>`3.0` - Critical nutrients<br>Many trait multipliers and thresholds |

---

## auto/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `auto/__init__.py` | Empty module initialization | None | None |
| `auto/goap_engine.py` | GOAP (Goal-Oriented Action Planning) with A* pathfinding for action sequences | `heapq`, `time`, `typing`, `collections` (defaultdict, deque) | `HEALTHY` - 60 (health threshold)<br>`CRITICAL` - 30 (health threshold)<br>`STARVATION` - 0<br>`ENEMY_FLEE` - 8 (distance)<br>`ACTION_WEIGHT_MIN` - 0.1<br>`ACTION_WEIGHT_MAX` - 10.0<br>`SLIME_MOLD_RECOVERY` - 40.0<br>`HEALTH_POTION_RECOVERY` - 50.0<br>`ATTACK_HUNGER` - 0.05<br>`LEARNING_RATE` - 0.15<br>`BASELINE_SCORE` - 0.6<br>`TIMEOUT` - 0.1s<br>`START_HEALTH/HUNGER` - 100.0 |
| `auto/gui/__init__.py` | Empty GUI subpackage initialization | None | None |
| `auto/gui/gui_widgets.py` | PySide6 widgets for ASCII grid view, action weights table, and planning display | `PySide6.QtCore` (Qt, Slot)<br>`PySide6.QtGui.QFont`<br>`PySide6.QtWidgets` (many widget classes) | Char map: "@"=agent, "E"=enemy, "*"=food, "."=empty<br>Color map: blue, red, lime, #555555<br>Font size: 10pt<br>Min window: 300×300 |
| `auto/gui/main_window.py` | Main GUI window with toolbar, docks, and simulation threading | `logging`<br>`PySide6` (Qt, QThread, widgets)<br>`..simulation` (constants, classes)<br>`.gui_widgets`, `.worker` | Speed range: 50-2000ms, default 200ms<br>Window: (100,100), 1200×700<br>Status timeout: 5000ms<br>Thread stop: 1500ms |
| `auto/gui/worker.py` | Simulation worker thread with frame-skipping and pause controls | `time`<br>`PySide6.QtCore` (QMutex, QObject, Signal, Slot)<br>`utils.game_rng.GameRNG`<br>`..simulation` (constants, classes) | Default delay: 200ms<br>Min delay: 10ms<br>Frame skip threshold: 50ms<br>Pause sleep: 0.1s |
| `auto/main.py` | Entry point for GUI and headless modes with multiprocessing | `argparse`, `cProfile`, `io`, `pstats`, `sys`, `time`, `traceback`<br>`collections.Counter`<br>`multiprocessing` (Pool, cpu_count)<br>`utils.game_rng.GameRNG`<br>`.simulation`, `.gui.main_window`<br>`PySide6.QtWidgets.QApplication` | `DEFAULT_NUM_RUNS` - 5<br>`DEFAULT_NUM_WORKERS` - cpu_count()//2<br>`DEFAULT_SEED` - time.time()*1000<br>RNG: "xorshift"<br>Seed range: 0 to 2^32-1<br>Profiler: top 40 functions |
| `auto/simulation.py` | Core simulation with entities, world grid, items, and GOAP AI | `heapq`, `sys`, `typing`, `uuid`<br>`collections` (defaultdict, deque)<br>`utils.game_rng.GameRNG`<br>`polars as pl`<br>`.goap_engine.Action`<br>`numba.njit` (with fallback) | `GRID_SIZE` - 15<br>`START_HEALTH` - 100<br>`START_HUNGER` - 100<br>`SLIME_HEALTH` - 15.0<br>`ENEMY_RANGE` - (40,60)<br>`STARVATION_DMG` - 0.5<br>`PASSIVE_HUNGER` - 0.1<br>`REST_REGEN` - 0.05<br>`BASE_AGENT_DMG` - 5<br>`ENEMY_DMG` - 15<br>`SLIME_DMG` - 5<br>`ENEMY_FLEE` - 0.25<br>`AGENT_MAX` - 5<br>Many more thresholds |

---

## Dungeon/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `Dungeon/core.py` | Core cave/dungeon generation using graph-based backbone algorithm | `json`, `math`, `traceback` - Core libraries<br>`dataclasses` (dataclass, field) - Data structures<br>`typing.Any` - Type hints<br>`numpy as np` - Array operations<br>`scipy.spatial.KDTree` - Spatial indexing<br>`utils.game_rng.GameRNG` - Deterministic RNG | `DEFAULT_INITIAL_PROBABILITY` - 100.0 - Starting branch probability<br>`DEPTH_METERS_PER_LEVEL_RANGE` - (4.0, 6.0) - Depth per level<br>`SEGMENT_LENGTH_RANGE` - (25.0, 35.0) - Segment length in meters<br>`BRANCH_CHECK_INTERVAL` - 4 - Nodes between branch checks<br>`PROBABILITY_DECAY` - 10.0 - Branch probability decay<br>`KDTREE_REBUILD_INTERVAL` - 50 - Nodes between KD-tree rebuilds<br>`DEFAULT_BRANCH_MOMENTUM_BIAS_RATE` - 0.2 - Momentum influence<br>`ANGLE_CLAMP_SINGLE` - (-40.0, 40.0) - Max angle change<br>`ANGLE_CLAMP_BRANCH` - (-45.0, 45.0) - Max branch angle<br>`BRANCH_ANGLE_OFFSET_RANGE` - (30.0, 60.0) - Branch angle offset<br>`LOOPS_ENABLED` - False - Whether loops are allowed<br>`CONVERGENCE_R_MIN` - 5.0 - Min convergence radius<br>`CONVERGENCE_R_MAX` - 20.0 - Max convergence radius<br>`CONVERGENCE_ALPHA` - 0.05 - Convergence probability<br>`CLIFF_FROM_LOW_PROB_CHANCE` - 30.0 - Cliff feature chance<br>`BIG_ROOM_CHANCE` - 15.0 - Large room feature chance<br>`WEIGHT_ADJUST_PERCENT` - 0.20 - 20% weight adjustment<br>Many other generation parameters |
| `Dungeon/processor.py` | Processes backbone graph to add segment geometry, bearing, slope classification | `math` - Math operations<br>`pathlib.Path` - File paths<br>`typing` (Any, Literal) - Type hints<br>`numpy as np` - Array operations<br>`polars as pl` - DataFrame operations | `GRID_RESOLUTION` - 1.0 - Meters per grid cell<br>`STRAIGHT_TURN_ANGLE_THRESHOLD_DEG` - 1.0 - Threshold for straight movement |
| `Dungeon/shaper.py` | Converts processed backbone into shaped cave map using cellular automata | Multiple imports for geometry and processing | Various CA and shaping constants |
| `Dungeon/run.sh` | Shell script to run dungeon generation standalone | None (shell script) | None |

---

## common/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `common/__init__.py` | Package initialization (likely empty or minimal exports) | Unknown (needs viewing) | Unknown |
| `common/constants.py` | Shared material and feature type enumerations | `enum.IntEnum` - Integer enumerations | `SOLID_ROCK` - 0 - Solid rock tile<br>`CAVE_FLOOR` - 1 - Cave floor tile<br>`SHAFT_OPENING` - 2 - Shaft opening tile<br>`CLIFF_EDGE` - 3 - Cliff edge tile<br>`DOOR_CLOSED` - 4 - Closed door<br>`DOOR_OPEN` - 5 - Open door<br>`FLOOR` - 0 - Floor feature<br>`WALL` - 1 - Wall feature<br>`CLOSED_DOOR` - 2 - Closed door feature<br>`OPEN_DOOR` - 3 - Open door feature<br>`SECRET_DOOR` - 4 - Secret door feature |
| `common/types.py` | Type aliases for grid-based systems | `typing.TypeAlias` - Type aliasing | None (only type definitions) |

---

## engine/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `engine/__init__.py` | Empty engine package initialization | None | None |
| `engine/action_handler.py` | Processes player actions (move, pickup, drop, use, equip, attach/detach), handles falling damage and combat | `importlib`, `structlog`<br>Game systems imports (effects, entities, state, movement, death, combat, equipment) | `FALL_DAMAGE_THRESHOLD` - 3 units<br>`FALL_DAMAGE_PER_UNIT_HEIGHT` - 2.0<br>`MAX_FALL_DEPTH` - 20 tiles<br>RGB colors: (255,100,0), (255,0,0), (200,200,200), etc. |
| `engine/glyphs.py` | Manages glyph/tile mappings from YAML with caching and lookup | `pathlib.Path`, `yaml` | None (uses YAML config) |
| `engine/main_loop.py` | Main game loop orchestrating turn processing, actions, and rendering | `numpy`, `structlog`, `PIL.Image`<br>`GameState`, `ZoneManager`, `action_handler`, `renderer`, config classes | None explicit (uses config parameters) |
| `engine/render_base_layers.py` | Prepares base color and glyph arrays for viewport rendering | `numpy`, `structlog`, `GameMap` | Height diff thresholds, viewport slice calculations |
| `engine/render_entities.py` | Renders items, entities, and tiles with Numba optimization | `numpy`, `numba` (with fallback)<br>`NumbaDict` type | `NJIT_SENTINEL_TILE_ARRAY_SHAPE` - (0,0,4)<br>Alpha threshold: 10<br>RGB defaults: 0, Alpha: 255<br>Types: int64, int32, uint8 |
| `engine/render_lighting.py` | Calculates lighting, height visualization, memory fade, colored lights | `math`, `numpy`, `structlog`, `numba`<br>`GameMap`, tile constants, `GameRNG`, light functions | `MEMORY_LEVEL_COUNT` - 5<br>Memory glyph arrays (Unicode ordinals)<br>Epsilon: 1e-6<br>Alpha threshold: 10<br>Intensity: [0.0, 1.0] |
| `engine/renderer.py` | Main rendering orchestrator combining all layers into PIL Image | `dataclasses`, `numpy`, `polars`, `structlog`<br>`PIL.Image/ImageDraw`<br>Various render functions, `numba` | Memory fade color: [128,128,128]<br>Variance: 0.0<br>Noise: 0.0<br>Alpha: 255<br>Enable flags: True<br>Color bounds: [0,255]<br>Min dimensions: 1 pixel |
| `engine/tileset_loader.py` | Loads PNG/SVG tiles, cleans backgrounds, rasterizes SVGs | `io`, `pathlib.Path`, `numpy`, `structlog`<br>`cairosvg.svg2png`, `PIL.Image` | PNG bg color: (21,21,21)<br>SVG error color: (255,0,255,255) magenta<br>Resampling: NEAREST |
| `engine/window_manager.py` | Main GUI window with display, input, rendering, UI state (54KB file) | `json`, `math`, `time`, `pathlib.Path`, `numpy`, `orjson`<br>`PIL.Image`, `PySide6` (Qt), `threading`, `structlog`<br>Config classes, handler modules | `DEFAULT_MIN_TILE_SIZE` - 4<br>`SCROLL_SCALE_DEBOUNCE_MS` - 200<br>`RESIZE_DEBOUNCE_MS` - 100<br>`INITIAL_WINDOW_WIDTH` - 1024<br>`INITIAL_WINDOW_HEIGHT` - 768 |
| `engine/window_manager_modules/__init__.py` | Module initialization (likely empty) | Unknown | Unknown |
| `engine/window_manager_modules/input_handler.py` | Translates keyboard events to actions via keybindings config | `structlog`<br>`PySide6` (QtCore, QtGui, QtWidgets, Qt.Key)<br>`GameState`, `MainLoop`, `WindowManager` | Common key map: "up", "down", etc. to Qt.Key<br>Modifiers: Ctrl, Shift, Alt<br>Action types: move, action, ui |
| `engine/window_manager_modules/tileset_manager.py` | Loads and manages tileset data as Numba-compatible NumPy arrays | `pathlib.Path`, `numpy`, `structlog`<br>`PIL.Image`, `numba`<br>`load_tiles`, `TILE_TYPES` | `SENTINEL_TILE_ARRAY_SHAPE` - (0,0,4)<br>Default FG: (255,255,255)<br>Default BG: (0,0,0)<br>Tile index: 0<br>Resampling: NEAREST |
| `engine/window_manager_modules/ui_overlay_manager.py` | Renders UI overlays from TOML, manages inventory state | `contextlib`, `tomllib`, `pathlib.Path`, `polars`, `structlog`<br>`PIL.Image/ImageDraw/ImageFont`<br>`GameState`, `MainLoop`, `WindowManager` | Overlay types: debug, height_key, inventory, image<br>UI map: dict[int, tuple[int \| None, bool, bool]] |

---

## utils/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `utils/__init__.py` | Empty utils package initialization | None | None |
| `utils/core.py` | Text generation with GameRNG, Markov chains, variety metrics, structured logging | `hashlib`, `json`, `math`, `time`<br>`collections` (defaultdict, deque)<br>`dataclasses`, `enum` (Enum, auto)<br>`pathlib.Path`, `typing`<br>`polars` (optional), `jinja2` (type checking)<br>`utils.game_rng.GameRNG` | Enums: ToneProfile (TERSE, NEUTRAL, ORNATE, WRY), OutputMode<br>`anti_repeat_size` - 50<br>Retry attempts: 5<br>Probability: 0.3<br>Markov order: 2<br>Name length: 4-12<br>Name retries: 10<br>Typing delay: 0.002, jitter: 0.01<br>Lexicon: 15 adjectives, 10 nouns, 10 features, 5 verbs, 4 adverbs, 5 clauses |
| `utils/game_rng.py` | Deterministic RNG with metrics, NumPy integration, thread-safety, JSON serialization | `contextlib`, `json`, `math`, `random`, `threading`, `time`, `uuid`, `warnings`<br>`collections` (OrderedDict, deque)<br>`dataclasses`, `enum` (Enum, auto)<br>`pathlib.Path`, `typing`<br>`numpy` | `_NP_INTEGERS_SUPPORTS_ENDPOINT` - NumPy feature detection<br>`collection_interval` - 1.0s (metrics thread)<br>Metrics defaults: all 0<br>Stats defaults: 0.0, cache_hit_rate: 0.0 |
| `utils/helpers.py` | Dice rolling with Pydantic validation and GameRNG | `structlog`<br>`pydantic` (BaseModel, ValidationError, field_validator)<br>`utils.game_rng.GameRNG` | Default dice: num_dice=1, modifier=0<br>Notation: "d" separator, "+"/"-" modifiers<br>Validation: dice, sides >= 1 |
| `utils/logging_utils.py` | Configures structlog with stdlib, ISO timestamps, colored console | `logging`, `structlog`<br>Processors: add_log_level, add_logger_name, TimeStamper<br>`structlog.dev.ConsoleRenderer` | Default level: INFO<br>Format: "%(message)s", "iso"<br>Flags: colors=True, cache_logger_on_first_use=True |
| `utils/savegame.py` | Deterministic JSON serialization with compression, handles Polars/NumPy/bytes | `base64`, `datetime`, `gzip`, `io`, `itertools`, `sys`<br>`pathlib.Path`, `typing.Any`<br>`numpy`, `orjson`, `polars` | `SchemaVersion = str`<br>`compresslevel` - 6 (gzip)<br>Type markers: __bytes_b64__, __ndarray__, __tuple__<br>Temp suffix: .tmp |
| `utils/shaped_map.py` | Loads Polars IPC maps to NumPy/GameMap with material-to-tile mapping | `collections.abc.Mapping`, `typing.Any`<br>`numpy`, `polars`<br>`common.constants.Material`<br>`game.world.game_map` (constants, GameMap) | `MAX_LOOKUP_MATERIAL_ID` - 100,000<br>Defaults: material_id=0, height=0.0, floor_depth=0.0, chamber_id=-1, tile_id=TILE_ID_WALL, ceiling=0<br>Material map: 6 types (SOLID_ROCK→WALL, CAVE_FLOOR→FLOOR, etc.) |

---

## game/ Directory (Core Modules)