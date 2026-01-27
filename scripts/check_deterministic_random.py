from __future__ import annotations

from pathlib import Path
from typing import Final

DISALLOWED_SNIPPETS: Final[list[str]] = [
    "import random",
    "from random",
    "random.",
    "numpy.random",
    "np.random",
    "import secrets",
    "from secrets",
    "secrets.",
    "os.urandom",
    "uuid.uuid4",
]

EXCLUDED_DIRECTORIES: Final[set[str]] = {
    ".git",
    ".venv",
    "__pycache__",
    "legacy",
}

ALLOWED_FILES: Final[set[str]] = {
    str(Path("utils") / "game_rng.py"),
}


def _should_skip(path: Path) -> bool:
    if path.suffix != ".py":
        return True
    if path.as_posix() in ALLOWED_FILES:
        return True
    for part in path.parts:
        if part in EXCLUDED_DIRECTORIES:
            return True
    return False


def _scan_file(path: Path) -> list[str]:
    contents = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for snippet in DISALLOWED_SNIPPETS:
        if snippet in contents:
            violations.append(snippet)
    return violations


def main() -> int:
    script_path = Path(__file__)
    repo_root = (
        script_path.resolve().parents[1]
        if script_path.exists()
        else script_path.parent.parent
    )
    failures: list[str] = []
    for file_path in repo_root.rglob("*.py"):
        relative_path = file_path.relative_to(repo_root)
        if _should_skip(relative_path):
            continue
        for snippet in _scan_file(file_path):
            failures.append(f"{relative_path}: contains '{snippet}'")

    if failures:
        print("Disallowed randomness usage found:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Deterministic RNG check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
