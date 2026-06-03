import sys
import glob
import re


def update_perception_py():
    with open("game/ai/perception.py", "r") as f:
        content = f.read()

    new_snapshot = '''def gather_perception_snapshot(game_state: GameState) -> PerceptionSnapshot:
    """Return structured AI-facing perception facts without breaking legacy callers."""
    from pathfinding.perception_systems import get_scent
    
    noise_map, scent_map, los_map = gather_perception(game_state)
    facts: dict[int, PerceptionFact] = {}

    flow_idx = int(FlowType.REAL_NOISE)
    center_y = int(game_state.perception_flow_centers[flow_idx, 0])
    center_x = int(game_state.perception_flow_centers[flow_idx, 1])
    global_heard_source = (center_x, center_y)
    
    alerted_set = set(game_state.perception_alerted_monster_ids)

    df = getattr(game_state.entity_registry, "entities_df", None)
    if df is not None and not df.is_empty():
        active_df = df.filter(
            (pl.col("is_active") == True) & (pl.col("entity_id") != game_state.player_id)
        )
        cave_when = game_state.perception_cave_when
        game_map = game_state.game_map
        
        for row in active_df.iter_rows(named=True):
            if not (row.get("ai_type") or row.get("species") or row.get("intelligence") is not None):
                continue
                
            ent_id = int(row["entity_id"])
            ex = row.get("x")
            ey = row.get("y")
            if ex is None or ey is None:
                continue
            ex, ey = int(ex), int(ey)
            
            # 1. Visible targets
            visible_targets = find_visible_enemies(row, game_state, los_map)
            
            # 2. Audio facts
            heard_source = global_heard_source if ent_id in alerted_set else None
            heard_flow = "real_noise" if heard_source else None
            
            # 3. Scent facts
            current_scent = get_scent(cave_when, ey, ex)
            best_scent_val = current_scent
            best_scent_pos = None
            
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = ex + dx, ey + dy
                if 0 <= nx < game_map.width and 0 <= ny < game_map.height:
                    # check passable - transparent is True for walkable
                    if game_map.transparent[ny, nx]:
                        n_scent = get_scent(cave_when, ny, nx)
                        if n_scent > best_scent_val:
                            best_scent_val = n_scent
                            best_scent_pos = (nx, ny)
            
            scent_position = best_scent_pos
            scent_strength = best_scent_val if best_scent_pos else current_scent
            
            # 5. Priority: LOS > fresh noise > fresh scent > last-known memory > idle
            last_known_position = None
            signal_type = "idle"
            confidence = 0.0
            
            if visible_targets:
                signal_type = "visual"
                confidence = 1.0
                first = visible_targets[0]
                last_known_position = (int(first["x"]), int(first["y"]))
            elif heard_source:
                signal_type = "audio"
                confidence = 1.0
                last_known_position = heard_source
            elif scent_position:
                signal_type = "scent"
                confidence = 0.8
                last_known_position = scent_position
                
            facts[ent_id] = PerceptionFact(
                signal_type=signal_type,
                confidence=confidence,
                visible_targets=visible_targets,
                heard_source=heard_source,
                heard_flow=heard_flow,
                scent_strength=scent_strength,
                scent_position=scent_position,
                last_known_position=last_known_position,
            )

    log.debug("Perception snapshot generated", facts_count=len(facts))
    return PerceptionSnapshot(
        los_map=los_map,
        entity_facts=facts,
        debug_noise_map=noise_map,
        debug_scent_map=scent_map,
    )'''

    # Replace the existing function
    pattern = re.compile(
        r"def gather_perception_snapshot\(game_state: GameState\) -> PerceptionSnapshot:.*?return PerceptionSnapshot\([^)]+\)",
        re.DOTALL,
    )
    content = pattern.sub(new_snapshot, content)

    with open("game/ai/perception.py", "w") as f:
        f.write(content)


def update_game_state_py():
    with open("game/game_state.py", "r") as f:
        content = f.read()
    content = content.replace(
        "from game.ai.perception import gather_perception",
        "from game.ai.perception import gather_perception, gather_perception_snapshot",
    )
    content = content.replace(
        "perception = gather_perception(self)",
        "perception = gather_perception_snapshot(self)",
    )
    with open("game/game_state.py", "w") as f:
        f.write(content)


