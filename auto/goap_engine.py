"""Reusable GOAP planning engine shared between the auto testbed and the game."""

from __future__ import annotations

import heapq
import time
import typing
from collections import defaultdict, deque

# --- Type Hinting Aliases ---
Position = tuple[int, int]
StateDict = dict[str, typing.Any]
ActionPlan = deque["Action"]

WorldLike = typing.Any
AgentLike = typing.Any
OptionalPosition = Position | None

# --- Configuration Constants ---
MAX_TURNS: int = 200
START_HEALTH: float = 100.0
START_HUNGER: float = 100.0
SLIME_MOLD_HUNGER_RECOVERY: float = 40.0
HEALTH_POTION_RECOVERY: float = 50.0
ATTACK_HUNGER_COST: float = 0.05
DEFEND_HUNGER_COST: float = 0.05
REST_HEALTH_REGEN: float = 0.05
ENEMY_NEARBY_FLEE_DISTANCE: int = 8
HEALTHY_THRESHOLD: float = START_HEALTH * 0.6
CRITICAL_HEALTH_THRESHOLD: float = START_HEALTH * 0.3
LOW_HEALTH_FLEE_THRESHOLD: float = START_HEALTH * 0.4
PLANNING_TIMEOUT: float = 0.1
ACTION_WEIGHT_MIN: float = 0.1
ACTION_WEIGHT_MAX: float = 10.0
LEARNING_RATE_FACTOR: float = 0.15
LEARNING_SCORE_BASELINE: float = 0.6


def _safe_item_name(item: typing.Any) -> str | None:
    if isinstance(item, dict):
        return item.get("name")
    return getattr(item, "name", None)


def _safe_item_kind(item: typing.Any) -> str | None:
    if isinstance(item, dict):
        return item.get("kind")
    return getattr(item, "kind", None)


# --- GOAP Action Class ---
CostCalculator = typing.Callable[[WorldLike, AgentLike], float]
PreconditionsChecker = typing.Callable[[StateDict], bool]
EffectsApplier = typing.Callable[[StateDict], StateDict]
Executor = typing.Callable[[WorldLike, AgentLike], bool]


class Action:
    """Represents a possible action in the GOAP system."""

    def __init__(
        self,
        name: str,
        cost_calculator: CostCalculator,
        preconditions_checker: PreconditionsChecker,
        effects_applier: EffectsApplier,
        executor: Executor | None = None,
    ):
        self.name: str = name
        self.calculate_cost: CostCalculator = cost_calculator
        self.check_preconditions: PreconditionsChecker = preconditions_checker
        self.apply_effects_to_state: EffectsApplier = effects_applier
        self.execute: Executor | None = executor

    def __repr__(self) -> str:
        return f"Action({self.name})"


