#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

terraform fmt -check -recursive infra/terraform

terraform \
  -chdir=infra/terraform/environments/local \
  init \
  -backend=false \
  -input=false

terraform \
  -chdir=infra/terraform/environments/local \
  validate

echo "Terraform validation passed."
