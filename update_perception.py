import sys
import re

def update_readme():
    with open("pathfinding/README.md", "a") as f:
        f.write("""
## Production Flow and Scent Contract

### Flow slices

Production noise fields are stored in `GameState.perception_cave_cost`,
indexed by `pathfinding.perception_systems.FlowType`.

Current flow types are:

- `PASS_DOORS`: door-capable movement flow; closed/secret doors add a passage
  penalty.
- `NO_DOORS`: door-blocked flow; closed/secret doors stop propagation.
- `REAL_NOISE`: player/world noise; closed/secret doors dampen propagation.
- `MONSTER_NOISE`: monster-originated noise; uses real-noise door dampening.

`update_noise()` rebuilds exactly one selected flow slice at a time and records
that slice origin in `perception_flow_centers`.

If richer sound behavior is needed, the next intended expansion is two
semantic production slices: player noise and world/monster noise. Arbitrary
per-source slices are intentionally out of scope for the current contract.

### Noise source semantics

`GameState.update_perception_fields()` may receive multiple queued
`NoiseEvent`s in one update.

Production noise semantics are loudest-event-wins:

- All queued noise events contribute to the legacy/debug `game_map.noise_map`.
- Only the loudest queued noise event is used to rebuild the production
  pathfinding flow slice.
- The selected event's `flow_type` chooses which `FlowType` slice is rebuilt.
- The selected event's position is stored in `perception_flow_centers`.
- If no noise events are queued, production noise costs are reset to infinity.

The current production contract does not model multiple simultaneous
pathfinding sound sources. Supporting multiple active sound sources requires a
separate source-attribution design.

### Scent lifecycle

Production turns call `GameState.update_perception_fields(include_player_scent=True)`.
That automatically appends a player `ScentEvent` at the current player position.

Normal gameplay systems should not enqueue explicit player scent events during
ordinary turns. Player scent is produced by the GameState lifecycle.

Explicit `ScentEvent`s remain supported for tests, legacy callers, scripted
events, and future non-player scent mechanics.

On update:

- All scent events contribute to the legacy/debug `game_map.scent_map`.
- The production Sil-style scent field applies only the latest scent event in
  the update batch.
- During normal production turns, the automatically appended player scent event
  is latest, so player scent is authoritative.
- `gather_perception()` may process queued events with
  `include_player_scent=False` for compatibility callers that invoke perception
  directly.

The production scent field stores freshness stamps in `perception_cave_when`;
it is not an additive arbitrary scent-intensity map.

`update_smell()` ages the global scent counter, lays a 5x5 stamp around the
source, skips sentinel corners, blocks walls and secret doors, and applies a
closed-door freshness penalty.

### AI-facing expectations

AI consumers should treat production perception as compact turn-level facts:

- Audio perception currently exposes one selected heard source per update,
  derived from the selected production noise flow center.
- `gather_perception_snapshot()` uses the `REAL_NOISE` flow center as the
  current heard source for alerted monsters.
- Scent perception exposes Sil-style freshness stamps suitable for scent
  following, trail heuristics, and last-known-position logic.
- `game_map.noise_map` and `game_map.scent_map` are compatibility/debug heat
  maps. They are not the authoritative pathfinding flow contract.
- AI should not assume that every queued noise or scent event becomes a distinct
  production source.
""")

def update_game_state():
    with open("game/game_state.py", "r") as f:
        content = f.read()

    # Find where to add noise comment
    noise_str = "if noise_events:\n            loudest = max(noise_events, key=lambda event: event_xy_intensity(event)[2])"
    noise_repl = """# Production noise is intentionally loudest-event-wins. The debug radius map
        # receives every queued event, but the pathfinding flow field represents one
        # authoritative investigate source for this update.
        if noise_events:
            loudest = max(noise_events, key=lambda event: event_xy_intensity(event)[2])"""
    content = content.replace(noise_str, noise_repl)

    # Find where to add scent comment
    scent_str = "if scent_events:\n            latest = scent_events[-1]"
    scent_repl = """# Production scent applies the latest scent event only. During normal turns,
        # automatic player scent is appended after queued scent events and is therefore
        # authoritative.
        if scent_events:
            latest = scent_events[-1]"""
    content = content.replace(scent_str, scent_repl)

    with open("game/game_state.py", "w") as f:
        f.write(content)

def update_tests():
    with open("tests/test_perception_systems.py", "a") as f:
        f.write("""

def test_update_perception_fields_uses_loudest_noise_for_production_flow() -> None:
    game_map = GameMap(width=7, height=7)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=11,
        enable_sound=False,
        enable_ai=False,
    )
    
    # We can use namedtuples from perception_systems or simple tuples.
    # The codebase usually uses tuples or dict-like for legacy compatibility in tests.
    # Since existing tests use tuples, we'll use tuples but pad them if needed.
    # If the system expects flow_type as 4th element:
    game_state.noise_events.extend(
        [
            (1, 1, 1.0, FlowType.REAL_NOISE),
            (5, 5, 20.0, FlowType.REAL_NOISE),
            (3, 3, 3.0, FlowType.REAL_NOISE),
        ]
    )

    game_state.update_perception_fields(include_player_scent=False)

    flow_idx = int(FlowType.REAL_NOISE)
    assert tuple(game_state.perception_flow_centers[flow_idx]) == (5, 5)


def test_update_perception_fields_resets_noise_flow_when_no_noise_events() -> None:
    game_map = GameMap(width=5, height=5)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=11,
        enable_sound=False,
        enable_ai=False,
    )
    
    # Fill with dummy value
    game_state.perception_cave_cost.fill(42)
    game_state.update_perception_fields(include_player_scent=False)
    
    infinity = np.iinfo(np.int32).max // 2
    assert np.all(game_state.perception_cave_cost == infinity)


def test_update_perception_fields_appends_player_scent_in_production_turn() -> None:
    game_map = GameMap(width=5, height=5)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=11,
        enable_sound=False,
        enable_ai=False,
    )
    
    game_state.update_perception_fields(include_player_scent=True)
    assert get_scent(game_state.perception_cave_when, 2, 2) > 0


def test_update_perception_fields_latest_scent_event_wins_for_production_scent() -> None:
    game_map = GameMap(width=7, height=7)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=12,
        enable_sound=False,
        enable_ai=False,
    )
    
    game_state.scent_events.extend(
        [
            (1, 1, 5.0),
            (4, 4, 5.0),
        ]
    )

    game_state.update_perception_fields(include_player_scent=False)
    
    assert get_scent(game_state.perception_cave_when, 4, 4) > 0
    assert get_scent(game_state.perception_cave_when, 1, 1) == 0


def test_gather_perception_does_not_add_automatic_player_scent_for_legacy_callers() -> None:
    game_map = GameMap(width=7, height=7)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.update_tile_transparency()
    game_state = GameState(
        existing_map=game_map,
        player_start_pos=(1, 1),
        player_glyph=64,
        player_start_hp=10,
        player_fov_radius=5,
        item_templates={},
        rng_seed=12,
        enable_sound=False,
        enable_ai=False,
    )
    
    game_state.scent_events.append((4, 4, 5.0))
    gather_perception(game_state)
    
    assert get_scent(game_state.perception_cave_when, 4, 4) > 0
    assert get_scent(game_state.perception_cave_when, 1, 1) == 0
""")

if __name__ == "__main__":
    update_readme()
    update_game_state()
    update_tests()
    print("Done")
