# Lighting/FOV Visual Tool

Run the tool from the repository root:

```bash
python -m tools.lighting_fov_tool.main
```

The tool is a PySide6 GUI for inspecting lighting, field-of-view, marker
visibility, and light-shape tuning against a fixed dungeon scene. It complements
production regression tests; it does not replace them.

## Production checks

Before treating a visual change as correct, run the production lighting/FOV tests:

```bash
python -m pytest tests/engine/test_render_lighting_advanced.py tests/game/world/test_light_fov.py tests/test_lighting_leaks.py
```

These tests exercise production `GameMap`, `LightContributionCache`, and
`game.world.light_fov` behavior. The GUI is best for debugging and tuning.

## Lighting backends

The backend selector exposes multiple render paths:

- **Fast Diffuse**: a debug radial/diffuse preview path. It is useful for quick
  light-shape inspection and can optionally use line-of-sight radial masking.
- **Production Side-Aware**: the renderer-facing path backed by
  `LightContributionCache`. Use this when validating side-aware production light
  contribution behavior.
- **Unified Preview**: combines diffuse and side-aware buffers with tunable
  weights so differences between the two contributions are visible.
- **Raw Heatmap**: shows raw light intensity/color as a diagnostic heatmap rather
  than drawing normal tiles.

When a defect only appears in one backend, record the backend name in the bug or
PR notes.

## Gameplay view vs full light field

The view can be switched between:

- **Gameplay view**: clips rendered lighting to the player's current FOV and
  darkens unseen tiles. This matches what a player should perceive.
- **Full light field**: shows the complete computed light field for tuning,
  including light outside the player's visible area.

Use gameplay view for player-facing validation and full light field for emitter
placement, color, falloff, and leak debugging.

## Hidden emitter markers

Light-source markers are hidden in gameplay view when the emitter is outside the
player-visible area, unless hidden-light-source marker display is enabled. This
prevents the tool from implying the player can see unseen emitters while still
letting developers inspect inactive or hidden lights during debugging.

Monster markers follow the same general visibility principle: gameplay view shows
what the player can see, while full-field/debug views are for development.

## LOS radial mode

The Fast Diffuse/debug radial path has an LOS toggle. With LOS enabled, radial
light contribution is clipped by Bresenham-style line-of-sight through opaque
scene geometry. With LOS disabled, the debug radial contribution is distance-only
and can intentionally show through blockers for comparison.

Use the toggle to distinguish geometry/FOV defects from color, radius, or falloff
configuration issues.

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
  pytest commands above.
- If the GUI fails only because no display server is available, treat that as an
  environment limitation rather than a lighting regression.
- For non-GUI debugging, inspect the production tests and the helper scripts in
  this directory before adding new one-off diagnostics.
