from __future__ import annotations

import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from settlegen.config import SettlementConfig
from settlegen.generator import SettlementGenerator
from settlegen.renderers.ascii import render_ascii

app = FastAPI()

STATIC_DIR = Path(__file__).parent / "static"

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class GenerateRequest(BaseModel):
    seed: int = 42
    kind: str = "town"
    width: int = 96
    height: int = 72
    population_target: int | None = None
    state: str = "ordinary"
    population_mode: str = "normal"
    magic: str = "low_magic"
    material: str = "mixed"
    layout: str = "organic"
    defense: str = "none"
    wealth: str = "modest"
    terrain: list[str] = ["plain"]
    facilities: list[str] = []


@app.get("/", response_class=HTMLResponse)
async def get_index():
    with open(STATIC_DIR / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    # Prepare the config
    cfg = SettlementConfig(
        kind=req.kind,
        width=req.width,
        height=req.height,
        population_target=req.population_target,
        state=req.state,
        population_mode=req.population_mode,
        magic=req.magic,
        material=req.material,
        layout=req.layout,
        defense=req.defense,
        wealth=req.wealth,
        terrain=tuple(req.terrain),
        facilities=tuple(req.facilities),
    ).normalized()

    # Generate
    settlement = SettlementGenerator(seed=req.seed).generate(cfg)
    ascii_map = render_ascii(settlement, unicode=True)

    return {
        "name": settlement.name,
        "population": settlement.population,
        "buildings_count": len(settlement.buildings),
        "districts_count": len(settlement.districts),
        "map": ascii_map,
    }


def main():
    print("Starting UI server on http://127.0.0.1:8000")
    webbrowser.open("http://127.0.0.1:8000")
    uvicorn.run("settlegen.ui.server:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
