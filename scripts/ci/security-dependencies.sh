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
  echo "Run scripts/ci/backend-lint.sh first; it installs requirements-dev.txt." >&2
  exit 1
fi

if ! "$PYTHON" -c 'import pip_audit' >/dev/null 2>&1; then
  echo "pip-audit is missing from $PYTHON; requirements-dev.txt was not installed." >&2
  exit 1
fi

# Backend dependency gate. Resolve the application requirements from the
# requirements file so development-only scanner packages do not become part
# of the application dependency report.
"$PYTHON" -m pip_audit \
  -r "$ROOT/backend/requirements.txt" \
  --format json \
  --output "$ARTIFACT_DIR/pip-audit.json"

# Frontend policy gate: critical findings fail the build. High/moderate/low
# findings remain visible in the archived report and are handled separately.
(
  cd "$ROOT/frontend"
  npm audit \
    --audit-level=critical \
    --json > "$ARTIFACT_DIR/npm-audit.json"
)

echo "Dependency security checks passed."
