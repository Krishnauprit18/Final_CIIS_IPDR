#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CI_VENV="${CI_VENV:-$ROOT/.ci-venv}"
PYTHON="$CI_VENV/bin/python"

if [ ! -x "$PYTHON" ]; then
  python3 -m venv "$CI_VENV"
fi

"$PYTHON" -m pip install --upgrade pip setuptools wheel
"$PYTHON" -m pip install -r "$ROOT/backend/requirements-dev.txt"

cd "$ROOT/backend"
"$PYTHON" -m ruff check .
