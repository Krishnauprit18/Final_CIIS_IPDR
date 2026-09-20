#!/usr/bin/env bash
set -euo pipefail

# Run ordinary Floci AWS CLI commands with local test/test credentials without
# changing the caller's shell environment or breaking EKS kubectl auth.
export AWS_ENDPOINT_URL="http://localhost:4566"
export AWS_DEFAULT_REGION="us-east-1"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="test"
export AWS_SECRET_ACCESS_KEY="test"

exec aws "$@"
