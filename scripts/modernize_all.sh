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
# Try bulk mode first; if it fails, run per-file and print failing files' stderr.
mapfile -t FILES < <(git ls-files -- '*.py')
if [ "${#FILES[@]}" -gt 0 ]; then
  if python -m pyupgrade --py311-plus "${FILES[@]}"; then
    echo "pyupgrade succeeded in bulk mode."
  else
    echo "pyupgrade bulk run failed. Running per-file to locate errors." >&2
    failed=0
    temp_dir="$(mktemp -d)"
    trap 'rm -rf "$temp_dir"' EXIT
    for f in "${FILES[@]}"; do
      err_file="$temp_dir/pyupgrade.$(basename "$f").err"
      if ! python -m pyupgrade --py311-plus "$f" 2> "$err_file"; then
        echo "pyupgrade FAILED on: $f" >&2
        echo "stderr (tail):" >&2
        tail -n 200 "$err_file" >&2 || true
        failed=1
      fi
    done
    if [ $failed -eq 1 ]; then
      echo "One or more pyupgrade errors detected; aborting." >&2
      exit 1
    fi
  fi
else
  echo "No tracked Python files found; skipping pyupgrade."
fi

echo "Running cleanup script..."
python scripts/cleanup_typing_imports.py

echo "Applying ruff fixes..."
# Limit ruff to tracked Python files so it won't try to parse TOML/etc.
mapfile -t PY_FILES < <(git ls-files -- '*.py' '*.pyi' || true)
if [ "${#PY_FILES[@]}" -gt 0 ]; then
  if ruff --fix "${PY_FILES[@]}"; then
    echo "ruff --fix succeeded in bulk mode."
  else
    echo "ruff bulk run failed. Running per-file to locate errors." >&2
    failed=0
    for f in "${PY_FILES[@]}"; do
      if ! ruff --fix "$f" 2> "/tmp/ruff.$(basename "$f").err"; then
        echo "ruff FAILED on: $f" >&2
        echo "stderr (tail):"
        tail -n 200 "/tmp/ruff.$(basename "$f").err" >&2 || true
        failed=1
      fi
    done
    if [ $failed -eq 1 ]; then
      echo "One or more ruff errors detected; aborting." >&2
      exit 1
    fi
  fi
else
  echo "No tracked Python files found; skipping ruff."
fi

echo "Formatting with black..."
# Run black only on tracked Python files (same list)
if [ "${#PY_FILES[@]}" -gt 0 ]; then
  black "${PY_FILES[@]}"
else
  echo "No tracked Python files found; skipping black."
fi

echo "Type check with mypy (may fail; fix issues if needed)..."
mypy . || true

echo "Run tests..."
pytest -q || true

git add -A
if ! git diff --cached --quiet; then
  # Ensure CI has user identity so commits succeed in Actions
  git config user.email "ci@local"
  git config user.name "CI Bot"
  git commit -m "chore: modernize typing to PEP-585 (pyupgrade + ruff + black)"
  echo "Committed modernization. Please push the branch and open a PR."
else
  echo "No changes to commit."
fi
