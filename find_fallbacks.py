import ast
import os
import sys


def find_try_imports(directory):
    matches = []
    for root, _, files in os.walk(directory):
        if ".venv" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                path = os.path.join(root, file)
                try:
                    with open(path, "r") as f:
                        content = f.read()
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Try):
                            for stmt in node.body:
                                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                                    for alias in stmt.names:
                                        if alias.name in (
                                            "numba",
                                            "numpy",
                                            "polars",
                                        ) or (
                                            hasattr(stmt, "module")
                                            and stmt.module
                                            in ("numba", "numpy", "polars")
                                        ):
                                            matches.append(
                                                f"{path}:{stmt.lineno}: import {alias.name}"
                                            )
                except Exception as e:
                    pass
    return matches


if __name__ == "__main__":
    matches = find_try_imports(".")
    for match in matches:
        print(match)
