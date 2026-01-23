from __future__ import annotations

from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from worldgen import build_full_world, default_world_config
from worldgen.config import WorldConfig


def test_deterministic_across_runs(tmp_path: Path) -> None:
    cfg: WorldConfig = default_world_config()
    out1: Path = tmp_path / "run1"
    out2: Path = tmp_path / "run2"
    seed: int = 999
    build_full_world(
        out1,
        seed=seed,
        N=4,
        cfg=cfg,
        overwrite=True,
        precompile_kernels=True,
    )
    build_full_world(
        out2,
        seed=seed,
        N=4,
        cfg=cfg,
        overwrite=True,
        precompile_kernels=True,
    )

    assert (out1 / "meta.json").read_text() == (out2 / "meta.json").read_text()
    assert (out1 / "tunables.json").read_text() == (out2 / "tunables.json").read_text()

    elev_a: NDArray[np.int32] = np.load(out1 / "elev_q.npy")
    elev_b: NDArray[np.int32] = np.load(out2 / "elev_q.npy")
    assert np.array_equal(elev_a, elev_b)
