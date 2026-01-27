# auto/simulation.py
# Updated to use GameRNG instance

import heapq
import sys

# Removed 'random' import
import itertools
import typing  # Use typing instead of from typing import ...
import uuid
from collections import defaultdict, deque

# --- Use relative imports for project modules ---
try:
    from utils.game_rng import GameRNG
except ImportError:
    print("Warning: Could not import GameRNG. Using dummy.", file=sys.stderr)

    # Define dummy if needed for standalone testing, but main path needs real one
    class GameRNG:  # type: ignore # noqa
        def get_int(self, a, b):
            return (a + b) // 2

        def choice(self, seq):
            return seq[0] if seq else None

        def shuffle(self, seq):
            pass

        def get_float(self, a=0.0, b=1.0):
            return (a + b) / 2.0


# --- NumPy for potential future use ---
# Use Polars instead of direct numpy for entity state usually
# --- Polars DataFrame Library ---
import polars as pl

from .goap_engine import Action

# --- Numba JIT Compiler ---
try:
    from numba import njit
except ImportError:
    print(
        "Warning: Numba not found, distance calculation will be slower.",
        file=sys.stderr,
    )

    # Dummy decorator if Numba not available
    def njit(func=None, **options):  # type: ignore # noqa
        if func:
            return func
        else:
            return lambda f: f


# --- Type Hinting Aliases (Using modern types where possible) ---
Position = tuple[int, int]
EntityID = str
StateDict = dict[str, typing.Any]  # Keep Any for flexibility initially
# ActionPlan = deque["Action"] # Forward reference string needed if Action defined later
ActionPlan = deque["Action"]  # Use deque with forward reference

# Forward reference for Entity if used before definition
Entity = typing.ForwardRef("Entity")  # If needed, otherwise define Entity first
OptionalEntity = Entity | None
OptionalPosition = Position | None
OptionalPath = list[Position] | None
NearestResult = tuple[EntityID | None, float]
ActionResult = str | None
# Forward reference for Item if needed
Item = typing.ForwardRef("Item")  # If needed
OptionalItem = Item | None

_ID_NAMESPACE: Final[uuid.UUID] = uuid.UUID(int=0)
_ID_COUNTER: Final[itertools.count | None] = None


def _next_deterministic_id(prefix: str) -> str:
    global _ID_COUNTER
    if _ID_COUNTER is None:
        _ID_COUNTER = itertools.count()
    counter = next(_ID_COUNTER)
    name = f"{prefix}-{counter}"
    return str(uuid.uuid5(_ID_NAMESPACE, name))


# --- Item Definitions ---
class Item:
    """Base class for all items."""

    def __init__(self, name: str, kind: str, description: str = "") -> None:
        self.id: str = _next_deterministic_id("item")
        self.name = name
        self.kind = kind
        self.description = description

    def __repr__(self) -> str:
        return f"Item({self.name})"


class Consumable(Item):
    """Items that can be consumed for an effect."""

    def __init__(self, name: str, restores: str, amount: float, description: str = ""):
        super().__init__(name, "consumable", description)
        self.restores = restores
        self.amount = amount


class Weapon(Item):
    """Items that can be equipped to enhance attacks."""

    def __init__(self, name: str, damage: int, description: str = ""):
        super().__init__(name, "weapon", description)
        self.damage = damage


class Utility(Item):
    """Items with other uses (like torches)."""

    def __init__(self, name: str, description: str = ""):
        super().__init__(name, "utility", description)


# Factory functions for items
def create_slime_mold() -> Consumable:
    return Consumable(
        "Slime Mold",
        restores="hunger",
        amount=40.0,
        description="A quivering, edible mold.",
    )


def create_health_potion() -> Consumable:
    return Consumable(
        "Health Potion",
        restores="health",
        amount=50.0,
        description="Restores some health.",
    )


def create_dagger() -> Weapon:
    return Weapon("Dagger", damage=5, description="A simple dagger.")


