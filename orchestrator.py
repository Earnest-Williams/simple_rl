"""Canonical pipeline entrypoint for simple_rl subsystems."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import numpy as np
import polars as pl

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
os.environ.setdefault("PYTHONPATH", str(REPO_ROOT))

from Dungeon import core, processor, shaper
from auto.simulation import (
    PASSIVE_HUNGER_PER_TURN,
    REST_HEALTH_REGEN,
    START_HEALTH,
    STARVATION_HEALTH_DAMAGE,
    AgentAI,
    World,
    enemy_act,
)
from engine.render_lighting import apply_memory_fade
from utils.game_rng import GameRNG

DEFAULT_SEED = int(time.time() * 1000)
DEFAULT_MAX_NODES = 400
DEFAULT_MAX_DEPTH = 50
DEFAULT_CA_ITERATIONS = 8
DEFAULT_OUTPUT_FILE = "generated_dungeon.arrow"
DEFAULT_GRID_SIZE = 128


def shaped_map_to_arrays(map_df: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Convert a shaped map DataFrame into tile + height grids."""
    required_columns = {"x", "y", "material_id", "height"}
    missing = required_columns - set(map_df.columns)
    if missing:
        raise ValueError(f"Missing columns in shaped map DataFrame: {sorted(missing)}")

    x_vals = map_df.get_column("x").to_numpy()
    y_vals = map_df.get_column("y").to_numpy()
    mat_ids = map_df.get_column("material_id").to_numpy()
    heights = map_df.get_column("height").to_numpy()

    x_int = np.rint(x_vals).astype(np.int32)
    y_int = np.rint(y_vals).astype(np.int32)
    min_x, max_x = int(x_int.min()), int(x_int.max())
    min_y, max_y = int(y_int.min()), int(y_int.max())

    width = max_x - min_x + 1
    height = max_y - min_y + 1

    tile_grid = np.zeros((height, width), dtype=np.uint16)
    height_grid = np.zeros((height, width), dtype=np.float32)

    col_x = x_int - min_x
    col_y = y_int - min_y
    tile_grid[col_y, col_x] = mat_ids.astype(np.uint16)
    height_grid[col_y, col_x] = heights.astype(np.float32)

    return tile_grid, height_grid


def run_headless_sim(
    world: World,
    agent_ai: AgentAI,
    rng: GameRNG,
    max_turns: int,
) -> str:
    """Run a lightweight headless sim loop using shared RNG."""
    world.reset(rng=rng)
    agent = world.agent
    if not agent:
        raise RuntimeError("Agent was not created in the world reset.")

    outcome = "Unknown"
    while agent.health > 0 and world.turn < max_turns:
        world.turn += 1
        action_taken = agent_ai.act(agent)

        new_hunger = max(0.0, agent.hunger - PASSIVE_HUNGER_PER_TURN)
        world.update_entity_hunger(agent.id, new_hunger)
        if agent.hunger <= 0:
            new_health = max(0.0, agent.health - STARVATION_HEALTH_DAMAGE)
            world.update_entity_health(agent.id, new_health)
            if new_health <= 0:
                outcome = "Starvation"
                break

        current_enemy_ids = list(world.entities_by_kind["enemy"].keys())
        for enemy_id in current_enemy_ids:
            if enemy_id in world.entities:
                enemy_act(world.entities[enemy_id], world, rng)
                if agent.health <= 0:
                    outcome = "KilledByEnemy"
                    break
        if agent.health <= 0:
            break

        world.spawn_random_enemy(rng=rng)

        agent_rested = action_taken == "Wait" or action_taken is None
        if agent_rested and agent.health < START_HEALTH:
            new_health = min(START_HEALTH, agent.health + REST_HEALTH_REGEN)
            if new_health > agent.health:
                world.update_entity_health(agent.id, new_health)

    if agent.health > 0 and world.turn >= max_turns:
        outcome = "Survived (MaxTurns)"
    elif agent.health > 0:
        outcome = "Survived"
    elif outcome == "Unknown":
        outcome = "Defeated"
    return outcome


def setup_lighting_context(rng: GameRNG) -> dict[str, object]:
    """Prepare lighting helpers that require the shared RNG."""
    return {"apply_memory_fade": apply_memory_fade, "rng": rng}


def run_pipeline(
    seed: int = DEFAULT_SEED,
    grid_size: int = DEFAULT_GRID_SIZE,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    ca_iterations: int = DEFAULT_CA_ITERATIONS,
    output_file: str = DEFAULT_OUTPUT_FILE,
    run_sim: bool = False,
    max_turns: int = 200,
) -> dict[str, object]:
    """Run the dungeon + world pipeline using a single shared RNG."""
    rng = GameRNG(seed=seed, metrics=False)

    generator = core.CaveGenerator(
        max_nodes=max_nodes,
        max_depth=max_depth,
        rng=rng,
    )
    generator.grow()
    raw_backbone = {"nodes": [n.to_dict() for n in generator.nodes]}

    augmented_nodes, augmented_node_map = processor.process_backbone_graph(raw_backbone)
    if not augmented_nodes:
        raise RuntimeError("Processor returned empty node list.")

    shaped_map = shaper.generate_shaped_cave(
        augmented_nodes,
        augmented_node_map,
        rng=rng,
        ca_iterations=ca_iterations,
    )
    if shaped_map is None or shaped_map.is_empty():
        raise RuntimeError("Shaper did not return a valid map DataFrame.")

    shaped_map.write_ipc(output_file)
    tile_grid, height_grid = shaped_map_to_arrays(shaped_map)

    world = World(size=grid_size, rng=rng)
    agent_ai = AgentAI(world=world, rng=rng)
    lighting_context = setup_lighting_context(rng)

    sim_outcome = None
    if run_sim:
        sim_outcome = run_headless_sim(world, agent_ai, rng, max_turns=max_turns)

    return {
        "rng": rng,
        "backbone_nodes": len(generator.nodes),
        "map_dataframe": shaped_map,
        "tile_grid": tile_grid,
        "height_grid": height_grid,
        "world": world,
        "agent_ai": agent_ai,
        "lighting_context": lighting_context,
        "sim_outcome": sim_outcome,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the simple_rl orchestrator.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="RNG seed.")
    parser.add_argument("--max-nodes", type=int, default=DEFAULT_MAX_NODES)
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH)
    parser.add_argument("--ca-iterations", type=int, default=DEFAULT_CA_ITERATIONS)
    parser.add_argument("--output-file", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--grid-size", type=int, default=DEFAULT_GRID_SIZE)
    parser.add_argument("--run-sim", action="store_true")
    parser.add_argument("--max-turns", type=int, default=200)
    args = parser.parse_args()

    results = run_pipeline(
        seed=args.seed,
        grid_size=args.grid_size,
        max_nodes=args.max_nodes,
        max_depth=args.max_depth,
        ca_iterations=args.ca_iterations,
        output_file=args.output_file,
        run_sim=args.run_sim,
        max_turns=args.max_turns,
    )
    print(f"Pipeline complete. Nodes: {results['backbone_nodes']}")
    if args.run_sim:
        print(f"Simulation outcome: {results['sim_outcome']}")


if __name__ == "__main__":
    main()
