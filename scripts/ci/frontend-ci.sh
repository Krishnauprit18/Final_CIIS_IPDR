#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT/frontend"

npm ci
npm run lint
CI=true npm test -- --watchAll=false --coverage --coverageReporters=text --coverageReporters=cobertura
mkdir -p "$ROOT/.ci-artifacts/frontend"
cp coverage/cobertura-coverage.xml "$ROOT/.ci-artifacts/frontend/coverage.xml"
npm run build
