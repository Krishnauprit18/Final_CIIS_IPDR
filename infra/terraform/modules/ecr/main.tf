resource "aws_ecr_repository" "api" {
  name                 = "ciis-api"
  image_tag_mutability = "IMMUTABLE"
}

resource "aws_ecr_repository" "worker" {
  name                 = "ciis-worker"
  image_tag_mutability = "IMMUTABLE"
}

resource "aws_ecr_repository" "web" {
  name                 = "ciis-web"
  image_tag_mutability = "IMMUTABLE"
}

output "api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "worker_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "web_repository_url" {
  value = aws_ecr_repository.web.repository_url
}
