"""Community AI adapter for the v9 agent system."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import structlog

from ai.v9 import (
    AgentF,
    Behavior,
    ExperienceMemory,
    FatigueSystem,
    Habit,
    Home,
    IllnessSystem,
    SelfConcept,
    TraitProfile,
)
from game.systems import movement_system

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from game.game_state import GameState

log = structlog.get_logger()


@dataclass(frozen=True)
class CommunityProfile:
    """Normalized view of community configuration stored on entities."""

    template_id: str | None
    traits: dict[str, float]
    habits: tuple[str, ...]


def _normalize_traits(template_data: dict[str, Any]) -> TraitProfile:
    trait_data = (
        template_data.get("community", {}).get("traits")
        or template_data.get("traits")
        or {}
    )
    return TraitProfile(
        endurance=float(trait_data.get("endurance", 1.0)),
        ingenuity=float(trait_data.get("ingenuity", 1.0)),
        perception=float(trait_data.get("perception", 1.0)),
        will=float(trait_data.get("will", 1.0)),
        resonance=float(trait_data.get("resonance", 1.0)),
    )


def _normalize_habits(
    template_data: dict[str, Any], behaviors: dict[str, Behavior]
) -> list[Habit]:
    habits: list[Habit] = []
    raw_habits = template_data.get("community", {}).get("habits", [])
    for habit_cfg in raw_habits:
        if not isinstance(habit_cfg, dict):
            log.warning("Community habit config should be a dict", habit=habit_cfg)
            continue
        name = habit_cfg.get("name")
        sequence = []
        for item in habit_cfg.get("sequence", []):
            if isinstance(item, str) and item in behaviors:
                sequence.append(behaviors[item])
            else:
                log.warning(
                    "Community habit references unknown behavior", habit=name, item=item
                )
        if not name or not sequence:
            continue
        habits.append(
            Habit(
                name=name,
                sequence=sequence,
                trigger=habit_cfg.get("trigger", {}),
                score=float(habit_cfg.get("score", 1.0)),
                created_day=int(habit_cfg.get("created_day", 0)),
            )
        )
    return habits


def _apply_traits(agent: AgentF, traits: TraitProfile) -> None:
    agent.traits = traits
    agent.fatigue = FatigueSystem(endurance=traits.endurance)
    agent.illness = IllnessSystem(
        endurance=traits.endurance, will=traits.will, rng=agent.rng
    )
    agent.memory = ExperienceMemory(ingenuity=traits.ingenuity)
    agent.self_concept = SelfConcept(resonance=traits.resonance)


def _build_home(template_data: dict[str, Any]) -> Home:
    home = Home()
    home_data = template_data.get("community", {}).get("home", {})
    home.water_storage = float(home_data.get("water_storage", 0.0))
    home.raw_inventory = home_data.get("raw_inventory", {}) or {}
    home.cooked_food = home_data.get("cooked_food", {}) or {}
    home.fiber = home_data.get("fiber", {}) or {}
    home.containers = home_data.get("containers", {}) or {}
    home.fields = home_data.get("fields", []) or []
    return home


def _build_profile(
    template_id: str | None, traits: TraitProfile, habits: list[Habit]
) -> CommunityProfile:
    trait_payload = {
        "endurance": traits.endurance,
        "ingenuity": traits.ingenuity,
        "perception": traits.perception,
        "will": traits.will,
        "resonance": traits.resonance,
    }
    habit_names = tuple(habit.name for habit in habits)
    return CommunityProfile(
        template_id=template_id, traits=trait_payload, habits=habit_names
    )


class CommunityManager:
    """Manage v9 community agents within the game loop."""

    def __init__(self, game_state: GameState) -> None:
        self.gs = game_state
        self.rng = game_state.rng_instance

    def spawn_agent_from_template(
        self, template: str | dict[str, Any], x: int, y: int
    ) -> int | None:
        template_id: str | None
        if isinstance(template, str):
            template_id = template
            template_data = self.gs.entity_templates.get_template(template) or {}
        elif isinstance(template, dict):
            template_id = template.get("id")
            template_data = template
        else:
            raise TypeError("template must be a template id string or dict")

        if not template_data:
            log.warning("Community template not found", template=template_id)
            return None

        traits = _normalize_traits(template_data)
        home = _build_home(template_data)
        ai_agent = AgentF(rng=self.rng, home=home, base_logger=log)
        _apply_traits(ai_agent, traits)

        ai_agent.habits = _normalize_habits(template_data, ai_agent.behaviors)

        state_overrides = template_data.get("community", {}).get("state", {})
        ai_agent.thirst = float(state_overrides.get("thirst", ai_agent.thirst))
        ai_agent.hunger = float(state_overrides.get("hunger", ai_agent.hunger))
        ai_agent.energy = float(state_overrides.get("energy", ai_agent.energy))

        profile = _build_profile(template_id, traits, ai_agent.habits)
        intelligence = int(
            template_data.get(
                "intelligence",
                max(1, round((traits.ingenuity + traits.perception + traits.will) * 2)),
            )
        )
        hp = int(template_data.get("hp", max(1, round(5 * traits.endurance))))
        new_id = self.gs.entity_registry.create_entity(
            x=x,
            y=y,
            glyph=template_data.get("glyph", ord("?")),
            color_fg=tuple(template_data.get("color", (200, 200, 200))),
            name=template_data.get("name", template_id or "Community Agent"),
            blocks_movement=template_data.get("blocks_movement", True),
            ai_type=template_data.get("ai_type", "community_v9"),
            species=template_data.get("species"),
            intelligence=intelligence,
            hp=hp,
            max_hp=int(template_data.get("max_hp", hp)),
        )
        if new_id is None:
            return None

        self.gs.entity_registry.set_entity_component(new_id, "community_ai", ai_agent)
        self.gs.entity_registry.set_entity_component(
            new_id, "community_profile", profile.__dict__
        )
        return new_id

    def step(self) -> None:
        self._spawn_configured_regions()
        registry = self.gs.entity_registry
        for idx in registry.active_indices():
            if not registry.is_active_at(int(idx)):
                continue
            entity_id = registry.entity_id_at(int(idx))
            agent = registry.get_component_at(int(idx), "community_ai")
            if agent is None:
                continue
            # Get the row dict for the agent (it expects this format)
            row = registry.row_dict_at(int(idx))
            self._step_agent(entity_id, row, agent)

    def _spawn_configured_regions(self) -> None:
        configs = self.gs.ai_config.get("community_regions", [])
        registry = self.gs.entity_registry
        for cfg in configs:
            template_id = cfg.get("template")
            region = cfg.get("region")
            if not template_id or not region:
                continue
            desired = int(cfg.get("count", 1))
            region_x, region_y, region_w, region_h = region
            existing = 0
            for idx in registry.active_indices():
                if not registry.is_active_at(int(idx)):
                    continue
                profile = registry.get_component_at(int(idx), "community_profile")
                if (
                    profile
                    and profile.get("template_id") == template_id
                ):
                    ex, ey = registry.xy_at(int(idx))
                    if (
                        region_x <= ex < region_x + region_w
                        and region_y <= ey < region_y + region_h
                    ):
                        existing += 1
            for _ in range(max(0, desired - existing)):
                spawn_x = self.rng.get_int(region_x, region_x + region_w - 1)
                spawn_y = self.rng.get_int(region_y, region_y + region_h - 1)
                if not self.gs.game_map.is_walkable(spawn_x, spawn_y):
                    continue
                if self.gs.entity_registry.get_blocking_entity_at(spawn_x, spawn_y):
                    continue
                self.spawn_agent_from_template(template_id, spawn_x, spawn_y)

    def _step_agent(self, entity_id: int, row: dict[str, Any], agent: AgentF) -> None:
        agent.context["day"] = self.gs.turn_count
        agent.context["position"] = (row["x"], row["y"])
        action_taken = False

        if agent.thirst > 0.6 and agent.home.water_storage > 0:
            if agent.drink():
                agent.daily_behavior_log.append(
                    (agent._capture_state_snapshot(), "drink")
                )
                action_taken = True
        elif agent.hunger > 0.6:
            for store_name in ("cooked_food", "raw_inventory"):
                store = getattr(agent.home, store_name, {}) or {}
                for crop, amount in store.items():
                    if amount > 0 and agent.eat_crop(crop, 1):
                        agent.daily_behavior_log.append(
                            (agent._capture_state_snapshot(), f"eat_{crop}")
                        )
                        action_taken = True
                        break
                if action_taken:
                    break

        if not action_taken:
            self._wander(entity_id)
            agent.daily_behavior_log.append((agent._capture_state_snapshot(), "wander"))
            agent.hours += 1.0

        if agent.hours >= agent.day_length:
            agent.end_of_day_update()

    def _wander(self, entity_id: int) -> bool:
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        start_index = self.rng.get_int(0, len(directions) - 1)
        for i in range(len(directions)):
            dx, dy = directions[(start_index + i) % len(directions)]
            if movement_system.try_move(entity_id, dx, dy, self.gs):
                return True
        return False


def spawn_community_agent(
    game_state: GameState, template: str | dict[str, Any], x: int, y: int
) -> int | None:
    """Public adapter API for spawning a community agent."""

    return game_state.community_manager.spawn_agent_from_template(template, x, y)


def step_community_agents(game_state: GameState) -> None:
    """Public adapter API for stepping all community agents."""

    game_state.community_manager.step()