def create_torch() -> Utility:
    return Utility("Torch", description="Provides light (eventually).")


# --- Configuration Constants ---
GRID_SIZE: int = 15
MAX_TURNS: int = 200
START_HEALTH: float = 100.0
START_HUNGER: float = 100.0
SLIME_MOLD_HUNGER_RECOVERY: float = 40.0
HEALTH_POTION_RECOVERY: float = 50.0
BASE_AGENT_DAMAGE: int = 5
ENEMY_DMG: int = 15
SLIME_HEALTH: float = 15.0  # Use float for consistency
SLIME_DMG: int = 5
ENEMY_START_HEALTH_RANGE: tuple[int, int] = (40, 60)
ENEMY_FLEE_THRESHOLD: float = 0.25
ENEMY_SPAWN_CHANCE: float = 0.02  # Use rng.get_float() < CHANCE instead
# FOOD_RESPAWN_CHANCE: float = 0.10 # Not used currently? Remove if unused
PASSIVE_HUNGER_PER_TURN: float = 0.1
STARVATION_HEALTH_DAMAGE: float = 0.5
ATTACK_HUNGER_COST: float = 0.05
DEFEND_HUNGER_COST: float = 0.05
REST_HEALTH_REGEN: float = 0.05
LOW_HEALTH_FLEE_THRESHOLD: float = START_HEALTH * 0.4
ENEMY_NEARBY_FLEE_DISTANCE: int = 8
HEALTHY_THRESHOLD: float = START_HEALTH * 0.6
CRITICAL_HEALTH_THRESHOLD: float = START_HEALTH * 0.3
PLANNING_TIMEOUT: float = 0.1  # seconds
ACTION_WEIGHT_MIN: float = 0.1
ACTION_WEIGHT_MAX: float = 10.0
LEARNING_RATE_FACTOR: float = 0.15
LEARNING_SCORE_BASELINE: float = 0.6
AGENT_MAX_INVENTORY: int = 5


# --- Helper Functions ---
@njit(cache=True)  # Numba is good for simple math like this
def distance(x1: int, y1: int, x2: int, y2: int) -> int:
    """Calculates Manhattan distance."""
    return abs(x1 - x2) + abs(y1 - y2)


# --- Entity Class ---
class Entity:
    """Represents agents, enemies, or items on the ground."""

    def __init__(
        self,
        x: int,
        y: int,
        kind: str,
        rng: GameRNG,  # Add rng for potential random initialization
        health: float | None = None,
        hunger: float | None = None,
        target: OptionalEntity = None,
        item: OptionalItem = None,  # Use alias
        max_inventory: int | None = None,  # Allow overriding default
    ) -> None:
        self.id: EntityID = _next_deterministic_id(kind)
        self.x: int = x
        self.y: int = y
        self.kind: str = kind
        self.target: OptionalEntity = target
        self.item: OptionalItem = item
        self.inventory: list[Item] = []  # Use modern type hint list[]

        # Set max inventory based on kind or override
        if max_inventory is not None:
            self.max_inventory: int = max_inventory
        else:
            self.max_inventory = AGENT_MAX_INVENTORY if kind == "agent" else 3

        self.equipped_weapon: Weapon | None = None  # Use modern Optional hint

        # --- Health Initialization ---
        if health is None:
            if kind == "agent":
                default_health = START_HEALTH
            elif kind == "enemy":
                # Use rng to determine starting health within range
                default_health = float(rng.get_int(*ENEMY_START_HEALTH_RANGE))
            elif kind == "slime":
                default_health = SLIME_HEALTH  # Already float
            else:  # Items etc.
                default_health = 0.0
            self.health: float = default_health
        else:
            self.health = float(health)

        # --- Hunger Initialization ---
        if hunger is None:
            # Assume relevant entities start full, others have no hunger concept
            self.hunger: float = (
                START_HUNGER if kind in ["agent", "enemy", "slime"] else 0.0
            )
        else:
            self.hunger = float(hunger)

    def get_position(self) -> Position:
        """Returns the entity's (x, y) position tuple."""
        return (self.x, self.y)

    def get_effective_damage(self) -> int:
        """Calculates damage based on equipment or base kind."""
        if self.equipped_weapon:
            return self.equipped_weapon.damage
        elif self.kind == "agent":
            return BASE_AGENT_DAMAGE
        elif self.kind == "enemy":
            return ENEMY_DMG
        elif self.kind == "slime":
            return SLIME_DMG
        return 0  # Items, etc., deal no damage

    def __repr__(self) -> str:
        """Provides a readable string representation of the entity."""
        details = []
        if self.kind in ["agent", "enemy", "slime"]:
            details.append(f"H:{self.health:.1f}")
            details.append(f"U:{self.hunger:.1f}")
        if self.item:
            details.append(f"Item:{self.item.name}")
        if self.equipped_weapon:
            details.append(f"W:{self.equipped_weapon.name}")
        if self.inventory:
            details.append(f"Inv:{len(self.inventory)}/{self.max_inventory}")
        detail_str = ", ".join(details)
        return (
            f"{self.kind.capitalize()}({self.id[:4]} @ ({self.x},{self.y})"
            + (f", {detail_str}" if detail_str else "")
            + ")"
        )


