Below is the combined migration TODO. It assumes the team has decided that **all remaining `lights_dev` capabilities are desired and must migrate before deletion**.

# `lights_dev` removal blocker TODO

## Goal

Remaining lights_dev production-worthy capabilities are migrated into canonical production modules, covered by tests, and documented as production-owned.

Current blocker categories:

1. Advanced FOV outputs.
2. Advanced lighting semantics.
3. Memory traits.
4. Documentation/status cleanup.
5. Deletion verification.

---

# 1. Advanced FOV migration

## 1.1 Create a production owner for light-aware FOV

Add one of the following:

Preferred:

```text
game/world/light_fov.py
```

Alternative:

```text
game/world/fov.py
```

I recommend `game/world/light_fov.py` to avoid overloading the existing general-purpose visibility API. Production `game/world/fov.py` currently owns ordinary visibility and callback shadowcasting, while these features are specifically for lighting/rendering.

## 1.2 Port side-bit output

Port the `lights_dev.fov` side-bit model into production.

Required outputs:

```python
visible_out: np.ndarray  # uint8 or bool
dist_out: np.ndarray     # int32 squared distance or equivalent
side_bits_out: np.ndarray  # uint8 bitmask
```

Required side constants:

```python
SIDE_N
SIDE_E
SIDE_S
SIDE_W
SIDE_NE
SIDE_SE
SIDE_SW
SIDE_NW
```

Behavior to preserve:

* Source tile sets all side bits.
* Cardinal exposure is based on vector from source to target.
* Exact diagonals set diagonal plus adjacent cardinals.
* Conservative refinement clears adjacent cardinal bits if neighboring blockers make that face unavailable.

This is the foundation for wall-face and 2.5D lighting.

## 1.3 Port angular cone constraints

Add FOV support for directional cones.

Required inputs:

```python
direction: float | None
cone_angle: float
```

or equivalent:

```python
start_angle: float | None
end_angle: float | None
```

Behavior to preserve:

* Omni lights use full-circle FOV.
* Directional lights only mark cells inside the cone.
* Source tile remains visible.
* Angle math must use the project’s screen-coordinate convention if the renderer expects `y` increasing downward.

## 1.4 Port channel/mask passthrough

Add optional per-cell channel masks to the light-aware FOV path.

Required inputs:

```python
cell_mask: np.ndarray | None  # uint32
light_channels: int
```

Behavior to preserve:

* Cells whose mask does not overlap the light’s channels are transparent for blocking.
* Those cells may be traversed by FOV.
* Lighting must still exclude masked cells during accumulation, unless design explicitly wants “transparent but lit.”

## 1.5 Port subtractive visibility

Add optional fractional visibility output.

Required output:

```python
visibility_out: np.ndarray  # float32, 0.0 to 1.0
```

Behavior to preserve:

* Source tile has visibility `1.0`.
* Intermediate opacity subtracts from visibility.
* Endpoint opacity is not subtracted, so opaque endpoint tiles can still be illuminated.
* Masked cells are transparent for visibility attenuation when channel passthrough applies.

## 1.6 Preserve LOS post-filtering

Port the post-FOV LOS occlusion filter or provide an equivalent production-tested behavior.

Reason: `lights_dev` computes shadowcast visibility, then filters potentially incorrect cells through Bresenham LOS. That reduces light leaks around blockers.

## 1.7 Add FOV tests

Add tests under something like:

```text
tests/game/world/test_light_fov.py
```

Required cases:

* Source tile has all side bits.
* Cardinal target gets correct face bit.
* Diagonal target gets diagonal plus adjacent cardinals.
* Adjacent blocker clears the relevant cardinal face bit.
* Cone FOV excludes cells outside the cone.
* Cone FOV includes cells inside the cone.
* Masked cells are transparent for blocking.
* Masked cells are excluded from lighting accumulation later.
* Subtractive visibility decreases through translucent cells.
* Opaque endpoint can be visible/lit while intermediate blocker blocks behind it.
* No wall leaks in diagonal and thin-wall cases.
* Output arrays are stable across repeated calls.

