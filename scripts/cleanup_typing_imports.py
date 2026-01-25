#!/usr/bin/env python3
"""
Small cleanup to remove obsolete typing imports (List, Dict, Tuple, Set, etc.)
and replace 'typing.X' references with builtin forms where possible.

This script runs after pyupgrade and is conservative: it only edits
lines that begin with 'from typing import'.
"""
from pathlib import Path
import re
from typing import Final

ROOT: Final[Path] = Path(".")
EXCLUDE: Final[set[str]] = {".venv", "venv", "build", "dist", ".git", "__pycache__"}
TYPING_NAMES: Final[set[str]] = {
    "List",
    "Dict",
    "Tuple",
    "Set",
    "FrozenSet",
    "Deque",
    "DefaultDict",
    "OrderedDict",
}

FROM_TYPING_RE: Final[re.Pattern[str]] = re.compile(
    r"^(\s*)from\s+typing\s+import\s+(.*)$", flags=re.MULTILINE
)
TYPING_DOT_RE: Final[re.Pattern[str]] = re.compile(
    r"\btyping\.(List|Dict|Tuple|Set|FrozenSet|Deque|DefaultDict|OrderedDict)\b"
)


def excluded(p: Path) -> bool:
    return any(part in EXCLUDE for part in p.parts)


def process_file(p: Path) -> bool:
    text = p.read_text(encoding="utf-8")
    original = text

    # Remove typed names from from-typing lines (only top-level import lines)
    def repl_from_typing(m: re.Match[str]) -> str:
        indent = m.group(1)
        rest = m.group(2)
        # strip trailing inline comment
        rest_nocomment = rest.split("#", 1)[0]
        names = [n.strip() for n in re.split(r",\s*", rest_nocomment) if n.strip()]
        new_names = [n for n in names if n not in TYPING_NAMES]
        if not new_names:
            # remove entire import line
            return ""
        return f"{indent}from typing import {', '.join(new_names)}"

    text = FROM_TYPING_RE.sub(repl_from_typing, text)

    # Replace occurrences of typing.List etc -> list
    text = TYPING_DOT_RE.sub(lambda m: m.group(1).lower(), text)

    if text != original:
        p.write_text(text, encoding="utf-8")
        print(f"Updated {p}")
        return True
    return False


def main() -> int:
    changed = 0
    for p in ROOT.rglob("*.py"):
        if excluded(p):
            continue
        if process_file(p):
            changed += 1
    print(f"Files updated: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
