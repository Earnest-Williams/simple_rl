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

1. The repository is not cleanly runnable as a whole today. The most severe
   immediate defect is a syntax error in `lights_dev/scent_and_sound_flow.py`,
   where a second module appears to have been concatenated after an incomplete
   `if len(results) == 0:` statement.
2. Some files are clearly generated or stale and have no practical source value
   in version control, especially `auto/gui.egg-info/*` and likely
   `fonts/classic_roguelike_preview.png`.
3. The documentation is mixed: the LLM policy copies are synchronized, but major
   overview documents contain stale claims about a root-level `game_rng.py`, a
   `legacy/` tree, old absolute paths, and CI/workflow state.
4. The most useful missing documents would be a current runbook, a current module
   ownership/status matrix, a generated-assets policy, a testing/CI status
   document, and architecture decision records (ADRs) for the duplicate or
   experimental systems.


## Resolution update: first five cleanup items

Date: 2026-05-31

The first five items from the recommended cleanup sequence have been addressed:

1. `lights_dev/scent_and_sound_flow.py` now compiles as a single module, has one
   module header, and identifies itself by its actual filename while noting that
   production sound playback lives in `game/systems/sound.py`.
2. `auto/gui.egg-info/` generated package metadata was removed from the working
   tree; it remains covered by the existing `*.egg-info/` ignore rule.
3. `fonts/classic_roguelike_preview.png` is documented in
   `fonts/glyph_name_chart.md` as the preview/contact-sheet image for the
   classic roguelike tile set.
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
  synchronized, but some human-facing overview docs are stale.
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
- `auto/gui.egg-info/` is generated packaging metadata. It is also covered by
  the repository `.gitignore` pattern `*.egg-info/`, so its tracked presence is
  suspicious.

## Pass 2: no-use and low-use files

The list below separates **likely removable** files from **unreferenced but
possibly intentional entrypoints/testbeds**. Static import/reference analysis is
not proof of dead code in a repo with CLIs, GUIs, shell entrypoints, and manual
R&D scripts, but it is enough to identify files that deserve confirmation or
cleanup tickets.

### High-confidence no-use or cleanup candidates

| File or group | Finding | Recommendation |
| --- | --- | --- |
| `auto/gui.egg-info/PKG-INFO`, `auto/gui.egg-info/SOURCES.txt`, `auto/gui.egg-info/dependency_links.txt`, `auto/gui.egg-info/top_level.txt` | Generated package metadata, appears to describe a local package named `gui`, and is ignored by the repo pattern `*.egg-info/`. | Remove from version control unless there is a reproducibility reason to keep generated build metadata. |
| `fonts/classic_roguelike_preview.png` | The only PNG asset not referenced by file path or filename in repository text scans. | Either document it as a preview/source asset or remove it. |
| `.github/copilot-instructions.md` vestigial component section | Mentions `simple_rl.py` and `dungeon_generator.py` as maintained files, but those files do not exist in the current tree. | Update or regenerate from canonical repo state. |
| `notes/to implement.txt` | Historical TODO scratchpad with code fragments, old typing style, TODOs, and `pass` placeholders. | Keep only if explicitly treated as archival notes; otherwise migrate relevant items into tracked issues or curated docs and delete the scratch file. |
| `notes/basicrl_project.txt` | Historical project synthesis for `basicrl`, not current `simple_rl` implementation docs. | Archive or summarize into current docs if still useful. |
| `notes/code_basicrl.txt` | Six-line historical note file. | Remove or fold into an archive note. |

### Currently unusable until repaired

| File | Finding | Recommendation |
| --- | --- | --- |
| `lights_dev/scent_and_sound_flow.py` | Fails Python compilation with `IndentationError`: line 687 has `if len(results) == 0:` immediately followed by a shebang/docstring for what appears to be another copy of a module. | Split/recover the intended file or remove it if superseded by `pathfinding/perception_systems.py` and `game/systems/sound.py`. |

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
- Strongest candidates for either integration, explicit R&D labeling, or removal:
  `lights_dev/scent_and_sound_flow.py`, `ai/v9.py`, `notes/*`,
  `auto/gui.egg-info/*`, and `fonts/classic_roguelike_preview.png`.

### Generated and derivative assets

- `fonts/classic_roguelike_sliced/` and
  `fonts/classic_roguelike_sliced_svgs/` are referenced by runtime/config/tooling
  as directories and are therefore not unused merely because most individual
  generated filenames are not imported individually.
- `fonts/glyphs.yaml` and `fonts/glyphs_report.txt` are generated by
  `scripts/generate_glyphs.py`. Keeping generated outputs can be reasonable for
  runtime convenience, but the repo should document whether they are source of
  truth or derived artifacts.
- `fonts/tree.txt` is a static directory listing. It is documentation-like and
  can become stale quickly; it should either be regenerated as part of the glyph
  pipeline or removed.

## Pass 3: documentation accuracy

### Accurate or mostly accurate documentation

- [AGENTS.md](../AGENTS.md) matches the repository-level engineering intent and current
  [pyproject.toml](../pyproject.toml) target of Python 3.11+.
- `docs/LLM_CRITICAL_RULES.md`, `CLAUDE.md`, `.codex/AGENTS.md`, and
  `.gemini/styleguide.md` are synchronized; `python scripts/sync_llm_policy.py
  --check` passed.
- Component docs such as `Dungeon/README.md`, `auto/README.md`,
  `lights_dev/README.md`, `pathfinding/README.md`, `utils/README.md`, and many
  skill-system docs broadly describe real code areas, but some integration-state
  claims should be reviewed against current code.
