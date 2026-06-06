from __future__ import annotations

from typing import Any, Callable
import numpy as np
from numpy.typing import NDArray
import polars as pl
import structlog

from game.entities.components import Position

log = structlog.get_logger()


def _is_list_dtype(dtype: pl.DataType) -> bool:
    """
    Helper function to check if a Polars dtype represents a list type.
    """
    try:
        if isinstance(dtype, pl.List):
            return True
        dtype_str = str(dtype)
        return dtype_str.startswith("List(")
    except Exception:
        return False


NUMERIC_FIELDS = {
    "entity_id": "entity_id",
    "is_active": "is_active",
    "x": "x",
    "y": "y",
    "glyph": "glyph",
    "color_fg_r": "color_fg_r",
    "color_fg_g": "color_fg_g",
    "color_fg_b": "color_fg_b",
    "blocks_movement": "blocks_movement",
    "hp": "hp",
    "max_hp": "max_hp",
    "intelligence": "intelligence",
    "fullness": "fullness",
    "fuel": "fuel",
}

OBJECT_FIELDS = {
    "name": "name",
    "ai_type": "ai_type",
    "species": "species",
    "faction": "faction",
    "strategy_state": "strategy_state",
    "status_effects": "status_effects",
}


class EntityStore:
    def __init__(self, capacity: int = 256):
        self.capacity = capacity
        self.count = 0
        self.dirty_polars_snapshot = True
        self.entity_id_to_index: dict[int, int] = {}

        # Numeric hot fields in NumPy arrays
        self.entity_id = np.zeros(capacity, dtype=np.uint32)
        self.is_active = np.zeros(capacity, dtype=np.bool_)
        self.x = np.zeros(capacity, dtype=np.int16)
        self.y = np.zeros(capacity, dtype=np.int16)
        self.glyph = np.zeros(capacity, dtype=np.uint16)
        self.color_fg_r = np.zeros(capacity, dtype=np.uint8)
        self.color_fg_g = np.zeros(capacity, dtype=np.uint8)
        self.color_fg_b = np.zeros(capacity, dtype=np.uint8)
        self.blocks_movement = np.zeros(capacity, dtype=np.bool_)
        self.hp = np.zeros(capacity, dtype=np.int16)
        self.max_hp = np.zeros(capacity, dtype=np.int16)
        self.intelligence = np.zeros(capacity, dtype=np.int16)
        self.fullness = np.zeros(capacity, dtype=np.float32)
        self.fuel = np.zeros(capacity, dtype=np.float32)

        # Object/string/list fields in Python lists
        self.name: list[str | None] = [None] * capacity
        self.ai_type: list[str | None] = [None] * capacity
        self.species: list[str | None] = [None] * capacity
        self.faction: list[str | None] = [None] * capacity
        self.strategy_state: list[str | None] = [None] * capacity
        self.status_effects: list[list[dict[str, object]]] = [[] for _ in range(capacity)]

        # Fallback dictionary list for all other components not explicitly stored
        self.extra_components: list[dict[str, object]] = [{} for _ in range(capacity)]

        # Occupancy grid
        self.blocking_entity_at = np.full((0, 0), -1, dtype=np.int32)
        self.occupancy_width = 0
        self.occupancy_height = 0

    def _ensure_capacity(self, needed: int) -> None:
        if needed <= self.capacity:
            return
        new_capacity = max(needed, self.capacity * 2)

        def resize_array(arr: np.ndarray, new_cap: int) -> np.ndarray:
            new_arr = np.zeros(new_cap, dtype=arr.dtype)
            new_arr[:len(arr)] = arr
            return new_arr

        # Resize all NumPy arrays
        self.entity_id = resize_array(self.entity_id, new_capacity)
        self.is_active = resize_array(self.is_active, new_capacity)
        self.x = resize_array(self.x, new_capacity)
        self.y = resize_array(self.y, new_capacity)
        self.glyph = resize_array(self.glyph, new_capacity)
        self.color_fg_r = resize_array(self.color_fg_r, new_capacity)
        self.color_fg_g = resize_array(self.color_fg_g, new_capacity)
        self.color_fg_b = resize_array(self.color_fg_b, new_capacity)
        self.blocks_movement = resize_array(self.blocks_movement, new_capacity)
        self.hp = resize_array(self.hp, new_capacity)
        self.max_hp = resize_array(self.max_hp, new_capacity)
        self.intelligence = resize_array(self.intelligence, new_capacity)
        self.fullness = resize_array(self.fullness, new_capacity)
        self.fuel = resize_array(self.fuel, new_capacity)

        # Extend Python lists
        diff = new_capacity - self.capacity
        self.name.extend([None] * diff)
        self.ai_type.extend([None] * diff)
        self.species.extend([None] * diff)
        self.faction.extend([None] * diff)
        self.strategy_state.extend([None] * diff)
        self.status_effects.extend([[] for _ in range(diff)])
        self.extra_components.extend([{} for _ in range(diff)])

        self.capacity = new_capacity

    def create_entity(
        self,
        entity_id: int,
        x: int,
        y: int,
        glyph: int,
        color_fg: tuple[int, int, int],
        name: str,
        blocks_movement: bool = True,
        ai_type: str | None = None,
        species: str | None = None,
        intelligence: int = 1,
        faction: str | None = None,
        strategy_state: str | None = None,
        hp: int = 1,
        max_hp: int = 1,
        fullness: float = 100.0,
        fuel: float = 0.0,
        status_effects: list | None = None,
        **extra,
    ) -> int:
        idx = self.count
        self._ensure_capacity(idx + 1)
        self.count += 1

        self.entity_id[idx] = entity_id
        self.is_active[idx] = True
        self.x[idx] = x
        self.y[idx] = y
        self.glyph[idx] = glyph
        self.color_fg_r[idx] = color_fg[0]
        self.color_fg_g[idx] = color_fg[1]
        self.color_fg_b[idx] = color_fg[2]
        self.blocks_movement[idx] = blocks_movement
        self.hp[idx] = hp
        self.max_hp[idx] = max_hp
        self.intelligence[idx] = intelligence
        self.fullness[idx] = fullness
        self.fuel[idx] = fuel

        self.name[idx] = name
        self.ai_type[idx] = ai_type
        self.species[idx] = species
        self.faction[idx] = faction
        self.strategy_state[idx] = strategy_state
        self.status_effects[idx] = status_effects if status_effects is not None else []

        self.extra_components[idx] = extra
        self.entity_id_to_index[entity_id] = idx

        # Update occupancy if grid initialized
        if self.blocking_entity_at.size and blocks_movement:
            if 0 <= x < self.occupancy_width and 0 <= y < self.occupancy_height:
                self.blocking_entity_at[y, x] = entity_id

        self.dirty_polars_snapshot = True
        return entity_id

    def has_active(self, entity_id: int) -> bool:
        idx = self.entity_id_to_index.get(entity_id)
        if idx is None:
            return False
        return bool(self.is_active[idx])

    def index_of(self, entity_id: int) -> int | None:
        return self.entity_id_to_index.get(entity_id)

    def get_component(self, entity_id: int, component: str) -> object | None:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return None

        if component in NUMERIC_FIELDS:
            val = getattr(self, component)[idx]
            if hasattr(val, "item"):
                return val.item()
            return val

        if component in OBJECT_FIELDS:
            return getattr(self, component)[idx]

        extra = self.extra_components[idx]
        if component not in extra:
            from game.entities.registry import ENTITY_SCHEMA
            dtype = ENTITY_SCHEMA.get(component)
            if dtype is not None:
                if _is_list_dtype(dtype):
                    return []
                elif dtype in (pl.Float32, pl.Float64):
                    return 0.0
                elif dtype in (
                    pl.Int16, pl.Int32, pl.Int64,
                    pl.UInt16, pl.UInt32, pl.UInt64, pl.UInt8
                ):
                    return 0
                elif dtype == pl.Boolean:
                    return False
            return None
        return extra.get(component)

    def set_component(self, entity_id: int, component: str, value: object) -> bool:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return False

        old_blocks = bool(self.blocks_movement[idx])
        if component in NUMERIC_FIELDS:
            getattr(self, component)[idx] = value
        elif component in OBJECT_FIELDS:
            getattr(self, component)[idx] = value
        else:
            self.extra_components[idx][component] = value

        if component == "blocks_movement":
            new_blocks = bool(value)
            if old_blocks != new_blocks:
                x = int(self.x[idx])
                y = int(self.y[idx])
                if 0 <= x < self.occupancy_width and 0 <= y < self.occupancy_height:
                    if new_blocks:
                        self.blocking_entity_at[y, x] = entity_id
                    else:
                        if int(self.blocking_entity_at[y, x]) == entity_id:
                            self.blocking_entity_at[y, x] = -1

        self.dirty_polars_snapshot = True
        return True

    def get_components(self, entity_id: int, components: list[str]) -> dict[str, object]:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return {}

        result = {}
        for component in components:
            if component in NUMERIC_FIELDS:
                val = getattr(self, component)[idx]
                result[component] = val.item() if hasattr(val, "item") else val
            elif component in OBJECT_FIELDS:
                result[component] = getattr(self, component)[idx]
            else:
                result[component] = self.extra_components[idx].get(component)
        return result

    def get_combat_components_bulk(
        self, entity_ids: list[int]
    ) -> tuple[
        dict[int, str | None],  # name
        dict[int, int],  # strength
        dict[int, int],  # defense
        dict[int, int],  # armor
        dict[int, int],  # hp
        dict[int, int],  # max_hp
        dict[int, int],  # x
        dict[int, int],  # y
        dict[int, dict[str, float]],  # resistances
        dict[int, dict[str, float]],  # vulnerabilities
        dict[int, int],  # xp_reward
    ]:
        """Bulk fetch combat-related components for multiple entities.
        
        Returns dictionaries mapping entity_id to component value for efficient
        lookup during combat resolution.
        """
        names: dict[int, str | None] = {}
        strengths: dict[int, int] = {}
        defenses: dict[int, int] = {}
        armors: dict[int, int] = {}
        hps: dict[int, int] = {}
        max_hps: dict[int, int] = {}
        xs: dict[int, int] = {}
        ys: dict[int, int] = {}
        resistances: dict[int, dict[str, float]] = {}
        vulnerabilities: dict[int, dict[str, float]] = {}
        xp_rewards: dict[int, int] = {}

        for entity_id in entity_ids:
            idx = self.index_of(entity_id)
            if idx is None or not self.is_active[idx]:
                continue
            
            eid = int(self.entity_id[idx])
            names[eid] = self.name[idx]
            
            # Get components from extra_components (strength, defense, armor are not in NUMERIC_FIELDS)
            extra = self.extra_components[idx]
            strengths[eid] = int(extra.get("strength", 0))
            defenses[eid] = int(extra.get("defense", 0))
            armors[eid] = int(extra.get("armor", 0))
            
            # Get numeric fields directly from arrays
            hps[eid] = int(self.hp[idx])
            max_hps[eid] = int(self.max_hp[idx])
            xs[eid] = int(self.x[idx])
            ys[eid] = int(self.y[idx])
            
            # Handle other extra components
            resistances[eid] = extra.get("resistances", {})
            vulnerabilities[eid] = extra.get("vulnerabilities", {})
            xp_rewards[eid] = int(extra.get("xp_reward", 0))

        return (
            names, strengths, defenses, armors, hps, max_hps, xs, ys,
            resistances, vulnerabilities, xp_rewards
        )

    def get_position(self, entity_id: int) -> Position | None:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return None
        return Position(int(self.x[idx]), int(self.y[idx]))

    def set_position(self, entity_id: int, position: Position) -> bool:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return False

        old_x = int(self.x[idx])
        old_y = int(self.y[idx])
        new_x = position.x
        new_y = position.y

        if bool(self.blocks_movement[idx]):
            if 0 <= old_x < self.occupancy_width and 0 <= old_y < self.occupancy_height:
                if int(self.blocking_entity_at[old_y, old_x]) == entity_id:
                    self.blocking_entity_at[old_y, old_x] = -1
            if 0 <= new_x < self.occupancy_width and 0 <= new_y < self.occupancy_height:
                self.blocking_entity_at[new_y, new_x] = entity_id

        self.x[idx] = new_x
        self.y[idx] = new_y
        self.dirty_polars_snapshot = True
        return True

    def delete_entity(self, entity_id: int) -> bool:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return False

        if bool(self.blocks_movement[idx]):
            old_x = int(self.x[idx])
            old_y = int(self.y[idx])
            if 0 <= old_x < self.occupancy_width and 0 <= old_y < self.occupancy_height:
                if int(self.blocking_entity_at[old_y, old_x]) == entity_id:
                    self.blocking_entity_at[old_y, old_x] = -1

        self.is_active[idx] = False
        self.dirty_polars_snapshot = True
        return True

    def ensure_occupancy_shape(self, width: int, height: int) -> None:
        if self.blocking_entity_at.shape == (height, width):
            return
        self.blocking_entity_at = np.full((height, width), -1, dtype=np.int32)
        self.occupancy_width = width
        self.occupancy_height = height
        self.rebuild_occupancy()

    def rebuild_occupancy(self) -> None:
        self.blocking_entity_at.fill(-1)
        for idx in range(self.count):
            if not self.is_active[idx]:
                continue
            if not self.blocks_movement[idx]:
                continue
            x = int(self.x[idx])
            y = int(self.y[idx])
            if 0 <= x < self.occupancy_width and 0 <= y < self.occupancy_height:
                self.blocking_entity_at[y, x] = int(self.entity_id[idx])

    def get_blocking_entity_at(self, x: int, y: int) -> int | None:
        if (
            x < 0
            or y < 0
            or x >= self.occupancy_width
            or y >= self.occupancy_height
        ):
            return None
        entity_id = int(self.blocking_entity_at[y, x])
        return None if entity_id < 0 else entity_id

    def try_move_entity(
        self,
        entity_id: int,
        dx: int,
        dy: int,
        *,
        width: int,
        height: int,
        is_walkable: Callable[[int, int], bool],
    ) -> tuple[bool, int, int]:
        idx = self.index_of(entity_id)
        if idx is None or not self.is_active[idx]:
            return False, 0, 0

        old_x = int(self.x[idx])
        old_y = int(self.y[idx])
        dest_x = old_x + dx
        dest_y = old_y + dy

        if not (0 <= dest_x < width and 0 <= dest_y < height):
            return False, dest_x, dest_y

        if not is_walkable(dest_x, dest_y):
            return False, dest_x, dest_y

        if bool(self.blocks_movement[idx]):
            blocking = self.get_blocking_entity_at(dest_x, dest_y)
            if blocking is not None and blocking != entity_id:
                return False, dest_x, dest_y

            if self.blocking_entity_at.shape == (height, width):
                if 0 <= old_x < width and 0 <= old_y < height:
                    if int(self.blocking_entity_at[old_y, old_x]) == entity_id:
                        self.blocking_entity_at[old_y, old_x] = -1
                self.blocking_entity_at[dest_y, dest_x] = entity_id

        self.x[idx] = dest_x
        self.y[idx] = dest_y
        self.dirty_polars_snapshot = True
        return True, dest_x, dest_y

    def active_indices(self) -> np.ndarray:
        return np.where(self.is_active[:self.count])[0]

    def ai_indices(self) -> np.ndarray:
        active = self.is_active[:self.count]
        has_ai = np.array(
            [self.ai_type[idx] is not None for idx in range(self.count)],
            dtype=np.bool_,
        )
        return np.where(active & has_ai)[0]

    def entity_id_at(self, idx: int) -> int:
        return int(self.entity_id[idx])

    def position_at(self, idx: int) -> tuple[int, int]:
        return int(self.x[idx]), int(self.y[idx])

    def kind_at(self, idx: int) -> str:
        species = self.species[idx]
        ai_type = self.ai_type[idx]
        if species == "enemy" or ai_type in {"goap", "combat"}:
            return "enemy"
        if species == "slime":
            return "slime"
        return str(species or ai_type or "entity")

    def row_dict_at(self, idx: int) -> dict[str, object]:
        row: dict[str, object] = {
            "entity_id": int(self.entity_id[idx]),
            "is_active": bool(self.is_active[idx]),
            "x": int(self.x[idx]),
            "y": int(self.y[idx]),
            "glyph": int(self.glyph[idx]),
            "color_fg_r": int(self.color_fg_r[idx]),
            "color_fg_g": int(self.color_fg_g[idx]),
            "color_fg_b": int(self.color_fg_b[idx]),
            "blocks_movement": bool(self.blocks_movement[idx]),
            "hp": int(self.hp[idx]),
            "max_hp": int(self.max_hp[idx]),
            "intelligence": int(self.intelligence[idx]),
            "fullness": float(self.fullness[idx]),
            "fuel": float(self.fuel[idx]),
            "name": self.name[idx],
            "ai_type": self.ai_type[idx],
            "species": self.species[idx],
            "faction": self.faction[idx],
            "strategy_state": self.strategy_state[idx],
            "status_effects": self.status_effects[idx],
        }
        row.update(self.extra_components[idx])
        return row

    def active_non_player_indices(self, player_id: int) -> np.ndarray:
        active = self.is_active[:self.count]
        entity_ids = self.entity_id[:self.count]
        return np.where(active & (entity_ids != player_id))[0]

    def has_perception_profile_at(self, idx: int) -> bool:
        return bool(
            self.ai_type[idx]
            or self.species[idx]
            or int(self.intelligence[idx]) > 0
        )

    def visible_target_at(self, idx: int) -> dict[str, object]:
        target: dict[str, object] = {
            "entity_id": int(self.entity_id[idx]),
            "x": int(self.x[idx]),
            "y": int(self.y[idx]),
        }
        faction = self.faction[idx]
        if faction is not None:
            target["faction"] = faction
        return target

    def faction_at(self, idx: int) -> str | None:
        return self.faction[idx]

    def xy_at(self, idx: int) -> tuple[int, int]:
        return int(self.x[idx]), int(self.y[idx])

    def name_at(self, idx: int) -> str | None:
        return self.name[idx]

    def index_of_entity(self, entity_id: int) -> int | None:
        return self.entity_id_to_index.get(entity_id)

    def is_active_at(self, idx: int) -> bool:
        return bool(self.is_active[idx])

    def get_component_at(self, idx: int, component: str) -> object | None:
        if idx is None or not self.is_active[idx]:
            return None
        if component in NUMERIC_FIELDS:
            val = getattr(self, component)[idx]
            if hasattr(val, "item"):
                return val.item()
            return val
        if component in OBJECT_FIELDS:
            return getattr(self, component)[idx]
        extra = self.extra_components[idx]
        if component not in extra:
            from game.entities.registry import ENTITY_SCHEMA
            dtype = ENTITY_SCHEMA.get(component)
            if dtype is not None:
                if _is_list_dtype(dtype):
                    return []
                elif dtype in (pl.Float32, pl.Float64):
                    return 0.0
                elif dtype in (
                    pl.Int16, pl.Int32, pl.Int64,
                    pl.UInt16, pl.UInt32, pl.UInt64, pl.UInt8
                ):
                    return 0
                elif dtype == pl.Boolean:
                    return False
            return None
        return extra.get(component)

    def monster_perception_records(self, player_id: int) -> list[dict[str, object]]:
        records = []
        for idx in range(self.count):
            if not self.is_active[idx]:
                continue
            entity_id = int(self.entity_id[idx])
            if entity_id == player_id:
                continue

            extra = self.extra_components[idx]
            p_stat = extra.get("perception_stat")
            if p_stat is None:
                p_stat = 10

            is_dead = not self.is_active[idx] or int(self.hp[idx]) <= 0

            records.append({
                "id": entity_id,
                "fy": int(self.y[idx]),
                "fx": int(self.x[idx]),
                "is_dead": bool(is_dead),
                "perception_stat": int(p_stat),
            })
        return records

    def monster_perception_arrays(
        self, player_id: int
    ) -> tuple[NDArray[np.int64], NDArray[np.int64], NDArray[np.int64], NDArray[np.bool_], NDArray[np.int64]]:
        """Return NumPy arrays for monster perception without materializing entities_df.

        Returns (ids, fy, fx, is_dead, perception_stat) arrays for all active
        non-player entities. This is the array-based alternative to
        monster_perception_records() for use in hot paths.
        """
        # Collect indices of active non-player entities
        active_mask = self.is_active[:self.count]
        entity_ids = self.entity_id[:self.count]
        non_player_mask = entity_ids != player_id
        valid_indices = np.where(active_mask & non_player_mask)[0]

        if len(valid_indices) == 0:
            return (
                np.array([], dtype=np.int64),
                np.array([], dtype=np.int64),
                np.array([], dtype=np.int64),
                np.array([], dtype=np.bool_),
                np.array([], dtype=np.int64),
            )

        # Extract arrays
        ids = self.entity_id[valid_indices].astype(np.int64)
        fy = self.y[valid_indices].astype(np.int64)
        fx = self.x[valid_indices].astype(np.int64)

        # Compute is_dead: since valid_indices is already filtered by active_mask,
        # we only need to check hp <= 0
        is_dead = self.hp[valid_indices] <= 0

        # Extract perception_stat with default of 10
        # Single dict lookup per entity for efficiency
        perception_stat = np.array([
            int(self.extra_components[idx].get("perception_stat", 10))
            for idx in valid_indices
        ], dtype=np.int64)

        return ids, fy, fx, is_dead, perception_stat

    def compact_store(self) -> None:
        if self.count == 0:
            return

        active_indices = np.where(self.is_active[:self.count])[0]
        new_count = len(active_indices)

        # Allocate new arrays
        new_entity_id = np.zeros(self.capacity, dtype=np.uint32)
        new_is_active = np.zeros(self.capacity, dtype=np.bool_)
        new_x = np.zeros(self.capacity, dtype=np.int16)
        new_y = np.zeros(self.capacity, dtype=np.int16)
        new_glyph = np.zeros(self.capacity, dtype=np.uint16)
        new_color_fg_r = np.zeros(self.capacity, dtype=np.uint8)
        new_color_fg_g = np.zeros(self.capacity, dtype=np.uint8)
        new_color_fg_b = np.zeros(self.capacity, dtype=np.uint8)
        new_blocks_movement = np.zeros(self.capacity, dtype=np.bool_)
        new_hp = np.zeros(self.capacity, dtype=np.int16)
        new_max_hp = np.zeros(self.capacity, dtype=np.int16)
        new_intelligence = np.zeros(self.capacity, dtype=np.int16)
        new_fullness = np.zeros(self.capacity, dtype=np.float32)
        new_fuel = np.zeros(self.capacity, dtype=np.float32)

        # Copy numeric fields
        new_entity_id[:new_count] = self.entity_id[active_indices]
        new_is_active[:new_count] = self.is_active[active_indices]
        new_x[:new_count] = self.x[active_indices]
        new_y[:new_count] = self.y[active_indices]
        new_glyph[:new_count] = self.glyph[active_indices]
        new_color_fg_r[:new_count] = self.color_fg_r[active_indices]
        new_color_fg_g[:new_count] = self.color_fg_g[active_indices]
        new_color_fg_b[:new_count] = self.color_fg_b[active_indices]
        new_blocks_movement[:new_count] = self.blocks_movement[active_indices]
        new_hp[:new_count] = self.hp[active_indices]
        new_max_hp[:new_count] = self.max_hp[active_indices]
        new_intelligence[:new_count] = self.intelligence[active_indices]
        new_fullness[:new_count] = self.fullness[active_indices]
        new_fuel[:new_count] = self.fuel[active_indices]

        # Copy list/object fields
        new_name = [None] * self.capacity
        new_ai_type = [None] * self.capacity
        new_species = [None] * self.capacity
        new_faction = [None] * self.capacity
        new_strategy_state = [None] * self.capacity
        new_status_effects = [[] for _ in range(self.capacity)]
        new_extra_components = [{} for _ in range(self.capacity)]

        for i, old_idx in enumerate(active_indices):
            new_name[i] = self.name[old_idx]
            new_ai_type[i] = self.ai_type[old_idx]
            new_species[i] = self.species[old_idx]
            new_faction[i] = self.faction[old_idx]
            new_strategy_state[i] = self.strategy_state[old_idx]
            new_status_effects[i] = self.status_effects[old_idx]
            new_extra_components[i] = self.extra_components[old_idx]

        # Update attributes
        self.entity_id = new_entity_id
        self.is_active = new_is_active
        self.x = new_x
        self.y = new_y
        self.glyph = new_glyph
        self.color_fg_r = new_color_fg_r
        self.color_fg_g = new_color_fg_g
        self.color_fg_b = new_color_fg_b
        self.blocks_movement = new_blocks_movement
        self.hp = new_hp
        self.max_hp = new_max_hp
        self.intelligence = new_intelligence
        self.fullness = new_fullness
        self.fuel = new_fuel

        self.name = new_name
        self.ai_type = new_ai_type
        self.species = new_species
        self.faction = new_faction
        self.strategy_state = new_strategy_state
        self.status_effects = new_status_effects
        self.extra_components = new_extra_components

        self.count = new_count
        self.entity_id_to_index = {int(new_entity_id[i]): i for i in range(new_count)}
        self.dirty_polars_snapshot = True

    def to_polars(self) -> pl.DataFrame:
        from game.entities.registry import ENTITY_SCHEMA

        # 1. Build standard columns conforming to ENTITY_SCHEMA
        std_data: dict[str, list] = {}

        for col in ENTITY_SCHEMA:
            if col in NUMERIC_FIELDS:
                std_data[col] = list(getattr(self, col)[:self.count])
            elif col in OBJECT_FIELDS:
                std_data[col] = getattr(self, col)[:self.count]
            else:
                col_list = []
                dtype = ENTITY_SCHEMA[col]
                for idx in range(self.count):
                    extra = self.extra_components[idx]
                    val = extra.get(col)
                    if val is None:
                        # Fallback default value based on dtype
                        if _is_list_dtype(dtype):
                            val = []
                        elif dtype in (pl.Float32, pl.Float64):
                            val = 0.0
                        elif dtype in (
                            pl.Int16, pl.Int32, pl.Int64,
                            pl.UInt16, pl.UInt32, pl.UInt64, pl.UInt8
                        ):
                            val = 0
                        elif dtype == pl.Boolean:
                            val = False
                    col_list.append(val)
                std_data[col] = col_list

        df_std = pl.DataFrame(std_data, schema=ENTITY_SCHEMA)

        # 2. Build dynamic columns that are not in ENTITY_SCHEMA
        extra_keys = set()
        for idx in range(self.count):
            extra_keys.update(self.extra_components[idx].keys())

        dynamic_cols = [k for k in extra_keys if k not in ENTITY_SCHEMA]

        if dynamic_cols:
            dyn_data = {}
            for col in dynamic_cols:
                dyn_data[col] = [self.extra_components[idx].get(col) for idx in range(self.count)]
            df_dyn = pl.DataFrame(dyn_data)
            return pl.concat([df_std, df_dyn], how="horizontal")

        return df_std

    @classmethod
    def from_polars(cls, df: pl.DataFrame) -> EntityStore:
        from game.entities.registry import ENTITY_SCHEMA

        store = cls(capacity=max(256, df.height))
        store.count = df.height

        # Populate numeric fields
        for col in NUMERIC_FIELDS:
            if col in df.columns:
                arr = df[col].to_numpy()
                getattr(store, col)[:df.height] = arr
            else:
                default_val = 0
                if col == "is_active":
                    default_val = 1
                elif col in ("hp", "max_hp", "intelligence"):
                    default_val = 1
                elif col == "blocks_movement":
                    default_val = 1
                elif col == "fullness":
                    default_val = 100.0
                getattr(store, col)[:df.height] = default_val

        # Populate object fields
        for col in OBJECT_FIELDS:
            if col in df.columns:
                lst = df[col].to_list()
                # If length doesn't match df.height, pad or truncate
                getattr(store, col)[:df.height] = lst
            else:
                if col == "status_effects":
                    getattr(store, col)[:df.height] = [[] for _ in range(df.height)]
                else:
                    getattr(store, col)[:df.height] = [None] * df.height

        # Determine which columns are extras
        extra_cols = [c for c in df.columns if c not in NUMERIC_FIELDS and c not in OBJECT_FIELDS]

        for idx, row in enumerate(df.iter_rows(named=True)):
            extra_dict = {}
            for col in extra_cols:
                extra_dict[col] = row[col]
            store.extra_components[idx] = extra_dict

            entity_id = int(row["entity_id"])
            store.entity_id_to_index[entity_id] = idx

        store.dirty_polars_snapshot = False
        return store
