variable "cluster_role_arn" {
  type = string
}

# Do not hard-code fake subnet IDs. The Terraform AWS provider validates that
# EKS receives subnet IDs, and Floci validates that those IDs actually exist.
# Create a small local VPC and two real Floci EC2 subnets, then feed their IDs
# into the EKS resource.
resource "aws_vpc" "ciis" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "ciis-local-vpc"
  }
}

resource "aws_subnet" "a" {
  vpc_id            = aws_vpc.ciis.id
  cidr_block        = "10.42.1.0/24"
  availability_zone = "us-east-1a"

  tags = {
    Name = "ciis-local-subnet-a"
  }
}

resource "aws_subnet" "b" {
  vpc_id            = aws_vpc.ciis.id
  cidr_block        = "10.42.2.0/24"
  availability_zone = "us-east-1b"

  tags = {
    Name = "ciis-local-subnet-b"
  }
}

resource "aws_eks_cluster" "ciis" {
  name     = "ciis-local"
  role_arn = var.cluster_role_arn

  vpc_config {
    subnet_ids = [
      aws_subnet.a.id,
      aws_subnet.b.id,
    ]
  }

  depends_on = [
    aws_subnet.a,
    aws_subnet.b,
  ]
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

output "vpc_id" {
  value = aws_vpc.ciis.id
}

output "subnet_ids" {
  value = [
    aws_subnet.a.id,
    aws_subnet.b.id,
  ]
}
