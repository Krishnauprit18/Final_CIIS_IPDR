output "database_secret_arn" {
  value = aws_secretsmanager_secret.database.arn
}

output "database_secret_name" {
  value = aws_secretsmanager_secret.database.name
}

output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}

output "application_secret_name" {
  value = aws_secretsmanager_secret.application.name
}

output "secret_arns" {
  value = [
    aws_secretsmanager_secret.database.arn,
    aws_secretsmanager_secret.application.arn,
  ]
}