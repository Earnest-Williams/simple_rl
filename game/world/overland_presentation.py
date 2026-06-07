from __future__ import annotations

from dataclasses import dataclass

from common.constants import Material


@dataclass(frozen=True, slots=True)
class OverlandMaterialPresentation:
    glyph_name: str
    fg: tuple[int, int, int]
    bg: tuple[int, int, int]


OVERLAND_MATERIAL_PRESENTATION: dict[int, OverlandMaterialPresentation] = {
    int(Material.ROAD): OverlandMaterialPresentation(
        glyph_name="road_stone",
        fg=(150, 140, 115),
        bg=(35, 32, 28),
    ),
    int(Material.DOCK): OverlandMaterialPresentation(
        glyph_name="dock_wood",
        fg=(145, 110, 70),
        bg=(20, 25, 35),
    ),
    int(Material.BRIDGE): OverlandMaterialPresentation(
        glyph_name="bridge_wood",
        fg=(150, 120, 80),
        bg=(25, 30, 35),
    ),
    int(Material.BUILDING_FLOOR): OverlandMaterialPresentation(
        glyph_name="building_floor",
        fg=(120, 110, 100),
        bg=(20, 18, 15),
    ),
    int(Material.WOOD_WALL): OverlandMaterialPresentation(
        glyph_name="building_wall",
        fg=(180, 170, 150),
        bg=(40, 35, 30),
    ),
    int(Material.FIELD): OverlandMaterialPresentation(
        glyph_name="field",
        fg=(160, 150, 60),
        bg=(40, 45, 15),
    ),
    int(Material.ORCHARD): OverlandMaterialPresentation(
        glyph_name="orchard",
        fg=(80, 160, 60),
        bg=(15, 45, 15),
    ),
    int(Material.PASTURE): OverlandMaterialPresentation(
        glyph_name="pasture",
        fg=(100, 180, 80),
        bg=(20, 50, 20),
    ),
    int(Material.RUIN_FLOOR): OverlandMaterialPresentation(
        glyph_name="ruin_floor",
        fg=(100, 95, 90),
        bg=(25, 25, 25),
    ),
    int(Material.CAVE_MOUTH): OverlandMaterialPresentation(
        glyph_name="cave_mouth",
        fg=(50, 50, 50),
        bg=(10, 10, 10),
    ),
    int(Material.SHALLOW_WATER): OverlandMaterialPresentation(
        glyph_name="shallow_water",
        fg=(80, 120, 200),
        bg=(20, 30, 80),
    ),
    int(Material.DEEP_WATER): OverlandMaterialPresentation(
        glyph_name="deep_water",
        fg=(40, 80, 160),
        bg=(10, 20, 60),
    ),
    int(Material.FOREST_FLOOR): OverlandMaterialPresentation(
        glyph_name="forest_floor",
        fg=(60, 100, 40),
        bg=(10, 25, 10),
    ),
    int(Material.MUDFLAT): OverlandMaterialPresentation(
        glyph_name="mudflat",
        fg=(100, 80, 60),
        bg=(30, 25, 20),
    ),
}

_resolved_cache: dict[int, tuple[int, tuple[int, int, int], tuple[int, int, int]]] | None = None

def get_resolved_overland_presentation() -> dict[int, tuple[int, tuple[int, int, int], tuple[int, int, int]]]:
    global _resolved_cache
    if _resolved_cache is not None:
        return _resolved_cache

    from engine.glyphs import tile_id_for
    _resolved_cache = {}
    for mat_id, pres in OVERLAND_MATERIAL_PRESENTATION.items():
        glyph_idx = tile_id_for(pres.glyph_name, default=0)
        _resolved_cache[mat_id] = (glyph_idx or 0, pres.fg, pres.bg)
    
    return _resolved_cache