---

# 2. Advanced lighting migration

## 2.1 Extend production light model

Current production `LightSource` is too simple:

```python
x
y
radius
color
```

Extend or replace with a richer production model, probably in:

```text
game/world/game_map.py
```

or a better dedicated path:

```text
game/world/light.py
```

Recommended production dataclass:

```python
@dataclass(slots=True)
class LightSource:
    x: int
    y: int
    radius: int
    color: tuple[int, int, int]
    intensity: float = 1.0
    direction: float | None = None
    cone_angle: float = math.tau
    cone_softness: float = 0.0
    channels: int = 0xFFFFFFFF
    id: int = -1
    height: float = 0.0
```

## 2.2 Update production cache keys

Extend `LightContributionCache._param_key()` to include every parameter that changes output:

```python
x
y
radius
color
intensity
direction
cone_angle
cone_softness
channels
height
```

Otherwise cached lighting will be stale when a light rotates, changes cone softness, changes channels, or changes height.

## 2.3 Replace simple radial contribution with light-aware contribution

Update `engine/render_lighting.py` so `_compute_single_light_contribution()` can consume the new light-aware FOV output.

Required inputs from FOV:

```python
visible
dist
side_bits
visibility
```

Required lighting behavior:

* Directional cone support.
* Cone softness support.
* Channel-mask support.
* Height incidence support.
* Per-side accumulation.
* Optional premultiplied RGBA composition.
* Scene-sequence invalidation remains intact.
* Viewport slicing remains intact.

## 2.4 Decide final lighting buffer shape

There are two viable designs.

### Option A: Preserve production RGB output only

Use side bits and advanced attenuation internally, but collapse to:

```python
(h, w, 3)
```

Pros:

* Least renderer churn.
* Compatible with current `apply_colored_lighting()`.

Cons:

* Loses per-face composition at final render unless tile renderer can consume side data.

### Option B: Add side-aware lighting buffers

Use:

```python
(h, w, 8, 4)
```

for side premultiplied RGBA, then compose per tile.

Pros:

* Preserves the full `lights_dev` model.
* Enables wall-face lighting and 2.5D visual effects.

Cons:

* Requires renderer/tile-composition changes.

Since you said you want all of these features, I recommend **Option B**, with a compatibility adapter that also produces the existing RGB viewport buffer.

## 2.5 Port premultiplied RGBA accumulation

Port the per-side premultiplied RGBA accumulation model.

Required behavior:

* Each exposed side receives RGB and alpha contribution.
* Multiple lights accumulate.
* Oversaturated alpha is normalized before composition.
* Blend modes should support at least:

  * additive RGB compatibility;
  * premultiplied “over.”

## 2.6 Port directional softness

Implement cone softness in production accumulation.

Required behavior:

* `cone_softness == 0.0` gives hard edge.
* `cone_softness > 0.0` interpolates between inner cone and outer cone.
* Cells outside outer cone receive zero contribution.
* Cells inside inner cone receive full directional weight.
* Cells between inner and outer cone receive interpolated weight.

## 2.7 Port height incidence

Implement:

```python
incidence = dz / sqrt(dx*dx + dy*dy + dz*dz)
```

Decision needed:

* Should `height <= 0.0` skip light entirely, as `lights_dev` does?
* Or should `height == 0.0` mean normal 2D light with incidence `1.0`?

I recommend this production behavior:

```text
height <= 0.0 => use 2D lighting with incidence = 1.0
height > 0.0  => use 3D incidence
```

Reason: production currently has ordinary 2D/radial lights. Preserving those as height `0` is less surprising than making zero-height lights disappear.

## 2.8 Port channel semantics

Lighting must respect channels in two places:

