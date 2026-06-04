# ADR 0005: Cave connectivity repair ownership

## Status

Accepted.

## Context

The cave-generation pipeline builds a backbone graph, rasterizes it into a grid,
and then applies cellular automata. Cellular automata can create disconnected
walkable islands, erase narrow graph passages, or leave tiny rasterization
fragments. Those artifacts are hard to debug later because downstream viewers,
simulation code, and map loaders receive only the shaped tile/depth data.

The current implementation performs connectivity repair inside
`Dungeon/shaper.py` after cellular automata and before shaped map export.

## Decision

`Dungeon/shaper.py` owns production cave connectivity repair for shaped cave
output. Repair is part of `generate_shaped_cave`, not a debug-viewer concern and
not a post-load compatibility pass.

Connectivity repair must:

1. Treat `CAVE_FLOOR`, `SHAFT_OPENING`, and `DOOR_OPEN` as walkable;
2. Prefer graph-aware repairs derived from processed parent/child node edges;
3. Delete small disconnected fragments below the configured component-size
   threshold instead of connecting every crumb;
4. Preserve semantic blockers such as `CLIFF_EDGE` and `DOOR_CLOSED`; and
5. Keep depth/type grids coherent with any corridor cells it creates.

## Consequences

- Debug players and runtime consumers should expect exported shaped maps to be
  walkable without adding their own connectivity repair.
- Future changes to walkability semantics must update the repair walkable mask
  and the debug-player movement rules together.
- Repair tuning belongs near `repair_connectivity` in `Dungeon/shaper.py` unless
  the whole shaping pipeline is moved behind a new production interface.
- Generated Arrow output remains an artifact of the current pipeline; repairing
  old exported maps in place is not the canonical migration path.