class GOAPPlanner:
    """Finds a sequence of actions to achieve a goal state."""

    def __init__(self, available_actions: list[Action]):
        self.actions: list[Action] = available_actions
        self.action_weights: defaultdict[str, float] = defaultdict(lambda: 1.0)

    def plan(
        self, world: WorldLike, agent: AgentLike, goal_state: StateDict
    ) -> list[Action] | None:
        """Plans a sequence of actions using A* search."""
        start_time = time.time()
        initial_state = self._get_world_state_representation(world, agent)

        open_list: list[tuple[float, int, StateDict, list[Action], float]] = [
            (self._heuristic(initial_state, goal_state), 0, initial_state, [], 0.0)
        ]
        closed_set: set[frozenset[tuple[str, typing.Any]]] = set()
        counter = 1

        while open_list:
            if time.time() - start_time > PLANNING_TIMEOUT:
                return None

            _, _, current_state, action_plan, cost_so_far = heapq.heappop(open_list)

            if self._goal_satisfied(current_state, goal_state):
                return action_plan

            state_tuple = frozenset(current_state.items())
            if state_tuple in closed_set:
                continue
            closed_set.add(state_tuple)

            for action in self.actions:
                if action.check_preconditions(current_state):
                    action_base_cost = action.calculate_cost(world, agent)
                    if action_base_cost == float("inf"):
                        continue

                    weighted_cost = action_base_cost * self.action_weights[action.name]

                    next_state = action.apply_effects_to_state(current_state.copy())
                    next_state_tuple = frozenset(next_state.items())

                    if next_state_tuple in closed_set:
                        continue

                    new_cost = cost_so_far + weighted_cost
                    h = self._heuristic(next_state, goal_state)
                    new_f_score = new_cost + h
                    new_plan = action_plan + [action]

                    heapq.heappush(
                        open_list,
                        (new_f_score, counter, next_state, new_plan, new_cost),
                    )
                    counter += 1

        return None

    def _get_world_state_representation(
        self, world: WorldLike, agent: AgentLike
    ) -> StateDict:
        """Creates a dictionary representing the current world state relevant to the agent."""
        item_id, item_dist = world.get_nearest_entity(agent, "item")
        enemy_id, enemy_dist = world.get_nearest_entity(agent, "enemy")
        slime_id, slime_dist = world.get_nearest_entity(agent, "slime")

        nearest_hostile_id = None
        nearest_hostile_dist = float("inf")
        if enemy_id and enemy_dist < nearest_hostile_dist:
            nearest_hostile_dist = enemy_dist
            nearest_hostile_id = enemy_id
        if slime_id and slime_dist < nearest_hostile_dist:
            nearest_hostile_dist = slime_dist
            nearest_hostile_id = slime_id

        inventory_items = getattr(agent, "inventory", [])
        inventory_count = len(inventory_items)
        has_slime_mold = any(
            _safe_item_name(item) == "Slime Mold" for item in inventory_items
        )
        has_health_potion = any(
            _safe_item_name(item) == "Health Potion" for item in inventory_items
        )
        has_weapon_in_inv = any(
            (_safe_item_kind(item) or "").lower() == "weapon"
            for item in inventory_items
        )

        nearest_item_is_slime_mold = False
        nearest_item_is_health_potion = False
        nearest_item_is_weapon = False
        if item_id is not None and hasattr(world, "get_entity_object"):
            item_obj = world.get_entity_object(item_id)
            item_name = None
            item_kind = None
            if item_obj is not None:
                if isinstance(item_obj, dict):
                    item_name = item_obj.get("name")
                    item_kind = item_obj.get("kind")
                else:
                    item_name = getattr(item_obj, "name", None)
                    item_kind = getattr(item_obj, "kind", None)
                if item_name is None and hasattr(item_obj, "item"):
                    item_name = getattr(item_obj.item, "name", None)
                    item_kind = getattr(item_obj.item, "kind", None)
            if item_name == "Slime Mold":
                nearest_item_is_slime_mold = True
            if item_name == "Health Potion":
                nearest_item_is_health_potion = True
            if (item_kind or "").lower() == "weapon":
                nearest_item_is_weapon = True

        state = {
            "agent_health": agent.health,
            "agent_hunger": agent.hunger,
            "is_starving": agent.hunger <= 0,
            "agent_pos": agent.get_position(),
            "is_healthy": agent.health > HEALTHY_THRESHOLD,
            "is_critically_injured": agent.health < CRITICAL_HEALTH_THRESHOLD,
            "can_find_item": item_id is not None,
            "nearest_item_dist": item_dist,
            "item_is_adjacent": item_dist <= 1.0,
            "can_find_enemy": nearest_hostile_id is not None,
            "nearest_enemy_dist": nearest_hostile_dist,
            "enemy_is_adjacent": nearest_hostile_dist <= 1.0,
            "inventory_count": inventory_count,
            "inventory_full": inventory_count >= agent.max_inventory,
            "max_inventory": agent.max_inventory,
            "has_slime_mold": has_slime_mold,
            "has_health_potion": has_health_potion,
            "has_weapon_in_inv": has_weapon_in_inv,
            "weapon_equipped": agent.equipped_weapon is not None,
            "nearest_item_is_slime_mold": nearest_item_is_slime_mold,
            "nearest_item_is_health_potion": nearest_item_is_health_potion,
            "nearest_item_is_weapon": nearest_item_is_weapon,
        }
        return state

    def _goal_satisfied(self, current_state: StateDict, goal_state: StateDict) -> bool:
        """Checks if the current state satisfies all conditions in the goal state."""
        if not goal_state:
            return True
        for key, desired_value in goal_state.items():
            current_value = current_state.get(key)

            satisfied = False
            if isinstance(desired_value, bool):
                satisfied = current_value == desired_value
            elif callable(desired_value):
                satisfied = (
                    desired_value(current_value) if current_value is not None else False
                )
            elif current_value is None:
                satisfied = False
            else:
                satisfied = current_value == desired_value

            if not satisfied:
                return False
        return True

    def _heuristic(self, state: StateDict, goal_state: StateDict) -> float:
        """Estimates the cost from the current state to the goal state."""
        cost: float = 0.0
        for key, desired_value in goal_state.items():
            current_value = state.get(key)
            is_satisfied = False
            if isinstance(desired_value, bool):
                is_satisfied = current_value == desired_value
            elif callable(desired_value):
                is_satisfied = (
                    desired_value(current_value) if current_value is not None else False
                )
            elif current_value is None:
                is_satisfied = False
            else:
                is_satisfied = current_value == desired_value
            if not is_satisfied:
                cost += 1.0

        if goal_state.get("is_not_starving", False) and state.get("is_starving", True):
            cost += 2.0
            if state.get("has_slime_mold"):
                cost += 0.1
            elif state.get("can_find_item"):
                cost += state.get("nearest_item_dist", 0) / 2.0

        if goal_state.get("is_healthy", False) and not state.get("is_healthy", False):
            cost += 1.0
            if state.get("has_health_potion"):
                cost += 0.1
            elif state.get("can_find_item"):
                cost += state.get("nearest_item_dist", 0) / 3.0

        if goal_state.get("flee_goal_achieved", False) and state.get(
            "can_find_enemy", False
        ):
            cost += max(
                0,
                ENEMY_NEARBY_FLEE_DISTANCE
                - state.get("nearest_enemy_dist", ENEMY_NEARBY_FLEE_DISTANCE),
            )

        if goal_state.get("has_weapon_equipped", False) and not state.get(
            "weapon_equipped", False
        ):
            if state.get("has_weapon_in_inv"):
                cost += 0.5
            elif state.get("can_find_item"):
                cost += state.get("nearest_item_dist", 0) / 4.0

        return cost

    def update_weights(
        self, executed_action_names: list[str], success_metric: float
    ) -> None:
        """Updates action weights based on the success of the executed plan."""
        if not executed_action_names:
            return

        learning_adjustment = (
            success_metric - LEARNING_SCORE_BASELINE
        ) * LEARNING_RATE_FACTOR
        updated_names = set()

        for name in executed_action_names:
            if name in updated_names:
                continue

            current_weight = self.action_weights[name]
            new_weight = current_weight * (1.0 - learning_adjustment)
            self.action_weights[name] = max(
                ACTION_WEIGHT_MIN, min(new_weight, ACTION_WEIGHT_MAX)
            )
            updated_names.add(name)