# --- World Class ---
class World:
    """Manages the simulation grid, entities, and game state."""

    def __init__(self, size: int, rng: GameRNG):  # Add rng to init
        if size <= 0:
            raise ValueError("Grid size must be positive.")
        self.size: int = size
        self.rng: GameRNG = rng  # Store RNG instance

        # --- State Attributes ---
        self.grid: list[list[OptionalEntity]] = [
            [None for _ in range(size)] for _ in range(size)
        ]
        self.entities: dict[EntityID, Entity] = {}
        self.entity_df: pl.DataFrame = self._create_empty_entity_df()
        self.entities_by_kind: defaultdict[str, dict[EntityID, Entity]] = defaultdict(
            dict
        )
        self.agent: OptionalEntity = None
        self.turn: int = 0
        self._free_tiles: set[Position] = {
            (x, y) for x in range(size) for y in range(size)
        }

        # --- Constants accessible via instance if needed ---
        self.HUNGER_PER_TURN = PASSIVE_HUNGER_PER_TURN  # Example constant

    def _create_empty_entity_df(self) -> pl.DataFrame:
        """Creates an empty Polars DataFrame with the entity schema."""
        schema = {
            "id": pl.Utf8,
            "x": pl.Int32,
            "y": pl.Int32,
            "kind": pl.Utf8,
            "health": pl.Float32,
            "hunger": pl.Float32,
        }
        # Consider adding 'equipped_weapon_id', 'inventory_count' etc. if useful for queries
        return pl.DataFrame(schema=schema)

    def is_valid(self, x: int, y: int) -> bool:
        """Checks if coordinates are within the grid bounds."""
        return 0 <= x < self.size and 0 <= y < self.size

    def get_entity_at(self, x: int, y: int) -> OptionalEntity:
        """Returns the entity at (x, y), or None if empty or out of bounds."""
        if not self.is_valid(x, y):
            return None
        # Grid access is typically fast for standard lists
        try:
            return self.grid[x][y]  # Grid indexed [x][y] based on initialization
        except IndexError:  # Should not happen if is_valid works
            return None

    def get_entity_object(self, entity_id: EntityID) -> OptionalEntity:
        """Retrieves an entity object by its ID."""
        return self.entities.get(entity_id)

    def add_entity(self, entity: Entity) -> bool:
        """Adds an entity to the world if the position is valid and mostly empty."""
        pos = entity.get_position()
        if not self.is_valid(pos[0], pos[1]):
            print(f"Warning: Cannot add entity {entity.id} outside grid at {pos}.")
            return False

        existing_entity = self.grid[pos[0]][pos[1]]

        # Allow placing items on floor, or agent/enemy displacing items
        can_place = False
        if existing_entity is None:
            can_place = True
        elif existing_entity.kind == "item" and entity.kind != "item":
            # Agent/Enemy overwrites item (item might be picked up later or destroyed)
            print(
                f"Warning: Entity {entity.kind} displacing item {existing_entity.id} at {pos}."
            )
            self.remove_entity(existing_entity)  # Remove the item first
            can_place = True
        elif entity.kind == "item" and existing_entity.kind != "item":
            # Cannot place item on top of agent/enemy
            print(
                "Warning: Cannot place item "
                f"{entity.id} on occupied tile {pos} ({existing_entity.kind})."
            )
            can_place = False
        elif entity.kind == "item" and existing_entity.kind == "item":
            # Allow stacking items? For now, disallow.
            print(
                "Warning: Cannot stack item "
                f"{entity.id} on existing item {existing_entity.id} at {pos}."
            )
            can_place = False
        else:  # Agent/Enemy trying to occupy same space
            can_place = False

        if not can_place:
            print(
                f"Warning: Position {pos} occupied, cannot add {entity.kind} {entity.id}."
            )
            return False

        # Place entity
        self.grid[pos[0]][pos[1]] = entity
        self._free_tiles.discard(pos)  # Remove from free tiles
        self.entities[entity.id] = entity
        self.entities_by_kind[entity.kind][entity.id] = entity

        # Update DataFrame only for non-items (performance)
        if entity.kind != "item":
            # Use compatible dtypes for DataFrame construction
            new_entity_data = {
                "id": [entity.id],
                "x": [entity.x],
                "y": [entity.y],
                "kind": [entity.kind],
                "health": [entity.health],
                "hunger": [entity.hunger],
            }
            try:
                # Ensure schema matches, create new DF safely
                new_df = pl.DataFrame(
                    new_entity_data,
                    schema_overrides={
                        "id": pl.Utf8,
                        "x": pl.Int32,
                        "y": pl.Int32,
                        "kind": pl.Utf8,
                        "health": pl.Float32,
                        "hunger": pl.Float32,
                    },
                )
                # Check if entity_df is empty before concatenating
                if self.entity_df.is_empty():
                    self.entity_df = new_df
                else:
                    self.entity_df = pl.concat([self.entity_df, new_df], how="vertical")
            except Exception as e:
                print(f"Error updating Polars DataFrame: {e}")
                # Potentially fallback or log error, but proceed with adding to dicts/grid

        # Assign agent reference if applicable
        if entity.kind == "agent":
            self.agent = entity

        return True

    def remove_entity(self, entity: Entity):
        """Removes an entity from the world state."""
        entity_id = entity.id
        if entity_id in self.entities:
            pos = self.entities[entity_id].get_position()
            del self.entities[entity_id]

            # Safely clear grid position
            if self.is_valid(pos[0], pos[1]) and self.grid[pos[0]][pos[1]] == entity:
                self.grid[pos[0]][pos[1]] = None
                self._free_tiles.add(pos)  # Add back to free tiles

            # Remove from kind dict
            self.entities_by_kind[entity.kind].pop(entity_id, None)

            # Remove from DataFrame if not item
            if entity.kind != "item":
                if not self.entity_df.is_empty() and "id" in self.entity_df.columns:
                    self.entity_df = self.entity_df.filter(pl.col("id") != entity_id)

            # Clear agent reference if it's the agent being removed
            if self.agent and entity_id == self.agent.id:
                self.agent = None

    def update_entity_health(self, entity_id: EntityID, new_health: float):
        """Updates entity health in object and DataFrame, clamping values."""
        entity_obj = self.get_entity_object(entity_id)
        if entity_obj is None:
            return

        # Clamp health between 0 and START_HEALTH (or a max_health attribute if exists)
        # Use START_HEALTH as a proxy for max health for now
        clamped_health = max(0.0, min(START_HEALTH, new_health))
        entity_obj.health = clamped_health

        # Update DataFrame if it's not an item
        if entity_obj.kind != "item":
            if not self.entity_df.is_empty() and "id" in self.entity_df.columns:
                self.entity_df = self.entity_df.with_columns(
                    pl.when(pl.col("id") == entity_id)
                    .then(pl.lit(clamped_health, dtype=pl.Float32))
                    .otherwise(pl.col("health"))
                    .alias("health")
                )

    def update_entity_hunger(self, entity_id: EntityID, new_hunger: float):
        """Updates entity hunger in object and DataFrame, clamping values."""
        entity_obj = self.get_entity_object(entity_id)
        if entity_obj is None:
            return

        # Clamp hunger between 0 and START_HUNGER
        clamped_hunger = max(0.0, min(START_HUNGER, new_hunger))
        entity_obj.hunger = clamped_hunger

        # Update DataFrame if relevant kind
        if entity_obj.kind in ["agent", "enemy", "slime"]:
            if not self.entity_df.is_empty() and "id" in self.entity_df.columns:
                self.entity_df = self.entity_df.with_columns(
                    pl.when(pl.col("id") == entity_id)
                    .then(pl.lit(clamped_hunger, dtype=pl.Float32))
                    .otherwise(pl.col("hunger"))
                    .alias("hunger")
                )

    def move_entity(self, entity: Entity, new_x: int, new_y: int) -> bool:
        """Moves an entity to a new position if valid and unoccupied (by non-items)."""
        if entity.kind == "item":
            # Items generally shouldn't move on their own
            return False

        entity_id = entity.id
        current_pos = entity.get_position()

        # Check validity of new position
        if not self.is_valid(new_x, new_y):
            return False

        # Check if target cell is occupied by something other than an item
        target_entity = self.grid[new_x][new_y]
        if target_entity is not None and target_entity.kind != "item":
            return False  # Blocked

        # Check if current position actually holds the entity (consistency check)
        if (
            not self.is_valid(current_pos[0], current_pos[1])
            or self.grid[current_pos[0]][current_pos[1]] != entity
        ):
            # This might indicate a state inconsistency
            print(
                f"Warning: Entity {entity_id} not found at expected position {current_pos}."
            )
            # Allow move anyway if target is clear? Or return False? Let's be strict.
            return False

        # --- Perform Move ---
        # Clear old position
        self.grid[current_pos[0]][current_pos[1]] = None
        self._free_tiles.add(current_pos)

        # If target cell had an item, remove it (entity moves onto it)
        if target_entity is not None and target_entity.kind == "item":
            print(
                "Warning: Entity "
                f"{entity.kind} moving onto item {target_entity.id} at "
                f"({new_x},{new_y}). Item removed."
            )
            self.remove_entity(target_entity)

        # Set new position
        self.grid[new_x][new_y] = entity
        self._free_tiles.discard((new_x, new_y))
        entity.x, entity.y = new_x, new_y

        # Update DataFrame
        if not self.entity_df.is_empty() and "id" in self.entity_df.columns:
            self.entity_df = self.entity_df.with_columns(
                pl.when(pl.col("id") == entity_id)
                .then(pl.lit(new_x, dtype=pl.Int32))
                .otherwise(pl.col("x"))
                .alias("x"),
                pl.when(pl.col("id") == entity_id)
                .then(pl.lit(new_y, dtype=pl.Int32))
                .otherwise(pl.col("y"))
                .alias("y"),
            )
        return True

    def get_entities_by_kind_df(self, kind: str) -> pl.DataFrame:
        """Efficiently gets a DataFrame subset for a specific entity kind."""
        if self.entity_df.is_empty():
            return self._create_empty_entity_df()  # Return empty DF with schema
        # Ensure 'kind' column exists before filtering
        if "kind" in self.entity_df.columns:
            return self.entity_df.filter(pl.col("kind") == kind)
        else:
            print("Warning: 'kind' column not found in entity_df.")
            return self._create_empty_entity_df()

    def get_nearest_entity(  # Unchanged logic, uses Polars/dict lookup
        self,
        source_entity: Entity,
        kind: str,
        max_dist: int | None = None,
    ) -> NearestResult:
        """Finds the nearest entity of a specific kind using Manhattan distance."""
        sx, sy = source_entity.get_position()

        if kind != "item":  # Use Polars for agent/enemy/slime etc.
            target_df = self.get_entities_by_kind_df(kind)
            if target_df.is_empty():
                return None, float("inf")

            # Calculate Manhattan distances efficiently
            distances = (target_df["x"] - sx).abs() + (target_df["y"] - sy).abs()
            target_df_with_dist = target_df.with_columns(distances.alias("dist"))

            # Filter by max_dist if provided
            if max_dist is not None:
                target_df_filtered = target_df_with_dist.filter(
                    pl.col("dist") <= max_dist
                )
                if target_df_filtered.is_empty():
                    return None, float("inf")
                target_df_to_search = target_df_filtered
            else:
                target_df_to_search = target_df_with_dist

            # Find the minimum distance index
            min_dist_idx = target_df_to_search["dist"].arg_min()

            if min_dist_idx is not None:
                # Extract ID and distance using the index
                nearest_row = target_df_to_search.row(min_dist_idx, named=True)
                nearest_id = nearest_row["id"]
                min_distance = nearest_row["dist"]
                return nearest_id, float(min_distance)
            else:
                # Should not happen if df wasn't empty, but handle defensively
                return None, float("inf")

        else:  # Handle items using the dictionary (usually fewer items)
            min_d = float("inf")
            nearest_id = None
            # Safely iterate using .get()
            for entity_id_loop, entity_obj in self.entities_by_kind.get(
                kind, {}
            ).items():
                # Check if it's the source entity itself (e.g., finding nearest *other* item)
                if entity_obj.id == source_entity.id:
                    continue
                d = distance(sx, sy, entity_obj.x, entity_obj.y)
                if d < min_d and (max_dist is None or d <= max_dist):
                    min_d = d
                    nearest_id = entity_id_loop
            return nearest_id, min_d

    def _get_random_free_pos(
        self, rng: GameRNG
    ) -> OptionalPosition:  # Added rng parameter
        """Gets a random free position from the available set."""
        if not self._free_tiles:
            return None
        try:
            # Use rng.choice for deterministic selection from the set
            return rng.choice(list(self._free_tiles))  # Convert set to list for choice
        except IndexError:  # Should not happen if set is not empty
            return None

    def populate_world(  # Added rng parameter
        self,
        rng: GameRNG,
        num_food: int,  # Currently unused, slime mold drops instead
        num_enemies: int,
        num_slimes: int = 3,
        num_items: int = 2,
    ):
        """Populates the world with agent, enemies, and items using RNG."""
        # Place Agent
        agent_start_pos = self._get_random_free_pos(rng)
        if agent_start_pos:
            agent = Entity(
                agent_start_pos[0],
                agent_start_pos[1],
                "agent",
                rng=rng,  # Pass rng
                health=START_HEALTH,
                hunger=START_HUNGER,
            )
            self.add_entity(agent)
        else:
            print("Fatal Error: No space to place agent!")
            # Consider raising an exception here?
            return

        # Place Enemies
        for _ in range(num_enemies):
            pos = self._get_random_free_pos(rng)
            if pos:
                enemy = Entity(
                    pos[0],
                    pos[1],
                    "enemy",
                    rng=rng,  # Pass rng
                    hunger=START_HUNGER,  # Health determined randomly in __init__
                )
                self.add_entity(enemy)

        # Place Slimes
        for _ in range(num_slimes):
            pos = self._get_random_free_pos(rng)
            if pos:
                slime = Entity(
                    pos[0],
                    pos[1],
                    "slime",
                    rng=rng,  # Pass rng
                    health=SLIME_HEALTH,
                    hunger=START_HUNGER,
                )
                self.add_entity(slime)

        # Place Items (Potions, Daggers)
        item_factories = [
            create_health_potion,
            create_dagger,
            create_torch,
        ]  # Example items
        for _ in range(num_items):
            pos = self._get_random_free_pos(rng)
            if pos:
                # Use rng.choice to select item factory
                item_factory = rng.choice(item_factories)
                item_obj = item_factory()
                item_entity = Entity(
                    pos[0], pos[1], "item", rng=rng, item=item_obj
                )  # Pass rng
                self.add_entity(item_entity)

    def reset(  # Added rng parameter
        self,
        rng: GameRNG,
        num_food: int = 0,
        num_enemies: int = 4,
        num_slimes: int = 3,
        num_items: int = 2,
    ):
        """Resets the world state and repopulates it using the provided RNG."""
        self.grid = [[None for _ in range(self.size)] for _ in range(self.size)]
        self.entities = {}
        self.entity_df = self._create_empty_entity_df()
        self.entities_by_kind = defaultdict(dict)
        self.agent = None
        self.turn = 0
        self._free_tiles = {(x, y) for x in range(self.size) for y in range(self.size)}
        # Populate using the provided RNG instance
        self.populate_world(rng, num_food, num_enemies, num_slimes, num_items)

    def spawn_random_enemy(self, rng: GameRNG):  # Added rng parameter
        """Spawns a random enemy (Enemy or Slime) at a free position using RNG."""
        pos = self._get_random_free_pos(rng)
        if pos:
            # Use rng.get_float for chance check
            if rng.get_float() < 0.4:  # 40% chance for Slime
                new_enemy = Entity(
                    pos[0],
                    pos[1],
                    "slime",
                    rng=rng,  # Pass rng
                    health=SLIME_HEALTH,
                    hunger=START_HUNGER,
                )
            else:  # 60% chance for Enemy
                new_enemy = Entity(
                    pos[0],
                    pos[1],
                    "enemy",
                    rng=rng,  # Pass rng
                    hunger=START_HUNGER,  # Health determined randomly in __init__
                )
            self.add_entity(new_enemy)

    def find_path(  # Unchanged logic, does not use random
        self, start_pos: Position, target_pos: Position, max_path_length: int = 20
    ) -> OptionalPath:
        """
        Implements A* pathfinding algorithm.
        Returns a list of positions or None if no path found.
        """
        if not (
            self.is_valid(start_pos[0], start_pos[1])
            and self.is_valid(target_pos[0], target_pos[1])
        ):
            return None
        if start_pos == target_pos:
            return []

        open_set: list[tuple[float, Position]] = []  # Use list as heap
        came_from: dict[Position, Position] = {}
        g_score: dict[Position, float] = defaultdict(lambda: float("inf"))
        f_score: dict[Position, float] = defaultdict(lambda: float("inf"))

        g_score[start_pos] = 0.0
        f_score[start_pos] = float(
            distance(start_pos[0], start_pos[1], target_pos[0], target_pos[1])
        )
        heapq.heappush(open_set, (f_score[start_pos], start_pos))

        path_nodes_explored = 0  # Limit search space

        while open_set and path_nodes_explored < max_path_length * 4:
            path_nodes_explored += 1
            current_f, current_pos = heapq.heappop(open_set)

            # Optimization: If popped node has higher f_score than already found, skip
            if current_f > f_score[current_pos]:
                continue

            if current_pos == target_pos:
                # Reconstruct path
                path: list[Position] = []
                temp = current_pos
                while temp in came_from:
                    path.append(temp)
                    temp = came_from[temp]
                # path.append(start_pos) # Add start if needed, usually excluded
                path.reverse()
                return path  # Path from step after start to target

            # Explore neighbors (4 directions)
            for dx, dy in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
                neighbor_pos = (current_pos[0] + dx, current_pos[1] + dy)

                if not self.is_valid(neighbor_pos[0], neighbor_pos[1]):
                    continue

                neighbor_entity = self.grid[neighbor_pos[0]][neighbor_pos[1]]
                # Check walkability (allow moving onto items)
                if neighbor_entity is not None and neighbor_entity.kind not in [
                    "item",
                    "food",
                ]:
                    continue

                # Cost to move to neighbor is 1
                tentative_g_score = g_score[current_pos] + 1.0

                if tentative_g_score < g_score[neighbor_pos]:
                    # Found a better path
                    came_from[neighbor_pos] = current_pos
                    g_score[neighbor_pos] = tentative_g_score
                    f_score[neighbor_pos] = tentative_g_score + float(
                        distance(
                            neighbor_pos[0],
                            neighbor_pos[1],
                            target_pos[0],
                            target_pos[1],
                        )
                    )
                    heapq.heappush(open_set, (f_score[neighbor_pos], neighbor_pos))

        return None  # No path found


