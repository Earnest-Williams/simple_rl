# ADR 0001: Canonical deterministic randomness

## Status

Accepted.

## Context

The codebase has historically included more than one path that exposes random
number generation. Repository policy requires deterministic, saveable game-logic
randomness and forbids direct use of Python, NumPy, OS, or UUID randomness in
game logic. The current implementation provides `utils.game_rng.GameRNG` and a
compatibility re-export at `worldgen.game_rng.GameRNG`.

## Decision

`utils.game_rng.GameRNG` is the canonical randomness API for game logic.
`worldgen/game_rng.py` remains a compatibility re-export only; it must not grow
independent behavior or separate state semantics.

All gameplay, generation, AI, combat, item, skill, effect, and simulation code
that needs randomness must accept or own an explicit `GameRNG` instance. Direct
`random`, `secrets`, `numpy.random`, `os.urandom`, and `uuid.uuid4` use is only
allowed in clearly non-game-logic boundaries or inside the canonical RNG module
when needed to implement the deterministic abstraction.

## Consequences

- New code imports `GameRNG` from `utils.game_rng`.
- Existing code that imports from `worldgen.game_rng` can continue to run, but
  should be migrated when touched for unrelated work.
- `scripts/check_deterministic_random.py` is the repository gate for accidental
  nondeterministic randomness outside approved boundaries.
- Any future RNG replacement must preserve state save/load and deterministic
  replay semantics before this ADR can be superseded.