class AgentAI:
    """Manages the agent's GOAP planning and execution."""

    def __init__(self, world: WorldLike, rng: typing.Any):
        self.world: WorldLike = world
        self.rng = rng
        self.actions: list[Action] = self._define_actions()
        self.planner: GOAPPlanner = GOAPPlanner(self.actions)
        self.current_plan: ActionPlan = deque()
        self.current_goal: StateDict | None = None
        self.last_executed_plan_actions: list[str] = []
        self.last_action_name: str | None = None

    def _define_actions(self) -> list[Action]:
        actions_list: list[Action] = []

        def _get_target_pos(w: WorldLike, a: AgentLike, kind: str) -> OptionalPosition:
            target_id, _ = w.get_nearest_entity(a, kind)
            if target_id:
                target_obj = w.get_entity_object(target_id)
                return target_obj.get_position() if target_obj else None
            return None

        def _execute_move_to(w: WorldLike, a: AgentLike, target_kind: str) -> bool:
            target_pos = _get_target_pos(w, a, target_kind)
            if not target_pos:
                return False
            path = w.find_path(a.get_position(), target_pos)
            if path:
                next_x, next_y = path[0]
                if w.is_valid(next_x, next_y):
                    target_entity = w.grid[next_x][next_y]
                    if target_entity is None or target_entity.kind == "item":
                        return w.move_entity(a, next_x, next_y)
            return False

        def cost_simple(w: WorldLike, a: AgentLike) -> float:
            return 1.0

        def cost_attack(w: WorldLike, a: AgentLike) -> float:
            return 1.5

        def cost_explore(w: WorldLike, a: AgentLike) -> float:
            return 2.0

        def cost_flee(w: WorldLike, a: AgentLike) -> float:
            return 0.5

        def cost_wait(w: WorldLike, a: AgentLike) -> float:
            return 0.1

        def cost_pickup(w: WorldLike, a: AgentLike) -> float:
            return 0.8

        def cost_consume(w: WorldLike, a: AgentLike) -> float:
            return 0.5

        def cost_equip(w: WorldLike, a: AgentLike) -> float:
            return 0.6

        def cost_move_via_distance(w: WorldLike, a: AgentLike, kind: str) -> float:
            _, dist = w.get_nearest_entity(a, kind)
            return (dist + 0.1) if dist != float("inf") else float("inf")

        def pre_always_true(state: StateDict) -> bool:
            return True

        def pre_can_find_enemy(state: StateDict) -> bool:
            return state.get("can_find_enemy", False)

        def pre_enemy_adjacent(state: StateDict) -> bool:
            return state.get("enemy_is_adjacent", False)

        def pre_can_flee(state: StateDict) -> bool:
            return (
                state.get("can_find_enemy", False)
                and state.get("nearest_enemy_dist", float("inf"))
                < ENEMY_NEARBY_FLEE_DISTANCE
            )

        def pre_item_adjacent(state: StateDict) -> bool:
            return state.get("item_is_adjacent", False)

        def pre_inventory_not_full(state: StateDict) -> bool:
            return not state.get("inventory_full", True)

        def pre_has_slime_mold(state: StateDict) -> bool:
            return state.get("has_slime_mold", False)

        def pre_has_health_potion(state: StateDict) -> bool:
            return state.get("has_health_potion", False)

        def pre_has_weapon_in_inv(state: StateDict) -> bool:
            return state.get("has_weapon_in_inv", False)

        def pre_weapon_not_equipped(state: StateDict) -> bool:
            return not state.get("weapon_equipped", True)

        def effect_update_position(state: StateDict) -> StateDict:
            state["agent_pos"] = None
            state["enemy_is_adjacent"] = False
            state["item_is_adjacent"] = False
            state["nearest_enemy_dist"] = (
                state.get("nearest_enemy_dist", float("inf")) + 1
            )
            state["nearest_item_dist"] = (
                state.get("nearest_item_dist", float("inf")) + 1
            )
            return state

        def effect_attack_enemy(state: StateDict) -> StateDict:
            state["enemy_is_adjacent"] = False
            state["can_find_enemy"] = False
            return state

        def effect_pickup_item(state: StateDict) -> StateDict:
            state["item_is_adjacent"] = False
            state["can_find_item"] = False
            state["inventory_count"] = state.get("inventory_count", 0) + 1
            max_inventory = state.get("max_inventory", state["inventory_count"])
            state["inventory_full"] = state["inventory_count"] >= max_inventory
            state["has_any_item"] = True
            if state.get("nearest_item_is_slime_mold"):
                state["has_slime_mold"] = True
            if state.get("nearest_item_is_health_potion"):
                state["has_health_potion"] = True
            if state.get("nearest_item_is_weapon"):
                state["has_weapon_in_inv"] = True
            return state

        def effect_explore(state: StateDict) -> StateDict:
            state["explored_something"] = True
            return effect_update_position(state)

        def effect_flee(state: StateDict) -> StateDict:
            state["flee_goal_achieved"] = True
            state["enemy_is_adjacent"] = False
            state["nearest_enemy_dist"] = state.get("nearest_enemy_dist", 0) + 3
            return state

        def effect_wait(state: StateDict) -> StateDict:
            state["agent_hunger"] = state.get("agent_hunger", 0) - DEFEND_HUNGER_COST
            state["agent_health"] = state.get("agent_health", 0) + REST_HEALTH_REGEN
            state["is_healthy"] = state.get("agent_health", 0) > HEALTHY_THRESHOLD
            state["is_critically_injured"] = (
                state.get("agent_health", 0) < CRITICAL_HEALTH_THRESHOLD
            )
            return state

        def effect_consume_slime_mold(state: StateDict) -> StateDict:
            state["agent_hunger"] = (
                state.get("agent_hunger", 0) + SLIME_MOLD_HUNGER_RECOVERY
            )
            state["has_slime_mold"] = False
            state["is_starving"] = state.get("agent_hunger", 0) <= 0
            state["inventory_count"] = max(state.get("inventory_count", 1) - 1, 0)
            max_inventory = state.get("max_inventory", state["inventory_count"])
            state["inventory_full"] = state["inventory_count"] >= max_inventory
            return state

        def effect_consume_health_potion(state: StateDict) -> StateDict:
            state["agent_health"] = (
                state.get("agent_health", 0) + HEALTH_POTION_RECOVERY
            )
            state["has_health_potion"] = False
            state["is_healthy"] = state.get("agent_health", 0) > HEALTHY_THRESHOLD
            state["is_critically_injured"] = (
                state.get("agent_health", 0) < CRITICAL_HEALTH_THRESHOLD
            )
            state["inventory_count"] = max(state.get("inventory_count", 1) - 1, 0)
            max_inventory = state.get("max_inventory", state["inventory_count"])
            state["inventory_full"] = state["inventory_count"] >= max_inventory
            return state

        def effect_equip_weapon(state: StateDict) -> StateDict:
            state["has_weapon_in_inv"] = False
            state["weapon_equipped"] = True
            return state

        def execute_attack_adjacent_enemy(w: WorldLike, a: AgentLike) -> bool:
            enemy_id, _ = w.get_nearest_entity(a, "enemy")
            if enemy_id:
                enemy = w.get_entity_object(enemy_id)
                if enemy:
                    enemy.health -= a.get_attack_damage()
                    if enemy.health <= 0:
                        w.remove_entity(enemy)
                    return True
            return False

        def execute_explore(w: WorldLike, a: AgentLike) -> bool:
            if not hasattr(self.rng, "get_int"):
                raise TypeError("rng must provide get_int from GameRNG")
            directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
            idx = self.rng.get_int(0, len(directions) - 1)
            dx, dy = directions[idx]
            nx, ny = a.x + dx, a.y + dy
            if w.is_valid(nx, ny) and w.move_entity(a, nx, ny):
                return True
            return False

        def execute_flee(w: WorldLike, a: AgentLike) -> bool:
            enemy_id, _ = w.get_nearest_entity(a, "enemy")
            if not enemy_id:
                return False
            enemy = w.get_entity_object(enemy_id)
            if enemy is None:
                return False
            ax, ay = a.get_position()
            ex, ey = enemy.get_position()
            dx = 1 if ax < ex else -1 if ax > ex else 0
            dy = 1 if ay < ey else -1 if ay > ey else 0
            new_x, new_y = ax - dx, ay - dy
            if w.is_valid(new_x, new_y):
                return w.move_entity(a, new_x, new_y)
            return False

        def execute_wait(w: WorldLike, a: AgentLike) -> bool:
            a.hunger -= DEFEND_HUNGER_COST
            a.health = min(a.health + REST_HEALTH_REGEN, START_HEALTH)
            return True

        def execute_pickup_item(w: WorldLike, a: AgentLike) -> bool:
            item_id, _ = w.get_nearest_entity(a, "item")
            if not item_id:
                return False
            item_obj = w.get_entity_object(item_id)
            if not item_obj:
                return False
            if len(a.inventory) >= a.max_inventory:
                return False
            if isinstance(item_obj, dict):
                a.inventory.append(item_obj)
            else:
                a.inventory.append(getattr(item_obj, "item", item_obj))
            w.remove_entity(item_obj)
            return True

        def execute_consume_slime_mold(w: WorldLike, a: AgentLike) -> bool:
            for item in list(a.inventory):
                if _safe_item_name(item) == "Slime Mold":
                    a.inventory.remove(item)
                    a.hunger = min(a.hunger + SLIME_MOLD_HUNGER_RECOVERY, START_HUNGER)
                    return True
            return False

        def execute_consume_health_potion(w: WorldLike, a: AgentLike) -> bool:
            for item in list(a.inventory):
                if _safe_item_name(item) == "Health Potion":
                    a.inventory.remove(item)
                    a.health = min(a.health + HEALTH_POTION_RECOVERY, START_HEALTH)
                    return True
            return False

        def execute_equip_weapon(w: WorldLike, a: AgentLike) -> bool:
            weapon_to_equip = None
            for item in a.inventory:
                if (_safe_item_kind(item) or "").lower() == "weapon":
                    weapon_to_equip = item
                    break
            if weapon_to_equip is None:
                return False
            a.equipped_weapon = weapon_to_equip
            a.inventory.remove(weapon_to_equip)
            return True

        actions_list.extend(
            [
                Action(
                    "MoveToNearestItem",
                    lambda w, a: cost_move_via_distance(w, a, "item"),
                    pre_inventory_not_full,
                    effect_update_position,
                    lambda w, a: _execute_move_to(w, a, "item"),
                ),
                Action(
                    "PickupItem",
                    cost_pickup,
                    pre_item_adjacent,
                    effect_pickup_item,
                    execute_pickup_item,
                ),
                Action(
                    "ConsumeSlimeMold",
                    cost_consume,
                    pre_has_slime_mold,
                    effect_consume_slime_mold,
                    execute_consume_slime_mold,
                ),
                Action(
                    "ConsumeHealthPotion",
                    cost_consume,
                    pre_has_health_potion,
                    effect_consume_health_potion,
                    execute_consume_health_potion,
                ),
                Action(
                    "EquipWeapon",
                    cost_equip,
                    lambda s: (
                        s.get("has_weapon_in_inv", False)
                        and not s.get("weapon_equipped", True)
                    ),
                    effect_equip_weapon,
                    execute_equip_weapon,
                ),
                Action(
                    "MoveToNearestEnemy",
                    lambda w, a: cost_move_via_distance(w, a, "enemy"),
                    pre_can_find_enemy,
                    effect_update_position,
                    lambda w, a: _execute_move_to(w, a, "enemy"),
                ),
                Action(
                    "AttackAdjacentEnemy",
                    cost_attack,
                    pre_enemy_adjacent,
                    effect_attack_enemy,
                    execute_attack_adjacent_enemy,
                ),
                Action(
                    "Explore",
                    cost_explore,
                    pre_always_true,
                    effect_explore,
                    execute_explore,
                ),
                Action("Flee", cost_flee, pre_can_flee, effect_flee, execute_flee),
                Action("Wait", cost_wait, pre_always_true, effect_wait, execute_wait),
            ]
        )
        return actions_list

    def _select_goal(self, agent: AgentLike) -> StateDict:
        state = self.planner._get_world_state_representation(self.world, agent)

        if state["is_starving"]:
            if state["has_slime_mold"]:
                return {"is_not_starving": True}
            if state["can_find_item"] and not state["inventory_full"]:
                return {"has_slime_mold": True}
            return {"explored_something": True}

        if state["is_critically_injured"]:
            if state["has_health_potion"]:
                return {"is_healthy": True}
            if (
                state["can_find_enemy"]
                and state["nearest_enemy_dist"] < ENEMY_NEARBY_FLEE_DISTANCE
            ):
                return {"flee_goal_achieved": True}
            if state["can_find_item"] and not state["inventory_full"]:
                return {"has_health_potion": True}
            return {"is_healthy": True}

        if state["enemy_is_adjacent"]:
            if not state["weapon_equipped"] and state["has_weapon_in_inv"]:
                return {"has_weapon_equipped": True}
            return {"enemy_is_adjacent": False}

        if (
            agent.health < LOW_HEALTH_FLEE_THRESHOLD
            and state["can_find_enemy"]
            and state["nearest_enemy_dist"] < ENEMY_NEARBY_FLEE_DISTANCE
        ):
            return {"flee_goal_achieved": True}

        if agent.health < START_HEALTH:
            if state["has_health_potion"]:
                return {"is_healthy": True}

        if agent.hunger < START_HUNGER * 0.5:
            if state["has_slime_mold"]:
                return {"is_not_starving": True}
            if state["can_find_item"] and not state["inventory_full"]:
                return {"has_slime_mold": True}

        if not state["weapon_equipped"] and state["has_weapon_in_inv"]:
            if state["can_find_enemy"] or state["nearest_enemy_dist"] < float("inf"):
                return {"has_weapon_equipped": True}

        if state["can_find_enemy"] and agent.health > HEALTHY_THRESHOLD:
            return {"enemy_is_adjacent": False}

        if state["can_find_item"] and not state["inventory_full"]:
            return {"has_any_item": True}

        return {"explored_something": True}

    def _is_plan_still_valid(self, agent: AgentLike) -> bool:
        if not self.current_plan:
            return False
        next_action = self.current_plan[0]
        current_state_rep = self.planner._get_world_state_representation(
            self.world, agent
        )
        return next_action.check_preconditions(current_state_rep)

    def plan_for(self, agent: AgentLike) -> list[Action]:
        """Return a plan without executing it."""
        current_state_rep = self.planner._get_world_state_representation(
            self.world, agent
        )
        needs_replan = not self.current_plan or not self._is_plan_still_valid(agent)

        if self.current_goal and self.planner._goal_satisfied(
            current_state_rep, self.current_goal
        ):
            needs_replan = True

        if needs_replan:
            self.current_goal = self._select_goal(agent)
            new_plan_list = self.planner.plan(self.world, agent, self.current_goal)
            if new_plan_list:
                self.current_plan = deque(new_plan_list)
                self.last_executed_plan_actions = [a.name for a in self.current_plan]
            else:
                self.current_plan = deque()
                self.last_executed_plan_actions = []
        return list(self.current_plan)

    def act(self, agent: AgentLike) -> str | None:
        self.last_action_name = None
        current_state_rep = self.planner._get_world_state_representation(
            self.world, agent
        )

        needs_replan = False
        if not self.current_plan:
            needs_replan = True
        elif not self._is_plan_still_valid(agent):
            needs_replan = True
        elif self.current_goal:
            if self.planner._goal_satisfied(current_state_rep, self.current_goal):
                needs_replan = True

        if needs_replan:
            self.current_goal = self._select_goal(agent)
            new_plan_list = self.planner.plan(self.world, agent, self.current_goal)

            if new_plan_list:
                self.current_plan = deque(new_plan_list)
                self.last_executed_plan_actions = [a.name for a in self.current_plan]
            else:
                self.current_plan = deque()
                self.last_executed_plan_actions = []

                wait_action = next((a for a in self.actions if a.name == "Wait"), None)
                explore_action = next(
                    (a for a in self.actions if a.name == "Explore"), None
                )

                if wait_action and agent.health < START_HEALTH * 0.9:
                    if wait_action.execute and wait_action.execute(self.world, agent):
                        self.last_action_name = wait_action.name
                elif explore_action:
                    if explore_action.execute and explore_action.execute(
                        self.world, agent
                    ):
                        self.last_action_name = explore_action.name
                else:
                    random_move = next(
                        (a for a in self.actions if a.name == "Explore"), None
                    )
                    if (
                        random_move
                        and random_move.execute
                        and random_move.execute(self.world, agent)
                    ):
                        self.last_action_name = "RandomMove"

                if self.last_action_name:
                    self.last_executed_plan_actions = [self.last_action_name]
                return self.last_action_name

        if self.current_plan:
            action_to_execute = self.current_plan.popleft()
            if action_to_execute.execute and action_to_execute.execute(
                self.world, agent
            ):
                self.last_action_name = action_to_execute.name
            else:
                self.current_plan = deque()
                self.last_action_name = None
        else:
            self.last_action_name = None

        return self.last_action_name

    def learn(self, turns_survived: int) -> None:
        survival_score = turns_survived / MAX_TURNS
        health_score = 0.0
        agent_survived = self.world.agent is not None and self.world.agent.health > 0

        if agent_survived and self.world.agent:
            health_score = self.world.agent.health / START_HEALTH

        success_metric = (survival_score + health_score) / 2.0
        self.planner.update_weights(self.last_executed_plan_actions, success_metric)


__all__ = ["Action", "GOAPPlanner", "AgentAI"]
