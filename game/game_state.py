# game/game_state.py
from __future__ import annotations

import contextlib
import heapq
from collections.abc import Callable
from typing import Any, Final, Literal

import numpy as np
import polars as pl
import structlog
from numpy.typing import NDArray

from common.constants import FeatureType
from game.ai.perception import gather_perception, gather_perception_snapshot
from game.entities.components import Position
from game.entities.registry import EntityRegistry
from game.items.registry import ItemRegistry
from game.perception import apply_radius_perception
from game.perception_events import (
    NoiseEvent,
    PendingNoiseEvent,
    PendingScentEvent,
    ScentEvent,
    event_xy_intensity,
    noise_event_flow_type,
)
from game.planning.spatial_hash import SpatialHashTable
from game.systems.ai_system import dispatch_ai

# Assuming these imports are correct relative to game_state.py
from game.world.game_map import GameMap, LightSource
from pathfinding.perception_systems import (
    MAX_FLOWS,
    SCENT_RESET_AGE,
    monster_perception,
    update_noise,
    update_smell,
)
from simulation.zone_manager import ZoneManager
from utils.game_rng import GameRNG  # Assuming this path is correct

# Import sound system
# Fallback removed
from game.systems.sound import get_sound_manager, update_music_context
SOUND_AVAILABLE = True


log = structlog.get_logger()

__all__: Final[tuple[str, ...]] = (
    "GameState",
    "NoiseEvent",
    "PendingNoiseEvent",
    "PendingScentEvent",
    "ScentEvent",
)


