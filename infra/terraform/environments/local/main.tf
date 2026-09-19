module "s3" {
  source = "../../modules/s3"
}

module "sqs" {
  source = "../../modules/sqs"
}

module "secrets" {
  source = "../../modules/secrets"
}

module "iam" {
  source = "../../modules/iam"

  ciis_secret_arns = module.secrets.secret_arns
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

output "database_secret_name" {
  value = module.secrets.database_secret_name
}

output "application_secret_name" {
  value = module.secrets.application_secret_name
}
