# Repository Audit: file usefulness and documentation accuracy

Date: 2026-05-31

## Scope and method

This audit was requested as a careful read-through of every repository file, with
three passes and running notes. I read all 660 non-`.git`, non-`.venv` files in
the working tree, including text files, scripts, configuration, generated
metadata, and binary font/image assets. For binary PNG assets I validated
presence and repository references rather than attempting semantic line-by-line
review; SVG assets were read as text and also checked as part of the font asset
set.

Commands used during the audit:

- `rg --files -g 'AGENTS.md' -g '!**/.git/**' -g '!**/.venv/**'`
- `rg --files -g '!**/.git/**' -g '!**/.venv/**' | sort`
- Python inventory scripts using `Path.rglob()` and `Path.read_bytes()` to read
  every file.
- Python AST import graph script for all `.py` files.
- Markdown link validation script for all `.md` files.
- Repository reference scans with `rg`.
- `python -m compileall -q .`
- `python scripts/sync_llm_policy.py --check`
- `python scripts/check_deterministic_random.py`
- `pytest -q`

## Executive summary

1. The repository was not cleanly runnable during the original audit because
   `lights_dev/scent_and_sound_flow.py` contained a concatenated duplicate module
   body. That blocker has been repaired and targeted compilation now succeeds.
2. The highest-confidence generated-file cleanup item, `auto/gui.egg-info/*`, has
   been removed from the working tree and remains covered by the repository
   `*.egg-info/` ignore rule.
3. `fonts/classic_roguelike_preview.png` is retained intentionally and is now
   documented as the classic roguelike tile-set preview/contact sheet.
4. The stale overview/compliance documentation findings from the first audit
   have been refreshed for the current tree, including canonical RNG location,
   absence of the legacy tree, active workflow files, and SDL/Qt dependencies.
5. Skill-system status has been consolidated in `docs/SKILL_SYSTEM_STATUS.md`;
   older skill-system docs now point readers to that current source of truth.
6. The most useful missing documents identified by the audit are now addressed:
   `docs/RUNBOOK.md`, `docs/CURRENT_STATUS.md`, `docs/ASSET_PIPELINE.md`,
   `docs/TESTING.md`, `docs/CONFIG_REFERENCE.md`, `docs/ADR/`, and
   `docs/DEPRECATION_POLICY.md` exist. Remaining work is implementation cleanup
   and enforcing all quality gates in CI.
7. The deterministic-random checker is now wired into the existing policy-sync
   workflow so CI catches direct nondeterministic randomness outside approved
   boundaries.

## Resolution update: mypy package mapping blockers

Date: 2026-06-01

The `lights_dev/fov.py` duplicate-module mapping blocker is now addressed:

1. Added `lights_dev/__init__.py` so editable installs and tests can import the
   experimental lighting package consistently.
2. Enabled mypy's `explicit_package_bases` option in `pyproject.toml` so files
   below the repository root are mapped from an explicit base instead of being
   inferred both as top-level modules and package modules.
3. Verified that `mypy .` now progresses past `lights_dev/fov.py` and the same
   namespace-package ambiguity in `tools/` and `Dungeon/`. The remaining mypy
   failures are pre-existing missing third-party stubs, import resolution
   problems, and downstream typing issues.

## Resolution update: ADRs, deprecation policy, and CI RNG gate

Date: 2026-06-01

The remaining documentation-policy gap from this audit is now addressed:

1. Added `docs/ADR/` with accepted decisions for canonical RNG ownership,
   production AI versus R&D AI boundaries, skill-system ownership boundaries,
   and perception/FOV/lighting boundaries.
2. Added `docs/DEPRECATION_POLICY.md` to classify production files, R&D
   experiments, historical notes, generated artifacts, and removal candidates.
3. Classified `notes/basicrl_project.txt`, `notes/to implement.txt`, and
   `notes/code_basicrl.txt` as retained historical notes with explicit deletion
   conditions instead of unresolved scratch files.