1. FOV blocking:

   * Non-overlapping cells are transparent for blocking.
2. Accumulation:

   * Non-overlapping cells do not receive light.

Add tests for both. This distinction is important.

## 2.9 Add lighting tests

Add tests under something like:

```text
tests/engine/test_render_lighting_advanced.py
```

Required cases:

* Omni light still matches current additive RGB behavior where applicable.
* Directional light illuminates cells inside cone.
* Directional light does not illuminate cells outside cone.
* Cone softness creates lower contribution near cone edge.
* Rotating a directional light invalidates/recomputes cache.
* Changing `cone_angle` invalidates/recomputes cache.
* Changing `cone_softness` invalidates/recomputes cache.
* Changing `channels` invalidates/recomputes cache.
* Changing `height` invalidates/recomputes cache.
* Channel-masked blockers are transparent to FOV.
* Channel-masked cells receive no light.
* Per-side buffer receives contribution only on exposed sides.
* Premultiplied composition clamps or normalizes correctly.
* Removed lights subtract their old contribution.
* Scene geometry version invalidates all relevant cached light contributions.
* Viewport output remains deterministic.

---

# 3. Memory traits migration

## 3.1 Add production `MemoryTraits`

Add to one of:

Preferred:

```text
game/world/memory.py
```

Alternative:

```text
game/components/memory.py
```

Recommended dataclass:

```python
@dataclass(frozen=True, slots=True)
class MemoryTraits:
    intelligence: int = 10
    has_confusion: bool = False
    has_illness: bool = False
    fatigue_level: float = 0.0
    magic_memory_bonus: float = 0.0
    location_familiarity: float = 0.0
```

## 3.2 Port trait validation

Preserve clamp behavior:

```text
intelligence: 1..30
fatigue_level: 0.0..1.0
magic_memory_bonus: 0.0..10.0
location_familiarity: 0.0..1.0
```

## 3.3 Port decay modifier calculation

Port:

```python
compute_decay_modifier()
get_effective_parameters()
```

Semantics:

* Higher intelligence slows decay.
* Confusion speeds decay.
* Illness speeds decay.
* Fatigue speeds decay.
* Magic memory bonus slows decay.
* Location familiarity slows decay.
* Modifiers compose multiplicatively.
* Final modifier is clamped above zero.

## 3.4 Decide ownership of traits

Do not store actor traits directly in `GameMap`.

Recommended architecture:

```text
Actor/player state owns MemoryTraits.
Game/system layer resolves traits into steepness and midpoint.
GameMap.fade_memory() receives resolved parameters.
```

Keep `GameMap` focused on map-shaped state:

```python
memory_intensity
memory_strength
last_seen_time
memory_fade_mask
tile_memory_modifiers
prev_visible
```

## 3.5 Integrate with existing production memory arrays

Production memory already supports:

* repeated exposure via `memory_strength`;
* tile-specific modifiers via `tile_memory_modifiers`;
* sparse update via `memory_fade_mask`.

Trait modifiers should combine with these, not replace them.

Recommended flow:

```python
traits = player.memory_traits
steepness, midpoint = traits.get_effective_parameters()
game_map.fade_memory(current_time, steepness, midpoint)
```

The existing `update_memory_fade()` then applies memory strength and tile modifiers.

## 3.6 Canonical API: resolve_memory_decay_parameters()

Add the canonical helper:

```python
def resolve_memory_decay_parameters(
    traits: MemoryTraits,
    *,
    base_steepness: float,
    base_midpoint: float,
) -> tuple[float, float]:
    ...
```

This keeps tuning centralized and makes tests easier.

## 3.7 Add memory trait tests

Add tests under:

```text
tests/game/world/test_memory_traits.py
```

Required cases:

