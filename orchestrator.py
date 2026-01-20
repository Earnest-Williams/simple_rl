"""Canonical pipeline entrypoint for simple_rl subsystems."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import orjson
import polars as pl
from pydantic import BaseModel, ConfigDict, TypeAdapter, ValidationError
from scipy.spatial import KDTree

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
from utils.shaped_map import load_shaped_map_as_arrays

DEFAULT_SEED = int(time.time() * 1000)
DEFAULT_MAX_NODES = 400
DEFAULT_MAX_DEPTH = 50
DEFAULT_CA_ITERATIONS = 8
DEFAULT_OUTPUT_FILE = "generated_dungeon.arrow"
DEFAULT_GRID_SIZE = 128

log = logging.getLogger(__name__)


class NodeMapRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    node_id: int
    tile_x: int
    tile_y: int
    node_x: float | None = None
    node_y: float | None = None
    df_index: int | None = None


NODE_MAP_ROWS_ADAPTER = TypeAdapter(List[NodeMapRow])


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

    # ----------------------------
    # Exact node -> tile mapping
    # ----------------------------
    # Build a nearest-tile mapping from augmented_nodes (processor output) to the
    # shaped_map's tiles (x,y). We also embed a `node_id` column into the shaped_map
    # (first node wins if many nodes map to same tile) and write a node_map JSON.
    if "x" in shaped_map.columns and "y" in shaped_map.columns:
        df = shaped_map
        x_arr = df.get_column("x").to_numpy().astype(np.float64)
        y_arr = df.get_column("y").to_numpy().astype(np.float64)

        node_map_rows: List[Dict[str, Any]] = []
        node_id_col = np.full(len(df), -1, dtype=np.int32)

        if isinstance(augmented_nodes, list) and len(df) > 0:
            node_ids: List[int] = []
            node_coords: List[Tuple[float, float]] = []
            for node in augmented_nodes:
                nid = int(node.get("id"))
                nx = float(node.get("x", 0.0))
                ny = float(node.get("y", 0.0))
                node_ids.append(nid)
                node_coords.append((nx, ny))

            if node_ids:
                tile_coords = np.column_stack((x_arr, y_arr))
                node_points = np.array(node_coords, dtype=np.float64)
                tree = KDTree(tile_coords)
                _, idxs = tree.query(node_points)

                # Pre-compute rounded tile coordinates for efficiency
                tile_x_arr = np.rint(x_arr[idxs]).astype(np.int32)
                tile_y_arr = np.rint(y_arr[idxs]).astype(np.int32)

                for i, ((nid, (nx, ny)), idx) in enumerate(zip(
                    zip(node_ids, node_coords), idxs.tolist()
                )):
                    tile_x = int(tile_x_arr[i])
                    tile_y = int(tile_y_arr[i])
                    node_map_rows.append(
                        {
                            "node_id": nid,
                            "node_x": nx,
                            "node_y": ny,
                            "tile_x": tile_x,
                            "tile_y": tile_y,
                            "df_index": int(idx),
                        }
                    )
                    if node_id_col[idx] == -1:
                        node_id_col[idx] = nid

        shaped_map = shaped_map.with_columns(
            pl.Series(name="node_id", values=node_id_col)
        )
        shaped_map.write_ipc(output_file)

        node_map_path = Path(f"{output_file}.node_map.json")
        try:
            with node_map_path.open("wb") as nmf:
                nmf.write(orjson.dumps(node_map_rows, option=orjson.OPT_INDENT_2))
        except OSError as exc:
            log.exception("Failed to write node map JSON: %s", exc)
    else:
        log.warning("Shaped map missing x/y columns; skipping node->tile mapping.")

    map_arrays = load_shaped_map_as_arrays(output_file)
    node_to_tile: Dict[int, Tuple[int, int]] = {}
    origin_obj = map_arrays.get("origin", (0, 0))
    if (
        isinstance(origin_obj, tuple)
        and len(origin_obj) == 2
        and isinstance(origin_obj[0], (int, float))
        and isinstance(origin_obj[1], (int, float))
    ):
        min_x = int(origin_obj[0])
        min_y = int(origin_obj[1])
    else:
        min_x = 0
        min_y = 0

    node_map_json_path = Path(f"{output_file}.node_map.json")
    if node_map_json_path.exists():
        try:
            with node_map_json_path.open("rb") as node_map_file:
                node_map_rows_local = orjson.loads(node_map_file.read())
            node_map_rows = NODE_MAP_ROWS_ADAPTER.validate_python(
                node_map_rows_local
            )
            # Vectorize coordinate transformations for efficiency
            tile_ys = np.array([row_obj.tile_y for row_obj in node_map_rows], dtype=np.float64)
            tile_xs = np.array([row_obj.tile_x for row_obj in node_map_rows], dtype=np.float64)
            rows = np.rint(tile_ys - min_y).astype(np.int32)
            cols = np.rint(tile_xs - min_x).astype(np.int32)

            for i, row_obj in enumerate(node_map_rows):
                node_to_tile[row_obj.node_id] = (int(rows[i]), int(cols[i]))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            log.exception("Failed to load node_map JSON: %s", exc)
    elif isinstance(augmented_nodes, list):
        # Vectorize node coordinate transformations for efficiency
        node_ids = np.array([int(node.get("id")) for node in augmented_nodes], dtype=np.int32)
        node_xs = np.array([float(node.get("x", 0.0)) for node in augmented_nodes], dtype=np.float64)
        node_ys = np.array([float(node.get("y", 0.0)) for node in augmented_nodes], dtype=np.float64)
        cols = np.rint(node_xs - min_x).astype(np.int32)
        rows = np.rint(node_ys - min_y).astype(np.int32)

        for i in range(len(augmented_nodes)):
            node_to_tile[int(node_ids[i])] = (int(rows[i]), int(cols[i]))
    tile_grid = map_arrays["tile_id_grid"]
    height_grid = map_arrays.get("height_grid")
    if height_grid is None:
        height_grid = np.full(tile_grid.shape, 0.0, dtype=np.float32)

    world = World(size=grid_size, rng=rng)
    agent_ai = AgentAI(world=world, rng=rng)
    lighting_context = setup_lighting_context(rng)

    sim_outcome = None
    if run_sim:
        sim_outcome = run_headless_sim(world, agent_ai, rng, max_turns=max_turns)

    generator_steps = [step.to_dict() for step in getattr(generator, "steps", [])]

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
        "raw_backbone": raw_backbone,
        "augmented_nodes": augmented_nodes,
        "augmented_node_map": augmented_node_map,
        "generator_steps": generator_steps,
        "node_to_tile": node_to_tile,
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
