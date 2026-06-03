import time

import numpy as np

from game.world.fov import compute_visibility
from utils.game_rng import GameRNG

# Constants
WALL_DENSITY_DIVISOR: int = 10
WARMUP_RUNS: int = 3


def bench(h: int = 200, w: int = 200, radius: int = 20, trials: int = 50) -> None:
    transparency = np.ones((h, w), dtype=np.float32)
    cx = h // 2
    cy = w // 2
    # make some random walls
    rng = GameRNG(seed=1)
    for _ in range(h * w // WALL_DENSITY_DIVISOR):
        y = rng.randint(0, h)
        x = rng.randint(0, w)
        transparency[y, x] = 0.0

    def is_opaque(y: int, x: int) -> bool:
        return transparency[y, x] < 0.5

    # warm up
    for _ in range(WARMUP_RUNS):
        compute_visibility(
            h, w, origin_y=cy, origin_x=cx, radius=radius, is_opaque=is_opaque
        )

    t0 = time.perf_counter()
    for _ in range(trials):
        compute_visibility(
            h, w, origin_y=cy, origin_x=cx, radius=radius, is_opaque=is_opaque
        )
    t1 = time.perf_counter()
    print(
        f"Ran {trials} trials in {t1 - t0:.3f}s, avg {((t1 - t0) / trials):.6f}s per FOV"
    )


if __name__ == "__main__":
    bench()
