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

# PyPI lookups are network-bound and Jenkins may occasionally see a slow
# response even when the agent has working internet access. Keep the gate
# blocking, but make transient read timeouts deterministic and diagnosable.
PIP_AUDIT_TIMEOUT="${PIP_AUDIT_TIMEOUT:-45}"
PIP_AUDIT_ATTEMPTS="${PIP_AUDIT_ATTEMPTS:-2}"
PIP_AUDIT_CACHE_DIR="${PIP_AUDIT_CACHE_DIR:-${HOME:-$ROOT}/.cache/pip-audit}"
mkdir -p "$PIP_AUDIT_CACHE_DIR"

# Backend dependency gate. Resolve the application requirements from the
# requirements file so development-only scanner packages do not become part
# of the application dependency report.
pip_audit_status=1
for attempt in $(seq 1 "$PIP_AUDIT_ATTEMPTS"); do
  echo "Running pip-audit attempt ${attempt}/${PIP_AUDIT_ATTEMPTS} (timeout=${PIP_AUDIT_TIMEOUT}s)."

  if "$PYTHON" -m pip_audit \
    -r "$ROOT/backend/requirements.txt" \
    --format json \
    --output "$ARTIFACT_DIR/pip-audit.json" \
    --cache-dir "$PIP_AUDIT_CACHE_DIR" \
    --progress-spinner off \
    --timeout "$PIP_AUDIT_TIMEOUT"; then
    pip_audit_status=0
  else
    pip_audit_status=$?
  fi

  if [ "$pip_audit_status" -eq 0 ]; then
    break
  fi

  if [ "$attempt" -lt "$PIP_AUDIT_ATTEMPTS" ]; then
    echo "pip-audit attempt ${attempt} failed; retrying after a short backoff." >&2
    sleep 5
  fi
done

if [ "$pip_audit_status" -ne 0 ]; then
  echo "pip-audit failed after ${PIP_AUDIT_ATTEMPTS} attempt(s)." >&2
  exit "$pip_audit_status"
fi

# Frontend policy gate: critical findings fail the build. High/moderate/low
# findings remain visible in the archived report and are handled separately.
(
  cd "$ROOT/frontend"
  npm audit \
    --audit-level=critical \
    --json > "$ARTIFACT_DIR/npm-audit.json"
)

echo "Dependency security checks passed."
