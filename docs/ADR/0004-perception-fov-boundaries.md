# ADR 0004: Perception, FOV, LOS, and lighting boundaries

## Status

Completed for ownership boundaries; R&D deletion deferred to ADR 0005.

## Context

The repository previously contained production world-visibility modules, pathfinding
perception helpers, and a substantial `lights_dev/` experimentation area. The
overlapping sound, scent, FOV, LOS, and lighting code required cleanup and a clear canonical path.
The decision was made to migrate all production-worthy advanced features to production and fully retire the `lights_dev/` directory.

## Decision

All production world visibility and line-of-sight behavior are implemented under
`game/world/` (including basic `game/world/fov.py`, `game/world/los.py`, and advanced light-aware `game/world/light_fov.py`).
Advanced rendering and lighting accumulation are implemented in `engine/render_lighting.py`.
The `lights_dev/` tree is frozen while deletion readiness is verified. All remaining production-worthy algorithms have graduated into production, covered by tests, and documented; ADR 0005 governs final folder retirement.

## Consequences

- New gameplay calls must use production `game/world/light_fov.py` and `engine/render_lighting.py` for advanced FOV/lighting.
- The `lights_dev/` directory remains frozen pending the deletion checks in ADR 0005; production code must not import it.
- `pathfinding/perception_systems.py` is the canonical owner for pathfinding-oriented sound and scent flow concepts.
- `game/systems/sound.py` remains responsible for runtime sound playback.
