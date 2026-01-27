#!/usr/bin/env bash
# tools/style/format_and_lint.sh — Canonical formatting & linting pipeline.
#
# Usage:
#   ./tools/style/format_and_lint.sh          # run on entire repo
#   ./tools/style/format_and_lint.sh path/     # run on a specific directory
#
# Steps:
#   1. ruff check (initial report)
#   2. black (formatting)
#   3. autopep8 aggressive pass
#   4. black (re-format after autopep8)
#   5. isort (import sorting)
#   6. ruff --fix (auto-fixable lint)
#   7. ruff check (final report)
#
# Tool versions are pinned in the root pyproject.toml.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET="${1:-.}"

cd "${REPO_ROOT}"

echo "=== Ruff (initial check) ==="
ruff check "${TARGET}" || true

echo "=== Black pass 1 ==="
black --line-length 88 --target-version py311 "${TARGET}"

echo "=== Ruff (after black) ==="
ruff check "${TARGET}" || true

echo "=== Autopep8 pass ==="
find "${TARGET}" -type f -name "*.py" -exec autopep8 --in-place --aggressive --aggressive {} +

echo "=== Black pass 2 ==="
black --line-length 88 --target-version py311 "${TARGET}"

echo "=== isort pass ==="
isort "${TARGET}"

echo "=== Ruff fix ==="
ruff check "${TARGET}" --fix

echo "=== Final Ruff report ==="
ruff check "${TARGET}"

echo "=== Done ==="
