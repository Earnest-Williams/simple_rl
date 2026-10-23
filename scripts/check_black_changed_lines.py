"""Check Black formatting only on lines a PR changed in legacy files.

Some historical modules predate the current Black baseline. Formatting an
entire file makes a review diff unnecessarily large; this gate instead
runs Black 24.x on every added/replaced line range, leaving untouched
pre-existing formatting outside the PR's scope.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_line_ranges(base: str, path: Path) -> list[tuple[int, int]]:
    """Read added/replaced line ranges from a zero-context Git diff."""
    result = subprocess.run(
        [
            "git",
            "diff",
            "--no-ext-diff",
            "--no-color",
            "--unified=0",
            base,
            "HEAD",
            "--",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    ranges: list[tuple[int, int]] = []
    for line in result.stdout.splitlines():
        match = HUNK.match(line)
        if match is None:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        if count:
            ranges.append((start, start + count - 1))
    return ranges


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", type=Path, nargs="+")
    args = parser.parse_args()
    base = subprocess.check_output(
        ["git", "merge-base", "origin/main", "HEAD"],
        text=True,
    ).strip()

    failed = False
    for path in args.paths:
        ranges = changed_line_ranges(base, path)
        if not ranges:
            continue
        cmd = [sys.executable, "-m", "black", "--check"]
        for first, last in ranges:
            cmd.extend(["--line-ranges", f"{first}-{last}"])
        cmd.append(str(path))
        result = subprocess.run(cmd, check=False)
        failed |= result.returncode != 0

    if failed:
        print("Black found formatting issues in changed legacy lines.", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
