# ADR 0004: Perception, FOV, LOS, and lighting boundaries

## Status

Completed / Retired R&D.

## Context

The repository previously contained production world-visibility modules, pathfinding
perception helpers, and a substantial `lights_dev/` experimentation area. The
overlapping sound, scent, FOV, LOS, and lighting code required cleanup and a clear canonical path.
The decision was made to migrate all production-worthy advanced features to production and fully retire the `lights_dev/` directory.

## Decision

All production world visibility and line-of-sight behavior are implemented under
`game/world/` (including basic `game/world/fov.py`, `game/world/los.py`, and advanced light-aware `game/world/light_fov.py`).
Advanced rendering and lighting accumulation are implemented in `engine/render_lighting.py`.
The `lights_dev/` tree has been fully retired and deleted. All remaining production-worthy algorithms have graduated into production, covered by tests, and documented.

## Consequences

- New gameplay calls must use production `game/world/light_fov.py` and `engine/render_lighting.py` for advanced FOV/lighting.
- The `lights_dev/` directory has been deleted, removing any risk of importing experimental code.
- `pathfinding/perception_systems.py` is the canonical owner for pathfinding-oriented sound and scent flow concepts.
- `game/systems/sound.py` remains responsible for runtime sound playback.
