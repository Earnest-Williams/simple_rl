# ADR 0007: Magic work runtime boundaries

## Status

Accepted.

## Context

The magic subsystem has three related but distinct concepts:

- `magic.models.Work`: parser/compiler output for ledger-style magical work
  declarations and effect-level calculation.
- `magic.executor.Work`: executable runtime work consumed by
  `magic.executor.execute_work`.
- `game/effects/handlers.py`: production effect handlers that can be adapted to
  runtime work execution through `(Art, Substance)` dispatch.

`docs/Current Status.md` correctly marks magic as in development. The system has
useful pieces, but production claims need a narrow integration boundary and
tests before broader spellcasting gameplay is added.

## Decision

`magic.executor.Work` is the runtime execution type. Top-level `magic.Work`
resolves to that executable type. Parser/compiler work remains available as
`magic.ModelWork` and `magic.models.Work`.

Runtime execution is owned by `magic.executor.execute_work`:

1. Check wards and counterseals.
2. Verify required actor seals, fonts, and vents through the `GameState`
   interface.
3. Dispatch an effect handler for the work's `(Art, Substance)` pair, or fall
   back to an explicit callable on the work.
4. Advance friction and trigger friction callbacks.

`game/effects/__init__.py` adapts existing effect handlers into the magic
executor registry. New spellcasting gameplay should call the executor rather
than calling effect handlers directly.

## Consequences

- Parser tests should import `magic.models.Work` when they mean compiled ledger
  work.
- Runtime tests should import `magic.Work` or `magic.executor.Work`.
- New production spellcasting work should add focused executor tests before
  claiming integration status in `docs/Current Status.md`.
- The next production slice should add a small game-facing command or system
  wrapper that builds an executor work, calls `execute_work`, and records the
  result for UI/messages, without expanding the full spell catalogue yet.