4. Updated `docs/CURRENT_STATUS.md` to link the new ADRs and deprecation policy
   from the subsystem status matrix.
5. Wired `python scripts/check_deterministic_random.py` into
   `.github/workflows/llm_policy_sync_check.yml`, closing the CI follow-up for
   deterministic-randomness enforcement.

## Resolution update: runbook, testing, config, and status docs

Date: 2026-06-01

The next documentation follow-up is now partially addressed:

1. Added `docs/RUNBOOK.md` as the canonical quick-start runbook for environment
   setup, main entrypoints, subsystem harnesses, asset generation, and standard
   repository checks.
2. Added `docs/TESTING.md` to collect required local checks, their purpose,
   current CI coverage gaps, and troubleshooting notes for dependency or
   headless-GUI limitations.
3. Added `docs/CONFIG_REFERENCE.md` to document checked-in configuration and
   data files, current consumers, high-level schema shapes, generated metadata,
   and change guidelines.
4. Added `docs/CURRENT_STATUS.md` as a concise module ownership/status matrix
   covering maturity, runnable commands, integration state, and follow-up
   decisions for integrated and R&D subsystems.
5. Local verification for this documentation pass now shows Markdown links,
   compileall, policy sync, deterministic-random checks, and `pytest -q` passing
   after installing `.[dev]`; Black/Ruff formatting, Ruff lint, and mypy still
   expose pre-existing codebase issues outside this documentation change.
6. The ADR and deprecation-policy follow-ups were closed in the later
   documentation-policy pass recorded above.

## Resolution update: asset pipeline and dependency-source documentation

Date: 2026-06-01

The first documentation-policy follow-up is now partially addressed:

1. Added `docs/ASSET_PIPELINE.md` as the source of truth for font asset
   ownership, generated glyph metadata, retained generated artifacts, and review
   expectations.
2. Documented that `fonts/glyphs.yaml` and `fonts/glyphs_report.txt` are
   generated by `scripts/generate_glyphs.py` but intentionally checked in for
   runtime convenience and reviewability.
3. Marked `fonts/tree.txt` as archival/diagnostic rather than a current source
   of truth; contributors should prefer `rg --files fonts` for inventory.
4. Replaced the non-portable `requirements.txt` Conda export with an archival
   note pointing to `pyproject.toml` and `environment.yml`, and updated
   contributor setup instructions to use `pip install -e ".[dev]"`.
5. Added an explicit follow-up that `requirements.txt` should be removed once
   downstream tooling no longer expects the placeholder file.

## Resolution update: deterministic-random checker hardening

Date: 2026-06-01

The deterministic-random checker follow-up is now addressed:

1. `scripts/check_deterministic_random.py` now scans Python AST structure instead
   of raw file text, so comments, docstrings, and ordinary string literals no
   longer create false positives.
2. The checker skips its own source file while retaining the canonical exemption
   for `utils/game_rng.py`.
3. Focused regression tests in `tests/test_check_deterministic_random.py` cover
   ignored comments/strings, aliased imports, NumPy randomness, `os.urandom`,
   and `uuid.uuid4`.
4. Import alias expansion now keeps non-aliased root module names stable, which
   prevents `import numpy.random` from incorrectly rewriting unrelated
   `numpy.*` attribute usage.
5. The checker and focused tests now use explicit local type annotations and
   grouped constant documentation consistent with the repository style guide.
6. `python scripts/check_deterministic_random.py` now passes locally and runs in
   `.github/workflows/llm_policy_sync_check.yml`.

## Resolution update: first five cleanup items

Date: 2026-05-31

The first five items from the recommended cleanup sequence have been addressed:

1. `lights_dev/scent_and_sound_flow.py` now compiles as a single module, has one
   module header, and identifies itself by its actual filename while noting that
   production sound playback lives in `game/systems/sound.py`.
2. `auto/gui.egg-info/` generated package metadata was removed from the working
   tree; it remains covered by the existing `*.egg-info/` ignore rule.
