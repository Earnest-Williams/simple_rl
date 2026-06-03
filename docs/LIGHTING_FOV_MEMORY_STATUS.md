# Lighting, FOV, Memory, and Perception Migration Status

This matrix tracks production readiness for retiring the historical
`lights_dev/` R&D area. It is intentionally permanent documentation: future
work should update this file when ownership, tests, or deletion blockers change.

| Area | Production owner | Migrated production behavior | Coverage / status | Deletion blocker? |
|---|---|---|---|---|
| Advanced FOV | `game/world/light_fov.py` | Octant shadowcasting, side-bit output, cone limits, channel masks, subtractive visibility, diagonal side-bit refinement | Covered by `tests/game/world/test_light_fov.py`, including adjacent-blocker cardinal-face pruning | No known FOV blocker |
| Basic gameplay FOV / LOS | `game/world/fov.py`, `game/world/los.py` | Gameplay visibility, LOS helpers, edge-case handling | Covered by `tests/test_fov.py` and `tests/test_fov_edge_cases.py` | No known blocker |
| Advanced lighting | `engine/render_lighting.py` | Per-light side-aware RGBA contribution cache, additive RGB blend policy, cone softness, height incidence, channel masks, viewport slicing, geometry-version invalidation | Covered by `tests/engine/test_render_lighting_advanced.py` and `tests/test_render_lighting_cache.py` | No known lighting blocker |
| Lighting diagnostic | `complete_light_diagnostic.py` | Wall leak diagnostic using production `GameMap`, `LightSource`, `light_fov`, and `render_lighting` | Manual smoke command: `python complete_light_diagnostic.py` | Must run before deletion |
| Memory fade | `game/world/memory.py`, `game/world/game_map.py` | Sigmoid fade, visible-tile pruning, forgotten-tile pruning, strength and tile modifiers | Covered by `tests/game/world/test_memory_traits.py` | No known memory algorithm blocker |
| Memory traits orchestration | `game/game_state.py`, `game/world/game_map.py` | Player entity components resolve `MemoryTraits`; `GameMap.fade_memory()` resolves trait-adjusted parameters internally | Covered by memory trait tests and exercised through `GameState.update_fov()` | No known orchestration blocker |
| Scent and noise | `pathfinding/perception_systems.py`, `game/perception_events.py`, `game/game_state.py` | Runtime noise/scent event queues and pathfinding perception flow fields | Production-owned; not a `lights_dev` dependency | No known `lights_dev` blocker |
| R&D folder deletion | Repository root | Remove `lights_dev/` only after production parity and smoke checks are verified | Pending explicit deletion task | Yes: full suite and generated/manual smoke evidence required |
