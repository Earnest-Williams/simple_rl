# Architecture decision records

Architecture decision records (ADRs) capture current repository-wide decisions
that prevent duplicate systems, R&D prototypes, and compatibility shims from
being mistaken for canonical implementation paths.

## Current records

| ADR | Decision area |
| --- | --- |
| [0001-canonical-rng.md](0001-canonical-rng.md) | Canonical deterministic randomness ownership. |
| [0002-ai-boundaries.md](0002-ai-boundaries.md) | Production AI versus R&D AI boundaries. |
| [0003-skill-system-boundaries.md](0003-skill-system-boundaries.md) | `game/skills/` and top-level `skills/` ownership. |
| [0004-perception-fov-boundaries.md](0004-perception-fov-boundaries.md) | Production FOV, LOS, perception, and lighting boundaries. |
| [0005-cave-connectivity-repair.md](0005-cave-connectivity-repair.md) | Cave connectivity repair ownership after cellular automata. |
| [0006-debug-viewer-pipeline-boundaries.md](0006-debug-viewer-pipeline-boundaries.md) | Dungeon debug viewer and orchestrator pipeline boundaries. |
| [0007-magic-work-runtime-boundaries.md](0007-magic-work-runtime-boundaries.md) | Magic parser, executor, and effect-handler runtime boundaries. |

## Status values

- **Accepted:** the decision is current and should be followed for new work.
- **Superseded:** another ADR replaces this decision.
- **Proposed:** the decision is under review and should not be treated as final.