class GameState:
    """Central container for mutable game data.

    The magic subsystem relies on the following minimal interface:

    ``player_id``
        Integer identifier of the acting entity (usually the player).
    ``has_seal_tag(entity_id, tag)``
        Return ``True`` if ``entity_id`` possesses the given seal tag.
    ``has_font_source(entity_id, source)``
        Return ``True`` if the entity can supply ``source`` as a font.
    ``has_vent_target(entity_id, target)``
        Return ``True`` if the entity exposes ``target`` as a vent.

    Each lookup is backed by list components (``seal_tags``, ``font_sources``,
    and ``vent_targets``) managed by :class:`game.entities.registry.EntityRegistry`.

    Pathfinding perception arrays are owned here, not by ``GameMap``. They are
    dynamic simulation state rather than static map-shaped terrain storage:

    - ``perception_cave_cost``
    - ``perception_flow_centers``
    - ``perception_cave_when``
    - ``perception_global_scent_when``
    """

    def __init__(
        self,
        existing_map: GameMap,
        player_start_pos: tuple[int, int],
        # Config values passed directly
        player_glyph: int,
        player_start_hp: int,
        player_fov_radius: int,
        item_templates: dict[str, Any],
        entity_templates: dict[str, Any] | None = None,
        effect_definitions: dict[str, Any] | None = None,
        rng_seed: int | None = None,
        ai_config: dict[str, Any] | None = None,
        memory_fade_config: dict[str, Any] | None = None,
        enable_sound: bool = True,
        enable_ai: bool = True,
    ):
        log.info("Initializing GameState...")

        if not isinstance(existing_map, GameMap):
            raise TypeError("GameState requires a valid GameMap instance.")
        if not player_start_pos or len(player_start_pos) != 2:
            raise ValueError(
                "GameState requires a valid player_start_pos tuple (x, y)."
            )

        self.game_map: GameMap = existing_map
        self._map_width: int = existing_map.width
        self._map_height: int = existing_map.height

        self.rng_instance: GameRNG = GameRNG(seed=rng_seed)
        log.debug("GameRNG initialized", seed=self.rng_instance.initial_seed)

        self.entity_registry: EntityRegistry = EntityRegistry()
        log.debug("EntityRegistry initialized")

        # Store loaded entity templates in a simple registry
        from game.entities.template_registry import EntityTemplateRegistry

        self.entity_templates = EntityTemplateRegistry(entity_templates or {})

        self.item_registry: ItemRegistry = ItemRegistry(item_templates)
        self.effect_definitions: dict[str, Any] = effect_definitions or {}
        self.ai_config: dict[str, Any] = ai_config or {}
        self.ai_enabled: bool = enable_ai
        mf_config = memory_fade_config or {}
        duration = mf_config.get("duration", 60.0)
        self.memory_fade_enabled: bool = mf_config.get("enabled", True)
        self.memory_fade_duration: float = duration
        self.memory_fade_midpoint: float = mf_config.get("midpoint", duration / 2.0)
        self.memory_fade_steepness: float = mf_config.get(
            "steepness", 6.0 / duration if duration else 0.0
        )
        tile_modifiers_cfg = mf_config.get("tile_modifiers", {})
        self.game_map.apply_memory_modifier_overrides(tile_modifiers_cfg)
        log.debug("ItemRegistry initialized", templates=len(item_templates))
        log.debug("Effect definitions stored", effects=len(self.effect_definitions))

        player_start_x, player_start_y = player_start_pos
        # Ensure all necessary components are passed during creation if defaults changed
        self.player_id: int = self.entity_registry.create_entity(
            x=player_start_x,
            y=player_start_y,
            glyph=player_glyph,
            color_fg=(255, 255, 255),
            name="Player",
            blocks_movement=True,
            hp=player_start_hp,
            max_hp=player_start_hp,
            # Add defaults for mana/fullness etc. if needed by registry init
        )
        log.debug(
            "Player entity created",
            player_id=self.player_id,
            pos=(player_start_x, player_start_y),
            hp=player_start_hp,
            glyph=player_glyph,
        )

        self.base_fov_radius = player_fov_radius
        self.fov_radius = player_fov_radius
        self.message_log: list[tuple[str, tuple[int, int, int]]] = []
        # Messages generated while their subjects are outside FOV are stored here.
        self.message_queue: list[tuple[int, str, tuple[int, int, int]]] = []
        self.turn_count: int = 0
        # Perception event queues processed by gather_perception.
        self.noise_events: list[PendingNoiseEvent] = []
        self.scent_events: list[PendingScentEvent] = []
        # Production pathfinding perception fields mirrored from queued events.
        perception_infinity = np.iinfo(np.int32).max // 2
        self.perception_cave_cost: NDArray[np.int32] = np.full(
            (MAX_FLOWS, self._map_height, self._map_width),
            perception_infinity,
            dtype=np.int32,
        )
        self.perception_flow_centers: NDArray[np.int32] = np.zeros(
            (MAX_FLOWS, 2), dtype=np.int32
        )
        self.perception_cave_when: NDArray[np.int32] = np.zeros(
            (self._map_height, self._map_width), dtype=np.int32
        )
        self.perception_global_scent_when: int = SCENT_RESET_AGE
        self.perception_alerted_monster_ids: list[int] = []
        self.spatial_index: SpatialHashTable = SpatialHashTable()
        # Track light sources (player has a default white light)
        self.light_sources: list[LightSource] = self.game_map.light_sources
        self.light_sources.append(
            LightSource(
                player_start_x, player_start_y, player_fov_radius, (255, 255, 255)
            )
        )
        self.player_light_index: int = 0
        self.player_max_fuel: int = 100
        self.player_fuel: int = self.player_max_fuel

        # Track simulation zones for coarse updates when entities are far away
        self.zone_manager: ZoneManager = ZoneManager(self._map_width, self._map_height)
        self.timed_events: list[tuple[int, int, Callable[[GameState], None]]] = []
        self._next_timed_event_id: int = 0

        # --- NEW: UI State ---
        self.ui_state: Literal["PLAYER_TURN", "INVENTORY_VIEW", "TARGETING"] = (
            "PLAYER_TURN"
        )
        # --- End NEW ---

        # --- Sound System ---
        self.sound_manager = (
            get_sound_manager() if SOUND_AVAILABLE and enable_sound else None
        )
        if self.sound_manager:
            log.debug("Sound system initialized")

        self.add_message("Welcome to BasicRL!", (0, 255, 0))

        from game.ai.community_adapter import CommunityManager

        self.community_manager = CommunityManager(self)

        log.info(
            "Game state initialized",
            map_size=f"{self._map_width}x{self._map_height}",
            player_id=self.player_id,
            item_templates_loaded=len(item_templates),
            effect_definitions_loaded=len(self.effect_definitions),
            rng_seed=self.rng_instance.initial_seed,
        )

        self.update_fov()  # Initial FOV calculation

        # Initial sound context update
        if self.sound_manager:
            self._update_sound_context()

    def update_fov(self) -> None:
        """Run the authoritative player FOV and memory lifecycle."""
        player_pos = self.player_position
        if player_pos is None:
            log.warning("Cannot update FOV: Player position not found.")
            self.game_map.visible[:] = False
            self.flush_message_queue()
            return

        px, py = player_pos
        if not self.game_map.in_bounds(px, py):
            log.warning("Player out of bounds, cannot compute FOV.", pos=(px, py))
            self.game_map.visible[:] = False
            self.flush_message_queue()
            return

        self.game_map.compute_fov(px, py, self.fov_radius)
        self._force_player_visible(px, py)
        self.game_map.refresh_visible_memory(self.turn_count)
        if self.memory_fade_enabled:
            self.game_map.fade_memory(
                self.turn_count,
                self.memory_fade_steepness,
                self.memory_fade_midpoint,
            )
        self._sync_player_light_source(px, py)
        self.flush_message_queue()

    def _force_player_visible(self, px: int, py: int) -> None:
        """Ensure the player's tile remains visible and explored after FOV."""
        if self.game_map.visible[py, px]:
            return
        log.warning(
            "Origin tile became non-visible after FOV calculation, forcing visible.",
            pos=(px, py),
        )
        self.game_map.visible[py, px] = True
        self.game_map.explored[py, px] = True

    def _sync_player_light_source(self, px: int, py: int) -> None:
        """Keep the player-owned light source aligned with the player position."""
        if not 0 <= self.player_light_index < len(self.light_sources):
            log.error(
                "Failed to update player light source",
                index=self.player_light_index,
                light_sources=len(self.light_sources),
                error="player light index out of range",
            )
            return
        player_light = self.light_sources[self.player_light_index]
        player_light.x = px
        player_light.y = py

    @property
    def map_width(self) -> int:
        return self._map_width

    @property
    def map_height(self) -> int:
        return self._map_height

    @property
    def player_position(self) -> Position | None:
        """Gets the current player position from the EntityRegistry."""
        return self.entity_registry.get_position(self.player_id)

    def add_message(
        self, text: str, color: tuple[int, int, int] = (255, 255, 255)
    ) -> None:
        """Adds a message to the game log."""
        self.message_log.append((text, color))
        log.debug("Message added", message=text, color=color)
        # Optional: Trim log length if it gets too long
        # MAX_LOG_LENGTH = 100
        # if len(self.message_log) > MAX_LOG_LENGTH:
        #     self.message_log = self.message_log[-MAX_LOG_LENGTH:]

    def queue_message(
        self, entity_id: int, text: str, color: tuple[int, int, int] = (255, 255, 255)
    ) -> None:
        """Queue a message to display when ``entity_id`` becomes visible."""
        self.message_queue.append((entity_id, text, color))
        log.debug("Message queued", entity_id=entity_id, message=text, color=color)

    def flush_message_queue(self) -> None:
        """Deliver queued messages whose entities are now visible."""
        if not self.message_queue:
            return
        remaining: list[tuple[int, str, tuple[int, int, int]]] = []
        for ent_id, text, color in self.message_queue:
            pos = self.entity_registry.get_position(ent_id)
            if pos and self.game_map.visible[pos.y, pos.x]:
                self.add_message(text, color)
            else:
                remaining.append((ent_id, text, color))
        self.message_queue = remaining

    def schedule_low_detail_update(
        self, x: int, y: int, callback: Callable[[GameState], None]
    ) -> None:
        """Queue a low-detail update for the zone containing ``(x, y)``.

        Systems can use this to defer expensive logic for entities that are
        far away from the player.  The callback will receive the ``GameState``
        instance when executed.
        """
        self.zone_manager.schedule_event(x, y, callback)

    def _process_status_effects_for_entity(self, entity_id: int) -> None:
        """Tick down status effects for a single entity."""
        status_effects = (
            self.entity_registry.get_entity_component(entity_id, "status_effects") or []
        )
        if not status_effects:
            return
        updated_effects: list[dict] = []
        for effect in status_effects:
            new_duration = effect.get("duration", 0) - 1
            if new_duration > 0:
                updated_effects.append({**effect, "duration": new_duration})
            else:
                effect_id = effect.get("id")
                log.debug(
                    "Status effect expired", entity_id=entity_id, effect=effect_id
                )
                entity_name = (
                    self.entity_registry.get_entity_component(entity_id, "name")
                    or f"Entity {entity_id}"
                )
                self.add_message(f"{entity_name}'s {effect_id} wears off.")
        if updated_effects != status_effects:
            self.entity_registry.set_entity_component(
                entity_id, "status_effects", updated_effects
            )

    def _process_resources_for_entity(self, entity_id: int) -> None:
        """Reduce generic per-turn resources like fullness or fuel."""
        for res in ("fullness", "fuel"):
            try:
                value = self.entity_registry.get_entity_component(entity_id, res)
            except ValueError:
                continue
            if value is None:
                continue
            new_val = max(0, value - 1)
            self.entity_registry.set_entity_component(entity_id, res, new_val)
            if res == "fullness" and entity_id == self.player_id and new_val <= 0:
                self.add_message("You are starving!", (255, 255, 0))

    def _consume_player_fuel(self) -> None:
        """Decrease player torch fuel and adjust light radius."""
        if self.player_max_fuel <= 0:
            return
        if self.player_fuel > 0:
            self.player_fuel -= 1
        ratio = self.player_fuel / self.player_max_fuel
        new_radius = max(1, round(self.base_fov_radius * ratio))
        self.fov_radius = new_radius
        with contextlib.suppress(IndexError, AttributeError):
            self.light_sources[self.player_light_index].radius = new_radius
        if self.player_fuel == 0:
            self.add_message("Your light flickers out!", (255, 255, 0))

    # --- Resource helper methods ---
    def _list_component_has(self, entity_id: int, component: str, value: str) -> bool:
        """Generic helper to check membership in a list component."""
        items = self.entity_registry.get_entity_component(entity_id, component)
        return bool(items and value in items)

    def _list_component_consume(
        self, entity_id: int, component: str, value: str
    ) -> bool:
        """Generic helper to remove a value from a list component if present."""
        items = self.entity_registry.get_entity_component(entity_id, component)
        if not items or value not in items:
            return False
        updated = list(items)
        updated.remove(value)
        self.entity_registry.set_entity_component(entity_id, component, updated)
        return True

    def has_seal_tag(self, entity_id: int, tag: str) -> bool:
        """Return ``True`` if ``entity_id`` possesses ``tag`` in its seal tags."""
        return self._list_component_has(entity_id, "seal_tags", tag)

    def consume_seal_tag(self, entity_id: int, tag: str) -> bool:
        """Consume ``tag`` from ``entity_id``'s seal tags, if present."""
        return self._list_component_consume(entity_id, "seal_tags", tag)

    def has_font_source(self, entity_id: int, source: str) -> bool:
        """Check whether ``entity_id`` has the specified font source available."""
        return self._list_component_has(entity_id, "font_sources", source)

    def consume_font_source(self, entity_id: int, source: str) -> bool:
        """Consume a font source from the entity, returning ``True`` on success."""
        return self._list_component_consume(entity_id, "font_sources", source)

    def has_vent_target(self, entity_id: int, target: str) -> bool:
        """Check whether ``entity_id`` has the specified vent target."""
        return self._list_component_has(entity_id, "vent_targets", target)

    def consume_vent_target(self, entity_id: int, target: str) -> bool:
        """Consume a vent target from the entity, returning ``True`` on success."""
        return self._list_component_consume(entity_id, "vent_targets", target)

    def schedule_timed_event(
        self, delay: int, callback: Callable[[GameState], None]
    ) -> None:
        """Schedule ``callback`` to run after ``delay`` turns."""
        trigger_turn = self.turn_count + max(0, delay)
        heapq.heappush(
            self.timed_events,
            (trigger_turn, self._next_timed_event_id, callback),
        )
        self._next_timed_event_id += 1

    def process_turn(
        self,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        """Handle per-turn updates like status effects and resources."""
        # Timed events scheduled for this turn
        while self.timed_events and self.timed_events[0][0] <= self.turn_count:
            _, _, cb = heapq.heappop(self.timed_events)
            try:
                cb(self)
            except Exception as err:
                log.error("Timed event callback failed", error=str(err))

        active_rows: list[dict[str, object]] = []
        ai_entities: list[dict[str, object]] = []
        self.spatial_index.clear()
        for row in self.entity_registry.entities_df.iter_rows(named=True):
            if not row.get("is_active", False):
                continue
            entity_id = int(row["entity_id"])
            x = row.get("x")
            y = row.get("y")
            if isinstance(x, int) and isinstance(y, int):
                species = row.get("species")
                ai_type = row.get("ai_type")
                if species == "enemy" or ai_type in {"goap", "combat"}:
                    kind_value = "enemy"
                elif species == "slime":
                    kind_value = "slime"
                else:
                    kind_value = species or ai_type or "entity"
                self.spatial_index.insert(entity_id, x, y, str(kind_value))
            self._process_status_effects_for_entity(entity_id)
            self._process_resources_for_entity(entity_id)
            active_rows.append(row)
            if row.get("ai_type"):
                ai_entities.append(row)

        self._consume_player_fuel()
        return active_rows, ai_entities

    def _terrain_map_for_perception(self) -> NDArray[np.int32]:
        """Return a FeatureType terrain map for production perception fields."""
        feature_map = getattr(self.game_map, "feature_map", None)
        if isinstance(feature_map, np.ndarray):
            return feature_map.astype(np.int32, copy=False)

        terrain_map = np.full(
            self.game_map.transparent.shape,
            int(FeatureType.WALL),
            dtype=np.int32,
        )
        terrain_map[self.game_map.transparent] = int(FeatureType.FLOOR)
        return terrain_map

    def _ensure_perception_arrays(self) -> None:
        """Resize production perception arrays if the active map shape changes."""
        if (
            self._map_width != self.game_map.width
            or self._map_height != self.game_map.height
        ):
            self._map_width = self.game_map.width
            self._map_height = self.game_map.height
            self.zone_manager.map_width = self._map_width
            self.zone_manager.map_height = self._map_height

        expected_cost_shape = (MAX_FLOWS, self.game_map.height, self.game_map.width)
        if self.perception_cave_cost.shape != expected_cost_shape:
            infinity = np.iinfo(np.int32).max // 2
            self.perception_cave_cost = np.full(
                expected_cost_shape,
                infinity,
                dtype=np.int32,
            )

        expected_centers_shape = (MAX_FLOWS, 2)
        if self.perception_flow_centers.shape != expected_centers_shape:
            self.perception_flow_centers = np.zeros(
                expected_centers_shape,
                dtype=np.int32,
            )

        expected_scent_shape = (self.game_map.height, self.game_map.width)
        if self.perception_cave_when.shape != expected_scent_shape:
            self.perception_cave_when = np.zeros(
                expected_scent_shape,
                dtype=np.int32,
            )

    def update_perception_fields(
        self,
        *,
        include_player_scent: bool = True,
        clear_events: bool = True,
    ) -> None:
        """Advance production sound/scent fields and derived monster alerts.

        This is the lifecycle owner for non-visual perception. ``gather_perception()``
        may still call this with ``include_player_scent=False`` as a compatibility
        fallback when tests or legacy callers enqueue events and then gather directly.
        """
        self._ensure_perception_arrays()

        terrain_map = self._terrain_map_for_perception()
        noise_events = list(self.noise_events)
        scent_events = list(self.scent_events)

        if include_player_scent:
            player_pos = self.player_position
            if player_pos is not None:
                scent_events.append(
                    ScentEvent(
                        x=int(player_pos.x),
                        y=int(player_pos.y),
                        intensity=5.0,
                        source_id=self.player_id,
                    )
                )

        # Debug/compatibility radius maps remain simple AI-facing heat maps.
        self.game_map.noise_map *= 0.6
        self.game_map.scent_map *= 0.9

        for event in noise_events:
            x, y, intensity = event_xy_intensity(event)
            apply_radius_perception(
                map_arr=self.game_map.noise_map,
                x=x,
                y=y,
                r=2,
                base_intensity=intensity,
                game_map=self.game_map,
            )

        for event in scent_events:
            x, y, intensity = event_xy_intensity(event)
            apply_radius_perception(
                map_arr=self.game_map.scent_map,
                x=x,
                y=y,
                r=4,
                base_intensity=intensity,
                game_map=self.game_map,
            )

        # Production noise is intentionally loudest-event-wins. The debug radius map
        # receives every queued event, but the pathfinding flow field represents one
        # authoritative investigate source for this update.
        if noise_events:
            loudest = max(noise_events, key=lambda event: event_xy_intensity(event)[2])
            loudest_x, loudest_y, _intensity = event_xy_intensity(loudest)
            flow_type = noise_event_flow_type(loudest)
            update_noise(
                self.perception_cave_cost,
                self.perception_flow_centers,
                terrain_map,
                loudest_y,
                loudest_x,
                flow_type,
                {},
            )
        else:
            infinity = np.iinfo(np.int32).max // 2
            self.perception_cave_cost.fill(infinity)

        # Production scent applies the latest scent event only. During normal turns,
        # automatic player scent is appended after queued scent events and is therefore
        # authoritative.
        if scent_events:
            latest = scent_events[-1]
            scent_x, scent_y, _intensity = event_xy_intensity(latest)
            self.perception_global_scent_when = update_smell(
                self.perception_cave_when,
                terrain_map,
                scent_y,
                scent_x,
                self.perception_global_scent_when,
            )

        self.resolve_monster_perception()

        if clear_events:
            self.noise_events.clear()
            self.scent_events.clear()

    def resolve_monster_perception(self) -> None:
        """Convert perception arrays into derived monster-alert facts."""
        entities_df = getattr(self.entity_registry, "entities_df", None)
        if not isinstance(entities_df, pl.DataFrame) or entities_df.is_empty():
            self.perception_alerted_monster_ids = []
            return

        required_columns = {"entity_id", "x", "y", "is_active"}
        if not required_columns.issubset(set(entities_df.columns)):
            self.perception_alerted_monster_ids = []
            return

        player_pos = self.player_position
        if player_pos is None:
            self.perception_alerted_monster_ids = []
            return
        player_x, player_y = player_pos.x, player_pos.y

        monster_df = entities_df.filter(
            (pl.col("entity_id") != self.player_id) & pl.col("is_active")
        )
        if monster_df.is_empty():
            self.perception_alerted_monster_ids = []
            return

        perception_stat = (
            pl.col("perception_stat")
            if "perception_stat" in monster_df.columns
            else pl.lit(10)
        )
        is_dead = (
            (~pl.col("is_active")) | (pl.col("hp") <= 0)
            if "hp" in monster_df.columns
            else ~pl.col("is_active")
        )
        adapted_df = monster_df.select(
            pl.col("entity_id").alias("id"),
            pl.col("y").cast(pl.Int64).alias("fy"),
            pl.col("x").cast(pl.Int64).alias("fx"),
            is_dead.alias("is_dead"),
            perception_stat.cast(pl.Int64).alias("perception_stat"),
        )

        self.perception_alerted_monster_ids = monster_perception(
            adapted_df,
            cave_cost=self.perception_cave_cost,
            flow_centers=self.perception_flow_centers,
            player_y=int(player_y),
            player_x=int(player_x),
            player_stealth_skill=0,
            rng=self.rng_instance,
            deterministic=True,
        )

    def _process_zone(self, zone: tuple[int, int]) -> None:
        """Aggregate update for all entities within ``zone``.

        This performs a very coarse simulation step used for areas that are far
        from the player.  Perception data is omitted for performance; AI
        adapters receive ``None`` for the perception argument.
        """
        for row in self.entity_registry.entities_df.iter_rows(named=True):
            if not row.get("is_active", False):
                continue
            if row.get("community_ai") is not None:
                continue
            if self.zone_manager.get_zone(row.get("x"), row.get("y")) != zone:
                continue
            entity_id = row["entity_id"]
            if entity_id == self.player_id:
                continue
            dispatch_ai(
                row,
                game_state=self,
                rng=self.rng_instance,
                perception=None,
            )

    def advance_turn(self) -> None:
        """Advances the game turn counter and performs turn-based updates."""
        self.turn_count += 1
        log.debug("Turn advanced", turn=self.turn_count)

        # Handle generic per-turn processing
        active_rows, ai_entities = self.process_turn()

        player_pos = self.player_position

        active_zones: set[tuple[int, int]] = self.zone_manager.get_active_zones(
            player_pos
        )

        # Schedule distant zones for AI updates
        for row in active_rows:
            if not row.get("is_active", False):
                continue
            entity_id = row["entity_id"]
            if entity_id == self.player_id:
                continue
            zone = self.zone_manager.get_zone(row.get("x"), row.get("y"))
            if zone not in active_zones:
                self.zone_manager.schedule_zone_event(
                    zone, lambda gs, z=zone: gs._process_zone(z)
                )

        # Recalculate FOV so perception and rendering use up-to-date visibility
        self.update_fov()
        self.update_perception_fields(include_player_scent=True)

        self.community_manager.step()

        # --- AI processing for nearby entities ---
        if self.ai_enabled:
            log.debug("Gathering perception data for AI")
            perception = gather_perception_snapshot(self)

            log.debug("Processing AI-controlled entities")
            ai_rows = []
            for row in ai_entities:
                if row.get("entity_id") == self.player_id:
                    continue
                if row.get("community_ai") is not None:
                    continue
                zone = self.zone_manager.get_zone(row.get("x"), row.get("y"))
                if zone not in active_zones:
                    continue
                ai_rows.append(row)
            if ai_rows:
                dispatch_ai(
                    ai_rows,
                    game_state=self,
                    rng=self.rng_instance,
                    perception=perception,
                )
        else:
            log.debug("AI subsystem disabled; skipping AI processing")

        # Process any queued low-detail zone updates
        self.zone_manager.process(self.turn_count, active_zones, self)

        # --- Other turn-based updates ---
        # (e.g., hunger increase, light source fuel consumption)

        # Update sound context for situational music
        if self.sound_manager:
            self._update_sound_context()

    # --- NEW: State transition helper ---
    def change_ui_state(
        self, new_state: Literal["PLAYER_TURN", "INVENTORY_VIEW", "TARGETING"]
    ):
        # Basic state change, could add validation or hooks later
        if self.ui_state != new_state:
            log.debug(f"Changing UI state from {self.ui_state} to {new_state}")
            self.ui_state = new_state
        else:
            log.debug(f"UI state already {new_state}, no change.")

    # --- Sound System Integration ---
    def _update_sound_context(self) -> None:
        """Update the sound system with current game context for situational music."""
        if not self.sound_manager:
            return

        # Determine current game state
        game_state = "exploring"  # Default state

        # Check if player is in combat (nearby hostile entities)
        player_pos = self.player_position
        if player_pos:
            px, py = player_pos
            # Look for nearby hostile entities within FOV
            for row in self.entity_registry.entities_df.iter_rows(named=True):
                if (
                    not row.get("is_active", False)
                    or row["entity_id"] == self.player_id
                ):
                    continue

                ex, ey = row.get("x", 0), row.get("y", 0)
                # Check if entity is within reasonable combat distance and visible
                distance_sq = (px - ex) ** 2 + (py - ey) ** 2
                if (
                    distance_sq <= (self.fov_radius + 2) ** 2
                    and hasattr(self.game_map, "visible")
                    and self.game_map.visible[ey, ex]
                ):
                    # Assume any visible nearby entity means combat
                    game_state = "combat"
                    break

        # Determine depth (if available)
        depth = getattr(self, "current_depth", 1)

        # Check for special entity types nearby
        enemy_types = []
        if player_pos:
            px, py = player_pos
            for row in self.entity_registry.entities_df.iter_rows(named=True):
                if (
                    not row.get("is_active", False)
                    or row["entity_id"] == self.player_id
                ):
                    continue

                ex, ey = row.get("x", 0), row.get("y", 0)
                distance_sq = (px - ex) ** 2 + (py - ey) ** 2
                if distance_sq <= self.fov_radius**2:
                    entity_name = row.get("name", "").lower()
                    if (
                        "boss" in entity_name
                        or "dragon" in entity_name
                        or "demon" in entity_name
                    ):
                        enemy_types.append("boss")
                    elif "elite" in entity_name or "champion" in entity_name:
                        enemy_types.append("elite")

        # Build context for sound system
        context = {
            "game_state": game_state,
            "depth": depth,
            "turn": self.turn_count,
            "player_hp_percent": 1.0,  # Default
            "ui_state": self.ui_state.lower(),
        }

        # Add enemy type if any special enemies nearby
        if enemy_types:
            context["enemy_type"] = enemy_types

        # Get player HP percentage if available
        player_hp = self.entity_registry.get_entity_component(self.player_id, "hp")
        player_max_hp = self.entity_registry.get_entity_component(
            self.player_id, "max_hp"
        )
        if player_hp is not None and player_max_hp is not None and player_max_hp > 0:
            context["player_hp_percent"] = player_hp / player_max_hp

        # Update background music based on context
        update_music_context(context)

    # --- End NEW ---