- Markdown relative links validated successfully: no broken markdown links were
  found by the link checker used in this audit.

### Stale or inaccurate documentation findings

| Document | Inaccuracy | Correction needed |
| --- | --- | --- |
| `README.md` | Says `game_rng.py` is the main root-level implementation and `utils/game_rng.py` is a thin wrapper. The current tree has no root-level `game_rng.py`; `utils/game_rng.py` contains the implementation. | Rewrite RNG section around `utils/game_rng.py` as canonical implementation and `worldgen/game_rng.py` as the small re-export. |
| `README.md` | Mentions `legacy/simple_rl.py`, `legacy/dungeon_generator.py`, and `legacy/lights_dev/dungeon_generator.py`; no `legacy/` directory exists. | Remove legacy run instructions or restore/archive the files intentionally. |
| `.github/copilot-instructions.md` | Mentions missing `simple_rl.py` and `dungeon_generator.py`, and lists `pygame` even though `pyproject.toml` uses PySDL2/PySide6 rather than a direct `pygame` dependency. | Update from current repo state or generate from canonical docs. |
| `docs/SYSTEMS_INVENTORY.md` | Contains stale absolute path `/home/user/simple_rl/`, stale root-level `game_rng.py` claims, stale `legacy/` structure, and a misplaced `flowfield.py` under `pathfinding/` instead of `game/systems/pathfinding/flowfield.py`. | Refresh the inventory from the actual file tree. |
| `docs/COMPLIANCE_REPORT.md` | Claims `.github/workflows/` does not exist, but the repo now has `llm_policy_sync_check.yml` and `modernize.yml`. | Regenerate compliance report. |
| `docs/COMPLIANCE_REPORT.md` | Claims `utils/game_rng.py` imports `random`; current `utils/game_rng.py` does not import Python `random`. | Remove stale caveat and replace with current deterministic-random check results. |
| `docs/COMPLIANCE_REPORT.md` | Cites a missing `dungeon_generator.py` for PEP 604 violations. | Re-run typing modernization checks against current files. |
| `docs/SKILL_SYSTEM_EVALUATION.md` vs `docs/SKILL_SYSTEM_INTEGRATION.md` / `docs/SKILL_ADVANCED_FEATURES.md` | The evaluation doc says the skill system is not fully integrated, while later docs claim it is fully integrated or production-ready. | Add a current skill-system status page or consolidate contradictory docs. |
| `requirements.txt` | Looks like an environment export with local conda build paths rather than a portable dependency specification. | Prefer `pyproject.toml` and `environment.yml`; either regenerate `requirements.txt` portably or mark it archival. |

### Documentation that does not exist but would be helpful

1. `docs/RUNBOOK.md`: one canonical file explaining how to install, run the main
   game, run each testbed, generate a dungeon, run lighting/FOV demos, and run
   worldgen.
2. `docs/CURRENT_STATUS.md`: a short source-of-truth status matrix with columns
   for system, owner, maturity, runnable command, integration state, and known
   blockers.
3. `docs/ASSET_PIPELINE.md`: source-of-truth for `fonts/`, generated glyph YAML,
   sliced PNG/SVG tiles, reports, and which files are generated versus authored.
4. `docs/TESTING.md`: exact test/lint/typecheck commands, expected current
   failures, dependency requirements, and CI coverage gaps.
5. `docs/CONFIG_REFERENCE.md`: schema-like documentation for `config/*.yaml`,
   `config/*.toml`, and `data/*.json` files.
6. `docs/ADR/` decision records: especially for canonical RNG location,
   production AI vs R&D AI, `skills/` vs `game/skills/`, and which perception/FOV
   implementation is canonical.
7. `docs/DEPRECATION_POLICY.md`: how to mark experiments, historical notes,
   generated metadata, and removal candidates so stale files do not accumulate.

## Follow-up passes 4-6: deeper unusable-file review

These follow-up passes were performed after the initial audit to re-check the
most serious blocker and to make the `lights_dev/scent_and_sound_flow.py`
finding more actionable. The original corruption has since been repaired: the
file is now a 750-line single module and `python -m compileall -q
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

`lights_dev/scent_and_sound_flow.py` is currently unusable for four separate
reasons:

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

Safe recovery options, in preferred order:

1. Compare the file against version-control history or the source that generated
   it, then restore the intended single module body.
2. If no history is available, split the two apparent module bodies into a scratch
   branch and manually keep only the coherent implementation after reviewing it
   against `pathfinding/perception_systems.py`.
3. If the production path is already covered by [pathfinding/perception_systems.py](../pathfinding/perception_systems.py)
   and [game/systems/sound.py](../game/systems/sound.py), delete `lights_dev/scent_and_sound_flow.py` and
   record that decision in a deprecation or R&D-status document.

## Verification results from this audit

- `python scripts/sync_llm_policy.py --check` passed.
- Markdown relative-link validation passed with zero missing links during the
  original audit.
- `python -m compileall -q lights_dev/scent_and_sound_flow.py` now passes for
  the repaired scent/sound flow file.
- `python -m compileall -q .` now passes after the scent/sound flow repair.
- `python scripts/check_deterministic_random.py` failed. It reports matches in
  itself because the checker scans its own disallowed string literals, and it
  reports `auto/gui/worker.py` because a comment contains `import random`.
- `pytest -q` failed during collection because the original audit environment
  lacked `numpy`; it did not get far enough to validate runtime behavior.

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
6. Add the missing runbook, testing guide, asset-pipeline guide, config
   reference, and ADR/deprecation docs listed above.
7. Improve `scripts/check_deterministic_random.py` so it does not scan itself or
   comments, then wire it into CI once it is reliable.
