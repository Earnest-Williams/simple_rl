from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

CHECKER_RELATIVE_PATH: Final[Path] = Path("scripts") / "check_deterministic_random.py"

BANNED_IMPORT_MODULES: Final[frozenset[str]] = frozenset({"random", "secrets"})
BANNED_ATTRIBUTE_NAMES: Final[frozenset[str]] = frozenset(
    {
        "random",
        "secrets",
        "numpy.random",
        "os.urandom",
        "uuid.uuid4",
    }
)

EXCLUDED_DIRECTORIES: Final[frozenset[str]] = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "legacy",
    }
)

ALLOWED_FILES: Final[frozenset[Path]] = frozenset(
    {
        Path("utils") / "game_rng.py",
        CHECKER_RELATIVE_PATH,
    }
)


class RandomnessVisitor(ast.NodeVisitor):
    """Detect direct Python, NumPy, and OS randomness usage in Python syntax."""

    def __init__(self) -> None:
        self.violations: list[str] = []
        self._module_aliases: dict[str, str] = {}

    def visit_Import(self, node: ast.Import) -> None:  # noqa: N802
        for alias in node.names:
            self._record_import_alias(alias)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:  # noqa: N802
        if node.module is None:
            self.generic_visit(node)
            return

        module_name = node.module
        module_root = module_name.split(".", maxsplit=1)[0]
        for alias in node.names:
            imported_name = alias.asname or alias.name
            qualified_name = f"{module_name}.{alias.name}"
            self._module_aliases[imported_name] = qualified_name
            if module_root in BANNED_IMPORT_MODULES:
                self.violations.append(f"from {module_root}")
            elif module_name == "numpy" and alias.name == "random":
                self.violations.append("from numpy import random")
            elif module_name.startswith("numpy.random"):
                self.violations.append(f"from {module_name}")
            elif qualified_name in {"os.urandom", "uuid.uuid4"}:
                self.violations.append(f"from {module_name} import {alias.name}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:  # noqa: N802
        qualified_name = _qualified_name(node)
        if qualified_name is not None:
            self._append_attribute_violation(qualified_name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:  # noqa: N802
        if node.id in self._module_aliases:
            self._append_attribute_violation(node.id)

    def _append_attribute_violation(self, qualified_name: str) -> None:
        expanded_name = self._expand_alias(qualified_name)
        violation = _matching_banned_attribute(expanded_name)
        if violation is not None:
            self.violations.append(violation)

    def _record_import_alias(self, alias: ast.alias) -> None:
        module_name = alias.name
        module_root = module_name.split(".", maxsplit=1)[0]
        imported_name = alias.asname or module_root
        self._module_aliases[imported_name] = module_name
        if module_root in BANNED_IMPORT_MODULES:
            self.violations.append(f"import {module_root}")
        elif module_name.startswith("numpy.random"):
            self.violations.append("import numpy.random")

    def _expand_alias(self, qualified_name: str) -> str:
        first_name, separator, rest = qualified_name.partition(".")
        mapped_name = self._module_aliases.get(first_name)
        if mapped_name is None:
            return qualified_name
        if separator == "":
            return mapped_name
        return f"{mapped_name}.{rest}"


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent_name = _qualified_name(node.value)
        if parent_name is None:
            return None
        return f"{parent_name}.{node.attr}"
    return None


def _matching_banned_attribute(qualified_name: str) -> str | None:
    for banned_name in BANNED_ATTRIBUTE_NAMES:
        if qualified_name == banned_name or qualified_name.startswith(
            f"{banned_name}."
        ):
            return banned_name
    return None


def _should_skip(path: Path) -> bool:
    if path.suffix != ".py":
        return True
    if path in ALLOWED_FILES:
        return True
    return any(part in EXCLUDED_DIRECTORIES for part in path.parts)


def _scan_source(source: str, filename: str) -> list[str]:
    tree = ast.parse(source, filename=filename)
    visitor = RandomnessVisitor()
    visitor.visit(tree)
    return visitor.violations


def _scan_file(path: Path) -> list[str]:
    contents = path.read_text(encoding="utf-8")
    return _scan_source(contents, str(path))


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
        for violation in _scan_file(file_path):
            failures.append(f"{relative_path}: contains '{violation}'")

    if failures:
        print("Disallowed randomness usage found:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("Deterministic RNG check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
