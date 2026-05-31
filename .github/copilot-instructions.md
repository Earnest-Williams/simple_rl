# GitHub Copilot Instructions for Simple RL

## Project Overview

Simple RL is a simulation-heavy roguelike/RPG research project focused on complex, emergent AI behaviors, procedural generation, and high-performance Python. The project emphasizes determinism, modularity, and efficient data structures.

## Core Principles

### Performance & Efficiency
- **Always** use high-performance libraries: Polars for data manipulation, Numba for JIT compilation on hot paths, NumPy for numerical operations
- **Prefer** vectorized operations over Python loops for data processing
- Use `mmap`, `numpy`, or vectorized operations for anything involving scale
- **Pandas is prohibited** - use Polars instead
- Consider parallelism with Joblib/multiprocessing for CPU-bound tasks

### Determinism
- **Always** use the custom `GameRNG` class for random number generation (import from `utils.game_rng`)
- Never use Python's built-in `random` module or numpy's random functions directly in game logic
- Ensure all stochastic processes are reproducible via RNG state management

### Type Safety
- **All code must have explicit type annotations** - no type inference
- Use PEP 604 syntax: `X | None` instead of `Optional[X]`
- Function signatures must have full annotations, including `-> None` for void functions
- Code must pass `mypy --strict` compliance
- No `Any` types unless absolutely necessary

### Code Style
- Follow PEP 8 and use `black` formatter with 88-character line limit
- Use `pathlib.Path` for all filesystem interactions, never string paths
- f-string expressions must be precomputed into variables if they exceed a single line's clarity
- Avoid regex when possible - prefer `pyparsing` or `pydantic` for structured data parsing
- Minimize object-oriented "clutter" - prefer structural clarity and functional patterns

### Data Modeling
- Use Polars DataFrames for game state and entity modeling
- Use `msgpack` or `orjson` for serialization
- Entity states should be stored in DataFrames for efficient querying and updates

## Project Structure

### Component Directories

- **`Dungeon/`**: Procedural cave generation using multi-stage pipeline (Core Graph → Processing → Shaping). Outputs Polars DataFrames
- **`ai/`**: Community-based NPC AI with social behaviors, needs, traits, and habit learning
- **`auto/`**: Combat/survival AI using Goal-Oriented Action Planning (GOAP) for adventurers and monsters
  - Contains the simulation harness and tuning GUI
  - Main game integration via `game/ai/goap.py`
- **`lights_dev/`**: R&D for lighting, FOV, and memory fade mechanics using Numba
- **`pathfinding/`**: Perception systems (noise propagation, scent tracking) for AI input
- **`game/`**: Main game engine and systems
- **`utils/`**: Shared utilities including `GameRNG` (deterministic RNG)
- **`scripting_engine.py`**: Macro expansion and Brainfuck interpreter for spell system

### Legacy status
- There is no root-level `simple_rl.py` or `dungeon_generator.py` in the current tree.
- There is no `legacy/` directory in the current tree. Use the component entrypoints below and keep stale legacy references out of new docs.

## Development Workflow

### Running Components
- Dungeon generation: `cd Dungeon && ./run.sh`
- GOAP AI (headless): `cd auto && ./run.sh --mode headless`
- GOAP AI (GUI): `cd auto && ./run.sh --mode gui`
- Lighting/FOV development: `cd lights_dev && python main_game.py`
- Main orchestrator: `python main.py`

### Dependencies
- Python 3.11+ required
- Core dependencies in `pyproject.toml`: numpy, polars, numba, scipy, scikit-image, joblib, PySide6, PySDL2, pysdl2-dll
- Install with: `pip install -e .`; use `pip install -e ".[dev]"` for development tooling
- Dev dependencies: mypy, black, ruff

## AI Systems

### Community AI (`ai/v9.py`)
- Manages non-combat NPCs in communities
- Features: trait system, needs management, habit learning, adaptive planning
- Agents learn multi-step behaviors from experience
- Uses `TraitProfile` (Endurance, Ingenuity, Perception, Will, Resonance)
- Plans daily activities based on utility calculations

### GOAP AI (`auto/`)
- Combat-oriented planning for adventurers and hostile NPCs
- Uses A* search over action space to achieve goals
- Actions: MoveTo, Attack, Flee, Pickup, Consume, Equip, Wait, Explore
- Learns action effectiveness over time
- Entity state stored in Polars DataFrame for scalability

## Common Patterns

### Random Number Generation
```python
from utils.game_rng import GameRNG

rng = GameRNG(seed=12345)
value = rng.random()  # uniform [0, 1)
roll = rng.randint(1, 7)  # dice roll
choice = rng.choice(items)  # random selection
```

### Working with Polars
```python
import polars as pl

# Create DataFrame
df = pl.DataFrame({"id": [1, 2, 3], "health": [100, 80, 90]})

# Filter and select
result = df.filter(pl.col("health") > 85).select(["id", "health"])

# Update values efficiently
df = df.with_columns((pl.col("health") - 10).alias("health"))
```

### Type Annotations
```python
from pathlib import Path

def process_data(
    input_path: Path,
    threshold: float,
    max_items: int | None = None
) -> list[dict[str, float]]:
    """Process data from file."""
    results: list[dict[str, float]] = []
    # Implementation
    return results
```

### Using Numba for Performance
```python
from numba import njit
import numpy as np

@njit
def calculate_distances(points: np.ndarray) -> np.ndarray:
    """Fast distance calculation using Numba."""
    n = len(points)
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.sqrt(np.sum((points[i] - points[j]) ** 2))
            distances[i, j] = dist
            distances[j, i] = dist
    return distances
```

## Documentation

- Update relevant `README.md` files in component directories when making changes
- Keep documentation in `docs/` directory up to date
- Follow existing documentation style and structure
- Document complex algorithms and design decisions

## Performance Considerations

- Profile code with `cProfile` when optimizing
- Use Numba `@njit` decorator for numerical loops
- Leverage Polars lazy evaluation for large datasets
- Consider memory-mapping for large files
- Avoid premature optimization - measure first

## Security & Best Practices

- Never commit secrets or credentials
- Validate user input appropriately
- Use type checking to catch errors early
- Write defensive code with proper error handling
- Keep dependencies up to date
- Follow the principle of least privilege

## Common Gotchas

- **Don't** use `pandas` - use `polars` instead
- **Don't** use Python's `random` module - use `GameRNG`
- **Don't** use `Optional[X]` - use `X | None`
- **Don't** omit type annotations - all code must be fully typed
- **Don't** use string paths - use `pathlib.Path`
- **Don't** write slow for-loops over arrays - vectorize or use Numba
- **Don't** forget to format with `black` before committing

## Questions to Ask

When working on this project, consider:
- Does this need to be deterministic? (Use GameRNG)
- Is this performance-critical? (Consider Numba, vectorization, or Polars)
- Are all types explicit and correct?
- Does this follow the project's architectural patterns?
- Is the documentation current?