def update_ai_system_py():
    with open("game/systems/ai_system.py", "r") as f:
        content = f.read()
    content = content.replace(
        "perception: tuple[np.ndarray, np.ndarray, np.ndarray] | None,",
        "perception: Any | None,",
    )
    with open("game/systems/ai_system.py", "w") as f:
        f.write(content)


def update_strategy_py():
    with open("game/ai/strategy.py", "r") as f:
        content = f.read()

    # We want to replace perception argument and unpack logic for charge and flee
    charge_repl = """def charge_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    if hasattr(perception, "entity_facts"):
        fact = perception.entity_facts.get(int(entity_row["entity_id"]))
        enemies = fact.visible_targets if fact else []
    else:
        noise, scent, los = perception
        enemies = find_visible_enemies(entity_row, game_state, los)
    if not enemies:"""

    flee_repl = """def flee_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    if hasattr(perception, "entity_facts"):
        fact = perception.entity_facts.get(int(entity_row["entity_id"]))
        enemies = fact.visible_targets if fact else []
    else:
        noise, scent, los = perception
        enemies = find_visible_enemies(entity_row, game_state, los)
    if not enemies:"""

    # Regex replacements
    content = re.sub(
        r"def charge_behavior\(.*?\) -> None:.*?if not enemies:",
        charge_repl,
        content,
        flags=re.DOTALL,
    )
    content = re.sub(
        r"def flee_behavior\(.*?\) -> None:.*?if not enemies:",
        flee_repl,
        content,
        flags=re.DOTALL,
    )

    # Also update smart_kobold and dispatch_strategy to accept Any
    content = content.replace(
        "perception: tuple[np.ndarray, np.ndarray, np.ndarray]", "perception: Any"
    )

    with open("game/ai/strategy.py", "w") as f:
        f.write(content)


def update_other_ai_files():
    for fpath in glob.glob("game/ai/*.py"):
        if fpath.endswith(("strategy.py", "perception.py", "__init__.py")):
            continue

        with open(fpath, "r") as f:
            content = f.read()

        if (
            "noise_map, scent_map, los_map = perception" not in content
            and "_, _, los_map = perception" not in content
        ):
            # Change type hints anyway
            content = content.replace(
                "perception: tuple[np.ndarray, np.ndarray, np.ndarray]",
                "perception: Any",
            )
            with open(fpath, "w") as f:
                f.write(content)
            continue

        # Replace unpack with conditional extract
        unpack_repl = """    if hasattr(perception, "los_map"):
        noise_map = perception.debug_noise_map
        scent_map = perception.debug_scent_map
        los_map = perception.los_map
    else:
        noise_map, scent_map, los_map = perception"""

        content = content.replace(
            "    noise_map, scent_map, los_map = perception", unpack_repl
        )
        content = content.replace("    _, _, los_map = perception", unpack_repl)

        # Change type hint
        content = content.replace(
            "perception: tuple[np.ndarray, np.ndarray, np.ndarray]", "perception: Any"
        )

        # In goap.py, try to utilize fact.scent_position if available
        if fpath.endswith("goap.py"):
            goap_repl = """    if move is None:
        if hasattr(perception, "entity_facts"):
            fact = perception.entity_facts.get(int(entity_id))
            if fact and fact.scent_position:
                move = (fact.scent_position[0] - x, fact.scent_position[1] - y)
        if move is None:
            current_scent = scent_map[y, x]
            best_scent = current_scent
            for ndx, ndy in directions:
                nx, ny = x + ndx, y + ndy
                if (
                    0 <= nx < scent_map.shape[1]
                    and 0 <= ny < scent_map.shape[0]
                    and scent_map[ny, nx] > best_scent
                ):
                    best_scent = scent_map[ny, nx]
                    move = (ndx, ndy)"""

            content = content.replace(
                """    if move is None:
        current_scent = scent_map[y, x]
        best_scent = current_scent
        for ndx, ndy in directions:
            nx, ny = x + ndx, y + ndy
            if (
                0 <= nx < scent_map.shape[1]
                and 0 <= ny < scent_map.shape[0]
                and scent_map[ny, nx] > best_scent
            ):
                best_scent = scent_map[ny, nx]
                move = (ndx, ndy)""",
                goap_repl,
            )

        with open(fpath, "w") as f:
            f.write(content)


if __name__ == "__main__":
    update_perception_py()
    update_game_state_py()
    update_ai_system_py()
    update_strategy_py()
    update_other_ai_files()
    print("Done refactoring AI.")