3. `fonts/classic_roguelike_preview.png` is documented in
   `fonts/glyph_name_chart.md` with explicit ownership (atlas/chart maintainers),
   regeneration guidance (local nearest-neighbor 10x scale from
   `fonts/classic_roguelike_white.png`), and retention criteria (kept as a stable
   checked-in review artifact, updated only with atlas/glyph-map changes).
4. The stale overview/compliance docs were refreshed for the current tree:
   `README.md`, `.github/copilot-instructions.md`,
   `docs/SYSTEMS_INVENTORY.md`, and `docs/COMPLIANCE_REPORT.md` no longer claim
   that root-level `game_rng.py`, a `legacy/` tree, missing workflows, or pygame
   are current facts.
5. Skill-system status is consolidated in `docs/SKILL_SYSTEM_STATUS.md`; older
   skill-system docs now point to that page as the source of truth.

## Pass 1: inventory and first-read notes

### Repository shape

- Total audited files: 660.
- Largest file groups by extension:
  - 198 `.png` files.
  - 195 `.svg` files.
  - 183 `.py` files.
  - 41 `.md` files.
  - 10 `.txt` files.
  - 9 `.yaml` files.
  - 8 `.sh` files.
  - 6 `.json` files.
  - 5 `.toml` files.
  - 3 `.yml` files.
  - 2 files without an extension.

### Notes while reading by area

- Root documentation and agent-policy files are numerous: [README.md](../README.md),
  [MANIFEST.md](../MANIFEST.md), [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), [.codex/AGENTS.md](../.codex/AGENTS.md),
  [.gemini/styleguide.md](../.gemini/styleguide.md), [.github/copilot-instructions.md](../.github/copilot-instructions.md), and several
  policy/check workflow files. The generated LLM-policy copies are internally
  synchronized; the original pass found stale human-facing overview docs, which
  were refreshed as part of the first-five cleanup pass.
- The `fonts/` tree dominates the repository by file count. It contains source
  charts/reports plus generated sliced PNG/SVG tiles. The runtime references the
  sliced directories, not each individual file by name.
- `game/`, `engine/`, `magic/`, `skills/`, `worldgen/`, `Dungeon/`,
  `pathfinding/`, `auto/`, and `lights_dev/` are all substantial independent or
  semi-independent systems. Several are integrated into the main game, while
  others are R&D/testbed systems.
- `notes/` contains planning/draft material rather than current executable or
  user-facing documentation. It should be treated as historical notes unless
  promoted into curated docs.
- `auto/gui.egg-info/` was generated packaging metadata covered by the
  repository `.gitignore` pattern `*.egg-info/`; it has been removed from the
  working tree as part of the first-five cleanup pass.

## Pass 2: no-use and low-use files

The list below separates **likely removable** files from **unreferenced but
possibly intentional entrypoints/testbeds**. Static import/reference analysis is
not proof of dead code in a repo with CLIs, GUIs, shell entrypoints, and manual
R&D scripts, but it is enough to identify files that deserve confirmation or
cleanup tickets.

### High-confidence no-use or cleanup candidates

