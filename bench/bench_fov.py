import time

import numpy as np

from lights_dev import fov


def bench(h: int = 200, w: int = 200, radius: int = 20, trials: int = 50) -> None:
    opaque = np.zeros((h, w), dtype=np.uint8)
    transparency = np.ones((h, w), dtype=np.float32)
    visible = np.zeros((h, w), dtype=np.uint8)
    dist = -np.ones((h, w), dtype=np.int32)
    side = np.zeros((h, w), dtype=np.uint8)
    cx = h // 2
    cy = w // 2
    # make some random walls
    rng = GameRNG(seed=1)
    for _ in range(h * w // 10):
        y = rng.randint(0, h)
        x = rng.randint(0, w)
        opaque[y, x] = 1
        transparency[y, x] = 0.0
    # warm up
    for _ in range(3):
        visible.fill(0)
        dist.fill(-1)
        fov.compute_fov_all_octants(
            opaque, transparency, visible, dist, side, cx, cy, radius
        )
    t0 = time.perf_counter()
    for _ in range(trials):
        visible.fill(0)
        dist.fill(-1)
        fov.compute_fov_all_octants(
            opaque, transparency, visible, dist, side, cx, cy, radius
        )
    t1 = time.perf_counter()
    print(
        f"Ran {trials} trials in {t1 - t0:.3f}s, avg {((t1 - t0) / trials):.6f}s per FOV"
    )


if __name__ == "__main__":
    bench()
