import re


def update_game_state():
    with open("game/game_state.py", "r") as f:
        content = f.read()

    if "self.ai_memory" not in content:
        content = content.replace(
            "self.perception_alerted_monster_ids: list[int] = []",
            "self.perception_alerted_monster_ids: list[int] = []\n        from typing import Any\n        self.ai_memory: dict[int, dict[str, Any]] = {}",
        )
        with open("game/game_state.py", "w") as f:
            f.write(content)


def update_perception():
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
        DEFAULT_MEMORY_TURNS = 5
        
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
            
            # Prioritize the current signals
            confidence = 0.0
            signal_type = "idle"
            current_target_pos: tuple[int, int] | None = None
            memorable = False

            if visible_targets:
                signal_type = "visual"
                confidence = 1.0
                first = visible_targets[0]
                current_target_pos = (int(first["x"]), int(first["y"]))
                memorable = True
            elif heard_source:
                signal_type = "audio"
                confidence = 1.0
                current_target_pos = heard_source
                memorable = True
            elif scent_position:
                signal_type = "scent"
                confidence = 0.8
                current_target_pos = scent_position
                memorable = False  # DO NOT memorize scent gradients as a "last known" position

            # Update or retrieve from explicit memory
            last_known_position: tuple[int, int] | None = None

            if memorable and current_target_pos is not None:
                # Hard signal detected: refresh memory
                game_state.ai_memory[ent_id] = {
                    "pos": current_target_pos, 
                    "turns_left": DEFAULT_MEMORY_TURNS
                }
                last_known_position = current_target_pos 
            else:
                # No hard signal: check memory
                if ent_id in game_state.ai_memory:
                    mem = game_state.ai_memory[ent_id]
                    if mem["turns_left"] > 0:
                        if not current_target_pos:
                            # Only fallback to memory if we don't even have a scent
                            signal_type = "memory"
                            confidence = 0.5
                        last_known_position = mem["pos"]
                        mem["turns_left"] -= 1
                    else:
                        del game_state.ai_memory[ent_id]
                
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

    pattern = re.compile(
        r"def gather_perception_snapshot\(game_state: GameState\) -> PerceptionSnapshot:.*?return PerceptionSnapshot\([^)]+\)",
        re.DOTALL,
    )
    content = pattern.sub(new_snapshot, content)
    with open("game/ai/perception.py", "w") as f:
        f.write(content)


def update_strategy():
    with open("game/ai/strategy.py", "r") as f:
        content = f.read()

    if (
        "from typing import TYPE_CHECKING, Any" not in content
        and "from typing import Any" not in content
    ):
        content = content.replace(
            "from typing import TYPE_CHECKING", "from typing import TYPE_CHECKING, Any"
        )

    if "def _get_priority_signal" not in content:
        helper = '''def _get_priority_signal(
    entity_id: int, 
    perception: Any
) -> tuple[str, tuple[int, int]] | None:
    """Return the highest priority signal type and its target coordinate."""
    if not hasattr(perception, "entity_facts"):
        return None
    
    fact = perception.entity_facts.get(int(entity_id))
    if not fact:
        return None
        
    if fact.visible_targets:
        first = fact.visible_targets[0]
        return "visual", (int(first.get("x")), int(first.get("y")))
    if fact.heard_source:
        return "audio", fact.heard_source
    if fact.scent_position:
        return "scent", fact.scent_position
    if fact.last_known_position:
        return "memory", fact.last_known_position
        
    return None

'''
        content = content.replace(
            "def charge_behavior(", helper + "def charge_behavior("
        )

    charge_repl = """def charge_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    entity_id = int(entity_row["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    signal_type, target_pos = signal
    dx, dy = _step_towards((int(entity_row.get("x")), int(entity_row.get("y"))), target_pos)
    _move(entity_row, dx, dy, game_state)"""
    content = re.sub(
        r"def charge_behavior\(.*?\) -> None:.*?_move\(entity_row, dx, dy, game_state\)",
        charge_repl,
        content,
        flags=re.DOTALL,
    )

    flee_repl = """def flee_behavior(
    entity_row: series,
    game_state: GameState,
    perception: Any,
) -> None:
    entity_id = int(entity_row["entity_id"])
    signal = _get_priority_signal(entity_id, perception)
    if not signal:
        return

    signal_type, target_pos = signal
    sx, sy = int(entity_row.get("x")), int(entity_row.get("y"))
    tx, ty = target_pos
    dx = 0 if tx == sx else (-1 if tx > sx else 1)
    dy = 0 if ty == sy else (-1 if ty > sy else 1)
    _move(entity_row, dx, dy, game_state)"""
    content = re.sub(
        r"def flee_behavior\(.*?\) -> None:.*?_move\(entity_row, dx, dy, game_state\)",
        flee_repl,
        content,
        flags=re.DOTALL,
    )

    with open("game/ai/strategy.py", "w") as f:
        f.write(content)