| File or group | Original finding | Current status |
| --- | --- | --- |
| `auto/gui.egg-info/PKG-INFO`, `auto/gui.egg-info/SOURCES.txt`, `auto/gui.egg-info/dependency_links.txt`, `auto/gui.egg-info/top_level.txt` | Generated package metadata, appears to describe a local package named `gui`, and is ignored by the repo pattern `*.egg-info/`. | ✅ Addressed: removed from the working tree; the existing `*.egg-info/` ignore rule should prevent it from returning. |
| `fonts/classic_roguelike_preview.png` | The only PNG asset not referenced by file path or filename in repository text scans. | ✅ Addressed: retained as an intentional preview/contact-sheet asset; `fonts/glyph_name_chart.md` now defines owner scope, local regeneration policy, and retention/update criteria. |
| `.github/copilot-instructions.md` vestigial component section | Mentioned `simple_rl.py` and `dungeon_generator.py` as maintained files, but those files do not exist in the current tree. | ✅ Addressed: refreshed to point contributors at current component entrypoints and to keep stale legacy references out of new docs. |
| `notes/to implement.txt` | Historical TODO scratchpad with code fragments, old typing style, TODOs, and `pass` placeholders. | ✅ Addressed: retained as a historical AI sketch under `docs/DEPRECATION_POLICY.md` with a deletion condition tied to promoting useful ideas into curated docs or issues. |
| `notes/basicrl_project.txt` | Historical project synthesis for `basicrl`, not current `simple_rl` implementation docs. | ✅ Addressed: classified as a historical roadmap snapshot under `docs/DEPRECATION_POLICY.md`; it is not current implementation guidance. |
| `notes/code_basicrl.txt` | Six-line historical note file. | ✅ Addressed: classified as a temporary historical index under `docs/DEPRECATION_POLICY.md`, with deletion tied to the broader notes cleanup. |

### Originally unusable until repaired

| File | Original finding | Current status |
| --- | --- | --- |
| `lights_dev/scent_and_sound_flow.py` | Failed Python compilation with `IndentationError`: line 687 had `if len(results) == 0:` immediately followed by a shebang/docstring for what appeared to be another copy of a module. | ✅ Addressed: restored to a single compiling module; `python -m compileall -q lights_dev/scent_and_sound_flow.py` succeeds. |

### Unreferenced Python files from AST import graph

The following `.py` modules had no inbound imports from other repository Python
modules. Many are legitimate CLIs, tests, plugins, or manual entrypoints; they
should not be deleted without owner confirmation. They are listed here because
these are the files most likely to contain stale or orphaned code.

- Entrypoints, tests, scripts, or benches that are probably intentional:
  `main.py`, `bench/bench_fov.py`, `lights_dev/__main__.py`,
  `lights_dev/main_game.py`, `scripts/check_deterministic_random.py`,
  `scripts/check_pep585.py`, `scripts/cleanup_typing_imports.py`,
  `scripts/find_tuning_dupes.py`, `scripts/generate_glyphs.py`,
  `scripts/run_auto_regression.py`, `scripts/sync_llm_policy.py`,
  `tests/test_fov.py`, `tools/fix_fstring_newlines.py`,
  `tools/lighting_fov_tool/main.py`, `tools/play_from_arrow.py`,
  `tools/sample_variants.py`, `worldgen/bench.py`.
- Unreferenced modules that may be library code awaiting integration:
  `engine/action_handler.py`, `game/ai/bird.py`, `game/ai/community.py`,
  `game/ai/goap_adapter.py`, `game/ai/insect.py`, `game/ai/mammal.py`,
  `game/ai/ml_policy.py`, `game/ai/plant.py`, `game/ai/reptile.py`,
  `game/ai/simple.py`, `game/ai/strategy.py`, `game/constants.py`,
  `game/perception.py`, `game/planning/cache.py`,
  `game/planning/spatial_hash.py`, `game/skills/effects.py`,
  `game/skills/system.py`, `game/state/dirty.py`,
  `game/systems/equipment_system.py`,
  `game/systems/magic_system_skill_integration.py`,
  `game/world/procgen.py`, `magic/work_parser.py`, `scripting_engine.py`,
  `skills/constants.py`, `skills/manuals.py`, `skills/milestones.py`,
  `skills/prerequisites.py`, `skills/shapeshifting.py`,
  `skills/synergies.py`, `utils/logging_utils.py`, `utils/savegame.py`,
  `worldgen/chunk_cache.py`, `worldgen/game_rng.py`.
- Strongest remaining candidates for either integration, explicit R&D labeling,
  or removal: `ai/v9.py` and `notes/*`. `lights_dev/scent_and_sound_flow.py`
  has been repaired, `auto/gui.egg-info/*` has been removed, and
  `fonts/classic_roguelike_preview.png` has been documented as intentional.

