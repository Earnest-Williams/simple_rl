# ADR 0006: Dungeon debug viewer pipeline boundaries

## Status

Accepted.

## Context

The repository now has lightweight 2D and 3D dungeon debug viewers:
`play_debug.py` and `play_3d_debug.py`. Both can load an existing shaped
`generated_dungeon.arrow` file or invoke the shared orchestrator pipeline when
no file is present.

Without an explicit boundary, debug viewers can drift into alternate generation
entrypoints, duplicate spawn logic, or accumulate local map-repair behavior that
does not match production output.

## Decision

`orchestrator.run_pipeline` is the shared generation entrypoint for debug
viewers. `play_debug.py` and `play_3d_debug.py` are inspection tools over the
same shaped-map artifact and must not own independent dungeon generation or
connectivity repair.

Debug viewers may own:

1. Loading shaped-map arrays through `utils.shaped_map.load_shaped_map_as_arrays`;
2. Choosing a spawn tile from the Arrow node map when available;
3. Falling back to the nearest walkable tile when the preferred node tile is
   missing, blocked, or out of bounds; and
4. Presentation-specific camera, movement, zoom, and ray-casting logic.

Debug viewers must reuse orchestrator defaults for shared generation parameters
such as maximum nodes, maximum depth, and cellular-automata iterations.

## Consequences

- Changes to production cave generation should be made in `Dungeon/` and
  `orchestrator.py`, then observed through the debug viewers.
- Debug viewers should not silently reinterpret tile IDs beyond movement,
  spawning, and rendering needs.
- The default `generated_dungeon.arrow` file is a local generated artifact unless
  a change explicitly promotes a fixture with documented purpose.
- If a future editor or test harness needs richer map interaction, it should
  share the same shaped-map loading and orchestrator boundary rather than
  forking the generation path.
