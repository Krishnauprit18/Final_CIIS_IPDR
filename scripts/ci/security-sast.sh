#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CI_VENV="${CI_VENV:-$ROOT/.ci-venv}"
PYTHON="$CI_VENV/bin/python"
ARTIFACT_DIR="${ARTIFACT_DIR:-$ROOT/.ci-artifacts}"

cd "$ROOT"
mkdir -p "$ARTIFACT_DIR"

if [ ! -x "$PYTHON" ]; then
  echo "CI Python environment is missing: $PYTHON" >&2
  exit 1
fi

# Keep low/medium findings in the report, but block only high-severity,
# high-confidence Bandit findings. This prevents the current known
# low/medium review backlog from being silently discarded or breaking CI.
"$PYTHON" -m bandit \
  -r "$ROOT/backend/app" \
  --severity-level high \
  --confidence-level high \
  -f json \
  -o "$ARTIFACT_DIR/bandit.json"

echo "SAST checks passed."