### Generated and derivative assets

- `fonts/classic_roguelike_sliced/` and
  `fonts/classic_roguelike_sliced_svgs/` are referenced by runtime/config/tooling
  as directories and are therefore not unused merely because most individual
  generated filenames are not imported individually.
- `fonts/glyphs.yaml` and `fonts/glyphs_report.txt` are generated by
  `scripts/generate_glyphs.py` and are now documented in
  `docs/ASSET_PIPELINE.md` as checked-in derived artifacts retained for runtime
  convenience and reviewability.
- `fonts/tree.txt` is now documented as an archival/diagnostic snapshot rather
  than a source of truth for current file presence.

## Pass 3: documentation accuracy

### Accurate or mostly accurate documentation

- [AGENTS.md](../AGENTS.md) matches the repository-level engineering intent and current
  [pyproject.toml](../pyproject.toml) target of Python 3.11+.
- `docs/LLM_CRITICAL_RULES.md`, `CLAUDE.md`, `.codex/AGENTS.md`, and
  `.gemini/styleguide.md` are synchronized; `python scripts/sync_llm_policy.py
  --check` passed.
- Component docs such as `Dungeon/README.md`, `auto/README.md`,
  `lights_dev/README.md`, `pathfinding/README.md`, `utils/README.md`, and many
  skill-system docs broadly describe real code areas. `docs/CURRENT_STATUS.md`
  now gives readers a concise source-of-truth status matrix while deeper
  integration-state claims continue to be reviewed.
- Markdown relative links validated successfully: no broken markdown links were
  found by the link checker used in this audit.

### Stale or inaccurate documentation findings

| Document | Original inaccuracy | Current status |
| --- | --- | --- |
| `README.md` | Said `game_rng.py` was the main root-level implementation and `utils/game_rng.py` was a thin wrapper, even though the current tree has no root-level `game_rng.py`. | ✅ Addressed: the RNG section now identifies `utils/game_rng.py` as canonical and `worldgen/game_rng.py` as the compatibility re-export. |
| `README.md` | Mentioned `legacy/simple_rl.py`, `legacy/dungeon_generator.py`, and `legacy/lights_dev/dungeon_generator.py`, but no `legacy/` directory exists. | ✅ Addressed: legacy run instructions were removed and the README notes that those historical entrypoints are absent from the current tree. |
| `.github/copilot-instructions.md` | Mentioned missing `simple_rl.py` and `dungeon_generator.py`, and listed `pygame` even though `pyproject.toml` uses PySDL2/PySide6 rather than a direct `pygame` dependency. | ✅ Addressed: refreshed for the current repository state and dependency set. |
| `docs/SYSTEMS_INVENTORY.md` | Contained stale absolute path `/home/user/simple_rl/`, stale root-level `game_rng.py` claims, stale `legacy/` structure, and a misplaced `flowfield.py` under `pathfinding/` instead of `game/systems/pathfinding/flowfield.py`. | ✅ Addressed: refreshed against the actual tree, including current RNG location, absent legacy tree, and the real flow-field module path. |
| `docs/COMPLIANCE_REPORT.md` | Claimed `.github/workflows/` did not exist, but the repo has `llm_policy_sync_check.yml` and `modernize.yml`. | ✅ Addressed: regenerated to reflect the current workflow files. |
| `docs/COMPLIANCE_REPORT.md` | Claimed `utils/game_rng.py` imports `random`; current `utils/game_rng.py` does not import Python `random`. | ✅ Addressed: stale caveat removed and replaced with current deterministic-random check status. |
| `docs/COMPLIANCE_REPORT.md` | Cited a missing `dungeon_generator.py` for PEP 604 violations. | ✅ Addressed: stale missing-file citation removed. |
| `docs/SKILL_SYSTEM_EVALUATION.md` vs `docs/SKILL_SYSTEM_INTEGRATION.md` / `docs/SKILL_ADVANCED_FEATURES.md` | The evaluation doc said the skill system was not fully integrated, while later docs claimed it was fully integrated or production-ready. | ✅ Addressed: added `docs/SKILL_SYSTEM_STATUS.md` and linked older docs to it as the current source of truth. |
| `requirements.txt` | Looked like an environment export with local conda build paths rather than a portable dependency specification. | ✅ Addressed: replaced with an archival note that points contributors to `pyproject.toml` and `environment.yml` as canonical dependency sources. Follow-up: remove `requirements.txt` entirely once no repository or external tooling depends on the placeholder. |

