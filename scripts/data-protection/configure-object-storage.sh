#!/usr/bin/env bash
set -Eeuo pipefail

ENDPOINT_URL="${STORAGE_ENDPOINT_URL:-http://127.0.0.1:59000}"
BUCKET="${STORAGE_BUCKET:-ciis-storage}"
REGION="${AWS_REGION:-us-east-1}"

export AWS_ACCESS_KEY_ID="${STORAGE_ACCESS_KEY:-ciisadmin}"
export AWS_SECRET_ACCESS_KEY="${STORAGE_SECRET_KEY:-ciisadmin123}"

aws_args=(--endpoint-url "$ENDPOINT_URL" --region "$REGION")
aws s3api head-bucket --bucket "$BUCKET" "${aws_args[@]}" >/dev/null 2>&1 || \
  aws s3api create-bucket --bucket "$BUCKET" "${aws_args[@]}" >/dev/null

aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --versioning-configuration Status=Enabled \
  "${aws_args[@]}"

LIFECYCLE_JSON='{"Rules":[{"ID":"expire-raw-inputs","Status":"Enabled","Filter":{"Prefix":"analysis-inputs/"},"Expiration":{"Days":30},"NoncurrentVersionExpiration":{"NoncurrentDays":7}},{"ID":"expire-results","Status":"Enabled","Filter":{"Prefix":"analysis-results/"},"Expiration":{"Days":90},"NoncurrentVersionExpiration":{"NoncurrentDays":30}},{"ID":"expire-quarantine","Status":"Enabled","Filter":{"Prefix":"quarantine/"},"Expiration":{"Days":180},"NoncurrentVersionExpiration":{"NoncurrentDays":30}}]}'

aws s3api put-bucket-lifecycle-configuration \
  --bucket "$BUCKET" \
  --lifecycle-configuration "$LIFECYCLE_JSON" \
  "${aws_args[@]}"

echo "Configured versioning and lifecycle policy for s3://${BUCKET} at ${ENDPOINT_URL}"
aws s3api get-bucket-versioning --bucket "$BUCKET" "${aws_args[@]}"
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" "${aws_args[@]}"
