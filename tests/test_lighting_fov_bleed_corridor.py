import numpy as np

from game.world.light_fov import compute_fov_all_octants
from tools.lighting_fov_tool.scene import ElementType, create_fixed_scene


def test_bleed_corridor_fov():
    scene = create_fixed_scene()

    opaque_grid = np.zeros((scene.height, scene.width), dtype=np.uint8)
    transparency_grid = np.ones((scene.height, scene.width), dtype=np.float32)

    for y in range(scene.height):
        for x in range(scene.width):
            if scene.tiles[y, x] in (ElementType.WALL, ElementType.PILLAR):
                opaque_grid[y, x] = 1
                transparency_grid[y, x] = 0.0

    # Find bleed_test_light
    bleed_light = next(
        (ls for ls in scene.light_sources if ls.name == "bleed_test_light"), None
    )
    assert bleed_light is not None

    visible_out = np.zeros_like(opaque_grid)
    dist_out = np.full_like(opaque_grid, -1, dtype=np.int32)
    side_bits_out = np.zeros_like(opaque_grid)

    cell_mask = np.zeros_like(opaque_grid, dtype=np.uint32)

    cell_mask = np.full((scene.height, scene.width), 0xFFFFFFFF, dtype=np.uint32)
    channels = 0xFFFFFFFF

    compute_fov_all_octants(
        opaque_grid,
        transparency_grid,
        cell_mask,
        channels,
        visible_out,
        dist_out,
        side_bits_out,
        np.zeros_like(opaque_grid, dtype=np.float32),  # visibility_out
        bleed_light.x,
        bleed_light.y,
        bleed_light.radius,
        0.999999,  # opacity_threshold
    )

    assert visible_out[19, 3] != 0  # separator wall face may be reached
    assert visible_out[19, 4] == 0
    assert visible_out[19, 5] == 0

    assert visible_out[19, 2] != 0  # light origin and left hallway reached
    assert visible_out[19, 1] != 0

    for y in range(15, 27):
        assert visible_out[y, 4] == 0
        assert visible_out[y, 5] == 0


if __name__ == "__main__":
    test_bleed_corridor_fov()
