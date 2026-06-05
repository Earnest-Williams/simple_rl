# Deprecation and archival policy

This policy explains how to mark experiments, historical notes, generated
metadata, and removal candidates so stale files do not accumulate or get deleted
without owner context.

## Categories

| Category | Meaning | Default action |
| --- | --- | --- |
| Production | Used by the main game, scripts, tests, or documented workflows. | Keep current, tested, and documented. |
| R&D | Experimental subsystem, benchmark, prototype, or manual harness. | Keep if it has an owner path, runnable command, or explicit status entry. |
| Historical note | Planning material retained for context but not current guidance. | Archive or summarize into curated docs; avoid using as implementation authority. |
| Generated artifact | Produced by a script or build process. | Ignore if reproducible and unused at runtime; commit only when documented as intentional. |
| Removal candidate | File with no current owner, current use, or archival value. | Delete in a focused cleanup after confirming no workflow depends on it. |

## Marking files and directories

When keeping non-production material, record the reason in one of these places:

1. `docs/Current Status.md` for subsystem-level maturity and ownership;
2. `docs/Asset Pipeline.md` for generated or retained asset outputs;
3. an ADR under `docs/ADR/` for architecture boundaries;
4. a short README in the directory when the scope is local and long-lived.

A retained R&D or historical file should state at least one of the following:

- The current owner subsystem;
- A runnable command or validation command;
- What production path supersedes it;
- What condition would allow deletion.

## Notes directory policy

The `notes/` directory is historical scratch material, not current user-facing
or implementation documentation. Contributors should not add new planning notes
there by default. Promote useful content into `docs/`, `README.md`, tracked
issues, or ADRs instead.

Current retained notes are summarized in `notes/README.md`:

| File | Classification | Retention reason | Deletion condition |
| --- | --- | --- | --- |
| `notes/basicrl_project.txt` | Historical note | Captures an older BasicRL roadmap and terminology snapshot. | Delete after useful roadmap items are represented in current issues or docs. |
| `notes/to implement.txt` | Historical note | Preserves an early cave-species AI sketch that may inform future R&D triage. | Delete after relevant AI ideas are promoted to `docs/ADR/`, `docs/Current Status.md`, or issues. |

The former `notes/code_basicrl.txt` index was removed after being replaced by
`notes/README.md`.

## Generated metadata policy

Generated files should not be committed unless at least one of these is true:

- runtime code reads the generated artifact directly;
- the artifact is a review aid that is expensive or noisy to regenerate;
- the artifact records externally useful metadata for asset review;
- downstream tooling still requires the path during a migration window.

If none of those applies, add or keep an ignore rule and remove the generated
file from the working tree.

## Removal workflow

1. Confirm the file is not referenced by current commands, imports, docs, or
   packaging metadata.
2. Confirm whether it is covered by a status document, ADR, asset policy, or
   directory README.
3. If no owner exists, delete it in a focused cleanup commit.
4. Update the relevant status document so the
   same file is not rediscovered as an unresolved cleanup item.
