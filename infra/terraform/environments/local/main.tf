module "s3" {
  source = "../../modules/s3"
}

module "sqs" {
  source = "../../modules/sqs"
}

module "iam" {
  source = "../../modules/iam"
}

module "ecr" {
  source = "../../modules/ecr"
}

module "eks" {
  source = "../../modules/eks"

  cluster_role_arn = module.iam.eks_cluster_role_arn
}

output "kube_admin_access_key_id" {
  value = module.iam.kube_admin_access_key_id
}

output "kube_admin_secret_access_key" {
  value     = module.iam.kube_admin_secret_access_key
  sensitive = true
}
