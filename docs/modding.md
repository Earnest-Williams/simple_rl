# Modding Guide

Simple RL is designed to load most game content from data files so that new content can be added without touching engine code.  This guide covers how to extend the game by editing configuration files and adding Python modules.

## Configuration driven assets

All core assets live in the `config/` directory and are written in YAML or TOML:

- `config.yaml` – global engine options
- `entities.yaml` – templates for monsters, NPCs and portals
- `items.yaml` – weapon and armor templates
- `effects.yaml` – reusable effect definitions
- `keybindings.toml`, `overlays.toml`, `settings.toml` – user interface and control configuration

The engine loads these files on start, so changes are picked up the next time the game is launched.

## Adding entities

1. Open `config/entities.yaml`.
2. Under the `templates:` section, add a new key for the entity (for example `goblin_chief`).
3. Provide fields such as `glyph`, `color`, `hp`, and `name` mirroring existing examples.
4. Save the file and launch the game or run tests to verify the new entity can be spawned.

## Adding items

1. Edit `config/items.yaml`.
2. Create a new entry inside `templates:` with `name`, `glyph`, `item_type`, and optional `attributes` and `effects`.
3. Use the `flags` list to mark special behavior like `EQUIPPABLE` or `MAGICAL`.  Combat-related flags such as `TWO_HANDED` or `OFF_HAND` influence how weapons are treated during damage calculation.
4. Save the file and load the game to see the new item.

## Adding effects

1. Add a new effect definition to `config/effects.yaml` under `effects:`.
2. Set the `type` (`active` or `triggered`), `target_category`, and `logic_handler`.
3. The `logic_handler` field references a Python function in `game/effects/handlers.py`.
4. Provide any parameters in `params:`; these are passed to the handler at runtime.

## Plugging in new AI

AI behaviors live in different locations depending on their purpose:

* **Production Combat AI**: `game/ai/` folder contains integrated AI systems:
  - `goap.py` - Goal-Oriented Action Planning for combat/survival
  - `strategy.py` - State machine behaviors (HOME, CHARGE, FLEE, SMART_KOBOLD)
  - Specialized behaviors: `bird.py`, `mammal.py`, `insect.py`, `plant.py`, `reptile.py`

* **Community NPC AI (In Development)**: `AI/` folder contains advanced trait-based AI for non-combat NPCs. Not yet integrated with main game.

* **AI Testing Environment**: `auto/` provides a standalone simulation for testing and tuning GOAP behaviors before deploying to production.

### Adding New Combat Behaviors

1. Create a new module in `game/ai/` that implements the desired behavior
2. Implement the behavior interface (typically a function that takes entity state and returns an action)
3. Register the behavior in the AI dispatcher (`game/systems/ai_system.py`)
4. Reference the behavior in entity templates via `entities.yaml`:
   ```yaml
   goblin_chief:
     ai_type: "smart_kobold"
     # ... other properties
   ```

### Integrating GOAP AI

The GOAP planner is already integrated and accessible via `game/ai/goap_adapter.py`:

```python
from game.ai.goap_adapter import plan_for_agent

# Generate a plan for an agent
plan = plan_for_agent(
    game_state=gs,
    entity_id=entity_id
)
```

The adapter translates between game state and GOAP world state automatically.

## Custom generation algorithms

Dungeon generation is managed by the modules in the `Dungeon/` directory. The current production pipeline is a sophisticated 3D-to-2D cave network generator:

* `Dungeon/core.py` - Core graph generation with probabilistic branching
* `Dungeon/processor.py` - Geometry processing and feature flagging
* `Dungeon/shaper.py` - 2D rasterization with cellular automata smoothing

### Adding a New Generator

To introduce a new generation algorithm:

1. Create a new Python module in the `Dungeon/` directory or a separate location
2. Implement the generator following this interface:
   ```python
   def generate_dungeon(width: int, height: int, rng: GameRNG) -> pl.DataFrame:
       """Generate dungeon and return Polars DataFrame.
       
       Required columns:
       - x, y: Coordinates
       - walkable: Boolean
       - floor_depth, ceiling_depth: 3D depth information
       - material_id: Tile type
       - chamber_id: Room/area identifier
       """
       # Your generation logic here
       return dungeon_df
   ```
3. Update the launch code (e.g., `main.py` or `orchestrator.py`) to call your generator
4. Ensure output is compatible with the engine's map loader (`game/world/game_map.py`)

### Important Considerations

* Always use `GameRNG` for deterministic generation (never Python's `random` module)
* Return a Polars DataFrame with the expected schema
* Preserve 3D depth information (floor_depth, ceiling_depth, height)
* Assign unique chamber_id values for connected regions
* Mark special tiles (cliffs, shafts, etc.) with appropriate material_id values

Generators should output data structures compatible with `game/world/game_map.py` so that entities and items can be placed on the resulting map.

## Testing mods

After editing configuration or adding code, run the game's unit tests to ensure nothing regresses:

```bash
pytest
```

Testing early helps catch schema mistakes or Python errors before launching the game.
