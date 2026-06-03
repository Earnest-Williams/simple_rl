# ADR 0005: lights_dev retirement readiness

## Status

Accepted — retirement preparation in progress.

## Context

`lights_dev/` was an R&D workspace for side-aware FOV, colored lighting,
light-leak diagnostics, and memory fade behavior. The repository is preparing
to remove that folder, but production must first own every quality-relevant
feature and diagnostic path so deletion does not break gameplay, tests, or
maintenance workflows.

## Decision

Production ownership is now the only supported path for migrated features:

- `game/world/light_fov.py` owns advanced light-aware FOV: side bits, cone
  limits, channel masks, and subtractive visibility.
- `engine/render_lighting.py` owns side-aware per-light contribution caching,
  RGB blend policy, cone softness, height incidence, channel masking, viewport
  output, and scene-geometry-version invalidation.
- `game/world/memory.py`, `game/world/game_map.py`, and `game/game_state.py`
  own persistent map memory, memory traits, and player-state orchestration.
- `complete_light_diagnostic.py` uses production `GameMap`, `LightSource`,
  `light_fov`, and `render_lighting` APIs rather than importing `lights_dev`.

The `lights_dev/` folder must not be deleted until the documented blocker
checks pass, including full automated tests and the generated-dungeon/manual
smoke check.

## Consequences

- New code must not import `lights_dev`.
- Retirement work should add or update production tests rather than extending
  the R&D folder.
- After deletion, diagnostics and documentation remain available through the
  production owners listed above.
- If a missing R&D behavior is discovered, migrate it into a production owner
  first, then update the feature matrix and tests before deleting R&D content.
