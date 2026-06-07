# Missing overland glyphs

This file lists descriptive glyph names used by the overland material presentation layer that are not currently present in `fonts/glyphs.yaml`.

The game uses fallback glyphs at runtime, but these descriptive names should eventually receive dedicated art entries.

| Desired glyph | Current fallback | Material enum | Purpose | Notes |
|---|---|---|---|---|
| `road_stone` | `terrain_pebbles` | `Material.ROAD` | Stone or packed-earth overland road | Should read as road, not random gravel. |
| `dock_wood` | `wall_wood_planks` | `Material.DOCK` | Dock, wharf, pier | Should read as flat wooden decking. |
| `bridge_wood` | `wall_wood_planks` | `Material.BRIDGE` | Bridge surface | Could reuse dock visual with edge treatment. |
| `building_floor` | `blank_tile_b` | `Material.BUILDING_FLOOR` | Settlement building interior floor | Should be subtle and floor-like. |
| `building_wall` | `wall_wood_planks` | `Material.WOOD_WALL` | Wooden building wall | Existing fallback is wall-like but too plank-heavy. |
| `stone_wall` | `wall_stone_bricks` | `Material.STONE_WALL` | Stone building/settlement wall | Existing fallback may be acceptable. |
| `field` | `vegetation_reeds` | `Material.FIELD` | Cultivated field | Needs crop-row visual. |
| `orchard` | `tree_evergreen` | `Material.ORCHARD` | Orchard/tree crop | Needs fruit/tree-grid visual. |
| `pasture` | `vegetation_bush_small` | `Material.PASTURE` | Pasture/grass enclosure | Needs grass/pasture visual. |
| `ruin_floor` | `debris_rubble` | `Material.RUIN_FLOOR` | Ruined floor | Existing fallback is close but too rubble-heavy. |
| `ruin_wall` | `debris_rubble` | `Material.RUIN_WALL` | Ruined wall | Needs collapsed wall edge/stonework. |
| `cave_mouth` | `prop_cave_entrance` | `Material.CAVE_MOUTH` | Cave entrance transition | Existing fallback may be acceptable; alias desired. |
| `shallow_water` | `liquid_water_1` | `Material.SHALLOW_WATER` | Shallow water | Existing fallback may be acceptable; alias desired. |
| `deep_water` | `liquid_water_2` | `Material.DEEP_WATER` | Deep water | Existing fallback may be acceptable; alias desired. |
| `flowing_water` | `liquid_water_1` | `Material.FLOWING_WATER` | River/stream/channel | Needs directional/flow visual eventually. |
| `forest_floor` | `vegetation_bush_small` | `Material.FOREST_FLOOR` | Forest ground | Needs ground-cover visual, not bush. |
| `fern_understory` | `vegetation_bush_small` | `Material.FERN_UNDERSTORY` | Dense fern/undergrowth | Needs fern visual. |
| `mudflat` | `terrain_mound` | `Material.MUDFLAT` | Coastal mudflat/wet mud | Needs flat mud visual. |
| `gravel` | `terrain_pebbles` | `Material.GRAVEL` | Gravel/stony ground | Existing fallback may be acceptable; alias desired. |
