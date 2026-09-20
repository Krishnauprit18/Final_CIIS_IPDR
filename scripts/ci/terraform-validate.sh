#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TF_ROOT="$ROOT/infra/terraform/environments/local"
TF_DATA_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ciis-terraform-validate.XXXXXX")"

cleanup() {
  rm -rf "$TF_DATA_DIR"
}

trap cleanup EXIT

export TF_DATA_DIR

cd "$ROOT"

terraform fmt -check -recursive infra/terraform

terraform   -chdir="$TF_ROOT"   init   -backend=false   -input=false   -reconfigure

terraform   -chdir="$TF_ROOT"   validate

echo "Terraform validation passed."
