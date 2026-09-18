resource "aws_iam_role" "ciis_app" {
  name = "ciis-app-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

output "role_name" {
  value = aws_iam_role.ciis_app.name
}

output "role_arn" {
  value = aws_iam_role.ciis_app.arn
}
