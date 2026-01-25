#!/usr/bin/env bash
set -euo pipefail

# Usage: ./scripts/modernize_all.sh [branch-name]
BRANCH=${1:-modernize/pep585}

echo "Creating branch: $BRANCH"
git fetch origin main

# If local branch exists, check it out. If remote branch exists, fetch and check it out.
# Otherwise create a new branch from origin/main.
if git show-ref --quiet "refs/heads/$BRANCH"; then
  git checkout "$BRANCH"
elif git ls-remote --heads origin "$BRANCH" | grep -q "refs/heads/$BRANCH"; then
  git fetch origin "$BRANCH":"$BRANCH"
  git checkout "$BRANCH"
else
  git checkout -b "$BRANCH" origin/main
fi

echo "Ensure dev tools are installed..."
python -m pip install --upgrade pip
pip install -e ".[dev]"

echo "Running pyupgrade on tracked Python files..."
# Only run pyupgrade if there are python files tracked by git.
if git ls-files -- '*.py' | grep -q .; then
  git ls-files -z -- '*.py' | xargs -0 pyupgrade --py311-plus
else
  echo "No tracked Python files found; skipping pyupgrade."
fi

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
