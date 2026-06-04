from __future__ import annotations

import argparse
from pathlib import Path

from .config import (
    BuildingMaterial,
    DefenseStyle,
    Facility,
    LayoutStyle,
    MagicMode,
    PopulationMode,
    SettlementConfig,
    SettlementKind,
    SettlementState,
    TerrainFeature,
    Wealth,
)
from .export import write_bundle
from .generator import SettlementGenerator
from .renderers.ascii import render_ascii


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Generate a medieval/fantasy settlement data bundle.")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--kind", choices=[x.value for x in SettlementKind], default=SettlementKind.TOWN.value)
    p.add_argument("--width", type=int, default=128)
    p.add_argument("--height", type=int, default=96)
    p.add_argument("--population", type=int, default=None)
    p.add_argument("--state", choices=[x.value for x in SettlementState], default=SettlementState.ORDINARY.value)
    p.add_argument("--population-mode", choices=[x.value for x in PopulationMode], default=PopulationMode.NORMAL.value)
    p.add_argument("--magic", choices=[x.value for x in MagicMode], default=MagicMode.LOW_MAGIC.value)
    p.add_argument("--material", choices=[x.value for x in BuildingMaterial], default=BuildingMaterial.MIXED.value)
    p.add_argument("--layout", choices=[x.value for x in LayoutStyle], default=LayoutStyle.ORGANIC.value)
    p.add_argument("--defense", choices=[x.value for x in DefenseStyle], default=DefenseStyle.NONE.value)
    p.add_argument("--wealth", choices=[x.value for x in Wealth], default=Wealth.MODEST.value)
    p.add_argument("--terrain", action="append", default=[], help="Terrain feature; repeatable, e.g. --terrain river --terrain hill")
    p.add_argument("--facility", action="append", default=[], help="Requested facility; repeatable, e.g. --facility keep")
    p.add_argument("--out", type=Path, default=Path("settlement_out"))
    p.add_argument("--ascii", action="store_true", help="Print an ASCII preview")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = SettlementConfig(
        kind=SettlementKind(args.kind),
        width=args.width,
        height=args.height,
        population_target=args.population,
        state=SettlementState(args.state),
        population_mode=PopulationMode(args.population_mode),
        magic=MagicMode(args.magic),
        material=BuildingMaterial(args.material),
        layout=LayoutStyle(args.layout),
        defense=DefenseStyle(args.defense),
        wealth=Wealth(args.wealth),
        terrain=tuple(TerrainFeature(t) for t in (args.terrain or [TerrainFeature.PLAIN.value])),
        facilities=tuple(Facility(f) for f in args.facility),
    )
    settlement = SettlementGenerator(seed=args.seed).generate(cfg)
    paths = write_bundle(settlement, args.out)
    print(f"Generated {settlement.name}: population={settlement.population}, buildings={len(settlement.buildings)}")
    for key, path in paths.items():
        print(f"{key}: {path}")
    if args.ascii:
        print(render_ascii(settlement))


if __name__ == "__main__":
    main()
