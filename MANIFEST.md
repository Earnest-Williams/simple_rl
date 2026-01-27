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
| `orchestrator.py` | Canonical pipeline entrypoint for dungeon generation, world initialization, and simulation | `argparse` - CLI argument parsing<br>`json` - JSON handling<br>`logging` - Logging framework<br>`os`, `sys` - System operations<br>`pathlib.Path` - Filesystem paths<br>`typing.Any` - Type hints<br>`numpy as np` - Numerical arrays<br>`orjson` - Fast JSON serialization<br>`polars as pl` - DataFrame operations<br>`pydantic` - Data validation<br>`scipy.spatial.KDTree` - Spatial indexing<br>`auto.simulation` - Simulation constants and classes<br>`common.tuning.DEFAULT_GRID_SIZE` - Centralized grid size constant<br>`Dungeon` (core, processor, shaper) - Cave generation pipeline<br>`engine.render_lighting.apply_memory_fade` - Lighting effects<br>`skills.utils.numba_warmup` - JIT warmup<br>`utils.game_rng.GameRNG` - Deterministic RNG<br>`utils.shaped_map.load_shaped_map_as_arrays` - Map loading | `DEFAULT_SEED` - None - CLI-provided seed (uses fallback)<br>`FALLBACK_SEED` - 1 - Deterministic fallback seed<br>`DEFAULT_MAX_NODES` - 400 - Max nodes in cave graph<br>`DEFAULT_MAX_DEPTH` - 50 - Max depth of cave generation<br>`DEFAULT_CA_ITERATIONS` - 8 - Cellular automata iterations<br>`DEFAULT_OUTPUT_FILE` - "generated_dungeon.arrow" - Output filename<br>`DEFAULT_GRID_SIZE` - 128 - Grid dimensions (imported from common.tuning)<br>`-1` - Sentinel value for unassigned node IDs<br>`0.0` - Default height value<br>`200` - Default max simulation turns<br>`50_000` - Max expanded macro characters<br>`10` - Default expansion limit |
| `scripting_engine.py` | Script processing, macro expansion, and Brainfuck integration for game commands | `re` - Regular expressions<br>`dataclasses.dataclass` - Data structures<br>`typing` (Literal, Protocol, TypedDict) - Type hints<br>`structlog` - Structured logging<br>`common.tuning.BF_TAPE_SIZE` - Centralized BF tape size constant<br>`magic.bf_backend` (BFBackend, BFResult, JitBackend, NumbaBackend, PureBackend) - Brainfuck backends | `_MACRO_TOKEN` - Regex `r"!\w+"` - Matches macro tokens<br>`_MACRO_NAME` - Regex `r"^!\w+$"` - Validates macro names<br>`BF_CHARS` - set `"><+-.,[]"` - Valid Brainfuck characters<br>`_MIN_BF_LEN` - 3 - Minimum Brainfuck code length<br>`MAX_MACROS` - 1024 - Maximum number of macros<br>`MAX_DEF_LEN` - 4096 - Maximum macro definition length<br>`BF_TAPE_SIZE` - 30,000 - Imported from common.tuning<br>`10` - Default macro expansion depth limit<br>`20` - Strict expansion max depth<br>`50_000` - Max expanded character count<br>`4` - Minimum BF characters for auto-detection |
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
| `auto/gui/main_window.py` | Main GUI window with toolbar, docks, deterministic RNG injection, and simulation threading | `logging`<br>`PySide6` (Qt, QThread, widgets)<br>`utils.game_rng.GameRNG`<br>`..simulation` (constants, classes)<br>`.gui_widgets`, `.worker` | Speed range: 50-2000ms, default 200ms<br>Window: (100,100), 1200×700<br>Status timeout: 5000ms<br>Thread stop: 1500ms |
| `auto/gui/worker.py` | Simulation worker thread with frame-skipping and pause controls | `time`<br>`PySide6.QtCore` (QMutex, QObject, Signal, Slot)<br>`utils.game_rng.GameRNG`<br>`..simulation` (constants, classes) | Default delay: 200ms<br>Min delay: 10ms<br>Frame skip threshold: 50ms<br>Pause sleep: 0.1s |
| `auto/main.py` | Entry point for GUI and headless modes with multiprocessing | `argparse`, `cProfile`, `io`, `pstats`, `sys`, `time`, `traceback`<br>`collections.Counter`<br>`multiprocessing` (Pool, cpu_count)<br>`utils.game_rng.GameRNG`<br>`.simulation`, `.gui.main_window`<br>`PySide6.QtWidgets.QApplication` | `DEFAULT_NUM_RUNS` - 5<br>`DEFAULT_NUM_WORKERS` - max(1, cpu_count() // 2) - Default worker count<br>`DEFAULT_SEED` - None (CLI-provided)<br>`FALLBACK_SEED` - 1<br>Seed range: 0 to 2^32-1<br>Profiler: top 40 functions |
| `auto/simulation.py` | Core simulation with entities, world grid, items, and GOAP AI | `heapq`, `itertools`, `sys`, `typing`, `uuid`<br>`collections` (defaultdict, deque)<br>`utils.game_rng.GameRNG`<br>`polars as pl`<br>`.goap_engine.Action`<br>`numba.njit` (with fallback) | `GRID_SIZE` - 15<br>`START_HEALTH` - 100<br>`START_HUNGER` - 100<br>`SLIME_HEALTH` - 15.0<br>`ENEMY_RANGE` - (40,60)<br>`STARVATION_DMG` - 0.5<br>`PASSIVE_HUNGER` - 0.1<br>`REST_REGEN` - 0.05<br>`BASE_AGENT_DMG` - 5<br>`ENEMY_DMG` - 15<br>`SLIME_DMG` - 5<br>`ENEMY_FLEE` - 0.25<br>`AGENT_MAX` - 5<br>`_ID_NAMESPACE` - UUID(int=0) - deterministic UUID namespace<br>`_ID_COUNTER` - itertools.count() - deterministic ID counter<br>Many more thresholds |

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
| `common/__init__.py` | Package initialization (empty) | None | None |
| `common/constants.py` | Shared material and feature type enumerations | `enum.IntEnum` - Integer enumerations | `SOLID_ROCK` - 0 - Solid rock tile<br>`CAVE_FLOOR` - 1 - Cave floor tile<br>`SHAFT_OPENING` - 2 - Shaft opening tile<br>`CLIFF_EDGE` - 3 - Cliff edge tile<br>`DOOR_CLOSED` - 4 - Closed door<br>`DOOR_OPEN` - 5 - Open door<br>`FLOOR` - 0 - Floor feature<br>`WALL` - 1 - Wall feature<br>`CLOSED_DOOR` - 2 - Closed door feature<br>`OPEN_DOOR` - 3 - Open door feature<br>`SECRET_DOOR` - 4 - Secret door feature |
| `common/tuning.py` | **Centralized tuning constants** shared across multiple subsystems. Single source of truth for cross-cutting numeric values. | `typing.Final` - Immutable constants | `MEMORY_LEVEL_COUNT` - 5 - Memory fade decay levels<br>`MAX_SKILL_LEVEL` - 27 - DCSS-inspired skill cap<br>`BF_TAPE_SIZE` - 30,000 - Brainfuck tape cells<br>`BF_MAX_STEPS` - 10,000,000 - BF safety limit<br>`GRID_SIZES` - (15,64,100,128,200) - Known grid dimensions<br>`DEFAULT_GRID_SIZE` - 128 - Default dungeon grid |
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
| `engine/render_lighting.py` | Calculates lighting, height visualization, memory fade, colored lights | `math`, `numpy`, `structlog`, `numba`<br>`common.tuning.MEMORY_LEVEL_COUNT` - Centralized memory level count<br>`GameMap`, tile constants, `GameRNG`, light functions | `MEMORY_LEVEL_COUNT` - 5 (imported from common.tuning)<br>Memory glyph arrays: MEMORY_WALL_GLYPHS, MEMORY_FLOOR_GLYPHS (Unicode ordinals)<br>Epsilon: 1e-6<br>Alpha threshold: 10<br>Intensity: [0.0, 1.0] |
| `engine/renderer.py` | Main rendering orchestrator combining all layers into PIL Image | `dataclasses`, `numpy`, `polars`, `structlog`<br>`PIL.Image/ImageDraw`<br>Various render functions, `numba` | Memory fade color: [128,128,128]<br>Variance: 0.0<br>Noise: 0.0<br>Alpha: 255<br>Enable flags: True<br>Color bounds: [0,255]<br>Min dimensions: 1 pixel |
| `engine/tileset_loader.py` | Loads PNG/SVG tiles, cleans backgrounds, rasterizes SVGs | `io`, `pathlib.Path`, `numpy`, `structlog`<br>`cairosvg.svg2png`, `PIL.Image` | PNG bg color: (21,21,21)<br>SVG error color: (255,0,255,255) magenta<br>Resampling: NEAREST |
| `engine/window_manager.py` | Main GUI window with display, input, rendering, UI state (54KB file) | `json`, `math`, `time`, `pathlib.Path`, `numpy`, `orjson`<br>`PIL.Image`, `PySide6` (Qt), `threading`, `structlog`<br>Config classes, handler modules | `DEFAULT_MIN_TILE_SIZE` - 4<br>`SCROLL_SCALE_DEBOUNCE_MS` - 200<br>`RESIZE_DEBOUNCE_MS` - 100<br>`INITIAL_WINDOW_WIDTH` - 1024<br>`INITIAL_WINDOW_HEIGHT` - 768 |
| `engine/window_manager_modules/` | Namespace package (no __init__.py). Contains: input_handler.py, tileset_manager.py, ui_overlay_manager.py | See module rows for imports | See module rows for constants |
| `engine/window_manager_modules/input_handler.py` | Translates keyboard events to actions via keybindings config | `structlog`<br>`PySide6` (QtCore, QtGui, QtWidgets, Qt.Key)<br>`GameState`, `MainLoop`, `WindowManager` | Common key map: "up", "down", etc. to Qt.Key<br>Modifiers: Ctrl, Shift, Alt<br>Action types: move, action, ui |
| `engine/window_manager_modules/tileset_manager.py` | Loads and manages tileset data as Numba-compatible NumPy arrays | `pathlib.Path`, `numpy`, `structlog`<br>`PIL.Image`, `numba`<br>`load_tiles`, `TILE_TYPES` | `SENTINEL_TILE_ARRAY_SHAPE` - (0,0,4)<br>Default FG: (255,255,255)<br>Default BG: (0,0,0)<br>Tile index: 0<br>Resampling: NEAREST |
| `engine/window_manager_modules/ui_overlay_manager.py` | Renders UI overlays from TOML, manages inventory state | `contextlib`, `tomllib`, `pathlib.Path`, `polars`, `structlog`<br>`PIL.Image/ImageDraw/ImageFont`<br>`GameState`, `MainLoop`, `WindowManager` | Overlay types: debug, height_key, inventory, image<br>UI map: dict[int, tuple[int \| None, bool, bool]] |

---

## utils/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `utils/__init__.py` | Empty utils package initialization | None | None |
| `utils/core.py` | Text generation with GameRNG, Markov chains, variety metrics, structured logging | `hashlib`, `json`, `math`, `time`<br>`collections` (defaultdict, deque)<br>`dataclasses`, `enum` (Enum, auto)<br>`pathlib.Path`, `typing`<br>`polars` (optional), `jinja2` (type checking)<br>`utils.game_rng.GameRNG` | Enums: ToneProfile (TERSE, NEUTRAL, ORNATE, WRY), OutputMode<br>`anti_repeat_size` - 50<br>Retry attempts: 5<br>Probability: 0.3<br>Markov order: 2<br>Name length: 4-12<br>Name retries: 10<br>Typing delay: 0.002, jitter: 0.01<br>Lexicon: 15 adjectives, 10 nouns, 10 features, 5 verbs, 4 adverbs, 5 clauses |
| `utils/game_rng.py` | Deterministic RNG with metrics, NumPy integration, thread-safety, JSON serialization | `contextlib`, `json`, `math`, `threading`, `time`, `uuid`, `warnings`<br>`collections` (OrderedDict, deque)<br>`dataclasses`, `enum` (Enum, auto)<br>`pathlib.Path`, `typing`<br>`numpy` | `DEFAULT_SEED` - 0 - Deterministic fallback seed<br>`_NP_INTEGERS_SUPPORTS_ENDPOINT` - NumPy feature detection<br>`collection_interval` - 1.0s (metrics thread)<br>Metrics defaults: all 0<br>Stats defaults: 0.0, cache_hit_rate: 0.0 |
| `utils/helpers.py` | Dice rolling with Pydantic validation and GameRNG | `structlog`<br>`pydantic` (BaseModel, ValidationError, field_validator)<br>`utils.game_rng.GameRNG` | Default dice: num_dice=1, modifier=0<br>Notation: "d" separator, "+"/"-" modifiers<br>Validation: dice, sides >= 1 |
| `utils/logging_utils.py` | Configures structlog with stdlib, ISO timestamps, colored console | `logging`, `structlog`<br>Processors: add_log_level, add_logger_name, TimeStamper<br>`structlog.dev.ConsoleRenderer` | Default level: INFO<br>Format: "%(message)s", "iso"<br>Flags: colors=True, cache_logger_on_first_use=True |
| `utils/savegame.py` | Deterministic JSON serialization with compression, handles Polars/NumPy/bytes | `base64`, `datetime`, `gzip`, `io`, `itertools`, `sys`<br>`pathlib.Path`, `typing.Any`<br>`numpy`, `orjson`, `polars` | `SchemaVersion = str`<br>`compresslevel` - 6 (gzip)<br>Type markers: __bytes_b64__, __ndarray__, __tuple__<br>Temp suffix: .tmp |
| `utils/shaped_map.py` | Loads Polars IPC maps to NumPy/GameMap with material-to-tile mapping | `collections.abc.Mapping`, `typing.Any`<br>`numpy`, `polars`<br>`common.constants.Material`<br>`game.world.game_map` (constants, GameMap) | `MAX_LOOKUP_MATERIAL_ID` - 100,000<br>Defaults: material_id=0, height=0.0, floor_depth=0.0, chamber_id=-1, tile_id=TILE_ID_WALL, ceiling=0<br>Material map: 6 types (SOLID_ROCK→WALL, CAVE_FLOOR→FLOOR, etc.) |

---

## game/ Directory (Core Modules)

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/__init__.py` | Empty module initialization | None | None |
| `game/constants.py` | Flow field types for noise/smell propagation and game flow mechanics | `enum.IntEnum`<br>`common.constants.FeatureType` | `FlowType.PASS_DOORS` - 0 (monsters open doors)<br>`FlowType.NO_DOORS` - 1 (monsters blocked)<br>`FlowType.REAL_NOISE` - 2 (dampened by doors)<br>`FlowType.MONSTER_NOISE` - 3 (monster-originated)<br>`MAX_FLOWS` - 4 (enum length) |
| `game/game_state.py` | Central state container managing map, entities, items, AI, perception, sound, turn processing, UI with deterministic AI dispatch wiring | `contextlib`, `heapq`, `structlog`<br>`game.ai.perception.gather_perception`<br>`game.entities.*`<br>`game.items.registry.ItemRegistry`<br>`game.systems.ai_system.dispatch_ai`<br>`game.world.game_map`<br>`simulation.zone_manager.ZoneManager`<br>`utils.game_rng.GameRNG`<br>`game.systems.sound` (optional) | `player_max_fuel` - 100 (max torch fuel)<br>`duration` - 60.0 (default memory fade)<br>`memory_fade_steepness` - 6.0/duration<br>`turn_count` - 0<br>`player_light_index` - 0<br>Combat detection: (fov_radius + 2)²<br>Enemy detection: fov_radius²<br>UI states: "PLAYER_TURN", "INVENTORY_VIEW", "TARGETING" |
| `game/perception.py` | Radius-based perception for noise/scent propagation using Manhattan distance | `numpy as np`<br>`game.world.game_map.GameMap` | Uses Manhattan distance (abs diff) |

---

## game/world/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/world/__init__.py` | Exports line_of_sight function | `from .los import line_of_sight` | None |
| `game/world/fov.py` | Numba-optimized FOV using iterative shadowcasting with height/ceiling checks | `time`, `deque`<br>`numba`, `numpy`, `structlog`<br>`los` - Line of sight | `BASE_THRESHOLD` - 1 (height diff baseline)<br>`CLOSE_RANGE_SQ_THRESHOLD` - 16<br>`CLOSE_RANGE_DIVISOR` - 8<br>`FAR_RANGE_DIVISOR` - 16<br>`_THRESHOLD_AT_CUTOFF` - 2 (16//8)<br>`MAX_SECTORS` - 10000 (safety limit) |
| `game/world/game_map.py` | Core map with tiles, FOV, visibility/exploration tracking, memory fading, height/ceiling | `math`, `dataclass`, `pathlib.Path`<br>`typing` (Final, NamedTuple)<br>`numpy`, `structlog`, `yaml`<br>`tile_id_for`, `update_memory_fade`, `MyVisibility` | `MAX_MEMORY_STRENGTH` - 5.0<br>TILE_ID_FLOOR/WALL computed<br>Default floor: "blank_tile_a", wall: "wall_stone_bricks"<br>Colors: FG (200,200,200)/(180,180,180), BG (10,10,30)/(30,30,50)<br>Memory modifier: 1.0 floor, 2.0 wall |
| `game/world/los.py` | Numba-accelerated Bresenham line-of-sight | `numpy`<br>`numba.njit` (with fallback) | None |
| `game/world/procgen.py` | BSP tree dungeon generation with rooms, corridors, CA caverns, prefab structures | `deque`, `typing.Iterator`, `NamedTuple`<br>`numpy`, `structlog`<br>`GameRNG`, `GameMap`, tile constants | `MIN_LEAF_SIZE` - 6 (BSP minimum)<br>`ROOM_MAX_SIZE_RATIO` - 0.8 (80% of leaf)<br>`ROOM_MIN_SIZE` - 4<br>`MAX_BSP_DEPTH` - 10<br>`DEFAULT_ROOM_CEILING_OFFSET` - 6<br>`DEFAULT_CORRIDOR_CEILING_OFFSET` - 4<br>`fill_prob` - 0.45<br>`wall_count threshold` - 4<br>4 story descriptions |
| `game/world/visibility.py` | Generic FOV calculator using symmetrical shadowcasting via callbacks | `typing.Callable`<br>`abc patterns` | `_multipliers` - 8 tuples for octant transformation<br>Slope calculations: 0.5 offsets |

---

## game/systems/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/systems/__init__.py` | Empty initialization | None | None |
| `game/systems/ai_system.py` | Central AI dispatch selecting adapters with deterministic ordering and optional parallel execution | `collections.abc` (Iterable, Mapping)<br>`multiprocessing.dummy.Pool`<br>`structlog`<br>`game.ai` (get_adapter, goap)<br>`utils.game_rng.GameRNG` | `batch_size` - 4 (default thread pool size) |
| `game/systems/combat_system.py` | Melee attacks, damage, skill bonuses, death checks, XP awards | `polars as pl`, `structlog`<br>Game systems (effects, entities, death, skills)<br>`utils.helpers.roll_dice` | `DEFAULT_UNARMED_DAMAGE` - "1d2"<br>`xp_amount` - 50 (base XP for hit)<br>Weapon type map (axe/mace/polearm/staff/blade/dagger/bow) |
| `game/systems/death_system.py` | Entity death cleanup: inventory drops, loot tables, registry removal, messages | `structlog`<br>`game.game_state.GameState` | None |
| `game/systems/equipment_system.py` | Equipment management with body plans, mount points, slot validation, caching | `contextlib`, `typing.TYPE_CHECKING`<br>`polars as pl`, `structlog`<br>Game components, registries | `EQUIPPED_CACHE` - Global cache instance |
| `game/systems/magic_system_skill_integration.py` | Spell casting integration with skill XP and power bonuses | `skills.effects.get_magic_bonuses_dict`<br>`skills.models.Skill`<br>`skills.system` (award_xp, record_skill_usage) | `base_xp` - spell_level * 10 (10-90 XP)<br>Failed spell: base_xp // 2 |
| `game/systems/movement_system.py` | Entity movement helpers checking bounds, walkability, noise generation | `contextlib`<br>`game.entities.components.Position`<br>`game.systems.sound.handle_event` (dynamic) | `noise_events` - (x, y, 10.0) |
| `game/systems/sound.py` | Sound effects and music with context-aware playback, distance falloff, settings | `contextlib`, `importlib`, `math`, `pathlib.Path`, `typing`<br>`numpy`, `structlog`<br>`game.world.line_of_sight`<br>`pathfinding.perception_systems`<br>`utils.game_rng.GameRNG`<br>`pydub.AudioSegment` (optional)<br>`yaml` (optional) | `SDL_MIXER_FREQUENCY` - 22050 Hz<br>`SDL_MIXER_CHANNELS` - 2 (stereo)<br>`SDL_MIXER_CHUNK_SIZE` - 512 samples<br>`master_volume` - 1.0<br>`sfx_volume` - 1.0<br>`music_volume` - 1.0<br>`max_concurrent_sounds` - 8<br>`sound_fade_distance` - 10<br>`fade_in_time` - 1.0<br>`fade_out_time` - 1.0 |
| `game/systems/pathfinding/flowfield.py` | Flowfield pathfinding with Numba acceleration using integration fields and flow vectors | `heapq`, `time`, `typing.Final`<br>`numpy`, `structlog`<br>`numba` (optional) | `DIRECTIONS_8` - 8 direction array<br>`DIAGONAL_MOVE_COST` - √2 (~1.414)<br>`DEFAULT_HEIGHT_COST_FACTOR` - 0.5<br>`MAX_PATHFIND_DISTANCE` - 50.0<br>Light calc: epsilon 1e-6, intensity [0.0, 1.0] |

---

## game/ai/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/ai/__init__.py` | AI adapter dispatcher mapping types to turn functions, uses ADAPTERS dict with GOAP fallback | `structlog`, `collections.abc.Callable`, `typing.TYPE_CHECKING`<br>Local submodules (bird, community, goap, etc.) | ADAPTERS dict: 10 AI type strings to functions |
| `game/ai/bird.py` | Bird flight with diagonal movement and double-step traversal | `structlog`, `game.systems.movement_system`, `typing`, `numpy`, `GameState`, `GameRNG` | `_DIRECTIONS` - 8-directional (diagonals allowed) |
| `game/ai/community.py` | Player following with pathfinding, noise/scent tracking, random fallback | `structlog`, `numpy`, `polars`<br>`game.systems.movement_system`<br>`FlowFieldPathfinder`, `TILE_TYPES` | `directions` - 4-cardinal<br>`max_traversable_step` - 1 |
| `game/ai/community_adapter.py` | Manages v9 community agents: spawning, trait initialization, state updates, turn stepping | `structlog`, `dataclasses`<br>`ai.v9` (AgentF, Behavior, etc.)<br>`game.systems.movement_system` | Default traits: all 1.0<br>`hp` - 5 * endurance<br>`intelligence` - 2 * (ingenuity + perception + will) |
| `game/ai/goap.py` | GOAP with tiered actions by plan_depth (intelligence): move/attack, cover, coordination | `structlog`, `numpy`, `functools.partial`, `collections.abc.Callable`<br>`game.systems.movement_system`<br>`FlowFieldPathfinder` | `directions` - 4-cardinal<br>`ACTION_TIERS` - 3 complexity levels<br>`max_traversable_step` - 1 |
| `game/ai/goap_adapter.py` | High-level GOAP planner adapter adapting game state to AgentAI | `structlog`, `numpy`, `polars`<br>`auto.goap_engine` (Action, AgentAI)<br>`TILE_TYPES` | None |
| `game/ai/insect.py` | Swarming: moves toward nearest ally or wanders | `structlog`, `polars`, `game.systems.movement_system`, `typing` | `_DIRECTIONS` - 4-cardinal |
| `game/ai/mammal.py` | Pack-hunting: charges player within 5 tiles Manhattan, else wanders | `structlog`, `game.systems.movement_system`, `typing` | `_DIRECTIONS` - 4-cardinal<br>`charge_range` - 5 |
| `game/ai/ml_policy.py` | ML policy stub: random cardinal movement until trained policy | `structlog`, `game.systems.movement_system`, `typing` | `_DIRECTIONS` - 4-cardinal |
| `game/ai/perception.py` | Perception maps: noise (decay 0.6), scent (decay 0.9), LOS, visible enemies | `structlog`, `numpy`, `polars`<br>`game.world.los.line_of_sight` | `noise decay` - 0.6<br>`scent decay` - 0.9<br>`noise radius` - 2<br>`scent radius` - 4 |
| `game/ai/plant.py` | Stationary plant: melee attacks adjacent player | `structlog`<br>`game.systems.combat_system` (lazy)<br>`typing` | `attack_range` - 1 (adjacent) |
| `game/ai/reptile.py` | Ambushing reptile: waits until player within 3 tiles, attacks when adjacent | `structlog`<br>`game.systems` (movement, combat)<br>`typing` | `awareness_range` - 3<br>`attack_range` - 1 |
| `game/ai/simple.py` | Lightweight random walker: one random cardinal direction | `structlog`, `game.systems.movement_system`, `typing` | `_DIRECTIONS` - 4-cardinal |
| `game/ai/strategy.py` | State machine: CHARGE, HOME, FLEE, SMART_KOBOLD (flees <30% HP) | `structlog`, `enum` (Enum, auto)<br>`game.systems.movement_system`<br>`perception.find_visible_enemies`, `typing` | `StrategyState` enum (4 states)<br>`flee_threshold` - 0.3 (30% HP) |

---

## game/entities/, game/items/, game/effects/ Directories

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/entities/__init__.py` | Empty package init | None | None |
| `game/entities/components.py` | ECS-style dataclasses for entity attributes (Position, Renderable, CombatStats, Inventory) | `dataclasses` (dataclass, field) | Uses dataclass defaults |
| `game/entities/registry.py` | Entity management with Polars DataFrames, 44+ components, skills, status effects, body plans | `polars as pl`, `structlog`, `threading.Lock`<br>`skills.models`, `skills.registry_integration` | Max ID: 2³²-1 (UInt32)<br>Default inventory: 26<br>Body plan slots (finger:10, hand:2, etc.) |
| `game/entities/template_registry.py` | Immutable entity template lookup service | `structlog` | None |
| `game/items/__init__.py` | Empty package init | None | None |
| `game/items/registry.py` | Item management with Polars: location (ground/inventory/equipped/attached), slots, properties | `polars as pl`, `structlog`, `typing` (Literal, cast) | Max ID: 2⁶⁴-1 (UInt64)<br>26+ EquipSlot types<br>14 BodySlotType<br>ItemLocation: 4 types |
| `game/effects/__init__.py` | Registers effect handlers with magic executor, adapts legacy signatures | `magic.executor.register_handler`<br>`.handlers.ART_SUBSTANCE_DISPATCHER` | None |
| `game/effects/executor.py` | Effect execution: targeting, cost validation (charge/mana/fullness), condition checks, consumables | `structlog`<br>`.handlers.EFFECT_LOGIC_HANDLERS`<br>`game_state.GameState` | Default cost: 1<br>Cost types: item_charge, mana, fullness |
| `game/effects/handlers.py` | 10+ effect handlers (heal, damage, status, AOE, portals, spawning), registered dispatcher | `polars as pl`, `structlog`<br>`magic.models` (Art, Substance)<br>`utils.game_rng.GameRNG`<br>Game systems | AOE radius: squared distance<br>Damage types: physical, fire, magic<br>Portal glyph: 62<br>Tunnel length: 1 |

---

## game/skills/, game/audio/, game/ui/, game/planning/, game/state/ Directories

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `game/skills/effects.py` | Skill bonuses for combat, defense, magic (damage multipliers, accuracy, armor) | `game.skills.models` (Skill, SkillProgress) | 0.01 (1% dmg/Fighting), 0.02 (2% dmg/weapon, armor), 0.03 (3% armor/Armour), 0.015 (1.5% spell/Spellcasting), 1.5x (stealth), 0.5x (Invocations MP), level//2 & /3 |
| `game/skills/models.py` | 29 skills in 4 categories, training modes, cross-training bonuses | `dataclasses`, `enum` (Enum, auto) | MAX_SKILL_LEVEL - 27<br>Aptitude: -5 to +11<br>Cross-training: 0.25 & 0.20<br>TrainingMode/State enums |
| `game/skills/progression.py` | DCSS-style quadratic scaling, 27-level cap, aptitude modifiers, XP tables | `math`<br>`common.tuning.MAX_SKILL_LEVEL` - Centralized skill level cap | `MAX_SKILL_LEVEL` - 27 (imported from common.tuning)<br>_BASE_XP_TABLE (0-27 → 0-18900)<br>Formula: 25×L×(L+1)<br>Aptitude: 2^(-apt/4) |
| `game/skills/system.py` | High-level API for skill initialization, XP awards, training config | `structlog`<br>`game.skills` (models, training)<br>`typing.TYPE_CHECKING` | Uses functions from progression/training |
| `game/skills/training.py` | XP distribution: manual/automatic modes, focus multipliers, cross-training, auto-disable | `structlog`<br>`game.skills` (models, progression) | 2.0 (focus multiplier)<br>0.1 (10% min share)<br>1.5x (50% focused bonus) |
| `game/audio/music.py` | Procedural music: monophonic motifs with tempo, harmony, intensity | `math`, `struct`, `tempfile`, `wave`, `pathlib` | SAMPLE_RATE - 22050 Hz<br>tempo - 120 BPM<br>harmony - major<br>intensity - 0.5<br>duration - 4.0s<br>Root - 440 Hz (A4)<br>Intervals: 4 (major), 3 (minor) |
| `game/audio/synthesis.py` | Procedural audio synthesis for SFX (footsteps, magic) generating WAV files | `math`, `tempfile`, `wave`, `collections.abc.Callable`<br>`pathlib`, `numpy`, `utils.game_rng.GameRNG` | SAMPLE_RATE - 44100 Hz<br>Footstep: 0.2s, 150Hz, decay 20.0x, noise 0.3/0.2<br>Magic: 0.5s, 880Hz, decay 3.0x |
| `game/ui/skill_screen.py` | Text-based skill UI: levels, XP progress, training config, grouped by category | `skills.models`, `skills.progression`, `typing` | 20 chars (name padding)<br>27 (max level)<br>5250 chars (buffer)<br>Categories: OFFENSIVE, DEFENSIVE, MAGIC, MISCELLANEOUS |
| `game/ui/skill_training_dialog.py` | PySide6 dialog for manual skill training: toggle, focus (2x), target levels | `PySide6` (QtCore, QtGui, QtWidgets)<br>`skills.models`, `skills.system`, `typing` | Window: 900×700px<br>Fonts: Arial 10/9, Courier 9<br>Level cap: 27<br>Focus: 2x<br>Spinbox: 0-27 |
| `game/planning/cache.py` | GOAP plan caching with memoization based on agent/world signatures | `functools.lru_cache` | LRU size - 1024 (maxsize) |
| `game/planning/spatial_hash.py` | Spatial partitioning for entity queries by radius/kind using grid cells | `collections.defaultdict` | Default cell_size - 10 units<br>Stores (entity_id, x, y, kind) tuples |
| `game/state/dirty.py` | Dirty flag tracking for incremental updates (frame, flow_fields) | None | frame - True<br>flow_fields - True<br>Global dirty instance |

---

## magic/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `magic/__init__.py` | Lazy-loaded exports for magic system: Works, MagicLibrary, Wards, execution utils | `annotations`, `TYPE_CHECKING`, `models` (wildcard) | None |
| `magic/bf_backend.py` | Abstract and concrete Brainfuck backends with Numba JIT and pure Python, forwarding deterministic mode | `annotations`, `ABC`, `abstractmethod`, `dataclass`<br>`common.tuning` (BF_TAPE_SIZE, BF_MAX_STEPS) - Centralized BF constants<br>`brainfuck_numba` | `BF_TAPE_SIZE` - 30,000 (imported from common.tuning)<br>`BF_MAX_STEPS` - 10,000,000 (imported from common.tuning) |
| `magic/brainfuck_numba.py` | High-performance BF interpreter with Numba JIT, sandboxing, safety limits, deterministic single-process mode | `resource`, `time`, `multiprocessing`, `numpy`<br>`numba.njit`, `bf_backend.BFResult`<br>`common.tuning` (BF_TAPE_SIZE, BF_MAX_STEPS) - Centralized BF constants | CMD chars (ASCII 43-93)<br>`BF_TAPE_SIZE` - 30,000 (imported from common.tuning)<br>`BF_MAX_STEPS` - 10,000,000 (imported from common.tuning)<br>SANDBOX_STEP_THRESHOLD - 1,000,000<br>SANDBOX_CPU - 1s<br>SANDBOX_WALL_TIME - 1.0s<br>SANDBOX_MEMORY - 256MB<br>Max output - 1,000,000 bytes |
| `magic/executor.py` | Executes Works with Ward/Counterseal checks, friction tracking, effect dispatch | `Callable`, `Iterable`, `dataclass`, `field`, `Literal`, `structlog`<br>`models` (Art, Substance), `wards` | Friction: quiver-10.0, warp-20.0, shiver-30.0, backlash-40.0<br>Fuel drain: 1/2/3/5 by event<br>HP drain: 1 |
| `magic/library.py` | In-memory registry for Works known by entities with learn/research commands | `annotations`, `dataclass` | None |
| `magic/models.py` | Core magic models (Art, Substance, Bounds, Balances, Flow, Seals, Work), AST compiler | `re`, `dataclass`, `field`, `Enum`, `auto` | Art rank max: 20<br>Bounds max: 1,000<br>Balance max: 10,000<br>Flow strength max: 10,000<br>Seal power max: 10,000 |
| `magic/wards.py` | Ward (blocks Works) and Counterseal (allows through) with protocol-based matching | `annotations`, `Iterable`, `dataclass`, `field`, `Protocol` | None |
| `magic/work_parser.py` | Ledger grammar parser converting text to Work AST using pyparsing | `pyparsing` (many parsers)<br>`models` | 9 clause keywords (ART, BOUNDS, etc.) |

---

## pathfinding/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `pathfinding/__init__.py` | Empty initialization | None | None |
| `pathfinding/perception_systems.py` | Noise, smell, perception systems for RL agents with deterministic job control | `logging`, `collections.deque`, `enum.IntEnum`<br>`numpy`, `polars`, `joblib` (Parallel, delayed)<br>`numba.njit`, `common.constants.FeatureType`<br>`common.types`, `game.world.los`, `utils.game_rng.GameRNG` | MAP_HGT/WID - 64<br>BASE_FLOW_CENTER - 100<br>NOISE_STRENGTH - 80<br>NOISE_MAX_DIST - 200<br>SMELL_STRENGTH - 80<br>SCENT_RESET_AGE - 250<br>DEFAULT_NUM_JOBS - 1<br>MAX_FLOWS - 4<br>NEIGHBORS_8 - 8 tuples<br>SCENT_ADJUST_TABLE - 5×5 array [0,1,2,250] |

---

## worldgen/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `worldgen/__init__.py` | World generation orchestrator: topology, elevation, climate, hydrology, chunk extraction, reports | `numpy`, `numba`, `json`, `shutil`, `pathlib`<br>worldgen modules | `_SEA_LEVEL_Q_DEFAULT` - 0 |
| `worldgen/bench.py` | Benchmark tool for world gen at different resolutions | `argparse`, `json`, `time`, `pathlib`<br>`build_full_world`, `WorldConfig` | default N: [4, 8]<br>default seed: 1 |
| `worldgen/chunk_cache.py` | Caching for chunks using SHA256 hash keys | `hashlib`, `pathlib`, `orjson`, `WorldMeta` | None |
| `worldgen/config.py` | World config dataclasses with validation and tunable hashes | `hashlib`, `dataclasses`, `typing`, `orjson`, `constants` | All defaults from constants.py |
| `worldgen/constants.py` | Central configuration: physics parameters, noise settings, tuning values, hash domains | None | ELEV_Q_M - 0.1m<br>ELEVATION_SMOOTH_PASSES - 4<br>ELEVATION_TARGET_OCEAN_FRAC - 0.68<br>ELEVATION_TECTONIC_AMPLITUDE_M - 3500m<br>CLIMATE_T_EQUATOR - 30°C<br>CLIMATE_T_POLE - -20°C<br>CLIMATE_LAPSE_C_PER_KM - 6.0<br>HYDROLOGY_MIN_CATCHMENT_CELLS - 256<br>Hash domains (0x42494F4D, etc.)<br>Many more constants |
| `worldgen/game_rng.py` | Re-exports GameRNG from utils for worldgen | `utils.game_rng.GameRNG` | None |
| `worldgen/hydrology.py` | Water flow networks: D8 priority-flood, topological sort, river ordering | `numpy`, `numba`, `constants`<br>`kernels.heap`, `kernels.union_find`<br>`utils_coord`, `validation` | `_INF_I32` - np.iinfo(np.int32).max |
| `worldgen/io.py` | I/O for numpy arrays as .npy with metadata | `pathlib`, `numpy`, `metadata` | None |
| `worldgen/metadata.py` | World/layer metadata dataclasses with pydantic validators | `json`, `dataclasses`, `pathlib`, `numpy`, `pydantic` | `format_version` - "2.0.0" |
| `worldgen/report.py` | World statistics: land/ocean, temp/precip quantiles, rivers, seams | `pathlib`, `typing`, `numpy`, `orjson`, `constants` | REPORT_SAMPLE_SIZE - 10000<br>REPORT_PERCENTILES_PCT - (5,25,50,75,95)<br>REPORT_QUANTILES - {p5:0.05, etc.} |
| `worldgen/topology_cube_sphere.py` | Cube-sphere topology: indexing, neighbors, position/area for geodesic grid | `numpy`, `numba`, `constants`<br>`kernels.geometry`, `utils_coord` | EDGE_NORTH/EAST/SOUTH/WEST - 0/1/2/3 |
| `worldgen/utils_coord.py` | Coordinate utils: SplitMix64 hashing, cube-sphere conversions, 3D mapping | `numpy`, `numba`, `constants` | HASH_MASK_64, HASH_SPLITMIX_* constants |
| `worldgen/validation.py` | Array validation: dtype/shape/contiguity, NaN/infinity detection | `numpy` | None |
| `worldgen/kernels/__init__.py` | Public API aggregator for kernel functions | From submodules | None |
| `worldgen/kernels/advection.py` | Moisture advection: wind transport, orographic precipitation, capacity clamping | `numpy`, `numba`, `constants` | ELEV_Q_M conversion |
| `worldgen/kernels/erosion.py` | Hydraulic (slope-driven) and thermal (talus angle) erosion | `numpy`, `numba`, `constants` | ELEV_Q_M |
| `worldgen/kernels/geometry.py` | 3D vector math: cross/dot, normalization, spherical triangle area, cell area | `numpy`, `numba` | Normalization threshold: 1e-10 |
| `worldgen/kernels/heap.py` | Numba min-heap: push/pop/decrease_key for Dijkstra | `numpy`, `numba` | None |
| `worldgen/kernels/noise.py` | Perlin-like noise on sphere: SplitMix64 hash, gradient interpolation, fBm | `numpy`, `numba`, `constants` | NOISE_OCTAVE_CONST - 0x9E3779B9<br>Normalization: 1e-10 |
| `worldgen/kernels/smoothing.py` | Neighbor-averaging smoothing (capped diffusion): float32/int32 variants | `numpy`, `numba` | None |
| `worldgen/kernels/union_find.py` | Union-find with path compression and union-by-rank, component extraction | `numpy`, `numba` | None |

---

## lights_dev/, simulation/ Directories

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `lights_dev/constants.py` | Global constants for FOV/light/memory: tile IDs, characters, RGB colors, ANSI codes, decay | `common.tuning.MEMORY_LEVEL_COUNT` - Centralized memory level count | MAX_LOS_DISTANCE - 500<br>WALL_ID - 0, FLOOR_ID - 1, PILLAR_ID - 2<br>MEMORY_DURATION - 60.0<br>MEMORY_SIGMOID_MIDPOINT - 30.0<br>MEMORY_SIGMOID_STEEPNESS - 0.1<br>`MEMORY_LEVEL_COUNT` - 5 (imported from common.tuning)<br>MAX_LIGHT_LEVEL_FOR_VIS_CHECK - 6<br>LIGHT_LEVEL_FALLOFF_RATE - 5<br>Colors: TORCH-(255,160,60), ORB-(160,200,255), AMBIENT-(30,30,45) |
| `lights_dev/dungeon_data.py` | Numba jitclass for dungeon data structure with grid, visibility, memory, time | `math`, `numba`, `numpy`<br>`PILLAR_ID`, `WALL_ID` | dungeon_spec - jitclass fields (width, height, tiles as int8, visible as bool, memory float32, last_seen_time float32) |
| `lights_dev/fov.py` | Numba integer-slope shadowcasting FOV with 8-directional octants, per-tile side bits, angle/cone | `math`, `typing.Final`, `numba`, `numpy`<br>Type imports (boolean, float32, uint8, uint32) | SIDE_N/E/S/W/NE/SE/SW/NW bits (1<<0 through 1<<7)<br>INT - numba.int64<br>_DUMMY_CELL_MASK - empty uint32<br>opacity_threshold - 0.999999 |
| `lights_dev/lighting.py` | Directional lighting with per-side accumulation, height/incidence effects, channel masking, incremental updates | `dataclass`, `typing.Iterable`, `math`, `numba`, `numpy`, `NDArray`<br>`compute_fov_all_octants` | SIDE_N through SIDE_NW - 0-7 indices<br>NUM_SIDES - 8<br>DEFAULT_CHANNEL_MASK - 0xFFFFFFFF |
| `lights_dev/main_game.py` | Main loop for FOV/light/memory simulation with player input, dungeon gen, colored lighting | `logging`, `math`, `os`, `sys`, `time`, `collections.deque`<br>`numba`, `numpy`<br>`compute_fov_all_octants`, `constants`, `dungeon_generator`<br>`Dungeon`, `GameRNG` | Fallback: WALL_ID-0, FLOOR_ID-1, PILLAR_ID-2<br>MAX_LOS_DISTANCE-10<br>MAX_LIGHT_LEVEL_FOR_VIS_CHECK-5 |
| `lights_dev/memory.py` | Numba memory fade with sigmoid decay, agent trait modifiers (intelligence, fatigue, magic), char index | `math`, `dataclass`, `field`, `typing.Final`<br>`numba`, `numpy`, `NDArray`<br>`common.tuning.MEMORY_LEVEL_COUNT` - Centralized memory level count | BASE_MEMORY_DURATION - 90.0<br>BASE_SIGMOID_MIDPOINT - 45.0<br>BASE_SIGMOID_STEEPNESS - ~0.056<br>`MEMORY_LEVEL_COUNT` - 5 (imported from common.tuning)<br>MIN_INTELLIGENCE - 1<br>MAX_INTELLIGENCE - 30<br>BASE_INTELLIGENCE - 10<br>DEFAULT_UPDATE_INTERVAL - 0.1<br>MIN_INTENSITY_THRESHOLD - 0.001<br>_EXP_CLAMP - 70.0 |
| `lights_dev/scent_and_sound_flow.py` | Noise flow propagation, scent stamping, and perception checks for AI sensing | `logging`, `os`, `typing.Final`<br>`numpy`, `polars`, `joblib`<br>`numba`, `NDArray`<br>`FeatureType`, `FlowType`, `MAX_FLOWS`<br>`game.world.los.line_of_sight`, `GameRNG` | BASE_FLOW_CENTER - 100<br>NOISE_STRENGTH - 80<br>NOISE_MAX_DIST - 200<br>SMELL_STRENGTH - 80<br>SCENT_RESET_AGE - 250<br>NEIGHBORS_8 - 8-direction offsets<br>SCENT_ADJUST_TABLE - 5×5 scent stamp table |
| `simulation/__init__.py` | Exports ZoneManager for zone-based simulation | `ZoneManager` | None |
| `simulation/zone_manager.py` | Zone-based simulation scheduler dividing map into zones with per-zone callbacks by proximity | `collections.defaultdict`, `typing.Callable`, `Any` | zone_size - 16 (default)<br>active_radius - 2 (zones around player)<br>passive_interval - 5 (turns between distant updates) |

---

## scripts/ Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `scripts/__init__.py` | Package marker | None | None |
| `scripts/check_pep585.py` | Validates PEP 585 built-in generics usage, fails if violations found | `re`, `sys`, `pathlib.Path`, `typing.Final` | ROOT - Path(".")<br>EXCLUDE_PARTS - {venv, build, dist, .git, __pycache__}<br>PATTERNS - 2 regex patterns |
| `scripts/check_deterministic_random.py` | Scans for disallowed nondeterministic randomness APIs outside GameRNG | `pathlib.Path`, `typing.Final` | DISALLOWED_SNIPPETS - substrings for random/urandom/uuid4<br>EXCLUDED_DIRECTORIES - {legacy, .venv, .git, __pycache__}<br>ALLOWED_FILES - utils/game_rng.py |
| `scripts/cleanup_typing_imports.py` | Removes obsolete typing imports, replaces typing.X with lowercase builtins | `re`, `pathlib.Path`, `typing.Final` | ROOT - Path(".")<br>EXCLUDE - {venv/build dirs}<br>TYPING_NAMES - 8 types (List, Dict, Tuple, Set, FrozenSet, Deque, DefaultDict, OrderedDict)<br>FROM_TYPING_RE & TYPING_DOT_RE - regex patterns |
| `scripts/generate_glyphs.py` | Parses markdown glyph chart, generates glyphs.yaml and glyphs_report.txt with metadata | `yaml`, `re`, `dataclasses`, `pathlib.Path`, `collections.abc.Sequence`, `typing.Final`<br>`glyph_utils.resolve_repo_root` | AMBIGUITY_TOKENS - ("best-effort", etc.)<br>USER_CLARIFIED_TOKENS - ("user clarified", etc.)<br>PLACEHOLDER_TOKENS - {"", "-", "—", "n/a", "na"}<br>PAREN_PATTERN & USER_LABEL_PATTERN - regex |
| `scripts/glyph_utils.py` | Shared utility providing repo root resolution for glyph tooling | `pathlib.Path` | None |
| `scripts/run_auto_regression.py` | Runs GOAP AI headless simulations, outputs JSON summary with stats | `argparse`, `json`, `time`, `collections.Counter`<br>`auto.main`, `auto.simulation`, `utils.game_rng.GameRNG` | num_runs default - 3<br>seed default - 1337<br>max int for seed - 2³²-1 |
| `scripts/find_tuning_dupes.py` | Scans repo for numeric literals matching tuned constants, prints likely duplicates for review | `re`, `sys`, `pathlib.Path`, `typing.Final` | TUNED_VALUES - dict mapping literal patterns to constant names<br>EXCLUDE_PARTS - directories to skip<br>ALLOWED_FILES - source-of-truth files |
| `scripts/sync_llm_policy.py` | Copies canonical `docs/LLM_CRITICAL_RULES.md` into agent-specific locations, supports `--check` for CI | `sys`, `pathlib.Path` | TARGETS - `.codex/AGENTS.md`, `.gemini/styleguide.md`, `CLAUDE.md` |

---

## skills/ (Top-Level) Directory

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `skills/__init__.py` | Package export hub re-exporting 30+ APIs from skill modules | `from __future__`, re-exports from `.models`, `.progression`, `.system` | XP_FORMULA_CONSTANT - 25<br>MAX_SKILL_LEVEL - 27<br>MIN_APTITUDE - -5<br>MAX_APTITUDE - 11 |
| `skills/models.py` | 29-skill IntEnum, training configs, dataclasses with strict typing | `dataclasses`, `enum.IntEnum`, `typing.Final`, `numpy`<br>`common.tuning.MAX_SKILL_LEVEL` - Centralized skill level cap | SKILL_COUNT - 29<br>`MAX_SKILL_LEVEL` - 27 (imported from common.tuning)<br>MIN_APTITUDE - -5<br>MAX_APTITUDE - 11<br>XP_FORMULA_CONSTANT - 25<br>Cross-training: 0.40 (high), 0.25 (medium), 0.10 (low) |
| `skills/constants.py` | Centralized balance tuning: combat, magic, training, manuals | `typing.Final` | Training weights: DISABLED-0.0, NORMAL-1.0, FOCUSED-2.0<br>Cross-training: HIGH-0.40, MEDIUM-0.25, LOW-0.10<br>Combat: FIGHTING_HP_PER_LEVEL-1, WEAPON_DAMAGE_PCT_PER_LEVEL-0.02, ARMOUR_EFFECTIVENESS_PCT_PER_LEVEL-0.03<br>Magic: INVOCATIONS_MP_MULTIPLIER-0.5, SPELL_FAILURE_SKILL_DIVISOR-0.5<br>Manuals: MANUAL_XP_COMMON-150, MANUAL_XP_RARE-300, MANUAL_XP_LEGENDARY-500, MANUAL_APTITUDE_BONUS-4 |
| `skills/progression.py` | XP formula calculations with binary search, Numba-JIT optimized | `numba.njit`, `numpy`, `typing.Final` from `.models` | APTITUDE_MULTIPLIERS - precomputed table<br>MAX_SKILL_LEVEL - 27<br>XP_FORMULA_CONSTANT - 25<br>LEVEL_BREAKPOINTS - (1,3,5,8,10,13,15,18,20,23,25,27) |
| `skills/effects.py` | Numba-compiled combat/magic bonus calculators with batch operations | `numba` (njit, parallel), `numpy`<br>`.models` (CombatBonuses, MagicBonuses, Skill) | fighting_damage-0.01/level, weapon_damage-0.02/level, armour_bonus-0.03/level, stealth_rating-25pts/level, invocations_mp-0.5x spellcasting, intelligence_threshold-8, intelligence_reduction-0.01/pt above 8 |
| `skills/cross_training.py` | Sparse matrix cross-training for related skill bonuses | `scipy.sparse`, `numpy`<br>`.models` (CROSS_TRAINING_PAIRS, Skill) | Uses multipliers from CROSS_TRAINING_PAIRS (0.10, 0.25, 0.40) |
| `skills/milestones.py` | Skill milestone abilities at specific levels with cooldowns | `dataclasses`, `typing.Final` from `.models` (Skill) | 30+ abilities: unlock_levels (10-24), cooldowns (0-200 turns), effect_types (active/passive/toggle) |
| `skills/prerequisites.py` | Skill prerequisite system requiring minimum levels in others | `dataclasses`, `typing.Final` from `.models` (Skill) | Prerequisite minimum_levels: Fighting (2-3), Spellcasting (3-6), Unarmed Combat (4), varying by skill |
| `skills/species_aptitudes.py` | 6 species with custom aptitude tables for all 29 skills | `typing.Final` from `.models` (Skill) | Aptitude range: -4 to +4<br>Species: Human, Troll, Deep Elf, Minotaur, Draconian, Halfling |
| `skills/shapeshifting.py` | 6 beast forms with temporary skill bonuses/penalties | `dataclasses`, `typing.Final`, `typing.Any` from `.models` (Skill) | Form bonuses/penalties (-10 to +8), e.g., Dragon: +5 Fighting, +8 Unarmed, -8 Dodging, -10 Shields |
| `skills/synergies.py` | 14 skill synergy combinations with bonus types and amounts | `dataclasses`, `typing.Final`, `typing.Any` from `.models` (Skill) | 14 synergies: min_level_each (8-15), bonus_amounts (0.10-0.40 multipliers, 3.0-25.0 flat) |
| `skills/registry_integration.py` | Polars DataFrame dual-mode migration layer for EntityRegistry, thread-safe | `polars`, `threading.Lock`, `typing.Final`, `logging` from `.models` | NULL_U8_SENTINEL - 255 (nullable UInt8)<br>Schema: 9 columns (UInt8/32, Int8, Float32) |
| `skills/system.py` | High-level XP distribution API with cross-training, batch operations, thread-safe | `numpy`, `polars`, `contextlib`<br>`.models`, `.progression`, `.cross_training`, `.registry_integration` | Largest-remainder distribution<br>Weights: 0.0 (disabled), 1.0 (normal), 2.0 (focused) |
| `skills/utils.py` | Numba warmup (prevents first-call spikes) and msgpack serialization | `msgpack`, `numpy`, `polars`, `pathlib.Path`, `logging` from `.effects`, `.progression`, `.models` | Test XP values (100-2750), aptitudes (-2 to +2), combat/magic test data<br>File format: skills_table_v1 key |

---

## tests/, tools/, bench/ Directories

| File | Purpose | Imports | Constants/Magic Numbers |
|------|---------|---------|------------------------|
| `tests/test_fov.py` | Unit tests for FOV computation verifying shadowing and visibility | `numpy`, `lights_dev.fov` | Grid sizes: 11, 21, 15<br>Radii: 3, 6, 10, 12<br>Coordinate offsets |
| `tools/fix_fstring_newlines.py` | CLI tool removing newline breaks inside f-strings, reformatting to single lines | `difflib`, `pathlib`, `subprocess`, `sys` | PREFIX_CHARS - {'r','R','b','B','u','U','f','F'} |
| `tools/style/format_and_lint.sh` | **Canonical formatting & linting script** — runs black, ruff, autopep8, isort in correct order. All sub-directory `fix.sh` scripts delegate to this. | bash | Uses pinned versions from `pyproject.toml` |
| `tools/play_from_arrow.py` | Game player for Arrow format maps with CLI/GUI modes, viewport rendering, actions | `argparse`, `inspect`, `sys`, `tomllib`, `pathlib`, `typing`<br>`numpy`, `polars`, `yaml`<br>Game imports (GameState, GameMap, MainLoop, Material) | SPAWN_MIN_ROOM_SIZE - 20<br>SPAWN_SEARCH_RADIUS - 100<br>SPAWN_REQUIRE_DIAGONALS - True<br>Viewport: radius_x=12, radius_y=8<br>Lighting: ambient=0.2, falloff=1.0, min_fov=0.0 |
| `tools/sample_variants.py` | CLI for generating/analyzing text variants from templates with RNG seed replay | `argparse`, `json`, `sys`, `pathlib`<br>`utils.core` (lexicon/RNG/metrics)<br>`utils.game_rng` | Default seed - 12345<br>Default count - 100<br>Default tone - "neutral"<br>4 tone types: terse/neutral/ornate/wry<br>Metrics separator - "=" * 70 |
| `bench/bench_fov.py` | Performance benchmark for FOV computation with random wall obstacles | `time`, `numpy`, `lights_dev.fov`, `utils.game_rng` | WALL_DENSITY_DIVISOR - 10<br>WARMUP_RUNS - 3<br>Defaults: grid 200×200, radius 20, trials 50 |

---

## Configuration and Data Files

| File | Purpose | Format | Key Contents |
|------|---------|--------|-------------|
| `config/config.yaml` | Main game configuration: window size, grid dimensions, rendering settings, FOV parameters | YAML | Window: 1920×1080, grid: 100×100, tile_size: 16px, fov_radius: 10, lighting params |
| `config/settings.toml` | Game settings and preferences | TOML | User preferences and game options |
| `config/keybindings.toml` | Keyboard bindings for game actions and UI commands | TOML | 59 lines of key mappings (movement, inventory, combat, UI) |
| `config/overlays.toml` | UI overlay definitions and layouts | TOML | 33 lines defining overlay types and positions |
| `config/ai_mappings.yaml` | Maps entity AI types to AI adapter functions | YAML | 16 lines mapping AI type strings to function names |
| `config/entities.yaml` | Entity templates: stats, AI, rendering, loot tables | YAML | 35 lines defining creature types and properties |
| `config/items.yaml` | Item definitions: stats, effects, rarity, equipment slots | YAML | 268 lines of item templates (weapons, armor, consumables) |
| `config/effects.yaml` | Spell/effect definitions with costs, damage, targeting | YAML | 40 lines defining magical effects and their properties |
| `config/sounds.yaml` | Sound effect and music definitions with filenames and volumes | YAML | 258 lines mapping game events to audio files |
| `data/items.json` | Runtime item instance data (empty or generated) | JSON | Item instances with locations and states |
| `data/monsters.json` | Runtime monster instance data (empty or generated) | JSON | Monster instances with positions and stats |
| `data/lexica/dungeon_default.json` | Default dungeon vocabulary for procedural text generation | JSON | 63 lines of words/phrases for dungeon descriptions |
| `data/lexica/combat.json` | Combat-related vocabulary for text generation | JSON | 44 lines of combat terms and descriptions |
| `data/lexica/treasure.json` | Treasure and loot vocabulary | JSON | 48 lines of treasure-related words |
| `data/lexica/nature.yaml` | Nature and environment vocabulary | YAML | 81 lines of environmental terms |
| `data/templates/room_templates.json` | Prefab room layouts for dungeon generation | JSON | Room structure definitions |
| `data/templates/jinja_examples.txt` | Example templates for Jinja2 text generation | Text | Template syntax examples |

---

## Documentation Files

| File | Purpose | Contents |
|------|---------|----------|
| `README.md` | Repository main documentation | Project overview, setup instructions, features, architecture notes |
| `AGENTS.md` | LLM and contributor guidelines | Critical engineering rules, Python 3.11+ target, determinism requirements, formatting (black 88-char), static typing (mypy --strict), PEP 585 compliance, tool version pinning, performance primitives (Polars/Numba), constants placement rules, LLM operating rules |
| `CLAUDE.md` | Project-specific LLM style guide | Purpose: LLM-only style rules; Critical rules: Python 3.11+, GameRNG for randomness, black formatting, static typing with PEP 604 unions, Polars (not Pandas), Numba for hot paths, pathlib.Path, pyparsing over regex, structural clarity over OOP, constants placement with Final/immutable types; Tooling: pinned mypy/black/ruff versions, CI consistency; Development workflow, performance guidelines |
| `docs/ARCHITECTURE.md` | Architecture overview with module map, data flows, and documentation index | Cross-references to all module READMEs |
| `docs/ENGINEERING.md` | Engineering rules hub — entry point for all standards, tooling, and tuning constants | Points to canonical files |
| `docs/LLM_CRITICAL_RULES.md` | **Canonical source** for LLM/contributor critical rules — synced to `.codex/AGENTS.md`, `.gemini/styleguide.md`, `CLAUDE.md` via `scripts/sync_llm_policy.py` | Single source of truth for all LLM agent configs |
| `docs/CHANGELOG.md` | Version history and changes | Release notes and feature additions |
| `docs/COMPLIANCE_REPORT.md` | Code compliance and quality metrics | Static analysis results, type coverage, linting status |
| `docs/PERFORMANCE_ANALYSIS.md` | Performance profiling and optimization notes | Benchmarks, bottlenecks, optimization strategies |
| `docs/PHASE_COMPLETION_SUMMARY.md` | Development phase milestones | Project phase completion status |
| `docs/SAVEGAME_IMPROVEMENTS.md` | Save game system documentation | Serialization format, compatibility notes |
| `docs/SKILL_ADVANCED_FEATURES.md` | Advanced skill system features | Milestones, prerequisites, species aptitudes, synergies |
| `docs/SKILL_SYSTEM_ENHANCEMENTS.md` | Skill system enhancement proposals | Proposed features and improvements |
| `docs/SKILL_SYSTEM_EVALUATION.md` | Skill system evaluation and testing | Test results, balance analysis |
| `docs/SKILL_SYSTEM_INTEGRATION.md` | Skill system integration guide | How to integrate skills with other systems |
| `docs/SKILL_TRAINING_CONTROLS.md` | Skill training UI and controls | User interface documentation |
| `docs/SYSTEMS_INVENTORY.md` | Inventory of all game systems | Complete system catalog with dependencies |
| `docs/World_generator_design_proposal.md` | World generation design document | Architecture for world generation system |
| `docs/contributing.md` | Contribution guidelines | How to contribute to the project |
| `docs/mechanism_relevant_lore.md` | Game mechanics and lore | In-game systems explained with narrative context |
| `docs/modding.md` | Modding guide and API documentation | How to create mods and extensions |
| `docs/rendering.md` | Rendering system documentation | Renderer architecture, tile system, lighting |
| `docs/sound_system.md` | Sound system documentation | Audio architecture, event system, music |
| `Dungeon/README.md` | Dungeon generation module documentation | Cave generation algorithm description |
| `ai/README.md` | AI system documentation | Community AI system architecture |
| `auto/README.md` | GOAP AI documentation | Goal-oriented action planning system |
| `pathfinding/README.md` | Pathfinding system documentation | Perception systems and flow fields |
| `lights_dev/README.md` | Lighting development module documentation | FOV, lighting, and memory fade R&D |
| `lights_dev/docs/memory_system.md` | Memory system technical documentation | Memory fade algorithm details |
| `game/skills/README.md` | Game-integrated skill system documentation | Skill system integration notes |
| `utils/README.md` | Utilities module documentation | Helper functions and utilities overview |
| `utils/CORE_README.md` | Core utilities documentation | Core utility function details |
| `skills/README.md` | Top-level skill system documentation | DCSS-inspired skill system complete guide |
| `skills/CONCURRENCY.md` | Skill system concurrency notes | Thread-safety and parallelization |
| `skills/INTEGRATION_GUIDE.md` | Skill system integration guide | Step-by-step integration instructions |
| `skills/skill_system_design.md` | Skill system design document | Architecture and design decisions |
| `notes/basicrl_project.txt` | Basic RL project notes | Development notes and ideas |
| `notes/code_basicrl.txt` | Code notes for basic RL | Implementation details |
| `notes/to implement.txt` | Future implementation todos | Feature wishlist and TODOs |

---

## Shell Scripts

| File | Purpose | Contents |
|------|---------|----------|
| `Dungeon/run.sh` | Runs dungeon generation standalone | Executes dungeon generator with default params |
| `auto/run.sh` | Runs GOAP AI system (headless or GUI mode) | CLI wrapper for auto/main.py |
| `auto/fix.sh` | Stub — delegates to `tools/style/format_and_lint.sh` | Single-line exec to canonical script |
| `pathfinding/fix.sh` | Stub — delegates to `tools/style/format_and_lint.sh` | Single-line exec to canonical script |
| `scripts/fix.sh` | Stub — delegates to `tools/style/format_and_lint.sh` | Single-line exec to canonical script |
| `tools/style/format_and_lint.sh` | **Canonical** formatting & linting pipeline (black, ruff, autopep8, isort) | All sub-directory fix.sh scripts delegate here |
| `scripts/modernize_all.sh` | Modernizes codebase to Python 3.11+ | Runs pyupgrade, cleanup scripts, formatters |
| `scripts/run_cave_demo.sh` | Runs cave generation demo | Executes Dungeon generation pipeline |

---

## Additional Metadata Files

| File | Purpose | Contents |
|------|---------|----------|
| `.gitignore` | Git ignore patterns | Excludes build artifacts, cache, venv, IDE files |
| `.pre-commit-config.yaml` | Pre-commit hooks configuration | Runs formatters and linters on commit |
| `fonts/glyph_name_chart.md` | Glyph name reference chart | Markdown table mapping glyph names to Unicode |
| `fonts/glyphs.yaml` | Glyph definitions for tile rendering | YAML mapping glyph IDs to tile coordinates |
| `fonts/glyphs_report.txt` | Glyph analysis report | Statistics and validation results |
| `fonts/tree.txt` | Font directory structure | Directory listing |
| `fonts/*.png` | Tileset images | PNG tilesets (Cheepicus 12×12, classic_roguelike sliced) |
| `auto/pyproject.toml` | Auto module Python project config | Separate project config for auto/ subsystem |

---

## Project Metadata and Automation

This section documents directories containing engineering guidelines, "Critical Rules", and automation configurations for LLM assistants, CI/CD workflows, and development tools. These directories define the repository's engineering standards referenced throughout documentation like `CLAUDE.md` and `AGENTS.md`.

| Directory/File | Purpose | Contents |
|----------------|---------|----------|
| `.github/` | GitHub-specific configurations and workflows | Contains CI/CD workflows and Copilot instructions |
| `.github/copilot-instructions.md` | GitHub Copilot LLM instructions | Comprehensive guidelines for GitHub Copilot including:<br>- Core principles (Performance, Determinism, Type Safety)<br>- Project structure overview<br>- Component directories documentation<br>- AI systems architecture<br>- Development workflow patterns<br>- Common coding patterns and examples<br>- Security best practices<br>**Critical Rules**: Python 3.11+, GameRNG for randomness, Polars (not Pandas), mypy --strict, pathlib.Path, explicit type annotations |
| `.github/workflows/` | GitHub Actions CI/CD workflows | YAML workflow definitions for automated testing and deployment |
| `.github/workflows/modernize.yml` | Code modernization workflow | Automates codebase updates to maintain modern Python standards |
| `.codex/` | GitHub Codex/OpenAI LLM configuration | Contains engineering rules for OpenAI-based code assistants |
| `.codex/AGENTS.md` | **Auto-generated** copy of `docs/LLM_CRITICAL_RULES.md` for GitHub Codex. Regenerated by `scripts/sync_llm_policy.py`. | All critical engineering rules synced from canonical source |
| `.gemini/` | Google Gemini LLM configuration | Contains style guidelines for Gemini-based code assistants |
| `.gemini/styleguide.md` | **Auto-generated** copy of `docs/LLM_CRITICAL_RULES.md` for Gemini. Regenerated by `scripts/sync_llm_policy.py`. | All critical engineering rules synced from canonical source |

### Key Engineering Standards Defined in Automation Directories

These directories collectively enforce:

1. **Type Safety**: All code must have explicit type annotations, pass `mypy --strict`, use PEP 604 (`X | None`) and PEP 585 (built-in generics)
2. **Determinism**: Use `utils.game_rng.GameRNG` for all randomness; never use Python's `random` or NumPy RNG
3. **Performance**: Prefer Polars (Pandas prohibited), Numba for hot paths, vectorized operations
4. **Code Quality**: Format with `black` (88-char), use `pathlib.Path`, explicit constants with `typing.Final`
5. **Tool Consistency**: Pin mypy, black, ruff versions; CI must match local development environment
6. **LLM Behavior**: Define minimal-diff approach, no API invention, stop when uncertain

---

## Summary Statistics

### Total Files by Type
- **Python files (.py)**: ~200 files
- **Configuration files (.yaml, .toml, .json)**: ~20 files
- **Documentation files (.md, .txt)**: ~30 files
- **Shell scripts (.sh)**: ~7 files
- **Image/font files (.png)**: ~100+ tileset images
- **Other**: pyproject.toml, requirements.txt, environment.yml, .gitignore

### Key Architectural Patterns
- **Deterministic RNG**: `utils.game_rng.GameRNG` used throughout for reproducibility
- **Type Safety**: Full mypy --strict compliance with explicit annotations
- **Performance**: Numba JIT compilation, Polars DataFrames, NumPy arrays
- **Modularity**: Clear separation of concerns (engine/, game/, utils/, skills/)
- **Configuration-Driven**: YAML/TOML configs for items, entities, sounds, keybindings
- **ECS-Inspired**: Component-based entity system with Polars DataFrames

### Major Subsystems
1. **Dungeon Generation**: Multi-stage cave generation (core → processor → shaper)
2. **AI Systems**: GOAP planning, community agents, species-specific behaviors
3. **Skill System**: 29 skills with DCSS-style progression, cross-training, aptitudes
4. **Magic System**: Ledger grammar, Ward/Counterseal blocking, Brainfuck interpreter
5. **World Generation**: Cube-sphere topology, elevation, climate, hydrology
6. **Rendering**: Multi-layer rendering with lighting, FOV, memory fade
7. **Audio**: Procedural synthesis, context-aware sound effects, background music
8. **Pathfinding**: Flow fields, perception systems (noise/scent propagation)

### Common Constants Across Codebase

**Note**: Many cross-cutting constants have been centralized in `common/tuning.py` and `skills/constants.py` to prevent duplication and establish single sources of truth.

**Centralized in `common/tuning.py`:**
- **Grid sizes**: GRID_SIZES = (15, 64, 100, 128, 200), DEFAULT_GRID_SIZE = 128
- **Skill max level**: MAX_SKILL_LEVEL = 27 (DCSS-inspired)
- **Tape size**: BF_TAPE_SIZE = 30,000 (Brainfuck interpreter)
- **Max steps**: BF_MAX_STEPS = 10,000,000 (Brainfuck safety limit)
- **Memory levels**: MEMORY_LEVEL_COUNT = 5 (memory fade decay levels)

**Centralized in `skills/constants.py`:**
- All skill-related balance tuning (combat, magic, training weights, manuals)
- Cross-training multipliers (HIGH=0.40, MEDIUM=0.25, LOW=0.10)
- Combat bonuses (damage per level, accuracy, armor effectiveness)
- Magic bonuses (MP multipliers, spell failure reduction)

**Subsystem-specific constants** (remain in their original modules):
- **Sample rates**: 22050 Hz (music), 44100 Hz (SFX)
- **Memory duration**: 60-90 seconds (memory fade base duration)
- **FOV radius**: Typically 10-20 tiles
- **Health thresholds**: 30 (critical), 60 (healthy), 100 (max)

---

*This manifest was automatically generated and documents all source files, configurations, and data in the Simple RL repository as of 2026-01-27.*