### Documentation that does not exist but would be helpful

1. ✅ `docs/RUNBOOK.md`: added as the canonical file explaining environment
   setup, main entrypoints, subsystem testbeds, asset generation, and standard
   checks.
2. ✅ `docs/CURRENT_STATUS.md`: added as a short source-of-truth status matrix
   with system, primary paths, maturity, runnable command, integration state, and
   known follow-ups.
3. ✅ `docs/ASSET_PIPELINE.md`: added as the source of truth for `fonts/`,
   generated glyph YAML, sliced PNG/SVG tiles, reports, and which files are
   generated versus authored.
4. ✅ `docs/TESTING.md`: added with exact test/lint/typecheck commands, CI
   coverage gaps, dependency expectations, and troubleshooting notes.
5. ✅ `docs/CONFIG_REFERENCE.md`: added with schema-like documentation for
   `config/*.yaml`, `config/*.toml`, and `data/*.json` files.
6. ✅ `docs/ADR/`: added accepted decision records for canonical RNG location,
   production AI vs R&D AI, `skills/` vs `game/skills/`, and perception/FOV
   implementation boundaries.
7. ✅ `docs/DEPRECATION_POLICY.md`: added the policy for marking experiments,
   historical notes, generated metadata, and removal candidates so stale files do
   not accumulate.

## Follow-up passes 4-6: deeper unusable-file review

These follow-up passes were performed after the initial audit to re-check the
most serious blocker and to make the `lights_dev/scent_and_sound_flow.py`
finding more actionable. The original corruption has since been repaired: the
file is now a 748-line single module and `python -m compileall -q
lights_dev/scent_and_sound_flow.py` succeeds. The historical details below are
kept to explain why this file was prioritized.

### Pass 4: parser-level verification

- `lights_dev/scent_and_sound_flow.py` has 1,458 lines.
- It contains two shebang markers: line 1 and line 687. The second one is not at
  the start of the file; it appears appended to executable code.
- It contains two `from __future__ import annotations` statements: line 70 and
  line 756. A future import is only legal near the beginning of a module, so the
  second future import would be illegal even if the earlier syntax error were
  repaired without removing the duplicate module body.
- `ast.parse()` reports `IndentationError` at line 688: Python expects an
  indented block after the `if len(results) == 0:` statement on line 687.
- `python -m compileall -q .` also fails on the same file, confirming this is not
  just a lint/style issue; Python cannot compile the module.

### Pass 5: structural corruption review

The exact corruption point is line 687:

```python
if len(results) == 0:#!/usr/bin/env python3
```

That single line combines an unfinished `if` statement with a second shebang. The
next line starts a module docstring instead of an indented suite, which causes
the parser failure. Additional structure checks show the file is not merely
missing one `return` line:

