from __future__ import annotations

from dataclasses import dataclass

from common.constants import Material


@dataclass(frozen=True, slots=True)
class OverlandMaterialPresentation:
    glyph_name: str
    fallback_glyph_name: str
    fg: tuple[int, int, int]
    bg: tuple[int, int, int]
    notes: str = ""


OVERLAND_MATERIAL_PRESENTATION: dict[int, OverlandMaterialPresentation] = {
    int(Material.GRASS): OverlandMaterialPresentation(
        glyph_name="vegetation_bush_small",
        fallback_glyph_name="blank_tile_b",
        fg=(80, 140, 50),
        bg=(15, 35, 15),
        notes="Standard grass tile.",
    ),
    int(Material.DIRT): OverlandMaterialPresentation(
        glyph_name="terrain_mound",
        fallback_glyph_name="terrain_pebbles",
        fg=(130, 100, 70),
        bg=(35, 25, 20),
        notes="Bare dirt.",
    ),
    int(Material.MUD): OverlandMaterialPresentation(
        glyph_name="terrain_mound",
        fallback_glyph_name="terrain_pebbles",
        fg=(100, 80, 60),
        bg=(30, 25, 20),
        notes="Muddy ground.",
    ),
    int(Material.LIMESTONE): OverlandMaterialPresentation(
        glyph_name="wall_stone_bricks",
        fallback_glyph_name="blank_tile_b",
        fg=(160, 160, 160),
        bg=(30, 30, 30),
        notes="Solid limestone.",
    ),
    int(Material.LIMESTONE_PAVEMENT): OverlandMaterialPresentation(
        glyph_name="terrain_pebbles",
        fallback_glyph_name="blank_tile_b",
        fg=(150, 150, 150),
        bg=(30, 30, 30),
        notes="Limestone pavement/floor.",
    ),
    int(Material.LIMESTONE_CLIFF): OverlandMaterialPresentation(
        glyph_name="wall_stone_bricks",
        fallback_glyph_name="blank_tile_b",
        fg=(140, 140, 140),
        bg=(20, 20, 20),
        notes="Steep limestone cliff.",
    ),
    int(Material.BASALT): OverlandMaterialPresentation(
        glyph_name="wall_stone_bricks",
        fallback_glyph_name="blank_tile_b",
        fg=(80, 80, 80),
        bg=(10, 10, 10),
        notes="Dark basalt rock.",
    ),
    int(Material.PEAT): OverlandMaterialPresentation(
        glyph_name="terrain_mound",
        fallback_glyph_name="blank_tile_b",
        fg=(110, 90, 60),
        bg=(25, 20, 15),
        notes="Peat bog surface.",
    ),
    int(Material.ROAD): OverlandMaterialPresentation(
        glyph_name="road_stone",
        fallback_glyph_name="terrain_pebbles",
        fg=(150, 140, 115),
        bg=(35, 32, 28),
        notes="Stone or packed-earth road surface.",
    ),
    int(Material.DOCK): OverlandMaterialPresentation(
        glyph_name="dock_wood",
        fallback_glyph_name="wall_wood_planks",
        fg=(145, 110, 70),
        bg=(20, 25, 35),
        notes="Wood dock or wharf surface.",
    ),
    int(Material.BRIDGE): OverlandMaterialPresentation(
        glyph_name="bridge_wood",
        fallback_glyph_name="wall_wood_planks",
        fg=(150, 120, 80),
        bg=(25, 30, 35),
        notes="Wood bridge over water or unstable ground.",
    ),
    int(Material.BUILDING_FLOOR): OverlandMaterialPresentation(
        glyph_name="building_floor",
        fallback_glyph_name="blank_tile_b",
        fg=(120, 110, 100),
        bg=(20, 18, 15),
        notes="Interior floor of settlement building.",
    ),
    int(Material.WOOD_WALL): OverlandMaterialPresentation(
        glyph_name="building_wall",
        fallback_glyph_name="wall_wood_planks",
        fg=(180, 170, 150),
        bg=(40, 35, 30),
        notes="Wooden exterior or interior wall.",
    ),
    int(Material.STONE_WALL): OverlandMaterialPresentation(
        glyph_name="stone_wall",
        fallback_glyph_name="wall_stone_bricks",
        fg=(175, 170, 160),
        bg=(35, 35, 40),
        notes="Stone wall or masonry structure.",
    ),
    int(Material.FIELD): OverlandMaterialPresentation(
        glyph_name="field",
        fallback_glyph_name="vegetation_reeds",
        fg=(160, 150, 60),
        bg=(40, 45, 15),
        notes="Cultivated field tile.",
    ),
    int(Material.ORCHARD): OverlandMaterialPresentation(
        glyph_name="orchard",
        fallback_glyph_name="tree_evergreen",
        fg=(80, 160, 60),
        bg=(15, 45, 15),
        notes="Orchard or tree crop tile.",
    ),
    int(Material.PASTURE): OverlandMaterialPresentation(
        glyph_name="pasture",
        fallback_glyph_name="vegetation_bush_small",
        fg=(100, 180, 80),
        bg=(20, 50, 20),
        notes="Grazing pasture or grassland enclosure.",
    ),
    int(Material.RUIN_FLOOR): OverlandMaterialPresentation(
        glyph_name="ruin_floor",
        fallback_glyph_name="debris_rubble",
        fg=(100, 95, 90),
        bg=(25, 25, 25),
        notes="Ruin floor, rubble floor, or collapsed structure interior.",
    ),
    int(Material.RUIN_WALL): OverlandMaterialPresentation(
        glyph_name="ruin_wall",
        fallback_glyph_name="debris_rubble",
        fg=(120, 115, 105),
        bg=(30, 30, 30),
        notes="Ruined wall or collapsed masonry.",
    ),
    int(Material.CAVE_MOUTH): OverlandMaterialPresentation(
        glyph_name="cave_mouth",
        fallback_glyph_name="prop_cave_entrance",
        fg=(50, 50, 50),
        bg=(10, 10, 10),
        notes="Cave entrance transition on the overland map.",
    ),
    int(Material.SHALLOW_WATER): OverlandMaterialPresentation(
        glyph_name="shallow_water",
        fallback_glyph_name="liquid_water_1",
        fg=(80, 120, 200),
        bg=(20, 30, 80),
        notes="Shallow water, ford, or flooded lowland.",
    ),
    int(Material.DEEP_WATER): OverlandMaterialPresentation(
        glyph_name="deep_water",
        fallback_glyph_name="liquid_water_2",
        fg=(40, 80, 160),
        bg=(10, 20, 60),
        notes="Deep water or non-walkable water.",
    ),
    int(Material.FLOWING_WATER): OverlandMaterialPresentation(
        glyph_name="flowing_water",
        fallback_glyph_name="liquid_water_1",
        fg=(70, 130, 210),
        bg=(15, 35, 90),
        notes="River, stream, or channel water.",
    ),
    int(Material.FOREST_FLOOR): OverlandMaterialPresentation(
        glyph_name="forest_floor",
        fallback_glyph_name="vegetation_bush_small",
        fg=(60, 100, 40),
        bg=(10, 25, 10),
        notes="Forest floor or wet woodland ground.",
    ),
    int(Material.FERN_UNDERSTORY): OverlandMaterialPresentation(
        glyph_name="fern_understory",
        fallback_glyph_name="vegetation_bush_small",
        fg=(55, 120, 45),
        bg=(8, 28, 8),
        notes="Dense fern or undergrowth tile.",
    ),
    int(Material.MUDFLAT): OverlandMaterialPresentation(
        glyph_name="mudflat",
        fallback_glyph_name="terrain_mound",
        fg=(100, 80, 60),
        bg=(30, 25, 20),
        notes="Mudflat, wet mud, or coastal muddy ground.",
    ),
    int(Material.GRAVEL): OverlandMaterialPresentation(
        glyph_name="gravel",
        fallback_glyph_name="terrain_pebbles",
        fg=(120, 115, 105),
        bg=(35, 35, 32),
        notes="Gravel or stony ground.",
    ),
}


