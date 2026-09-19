resource "aws_secretsmanager_secret" "database" {
  name        = "ciis/database"
  description = "CIIS database runtime credentials"
}

resource "aws_secretsmanager_secret" "application" {
  name        = "ciis/application"
  description = "CIIS application runtime secrets"
}