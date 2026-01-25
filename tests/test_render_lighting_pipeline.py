import sys
import types

import numpy as np
from PIL import Image

from engine.render_lighting import apply_light_sources, calculate_lighting
from engine.renderer import RenderConfig, ViewportParams, render_viewport
from game.game_state import GameState
from game.world.game_map import TILE_ID_FLOOR, GameMap, LightSource

# Provide a minimal ai_system module for GameState imports
ai_module = types.ModuleType("game.systems.ai_system")


def dispatch_ai(*args, **kwargs):
    return None


ai_module.dispatch_ai = dispatch_ai
sys.modules["game.systems.ai_system"] = ai_module

MEMORY_FADE_CFG = {"enabled": False, "duration": 5.0, "midpoint": 2.5, "steepness": 1.2}


def create_basic_game_state():
    game_map = GameMap(width=5, height=5)
    game_map.tiles[:, :] = TILE_ID_FLOOR
    game_map.height_map[:, :] = 0
    game_map.ceiling_map[:, :] = 6
    game_map.update_tile_transparency()
    return GameState(
        existing_map=game_map,
        player_start_pos=(2, 2),
        player_glyph=ord("@"),
        player_start_hp=10,
        player_fov_radius=2,
        item_templates={},
        entity_templates={},
        effect_definitions={},
        rng_seed=42,
        memory_fade_config=MEMORY_FADE_CFG,
    )


def test_apply_light_sources_adds_color_within_radius():
    gm = GameMap(width=5, height=5)
    gm.tiles[:, :] = TILE_ID_FLOOR
    gm.height_map[:, :] = 0
    gm.ceiling_map[:, :] = 6
    gm.update_tile_transparency()
    gm.light_sources.append(LightSource(2, 2, 2, (100, 0, 0)))

    base_fg = np.full((5, 5, 3), 10, dtype=np.uint8)
    base_bg = np.full((5, 5, 3), 5, dtype=np.uint8)
    visible_mask = np.ones((5, 5), dtype=bool)

    lit_fg, lit_bg, _ = calculate_lighting(
        base_fg,
        base_bg,
        visible_mask,
        5,
        5,
        0,
        0,
        2,
        2,
        np.float32(1.0),
        np.float32(0.0),
        np.float32(1.0),
        np.float32(4.0),
    )

    final_fg, final_bg, _ = apply_light_sources(
        lit_fg,
        lit_bg,
        gm.light_sources,
        gm,
        0,
        0,
        5,
        5,
    )

    assert (final_fg[2, 2] == np.array([110, 10, 10], dtype=np.uint8)).all()
    assert (final_bg[2, 2] == np.array([105, 5, 5], dtype=np.uint8)).all()
    assert np.array_equal(final_fg[0, 0], lit_fg[0, 0])


def test_render_viewport_uses_game_map_lights():
    gs = create_basic_game_state()
    gm = gs.game_map

    gm.visible[:, :] = True
    gm.explored[:, :] = True
    gm.memory_intensity[:, :] = 1.0
    gm.light_sources.clear()
    gm.light_sources.append(LightSource(2, 2, 2, (100, 0, 0)))
    gs.light_sources = []

    max_defined_tile_id = 255
    tile_fg_colors = np.zeros((max_defined_tile_id + 1, 3), dtype=np.uint8)
    tile_bg_colors = np.zeros((max_defined_tile_id + 1, 3), dtype=np.uint8)
    tile_indices_render = np.zeros(max_defined_tile_id + 1, dtype=np.uint16)
    tile_fg_colors[TILE_ID_FLOOR] = [10, 10, 10]
    tile_bg_colors[TILE_ID_FLOOR] = [20, 20, 20]
    tile_indices_render[TILE_ID_FLOOR] = ord(".")

    tile_coord_y, tile_coord_x = np.indices((gm.height, gm.width))
    coord_arrays = {
        "tile_coord_y": tile_coord_y.astype(np.int16),
        "tile_coord_x": tile_coord_x.astype(np.int16),
    }

    viewport = ViewportParams(
        viewport_x=0,
        viewport_y=0,
        viewport_width=gm.width,
        viewport_height=gm.height,
        tile_arrays={},
        tile_fg_colors=tile_fg_colors,
        tile_bg_colors=tile_bg_colors,
        tile_indices_render=tile_indices_render,
        max_defined_tile_id=max_defined_tile_id,
        tile_w=1,
        tile_h=1,
        coord_arrays=coord_arrays,
    )
    render_config = RenderConfig(
        show_height_vis=False,
        vis_max_diff=0,
        vis_color_high_np=np.zeros(3, dtype=np.uint8),
        vis_color_mid_np=np.zeros(3, dtype=np.uint8),
        vis_color_low_np=np.zeros(3, dtype=np.uint8),
        vis_blend_factor=np.float32(0.0),
        lighting_ambient=np.float32(1.0),
        lighting_min_fov=np.float32(0.0),
        lighting_falloff=np.float32(1.0),
        fov_radius_sq=np.float32(4.0),
        enable_memory_fade=False,
        enable_colored_lights=True,
    )

    image = render_viewport(gs, viewport, render_config)
    assert isinstance(image, Image.Image)
    rendered = np.array(image)
    assert (rendered[2, 2, :3] == np.array([120, 20, 20], dtype=np.uint8)).all()
