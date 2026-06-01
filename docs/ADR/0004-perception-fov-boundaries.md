# ADR 0004: Perception, FOV, LOS, and lighting boundaries

## Status

Accepted.

## Context

The repository contains production world-visibility modules, pathfinding
perception helpers, and a substantial `lights_dev/` experimentation area. The
audit identified overlapping sound, scent, FOV, LOS, and lighting code as an
area where future contributors need a clear canonical path.

## Decision

Production world visibility and line-of-sight behavior belongs under
`game/world/`, currently including `game/world/fov.py`, `game/world/visibility.py`,
and `game/world/los.py`. Production pathfinding and perception utilities that
serve AI routing or sound/scent concepts belong under `pathfinding/` or the
relevant `game/systems/pathfinding/` modules. The `lights_dev/` tree remains an
R&D harness for lighting, FOV, sound, scent, and visualization experiments.

Algorithms may graduate from `lights_dev/` only through focused production
patches that add tests or runnable harness coverage, preserve deterministic
inputs, and update status documentation.

## Consequences

- New gameplay calls should prefer `game/world/` visibility and LOS APIs instead
  of importing experimental `lights_dev/` modules.
- `pathfinding/perception_systems.py` remains the documented owner for
  pathfinding-oriented sound and scent flow concepts.
- `lights_dev/scent_and_sound_flow.py` is retained as a repaired experimental
  module, not as the production sound playback owner.
- `game/systems/sound.py` remains responsible for runtime sound playback unless
  a future ADR supersedes this boundary.