# --- Enemy AI ---
def enemy_act(enemy: Entity, world: World, rng: GameRNG):  # Added rng parameter
    """Basic enemy AI: move towards agent if nearby, attack if adjacent."""
    agent = world.agent
    if not agent or agent.health <= 0:
        return  # Agent is gone or dead

    enemy_pos = enemy.get_position()
    agent_pos = agent.get_position()
    dist_to_agent = distance(enemy_pos[0], enemy_pos[1], agent_pos[0], agent_pos[1])

    # --- Fleeing Logic ---
    # Use a base health reference (e.g., average start health or fixed value)
    max_enemy_health = (
        SLIME_HEALTH
        if enemy.kind == "slime"
        else (ENEMY_START_HEALTH_RANGE[0] + ENEMY_START_HEALTH_RANGE[1]) / 2.0
    )
    should_flee = enemy.health < (max_enemy_health * ENEMY_FLEE_THRESHOLD)

    if should_flee and dist_to_agent < 10:
        # Attempt to move away from the agent
        best_flee_spot: OptionalPosition = None
        max_dist_from_agent = -1.0
        current_dist = float(dist_to_agent)

        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = enemy_pos[0] + dx, enemy_pos[1] + dy
                if world.is_valid(nx, ny):
                    target_entity = world.grid[nx][ny]
                    if target_entity is None or target_entity.kind == "item":
                        dist_from_agent = float(
                            distance(nx, ny, agent_pos[0], agent_pos[1])
                        )
                        if dist_from_agent > max_dist_from_agent:
                            max_dist_from_agent = dist_from_agent
                            best_flee_spot = (nx, ny)

        if best_flee_spot and max_dist_from_agent > current_dist:
            world.move_entity(enemy, best_flee_spot[0], best_flee_spot[1])
            return  # Flee successful
        # If no better spot, might hold position or attack if adjacent

    # --- Attack Logic ---
    if dist_to_agent <= 1:
        damage = enemy.get_effective_damage()
        # Apply damage to agent
        new_agent_health = max(0.0, agent.health - damage)
        world.update_entity_health(agent.id, new_agent_health)
        # Apply hunger cost to agent for defending/being hit
        new_agent_hunger = max(0.0, agent.hunger - DEFEND_HUNGER_COST)
        world.update_entity_hunger(agent.id, new_agent_hunger)
        # print(f"{enemy.kind} attacks Agent for {damage} damage!") # Debug
        return  # Attacked

    # --- Pursue Logic ---
    else:
        # Use pathfinding to move towards agent
        path = world.find_path(enemy_pos, agent_pos)
        if path:  # Check if path exists and is not empty
            next_pos = path[0]
            # Check if next step is valid before moving
            if world.is_valid(next_pos[0], next_pos[1]):
                target_entity = world.grid[next_pos[0]][next_pos[1]]
                if target_entity is None or target_entity.kind == "item":
                    world.move_entity(enemy, next_pos[0], next_pos[1])
                    return  # Moved towards agent
        # If no path or blocked, do nothing (or random move?)
        # Consider adding random movement if idle and agent not visible?
        # if rng.get_float() < 0.2: # 20% chance to move randomly if idle
        #    # Simple random move logic (similar to explore)
        #    pass