- The module header/docstring/import block repeats after line 687.
- `def monster_perception` appears twice, at lines 626 and 1312.
- `def choose_step_by_flow` appears twice, at lines 1381 and 1424.
- `# End of module` appears twice, at lines 1415 and 1458.
- Lines 1419-1420 contain the likely missing body for the first line-687 `if`
  block, but those lines appear after the duplicated module's first `# End of
  module` marker. In other words, the file appears to have been interleaved or
  concatenated, not just truncated.

### Pass 6: impact and recovery assessment

At the time of the original audit, `lights_dev/scent_and_sound_flow.py` was
unusable for four separate reasons:

1. **It cannot be imported or compiled.** Any direct import, compile step, or
   whole-repo compile check stops at the line-688 `IndentationError`.
2. **The intended control flow is ambiguous.** The probable missing block for
   `if len(results) == 0:` exists much later in the file, after a duplicated
   complete module body, so an automated one-line indentation fix would be a
   guess rather than a safe repair.
3. **The duplicate module body would create secondary failures.** If the first
   syntax error were patched in place without removing the duplicate block, the
   second `from __future__ import annotations` would be invalid because future
   imports must occur before ordinary imports and executable definitions.
4. **The file conflicts with nearby canonical implementations.** Its docstring
   calls itself `perception_systems.py`, while the repo already has
   `pathfinding/perception_systems.py` and `game/systems/sound.py` covering
   related sound/scent behavior. Recovery should therefore start by deciding
   whether this file is an experimental fork worth salvaging or an accidental
   duplicate that should be deleted.

The safe recovery options considered during repair, in preferred order, were:

1. Compare the file against version-control history or the source that generated
   it, then restore the intended single module body.
2. If no history is available, split the two apparent module bodies into a scratch
   branch and manually keep only the coherent implementation after reviewing it
   against `pathfinding/perception_systems.py`.
3. If the production path is already covered by [pathfinding/perception_systems.py](../pathfinding/perception_systems.py)
   and [game/systems/sound.py](../game/systems/sound.py), delete `lights_dev/scent_and_sound_flow.py` and
   record that decision in a deprecation or R&D-status document.

The chosen resolution was option 2: keep a coherent single experimental module
body, update the header to match the actual filename, and leave production sound
playback ownership with `game/systems/sound.py`.

## Verification results from this audit

- `python scripts/sync_llm_policy.py --check` passed.
- Markdown relative-link validation passed with zero missing links during the
  original audit.
- `python -m compileall -q lights_dev/scent_and_sound_flow.py` now passes for
  the repaired scent/sound flow file.
- `python -m compileall -q .` now passes after the scent/sound flow repair.
- `python scripts/check_deterministic_random.py` now passes after the checker
  was changed to parse Python syntax, skip itself, and ignore comments and
  string literals.
- `pytest -q` failed during original audit collection because that environment
  lacked `numpy`; after installing `.[dev]` during the 2026-06-01 documentation
  follow-up, `pytest -q` passed with 8 tests.
- `python scripts/check_deterministic_random.py` is now wired into
  `.github/workflows/llm_policy_sync_check.yml`.
- `black --check .`, `ruff check .`, and `mypy .` still report pre-existing
  codebase formatting, lint, missing-stub, import-resolution, and typing issues
  that are outside this package-mapping follow-up.

## Recommended cleanup sequence

1. ✅ Fixed `lights_dev/scent_and_sound_flow.py`; it now compiles and no longer
   blocks targeted compilation of that module.
2. ✅ Removed `auto/gui.egg-info/*` generated metadata from the working tree; the
   existing `*.egg-info/` ignore rule should prevent it from returning.
3. ✅ Kept `fonts/classic_roguelike_preview.png` and documented it from
   `fonts/glyph_name_chart.md`.
4. ✅ Refreshed `README.md`, `docs/SYSTEMS_INVENTORY.md`,
   `docs/COMPLIANCE_REPORT.md`, and `.github/copilot-instructions.md` for the
   current tree.
5. ✅ Added `docs/SKILL_SYSTEM_STATUS.md` as the current skill-system status page
   and linked older skill docs to it.
6. ✅ Added the missing runbook, status matrix, testing guide, config
   reference, ADRs, deprecation policy, and asset-pipeline guide.
7. ✅ Improved `scripts/check_deterministic_random.py` so it parses Python
   syntax, skips its own checker module, ignores comments and string literals,
   passes focused regression tests, and runs in CI.
