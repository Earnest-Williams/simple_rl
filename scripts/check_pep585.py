#!/usr/bin/env python3
"""
Fail if code uses typing.List / typing.Dict / typing.Tuple or imports them
from typing. Excludes common venv/build dirs.
"""
from pathlib import Path
import re
import sys
from typing import Final

ROOT: Final[Path] = Path(".")
EXCLUDE_PARTS: Final[set[str]] = {".venv", "venv", "build", "dist", ".git", "__pycache__"}
PATTERNS: Final[list[re.Pattern[str]]] = [
    re.compile(
        r"from\s+typing\s+import\s+.*\b"
        r"(List|Dict|Tuple|Set|FrozenSet|Deque|DefaultDict|OrderedDict)\b"
    ),
    re.compile(
        r"\btyping\.(List|Dict|Tuple|Set|FrozenSet|Deque|DefaultDict|OrderedDict)\b"
    ),
]


def is_excluded(p: Path) -> bool:
    return any(part in EXCLUDE_PARTS for part in p.parts)


def find_violations() -> int:
    bad_count = 0
    for p in ROOT.rglob("*.py"):
        if is_excluded(p):
            continue
        text = p.read_text(encoding="utf-8")
        for pat in PATTERNS:
            for m in pat.finditer(text):
                bad_count += 1
                lineno = text.count("\n", 0, m.start()) + 1
                print(f"{p}:{lineno}: matches `{m.group(0)}`")
    return bad_count


if __name__ == "__main__":
    n = find_violations()
    if n:
        print(
            f"\nFound {n} forbidden typing usages. "
            "Use built-in generics (list/dict/tuple)."
        )
        sys.exit(1)
    print("OK: no forbidden typing usages found.")
    sys.exit(0)
