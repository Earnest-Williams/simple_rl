from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from worldgen import build_full_world, default_world_config, read_world_meta
from worldgen.config import WorldConfig
from worldgen.metadata import WorldMeta


def test_full_pipeline_creates_meta_and_report(tmp_path: Path) -> None:
    cfg: WorldConfig = default_world_config()
    out_dir: Path = tmp_path / "world"
    build_full_world(
        out_dir,
        seed=12345,
        N=4,
        cfg=cfg,
        overwrite=True,
        precompile_kernels=True,
    )

    meta: WorldMeta = read_world_meta(out_dir)
    assert "elev_q" in meta.layers
    assert "temp" in meta.layers
    assert "precip" in meta.layers
    assert "flow_to" in meta.layers

    report_path: Path = out_dir / "report.json"
    assert report_path.exists()
    report: Dict[str, object] = json.loads(report_path.read_text())
    assert "land_fraction" in report
    assert "temp_quantiles" in report
    assert "precip_quantiles" in report
    assert "river_stats" in report
