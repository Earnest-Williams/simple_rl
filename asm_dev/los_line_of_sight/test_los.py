import numpy as np
from los_wrapper import los_many  # Replace with actual filename


def test_los_bounds():
    # 10x10 map, completely transparent
    transparency = np.ones((10, 10), dtype=np.uint8)

    # Introduce a single wall at (5, 5)
    transparency[5, 5] = 0

    starts_x = np.array([0, 0, 9], dtype=np.int32)
    starts_y = np.array([0, 5, 0], dtype=np.int32)
    ends_x = np.array([9, 9, 0], dtype=np.int32)
    ends_y = np.array([9, 5, 9], dtype=np.int32)

    results = los_many(starts_x, starts_y, ends_x, ends_y, transparency)

    # Query 0: (0,0) to (9,9) passes through (5,5) -> Blocked (0)
    # Query 1: (0,5) to (9,5) passes through (5,5) -> Blocked (0)
    # Query 2: (9,0) to (0,9) avoids (5,5)          -> Clear (1)

    expected = np.array([0, 0, 1], dtype=np.uint8)

    if np.array_equal(results, expected):
        print("ABI mapping and LOS execution successful.")
    else:
        print(f"Failed. Expected {expected}, got {results}")


if __name__ == "__main__":
    test_los_bounds()
