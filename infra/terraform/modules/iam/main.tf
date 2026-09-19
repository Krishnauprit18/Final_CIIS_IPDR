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

resource "aws_iam_role" "eks_cluster" {
  name = "ciis-eks-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "eks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

# Floci EKS authentication deliberately rejects the public test/test pair.
# Create a dedicated local IAM principal so aws eks get-token can sign a
# resolvable caller identity for kubectl.
resource "aws_iam_user" "kube_admin" {
  name = "ciis-kube-admin"
}

resource "aws_iam_access_key" "kube_admin" {
  user = aws_iam_user.kube_admin.name
}

output "role_name" {
  value = aws_iam_role.ciis_app.name
}

output "role_arn" {
  value = aws_iam_role.ciis_app.arn
}

output "eks_cluster_role_arn" {
  value = aws_iam_role.eks_cluster.arn
}

output "kube_admin_access_key_id" {
  value = aws_iam_access_key.kube_admin.id
}

output "kube_admin_secret_access_key" {
  value     = aws_iam_access_key.kube_admin.secret
  sensitive = true
}
