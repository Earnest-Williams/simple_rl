import numpy as np

from game.world.los import line_of_sight, line_of_sight_many_u8


def test_line_of_sight_many_matches_scalar_open_map() -> None:
    # 10x10 fully transparent map
    transparency_map = np.ones((10, 10), dtype=bool)

    # We can test various paths
    starts_x = np.asarray([0, 1, 2, 5, 0], dtype=np.int32)
    starts_y = np.asarray([0, 1, 2, 5, 9], dtype=np.int32)
    ends_x = np.asarray([9, 8, 7, 5, 9], dtype=np.int32)
    ends_y = np.asarray([9, 8, 2, 5, 0], dtype=np.int32)

    batch = line_of_sight_many_u8(starts_x, starts_y, ends_x, ends_y, transparency_map)

    scalar = np.asarray(
        [
            int(
                line_of_sight(
                    starts_x[i],
                    starts_y[i],
                    ends_x[i],
                    ends_y[i],
                    transparency_map,
                )
            )
            for i in range(len(starts_x))
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(batch, scalar)


def test_line_of_sight_many_matches_scalar_blocked_map() -> None:
    # 10x10 map with some obstacles
    transparency_map = np.ones((10, 10), dtype=bool)
    transparency_map[5, 5] = False  # Block the center
    transparency_map[3, :] = False  # Block a whole row

    starts_x = np.asarray([0, 5, 2, 2], dtype=np.int32)
    starts_y = np.asarray([0, 0, 1, 4], dtype=np.int32)
    ends_x = np.asarray([9, 9, 2, 8], dtype=np.int32)
    ends_y = np.asarray([9, 9, 8, 4], dtype=np.int32)

    batch = line_of_sight_many_u8(starts_x, starts_y, ends_x, ends_y, transparency_map)
    scalar = np.asarray(
        [
            int(
                line_of_sight(
                    starts_x[i],
                    starts_y[i],
                    ends_x[i],
                    ends_y[i],
                    transparency_map,
                )
            )
            for i in range(len(starts_x))
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(batch, scalar)


def test_line_of_sight_many_matches_scalar_out_of_bounds() -> None:
    transparency_map = np.ones((10, 10), dtype=bool)

    starts_x = np.asarray([-1, 0, 5, 0, 10], dtype=np.int32)
    starts_y = np.asarray([0, -2, 5, 0, 5], dtype=np.int32)
    ends_x = np.asarray([5, 5, 11, -1, 5], dtype=np.int32)
    ends_y = np.asarray([5, 5, 5, 5, -1], dtype=np.int32)

    batch = line_of_sight_many_u8(starts_x, starts_y, ends_x, ends_y, transparency_map)
    scalar = np.asarray(
        [
            int(
                line_of_sight(
                    starts_x[i],
                    starts_y[i],
                    ends_x[i],
                    ends_y[i],
                    transparency_map,
                )
            )
            for i in range(len(starts_x))
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(batch, scalar)


def test_line_of_sight_many_matches_scalar_diagonal_corner_cases() -> None:
    # Testing Bresenham steps specifically around obstacles
    # Diagonal paths with corners
    transparency_map = np.ones((10, 10), dtype=bool)
    # Put diagonal blockers
    transparency_map[4, 4] = False
    transparency_map[5, 6] = False

    # Check paths passing near or through the blockers
    starts_x = np.asarray([3, 3, 4, 2], dtype=np.int32)
    starts_y = np.asarray([3, 5, 3, 2], dtype=np.int32)
    ends_x = np.asarray([5, 5, 5, 8], dtype=np.int32)
    ends_y = np.asarray([5, 3, 5, 8], dtype=np.int32)

    batch = line_of_sight_many_u8(starts_x, starts_y, ends_x, ends_y, transparency_map)
    scalar = np.asarray(
        [
            int(
                line_of_sight(
                    starts_x[i],
                    starts_y[i],
                    ends_x[i],
                    ends_y[i],
                    transparency_map,
                )
            )
            for i in range(len(starts_x))
        ],
        dtype=np.uint8,
    )
    np.testing.assert_array_equal(batch, scalar)