* Default traits return base behavior.
* Intelligence above base slows decay.
* Intelligence below base speeds decay.
* Confusion speeds decay.
* Illness speeds decay.
* Fatigue scales decay.
* Magic memory bonus slows decay.
* Location familiarity slows decay.
* Combined modifiers compose deterministically.
* Clamp behavior works.
* Trait-derived parameters affect `update_memory_fade()`.
* Traits compose with `memory_strength`.
* Traits compose with `tile_memory_modifiers`.
* Visible tiles still refresh to full memory.
* Forgotten tiles are pruned from `needs_update_mask`.

---

# 4. Scent/noise/perception verification

This area appears already migrated to `pathfinding/perception_systems.py`, but include a verification task so deletion is safe.

## 4.1 Confirm production parity

Verify production covers:

* full-slice flow reset;
* Sil-style scent global counter;
* 5×5 scent stamping;
* scent LOS/path blocking;
* closed-door scent attenuation;
* two-d10 monster perception checks;
* deterministic RNG behavior;
* ordered monster alert output.

## 4.2 Add or confirm tests

Required test coverage:

* Noise flow slice resets fully before rebuild.
* Old costs do not survive after source moves.
* Scent counter decrements.
* Scent reset cycle preserves/rebases recent scent and clears old scent.
* 5×5 scent stamp uses the adjustment table.
* Walls and secret doors block scent.
* Closed doors attenuate scent.
* `skill_check()` uses two d10 rolls.
* `monster_perception()` returns deterministic ordered IDs.

## 4.3 Decide whether to port anything from `lights_dev/scent_and_sound_flow.py`

Expected decision:

```text
No remaining migration required. Production owner is pathfinding/perception_systems.py.
```

Document that decision before deletion.

---

# 5. Production API cleanup

## 5.1 Define canonical APIs

After migration, document the canonical production APIs:

```text
game/world/fov.py
game/world/light_fov.py
game/world/los.py
game/world/memory.py
game/world/light.py
engine/render_lighting.py
pathfinding/perception_systems.py
```

## 5.2 Avoid production imports from `lights_dev`

Run a code search and ensure no production code imports:

```python
lights_dev
```

If any imports remain, replace them with production modules.

## 5.3 Remove compatibility shims only after tests pass

Do not keep long-lived wrappers like:

```python
from lights_dev.fov import compute_fov_all_octants
```

The final production code should not require `lights_dev`.

---

# 6. Documentation TODO

## 6.1 Update `lights_dev/README.md` before deletion

Replace the broad parity claim with a migration record.

Suggested wording:

```markdown
`lights_dev/` was an R&D harness for advanced FOV, lighting, memory, scent, and noise systems. Its remaining production-worthy features have been migrated as follows:

- Light-aware FOV side bits, cones, masks, and subtractive visibility: `game/world/light_fov.py`
- Advanced lighting, directional cones, channels, height incidence, and side-aware RGBA: `engine/render_lighting.py`
- Memory trait modifiers: `game/world/memory.py` and actor/player memory trait owner
- Scent/noise perception: `pathfinding/perception_systems.py`

The directory is now safe to delete.
```

## 6.2 Update current status docs

Update:

```text
docs/CURRENT_STATUS.md
```

Change `lights_dev/` from active R&D to removed/archive status.

## 6.3 Update or supersede stale ADR

Since the accepted ADR is out of date, do one of the following:

Preferred:

```text
docs/ADR/0005-lights-dev-retirement.md
```

Record:

* `lights_dev/` is retired.
* Production ownership has moved to specific modules.
* Advanced FOV and lighting semantics were intentionally retained and migrated.
* No new code may import `lights_dev`.

Alternative:

Update ADR 0004 directly if that is your repository convention.

## 6.4 Add feature matrix

Add a compact feature matrix somewhere permanent:

```text
docs/LIGHTING_FOV_MEMORY_STATUS.md
```

Suggested table:

