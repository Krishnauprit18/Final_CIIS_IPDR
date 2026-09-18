variable "cluster_role_arn" {
  type = string
}

resource "aws_eks_cluster" "ciis" {
  name     = "ciis-local"
  role_arn = var.cluster_role_arn

  vpc_config {
    subnet_ids         = []
    security_group_ids = []
  }
}

output "cluster_name" {
  value = aws_eks_cluster.ciis.name
}

output "endpoint" {
  value = aws_eks_cluster.ciis.endpoint
}