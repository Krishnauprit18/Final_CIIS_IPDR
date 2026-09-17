#!/bin/sh
set -eu

echo "Creating CIIS analysis DLQ..."

DLQ_URL=$(awslocal sqs create-queue \
  --queue-name ciis-analysis-dlq \
  --query QueueUrl \
  --output text)

DLQ_ARN=$(awslocal sqs get-queue-attributes \
  --queue-url "$DLQ_URL" \
  --attribute-names QueueArn \
  --query 'Attributes.QueueArn' \
  --output text)

echo "Creating CIIS analysis main queue..."

awslocal sqs create-queue \
  --queue-name ciis-analysis \
  --attributes "{
    \"VisibilityTimeout\":\"900\",
    \"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"${DLQ_ARN}\\\",\\\"maxReceiveCount\\\":\\\"3\\\"}\"
  }"

echo "SQS queues ready."