def update_goap():
    with open("game/ai/goap.py", "r") as f:
        content = f.read()

    goap_repl = '''def _action_move_attack(
    entity_row: Any,
    game_state: GameState,
    rng: GameRNG,
    perception: Any,
) -> bool:
    """Basic behaviour: move toward priority signal or wander."""
    entity_id = int(entity_row["entity_id"])
    x, y = int(entity_row["x"]), int(entity_row["y"])

    move: tuple[int, int] | None = None
    target_pos: tuple[int, int] | None = None
    active_signal: str = "none"

    # Consume structured perception facts based on strict priority
    if hasattr(perception, "entity_facts"):
        fact = perception.entity_facts.get(entity_id)
        if fact:
            if fact.visible_targets:
                first_target = fact.visible_targets[0]
                target_pos = (int(first_target.get("x")), int(first_target.get("y")))
                active_signal = "visual"
            elif fact.heard_source:
                target_pos = fact.heard_source
                active_signal = "audio"
            elif fact.scent_position:
                target_pos = fact.scent_position
                active_signal = "scent"
            elif fact.last_known_position:
                target_pos = fact.last_known_position
                active_signal = "memory"

    # 1. Move towards highest-priority target
    if target_pos is not None:
        tx, ty = target_pos
        pathfinder = _ensure_pathfinder(game_state)
        # Note: compute_field expects (y, x) tuples
        pathfinder.compute_field([(ty, tx)])
        pdx, pdy = pathfinder.get_flow_vector(y, x)
        
        nx, ny = x + pdx, y + pdy
        if not (0 <= nx < game_state.map_width and 0 <= ny < game_state.map_height):
            # Fallback simple step if pathfinding gives an out-of-bounds or zero vector
            pdx = 0 if tx == x else (-1 if tx < x else 1)
            pdy = 0 if ty == y else (-1 if ty < y else 1)
        move = (pdx, pdy)

    # 2. Else: Idle/Wander/Patrol
    if move is None:
        if not hasattr(rng, "get_int"):
            raise TypeError("rng must provide get_int from GameRNG")
        idx = rng.get_int(0, len(directions) - 1)
        move = directions[idx]

    dx, dy = move
    moved = movement_system.try_move(entity_id, dx, dy, game_state)

    log.debug(
        "GOAP AI entity processed",
        entity_id=entity_id,
        pos=(x, y),
        target_pos=target_pos,
        signal=active_signal,
        dx=dx,
        dy=dy,
        moved=moved,
    )
    return True'''

    content = re.sub(
        r"def _action_move_attack\(.*?\) -> bool:.*?return True",
        goap_repl,
        content,
        flags=re.DOTALL,
    )

    if (
        "from typing import TYPE_CHECKING" in content
        and "Any" not in content[: content.find("import numpy")]
    ):
        content = content.replace(
            "from typing import TYPE_CHECKING", "from typing import TYPE_CHECKING, Any"
        )

    with open("game/ai/goap.py", "w") as f:
        f.write(content)


if __name__ == "__main__":
    update_game_state()
    update_perception()
    update_strategy()
    update_goap()
    print("Done")
