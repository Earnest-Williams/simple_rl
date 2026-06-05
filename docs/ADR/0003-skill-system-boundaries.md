# ADR 0003: Skill-system ownership boundaries

## Status

Accepted.

## Context

Skill-system documentation previously contained conflicting integration claims,
and the repository contains both top-level `skills/` modules and game-facing
`game/skills/` modules. `docs/Skill System Status.md` now centralizes current
status, but the implementation boundary still needs an explicit decision.

## Decision

`game/skills/` owns game-facing skill execution and integration points used by
runtime gameplay systems. The top-level `skills/` package owns reusable skill
models, rule data, progression helpers, manuals, prerequisites, synergies, and
research support code that may be consumed or adapted by the game-facing layer.

`docs/Skill System Status.md` is the source of truth for maturity and
integration claims. Older skill documents may provide design history or feature
notes, but they must link back to the status page rather than making independent
production-readiness claims.

## Consequences

- New runtime hooks should be added under `game/skills/` or a documented caller
  in `game/`.
- New reusable data/rule helpers may live under top-level `skills/` when they do
  not depend on live game state.
- When a skill feature is promoted, update tests and
  `docs/Skill System Status.md` in the same change.
- Duplicate or experimental skill documents should be reconciled through status
  links instead of being silently edited into contradictory narratives.
