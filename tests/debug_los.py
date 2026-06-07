import numpy as np

from tools.lighting_fov_tool.scene import ElementType, create_fixed_scene


def test_los():
    scene = create_fixed_scene()

    opaque_grid = np.zeros((scene.height, scene.width), dtype=np.uint8)
    transparency_grid = np.ones((scene.height, scene.width), dtype=np.float32)

    for y in range(scene.height):
        for x in range(scene.width):
            if scene.tiles[y, x] in (ElementType.WALL, ElementType.PILLAR):
                opaque_grid[y, x] = 1
                transparency_grid[y, x] = 0.0

    print(f"wall at (3, 19): {opaque_grid[19, 3]}")

    def _has_clear_extended_los(x0, y0, x1, y1):
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x = x0
        y = y0

        while x != x1 or y != y1:
            twice_err = 2 * err
            if twice_err > -dy:
                err -= dy
                x += sx
            if twice_err < dx:
                err += dx
                y += sy

            if x == x1 and y == y1:
                return True
            if x < 0 or y < 0 or x >= scene.width or y >= scene.height:
                return False
            if opaque_grid[y, x] != 0:
                print(f"blocked by ({x}, {y})")
                return False

        return True

    print("checking 4, 19")
    print(_has_clear_extended_los(2, 19, 4, 19))
    print("checking 4, 18")
    print(_has_clear_extended_los(2, 19, 4, 18))
    print("checking 4, 20")
    print(_has_clear_extended_los(2, 19, 4, 20))


if __name__ == "__main__":
    test_los()