@dataclass(frozen=True, slots=True)
class ResolvedOverlandPresentation:
    glyph_index: int
    fg: tuple[int, int, int]
    bg: tuple[int, int, int]
    glyph_name: str
    fallback_glyph_name: str
    resolved_glyph_name: str
    used_fallback: bool
    notes: str


_resolved_cache: dict[int, ResolvedOverlandPresentation] | None = None


def get_resolved_overland_presentation() -> dict[int, ResolvedOverlandPresentation]:
    global _resolved_cache
    if _resolved_cache is not None:
        return _resolved_cache

    from engine.glyphs import tile_id_for

    resolved: dict[int, ResolvedOverlandPresentation] = {}

    for mat_id, pres in OVERLAND_MATERIAL_PRESENTATION.items():
        desired_id = tile_id_for(pres.glyph_name, default=None)
        fallback_id = tile_id_for(pres.fallback_glyph_name, default=None)

        if desired_id is not None:
            glyph_index = int(desired_id)
            resolved_name = pres.glyph_name
            used_fallback = False
        elif fallback_id is not None:
            glyph_index = int(fallback_id)
            resolved_name = pres.fallback_glyph_name
            used_fallback = True
        else:
            raise ValueError(
                "Overland presentation fallback glyph is missing: "
                f"desired={pres.glyph_name!r}, fallback={pres.fallback_glyph_name!r}"
            )

        resolved[mat_id] = ResolvedOverlandPresentation(
            glyph_index=glyph_index,
            fg=pres.fg,
            bg=pres.bg,
            glyph_name=pres.glyph_name,
            fallback_glyph_name=pres.fallback_glyph_name,
            resolved_glyph_name=resolved_name,
            used_fallback=used_fallback,
            notes=pres.notes,
        )

    _resolved_cache = resolved
    return _resolved_cache
