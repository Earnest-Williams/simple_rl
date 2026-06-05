# ADR 0001: Canonical deterministic randomness

## Status

Accepted.

## Context

The codebase has historically included more than one path that exposes random
number generation. Repository policy requires deterministic, saveable game-logic
randomness and forbids direct use of Python, NumPy, OS, or UUID randomness in
game logic. The current implementation provides `utils.game_rng.GameRNG` as the sole
canonical randomness API.

## Decision

`utils.game_rng.GameRNG` is the canonical randomness API for game logic.
Compatibility wrapper modules are intentionally avoided so RNG semantics do
not drift across import paths.

All gameplay, generation, AI, combat, item, skill, effect, and simulation code
that needs randomness must accept or own an explicit `GameRNG` instance. Direct
`random`, `secrets`, `numpy.random`, `os.urandom`, and `uuid.uuid4` use is only
allowed in clearly non-game-logic boundaries or inside the canonical RNG module
when needed to implement the deterministic abstraction.

The nested `settlegen/` package is an approved boundary: it exposes a
same-seed/same-config deterministic API backed by NumPy RNG. Simple RL
integration code must derive the `settlegen` seed from `GameRNG`, as
`worldgen/settlements/generator.py` does, rather than allowing unseeded calls
to leak into game logic.

## Consequences

- New code imports `GameRNG` from `utils.game_rng`.
- Existing code must import from `utils.game_rng`; legacy RNG wrapper modules
    should be deleted rather than preserved.
- `scripts/check_deterministic_random.py` is the repository gate for accidental
  nondeterministic randomness outside approved boundaries.
- Any future RNG replacement must preserve state save/load and deterministic
  replay semantics before this ADR can be superseded.
