from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from worldgen import build_full_world, default_world_config
from worldgen.config import WorldConfig


def run_profile(
    out_root: Path,
    *,
    Ns: list[int],
    seed: int,
    precompile: bool,
) -> dict[str, dict[str, float]]:
    results: dict[str, dict[str, float]] = {}
    cfg: WorldConfig = default_world_config()
    for N in Ns:
        out_dir: Path = out_root / f"world_N{N}"
        out_dir.mkdir(parents=True, exist_ok=True)
        t0: float = time.perf_counter()
        build_full_world(
            out_dir,
            seed=seed,
            N=N,
            cfg=cfg,
            overwrite=True,
            precompile_kernels=precompile,
        )
        t1: float = time.perf_counter()
        results[f"N_{N}"] = {"duration_s": float(t1 - t0)}
    return results


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("bench_out"))
    parser.add_argument("--Ns", nargs="+", type=int, default=[4, 8])
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--precompile", action="store_true")
    args: argparse.Namespace = parser.parse_args()
    out_root: Path = args.out
    Ns: list[int] = args.Ns
    seed_val: int = args.seed
    precompile_val: bool = args.precompile

    stats: dict[str, dict[str, float]] = run_profile(
        out_root,
        Ns=Ns,
        seed=seed_val,
        precompile=precompile_val,
    )
    output_path: Path = out_root / "profile.json"
    output_path.write_text(json.dumps(stats, indent=2, sort_keys=True))
    print("Profile results written to", output_path)


if __name__ == "__main__":
    main()
