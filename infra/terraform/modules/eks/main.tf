variable "cluster_role_arn" {
  type = string
}

resource "aws_eks_cluster" "ciis" {
  name     = "ciis-local"
  role_arn = var.cluster_role_arn

  # Floci seeds these default subnets in every region. Using real seeded IDs
  # satisfies the AWS provider schema and Floci's EKS validation without
  # inventing a subnet that does not exist.
  vpc_config {
    subnet_ids = [
      "subnet-default-a",
      "subnet-default-b",
    ]
  }
}

output "cluster_name" {
  value = aws_eks_cluster.ciis.name
}

output "endpoint" {
  value = aws_eks_cluster.ciis.endpoint
}

output "status" {
  value = aws_eks_cluster.ciis.status
}
