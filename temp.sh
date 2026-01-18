#!/usr/bin/env bash
set -euo pipefail

ENV_NAME=${1:-simple_rl}
OUT_FILE=${2:-requirements.txt}

echo "Exporting pip-style requirements from env: $ENV_NAME -> $OUT_FILE"

# Prefer mamba/micromamba, fall back to MAMBA_EXE, then conda
if command -v mamba >/dev/null 2>&1; then
  RUNNER="mamba"
elif command -v micromamba >/dev/null 2>&1; then
  RUNNER="micromamba"
elif [ -n "${MAMBA_EXE:-}" ] && [ -x "${MAMBA_EXE}" ]; then
  RUNNER="$MAMBA_EXE"
elif command -v conda >/dev/null 2>&1; then
  RUNNER="conda"
else
  echo "Error: neither mamba/micromamba nor conda found in PATH." >&2
  exit 2
fi

echo "Using runner: $RUNNER"

# Try the simple / preferred approach: runner run -n <env> python -m pip freeze
# Some runner versions accept '--' or require it; try both.
if "$RUNNER" run -n "$ENV_NAME" python -m pip freeze > "$OUT_FILE" 2>/dev/null; then
  echo "Wrote $OUT_FILE via '$RUNNER run -n $ENV_NAME'."
  exit 0
fi

if "$RUNNER" run -n "$ENV_NAME" -- python -m pip freeze > "$OUT_FILE" 2>/dev/null; then
  echo "Wrote $OUT_FILE via '$RUNNER run -n $ENV_NAME -- python ...'."
  exit 0
fi

# Last resort: ask user to activate and run pip freeze manually.
cat <<EOF

Could not run '$RUNNER run' for env '$ENV_NAME'. Please activate the environment manually and run:

  python -m pip freeze > $OUT_FILE

Examples:
  # for conda users
  eval "\$(conda shell.bash hook)"
  conda activate $ENV_NAME
  python -m pip freeze > $OUT_FILE

  # for micromamba users you might do
  eval "\$($RUNNER shell hook -s bash)"   # if your micromamba/mamba supports this
  $RUNNER activate $ENV_NAME
  python -m pip freeze > $OUT_FILE

EOF

exit 3
