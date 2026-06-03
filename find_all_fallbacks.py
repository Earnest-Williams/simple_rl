import ast
import os


def find_try_except_import_error(directory):
    matches = []
    for root, _, files in os.walk(directory):
        if ".venv" in root or ".git" in root:
            continue
        for file in files:
            if not file.endswith(".py"):
                continue
            path = os.path.join(root, file)
            try:
                with open(path, "r") as f:
                    content = f.read()
                tree = ast.parse(content)
                lines = content.split("\n")
                for node in ast.walk(tree):
                    if isinstance(node, ast.Try):
                        is_import_try = False
                        for stmt in node.body:
                            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                                is_import_try = True
                                break
                        if not is_import_try:
                            continue

                        has_import_error = False
                        has_raise = False
                        for handler in node.handlers:
                            if (
                                isinstance(handler.type, ast.Name)
                                and handler.type.id == "ImportError"
                            ):
                                has_import_error = True
                                for stmt in handler.body:
                                    if isinstance(stmt, ast.Raise):
                                        has_raise = True

                        if has_import_error and not has_raise:
                            matches.append((path, node.lineno, node.end_lineno))
            except Exception as e:
                pass
    return matches


if __name__ == "__main__":
    matches = find_try_except_import_error(".")
    for path, start, end in matches:
        print(f"{path}:{start}-{end}")
