# ADR 0004: Perception, FOV, LOS, and lighting boundaries

## Status

Completed for ownership boundaries and production ownership.

## Context

The repository previously contained production world-visibility modules, pathfinding
perception helpers, and a substantial experimentation area for lighting and
visibility. The overlapping sound, scent, FOV, LOS, and lighting code required
cleanup and a clear canonical path. The decision was made to migrate all
production-worthy advanced features into production modules.

## Decision

All production world visibility and line-of-sight behavior are implemented under
`game/world/` (including basic `game/world/fov.py`, `game/world/los.py`, and advanced light-aware `game/world/light_fov.py`).
Advanced rendering and lighting accumulation are implemented in `engine/render_lighting.py`.
All production-worthy algorithms have graduated into production, are covered by tests, and are documented.

## Consequences

- New gameplay calls must use production `game/world/light_fov.py` and `engine/render_lighting.py` for advanced FOV/lighting.
- `pathfinding/perception_systems.py` is the canonical owner for pathfinding-oriented sound and scent flow concepts.
- `game/systems/sound.py` remains responsible for runtime sound playback.
