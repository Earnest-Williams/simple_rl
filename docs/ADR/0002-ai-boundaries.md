# ADR 0002: Production AI and R&D AI boundaries

## Status

Accepted.

## Context

The repository contains several AI-related areas with different maturity levels:
main-game AI modules under `game/ai/`, a community-AI research area under
`ai/`, and a GOAP simulation/testbed under `auto/`. The audit identified this
as a source of ambiguity because unreferenced modules can look stale even when
they are intentional experiments or subsystem harnesses.

## Decision

Production gameplay AI belongs under `game/ai/` and is integrated through the
main game state, entity, planning, and action systems. The `auto/` tree is the
GOAP tuning and simulation harness; it may inform production behavior, but it is
not itself the production game loop. The top-level `ai/` tree is an R&D area for
community and large-scale behavior experiments until individual features are
promoted into `game/ai/` with tests and current documentation.

Promotion from R&D to production requires:

1. a small integration patch in `game/ai/` or the calling game system;
2. deterministic `GameRNG` ownership for any randomness;
3. runnable tests or a documented harness command; and
4. status updates in `docs/CURRENT_STATUS.md` when maturity changes.

## Consequences

- Do not delete `ai/` or `auto/` solely because static import analysis shows no
  inbound imports from production modules.
- New production behavior should not import directly from top-level `ai/` unless
  that module is explicitly promoted and documented.
- R&D modules should avoid claiming production readiness until their integration
  path, checks, and ownership are documented.
