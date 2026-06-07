from __future__ import annotations

import numpy as np

from engine.render_base_layers import prepare_base_layers
from game.game_state import GameState
from game.systems.movement_system import try_move
from game.systems.overland_movement import human_on_foot_can_enter
from tools.play_game import create_gamestate_from_overland


def _find_adjacent_human_walkable_tile(gs: GameState) -> tuple[int, int] | None:
    pos = gs.player_position
    if not pos:
        return None
    px, py = pos
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        if human_on_foot_can_enter(gs, px + dx, py + dy):
            return px + dx, py + dy
    return None


def _find_adjacent_unwalkable_tile(gs: GameState) -> tuple[int, int] | None:
    pos = gs.player_position
    if not pos:
        return None
    px, py = pos
    # Search slightly wider if none immediately adjacent
    for radius in range(1, 5):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = px + dx, py + dy
                if gs.game_map.in_bounds(nx, ny) and not human_on_foot_can_enter(
                    gs, nx, ny
                ):
                    return nx, ny
    return None


def test_starting_overland_game_start_and_mechanics() -> None:
    # 1. Start from tools script (catches config/template/renderer integration errors missed by pure loader)
    gs = create_gamestate_from_overland(seed=20260604, width=128, height=96)
    game_map = gs.game_map

    assert game_map.overland_metadata is not None
    spawn = gs.player_position
    assert spawn is not None
    sx, sy = spawn

    # 2. Deterministic-seed regression test for player_spawn
    assert game_map.in_bounds(sx, sy)
    assert human_on_foot_can_enter(gs, sx, sy)

    contract = game_map.overland_metadata.starting_contract
    assert "player_spawn" in contract
    harbor = contract.get("harbor")

    # Assert near harbor (within a reasonable distance, e.g. 30 tiles)
    hx, hy = harbor["point"]
    dist2 = (sx - hx) ** 2 + (sy - hy) ** 2
    assert dist2 < 30 * 30, f"Spawn ({sx},{sy}) too far from harbor ({hx},{hy})"

    # Smoke test positive movement
    adjacent = _find_adjacent_human_walkable_tile(gs)
    assert adjacent is not None, "No adjacent walkable tile found for player spawn"
    ax, ay = adjacent
    assert try_move(gs.player_id, ax - sx, ay - sy, gs)

    # Re-sync pos after move
    sx, sy = ax, ay

    # 3. Movement denial test (nearby blocked/flooded tile)
    unwalkable = _find_adjacent_unwalkable_tile(gs)
    assert unwalkable is not None, "No unwalkable tile found near player"
    ux, uy = unwalkable

    assert not human_on_foot_can_enter(gs, ux, uy)

    # Find a walkable tile adjacent to ux, uy to place the player temporarily
    px_new, py_new = None, None
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        tx, ty = ux + dx, uy + dy
        if gs.game_map.in_bounds(tx, ty) and human_on_foot_can_enter(gs, tx, ty):
            px_new, py_new = tx, ty
            break

    assert px_new is not None, "No walkable tile adjacent to the unwalkable tile found"

    from game.entities.components import Position

    original_pos = gs.player_position
    assert original_pos is not None

    # Temporarily place player adjacent to the unwalkable tile
    gs.entity_registry.set_position(gs.player_id, Position(px_new, py_new))
    assert gs.player_position == Position(px_new, py_new)

    # Try to move player into the unwalkable tile (should fail)
    moved = try_move(gs.player_id, ux - px_new, uy - py_new, gs)
    assert (
        not moved
    ), f"Player was incorrectly allowed to move to unwalkable tile ({ux},{uy})"

    # Restore original position
    gs.entity_registry.set_position(gs.player_id, Position(*original_pos))

    # 4. Renderer assertion (more than one glyph index / material presentation value)
    game_map.compute_fov(sx, sy, gs.fov_radius)
    # Give some colors and indices to test with
    max_id = np.max(game_map.tiles)
    fg_colors = np.ones((max_id + 1, 3), dtype=np.uint8) * 255
    bg_colors = np.zeros((max_id + 1, 3), dtype=np.uint8)
    indices = np.arange(max_id + 1, dtype=np.uint16)

    (
        base_fg,
        base_bg,
        glyph_indices,
        vis,
        drawn,
        h_map,
        map_vis,
        map_mem,
        map_tiles,
        vp_shape,
    ) = prepare_base_layers(
        game_map=game_map,
        viewport_x=max(0, sx - 10),
        viewport_y=max(0, sy - 10),
        viewport_width=20,
        viewport_height=20,
        max_defined_tile_id=max_id,
        tile_fg_colors=fg_colors,
        tile_bg_colors=bg_colors,
        tile_indices_render=indices,
    )

    # Assert there's more than one distinct glyph index OR distinct FG color used in the drawn area
    unique_glyphs = np.unique(glyph_indices[drawn])
    unique_fgs = np.unique(base_fg[drawn], axis=0)

    assert (
        len(unique_glyphs) > 1 or len(unique_fgs) > 1
    ), "Renderer silent fallback to floor/wall visuals detected."
