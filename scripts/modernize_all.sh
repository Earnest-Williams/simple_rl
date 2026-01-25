#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/modernize_all.sh [branch-name]
BRANCH=${1:-modernize/pep585}

echo "Creating branch: $BRANCH"
git fetch origin
git checkout -b "$BRANCH"

echo "Ensure dev tools are installed..."
python -m pip install --upgrade pip
pip install -e ".[dev]"

echo "Running pyupgrade..."
pyupgrade --py311-plus -r .

echo "Running cleanup script..."
python scripts/cleanup_typing_imports.py

echo "Applying ruff fixes..."
ruff --fix .

echo "Formatting with black..."
black .

echo "Type check with mypy (may fail; fix issues if needed)..."
mypy . || true

echo "Run tests..."
pytest -q || true

git add -A
if ! git diff --cached --quiet; then
  git commit -m "chore: modernize typing to PEP-585 (pyupgrade + ruff + black)"
  echo "Committed modernization. Please push the branch and open a PR."
else
  echo "No changes to commit."
fi
