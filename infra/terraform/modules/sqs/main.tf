resource "aws_sqs_queue" "dlq" {
  name = "ciis-analysis-dlq"
}

resource "aws_sqs_queue" "jobs" {
  name = "ciis-analysis-jobs"

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

output "queue_url" {
  value = aws_sqs_queue.jobs.url
}

output "dlq_url" {
  value = aws_sqs_queue.dlq.url
}
