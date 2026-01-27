#!/usr/bin/env python3
"""Scan the repository for numeric literals that match tuned constants.

Prints likely duplicates so a developer can decide whether to replace them
with an import from ``common.tuning``.

Usage::

    python scripts/find_tuning_dupes.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Known tuned values → name mapping
# ---------------------------------------------------------------------------
TUNED_VALUES: Final[Mapping[str, list[str]]] = MappingProxyType({
    # value pattern  → human-readable constant names
    "30_000": ["BF_TAPE_SIZE"],
    "30000": ["BF_TAPE_SIZE"],
    "10_000_000": ["BF_MAX_STEPS"],
    "10000000": ["BF_MAX_STEPS"],
    "27": ["MAX_SKILL_LEVEL"],
    "128": ["DEFAULT_GRID_SIZE"],
    "5": ["MEMORY_LEVEL_COUNT"],
})

# Directories / files to skip
EXCLUDE_PARTS: Final[frozenset[str]] = frozenset(
    {
        "venv",
        ".venv",
        "build",
        "dist",
        ".git",
        "__pycache__",
        "legacy",
        "node_modules",
    }
)

# Files that are allowed to define these constants (the source-of-truth).
ALLOWED_FILES: Final[frozenset[str]] = frozenset(
    {
        "common/tuning.py",
    }
)


def _should_skip(path: Path) -> bool:
    return bool(EXCLUDE_PARTS & set(path.parts))


def _is_allowed(path: Path, repo_root: Path) -> bool:
    rel = str(path.relative_to(repo_root))
    return rel in ALLOWED_FILES


def scan(repo_root: Path) -> list[tuple[Path, int, str, list[str]]]:
    """Return list of (file, line_no, matched_value, constant_names)."""
    hits: list[tuple[Path, int, str, list[str]]] = []

    for py_file in sorted(repo_root.rglob("*.py")):
        if _should_skip(py_file) or _is_allowed(py_file, repo_root):
            continue

        try:
            lines = py_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue

        for line_no, line in enumerate(lines, start=1):
            # Skip comments
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue

            for pattern, names in TUNED_VALUES.items():
                # Word-boundary match so "127" doesn't match "27"
                if re.search(rf"\b{re.escape(pattern)}\b", line):
                    hits.append((py_file, line_no, pattern, names))

    return hits


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    hits = scan(repo_root)

    if not hits:
        print("No duplicate tuning literals found.")
        sys.exit(0)

    print(f"Found {len(hits)} potential tuning-constant duplicates:\n")
    for path, line_no, value, names in hits:
        rel = path.relative_to(repo_root)
        name_str = ", ".join(names)
        print(f"  {rel}:{line_no}  value={value}  -> {name_str}")

    print(
        "\nReview each hit and replace with an import from common.tuning "
        "where appropriate."
    )


if __name__ == "__main__":
    main()