| Feature                | Old owner                            | New owner                                | Tests |
| ---------------------- | ------------------------------------ | ---------------------------------------- | ----- |
| Basic FOV              | `lights_dev/fov.py`                  | `game/world/fov.py`                      | yes   |
| Side-bit FOV           | `lights_dev/fov.py`                  | `game/world/light_fov.py`                | yes   |
| Cone FOV               | `lights_dev/fov.py`                  | `game/world/light_fov.py`                | yes   |
| Channel mask FOV       | `lights_dev/fov.py`                  | `game/world/light_fov.py`                | yes   |
| Subtractive visibility | `lights_dev/fov.py`                  | `game/world/light_fov.py`                | yes   |
| Additive RGB lighting  | `lights_dev/lighting.py`             | `engine/render_lighting.py`              | yes   |
| Directional lighting   | `lights_dev/lighting.py`             | `engine/render_lighting.py`              | yes   |
| Cone softness          | `lights_dev/lighting.py`             | `engine/render_lighting.py`              | yes   |
| Per-side RGBA          | `lights_dev/lighting.py`             | `engine/render_lighting.py`              | yes   |
| Height incidence       | `lights_dev/lighting.py`             | `engine/render_lighting.py`              | yes   |
| Memory fade            | `lights_dev/memory.py`               | `game/world/memory.py`                   | yes   |
| Memory traits          | `lights_dev/memory.py`               | `game/world/memory.py` or component path | yes   |
| Scent/noise            | `lights_dev/scent_and_sound_flow.py` | `pathfinding/perception_systems.py`      | yes   |

---

# 7. Deletion checklist

Only delete `lights_dev/` after all of these are true:

```text
[ ] Light-aware FOV production module exists.
[ ] Side-bit output migrated.
[ ] Cone constraints migrated.
[ ] Channel/mask passthrough migrated.
[ ] Subtractive visibility migrated.
[ ] LOS post-filtering or equivalent leak prevention migrated.
[ ] Advanced light model exists in production.
[ ] Lighting cache key includes all advanced parameters.
[ ] Directional lighting migrated.
[ ] Cone softness migrated.
[ ] Channel lighting migrated.
[ ] Height incidence migrated.
[ ] Per-side premultiplied RGBA migrated.
[ ] Compatibility RGB output still works.
[ ] MemoryTraits migrated.
[ ] Trait-derived memory decay integrated.
[ ] Memory trait tests added.
[ ] Scent/noise production parity confirmed.
[ ] No production imports from lights_dev remain.
[ ] Feature matrix added or updated.
[ ] CURRENT_STATUS updated.
[ ] ADR updated or superseded.
[ ] Full test suite passes.
[ ] Manual smoke test of FOV/lighting/memory in a generated dungeon passes.
[ ] lights_dev directory deleted.
```

---

# Suggested implementation order

## Phase 1: Preserve behavior behind tests

1. Add characterization tests against `lights_dev` behavior for:

   * side bits;
   * cone FOV;
   * channel masks;
   * subtractive visibility;
   * directional lighting;
   * cone softness;
   * side RGBA;
   * memory traits.

This phase creates a safety net before touching production.

## Phase 2: Migrate FOV

2. Add `game/world/light_fov.py`.
3. Port side-bit, cone, mask, distance, and visibility outputs.
4. Add production tests.
5. Stop using any `lights_dev.fov` reference.

## Phase 3: Migrate lighting

6. Add richer production `LightSource`.
7. Extend `LightContributionCache`.
8. Add side-aware contribution buffers.
9. Add compatibility RGB composition.
10. Add advanced lighting tests.

## Phase 4: Migrate memory traits

11. Add `MemoryTraits`.
12. Integrate trait-derived parameters into memory fade orchestration.
13. Add memory trait tests.

## Phase 5: Verify perception

14. Confirm `pathfinding/perception_systems.py` covers the scent/noise items.
15. Add missing tests if any.

## Phase 6: Retire `lights_dev`

16. Update docs.
17. Remove imports.
18. Delete `lights_dev/`.
19. Run tests and smoke test.

---

