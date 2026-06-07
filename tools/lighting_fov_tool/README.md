# Lighting/FOV Visual Tool

Run the GUI tool from the repository root:

```bash
python -m tools.lighting_fov_tool.main
```

The tool opens a fixed lighting/FOV scene for checking light leaks, emitter
visibility, marker visibility, light color/radius sliders, compositing, cone and
beam controls, ambient spill, and gameplay-view clipping. It complements the
production regression tests; it does not replace them.

## Production checks

Before treating a visual change as correct, run the production lighting/FOV tests:

```bash
python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py
```

These tests exercise production `GameMap`, `LightContributionCache`, and
`game.world.light_fov` behavior. The GUI is best for debugging and tuning.

## Lighting backends

The tool exposes two important lighting paths, plus comparison views built from
them:

- **Debug radial light / Fast Diffuse**: a tool-only, readable radial accumulator
  for inspecting slider behavior, light color, radius, falloff, LOS clipping, and
  compositing. It is intentionally simple and is not the production renderer path.
- **Production `LightContributionCache` / Production Side-Aware**: the
  renderer-facing production lighting path. Use this backend when validating
  production side-aware light contribution behavior.

Additional comparison/debug views may combine or visualize those paths:

- **Unified Preview** combines diffuse and side-aware buffers with tunable
  weights so differences between the debug radial contribution and production
  contribution are visible.
- **Raw Heatmap** shows raw light intensity/color as a diagnostic heatmap rather
  than drawing normal tiles.

When a defect only appears in one backend, record the backend name in the bug or
PR notes.

## Debug visualization toggles

The Debug Visualization controls are intentionally separate from the selected
lighting backend:

- **Show full light field**: disables gameplay FOV clipping and displays the full
  computed light field for tuning emitter placement, color, radius, falloff, and
  leaks.
- **Show hidden emitters**: displays markers for inactive or hidden light sources
  that gameplay view would normally suppress.
- **Use LOS for debug radial**: makes the debug radial/Fast Diffuse path clip
  contribution through scene geometry using line-of-sight. With this disabled,
  debug radial contribution is distance-only and may intentionally pass through
  blockers for comparison.

## Gameplay view, full light field, and marker visibility

The view can be switched between:

- **Gameplay view**: clips rendered lighting to the player's current FOV and
  darkens unseen tiles. This matches what a player should perceive.
- **Full light field**: shows the complete computed light field for tuning,
  including light outside the player's visible area.

Marker visibility follows the selected view:

- In **full-light-field mode**, emitter markers remain visible so developers can
  inspect source placement while tuning the complete light buffer.
- In **gameplay view**, hidden emitter markers are suppressed unless **Show hidden
  emitters** is enabled. This prevents the tool from implying that a player can
  see unseen emitters while still allowing explicit debug inspection.

Monster markers follow the same general visibility principle: gameplay view shows
what the player can see, while full-field/debug views are for development.

## Cone, beam, and softness controls

Each configured light can be tuned with shape controls:

- **Cone angle** controls angular spread for cone lights.
- **Beam width** and **beam length** control rectangular/linear beam coverage.
- **Softness** feathers cone or beam edges instead of using a hard cutoff.

These settings are stored in the tool configuration and exported with the other
light properties.

## Ambient spill controls

Ambient spill is a weak room-aware post-pass that spreads light from direct-lit
floor cells into nearby floor space. The tool exposes both global and per-light
ambient-spill controls:

- Enable/disable spill.
- Extra spill radius.
- Spill strength.
- Spill decay.
- Maximum RGB contribution.
- Debug display mode that shows only the spill contribution.

Use ambient-spill debug mode when diagnosing whether a tile is lit by direct
emitter contribution or by the spill pass.

## Configuration export/import

The tool can load and export text configuration files for tile colors and light
parameters. The default configuration lives next to the tool code as
`default_config.txt`.

Exported configuration includes cone/beam/softness and ambient-spill fields, so
include the exported file in PRs when a visual tuning change is intentional.

## GUI and headless limitations

- The main tool requires a working Qt/PySide6 GUI environment.
- In headless CI or containers without display forwarding, prefer the production
  pytest command above.
- If the GUI fails only because no display server is available, treat that as an
  environment limitation rather than a lighting regression.
- For non-GUI debugging, inspect the production tests and the helper scripts in
  this directory before adding new one-off diagnostics.
