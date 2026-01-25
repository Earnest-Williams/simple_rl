# Rendering Options

The renderer supports additional controls for how remembered tiles fade over time.

## Lighting Pipeline

The renderer combines the player's field of view (FOV) lighting falloff with
colored light sources stored on `GameMap.light_sources`. The lighting pipeline
uses `engine/render_lighting.py` to calculate the base FOV intensity map and
then accumulates colored light contributions (respecting occlusion via the FOV
algorithm) before applying the memory fade pass. This keeps light source color,
visibility, and memory rendering in a single shared pipeline.

## Memory Fade System

The memory fade system uses a simple color-blending approach to visually
represent the player's fading memory of previously explored areas. When a tile
is no longer visible but has been seen before (in the "fog of war"), its colors
are blended towards a neutral fade color based on how long ago it was last seen.

The memory fade implementation in `engine/render_lighting.py:apply_memory_fade()`
performs the following:

- **Color Blending Only**: Tiles in memory are rendered by blending their
  foreground and background colors towards a fade color (typically a neutral
  gray). The blend amount is determined by the tile's memory intensity value
  (0.0 = fully faded, 1.0 = recently seen).

- **Glyph Preservation**: The tile glyph indices remain unchanged—memory is
  expressed purely through color and brightness adjustments. This ensures that
  the underlying tile graphics are preserved while their appearance is dimmed
  to indicate they are no longer directly visible.

- **Deterministic Rendering**: The same memory state produces the same visual
  output across frames, ensuring stable and predictable rendering behavior.

The fade color and memory decay parameters are configured through `RenderConfig`
and `config.yaml` (see `memory_fade` section). Memory intensity values are
managed by the game state and updated based on time elapsed since each tile
was last seen, using a sigmoid decay function defined in the memory system.
