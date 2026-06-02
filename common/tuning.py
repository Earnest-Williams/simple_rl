"""Centralized tuning constants shared across multiple subsystems.

This module is the single source of truth for numeric constants that appear
in two or more modules.  Subsystem-specific constants (e.g. worldgen physics,
skill-balance numbers) stay in their own ``constants.py``; only values that
are genuinely cross-cutting belong here.

All values are annotated with ``typing.Final`` and use immutable types.
"""

from __future__ import annotations

from typing import Final

# =============================================================================
# Memory / FOV fade
# =============================================================================

# Number of discrete decay levels for the memory-fade renderer.
# Used by: engine/render_lighting.py and legacy lighting constants/memory modules.
MEMORY_LEVEL_COUNT: Final[int] = 5

# =============================================================================
# Skill progression
# =============================================================================

# Hard cap on any single skill (DCSS-inspired 27-level system).
# Used by: skills/models.py, game/skills/progression.py
MAX_SKILL_LEVEL: Final[int] = 27

# =============================================================================
# Brainfuck interpreter
# =============================================================================

# Virtual tape cell count for the Brainfuck interpreter.
# Used by: magic/bf_backend.py, magic/brainfuck_numba.py, scripting_engine.py
BF_TAPE_SIZE: Final[int] = 30_000

# Safety limit on executed BF instructions before forced halt.
# Used by: magic/bf_backend.py, magic/brainfuck_numba.py
BF_MAX_STEPS: Final[int] = 10_000_000

# =============================================================================
# Grid / map dimensions
# =============================================================================

# Canonical grid sizes referenced across the codebase.
# Individual subsystems pick the size that fits their purpose; this tuple
# documents the set of "known good" sizes used in tests and production.
GRID_SIZES: Final[tuple[int, ...]] = (15, 64, 100, 128, 200)

# Default grid dimension for dungeon generation (orchestrator).
DEFAULT_GRID_SIZE: Final[int] = 128
