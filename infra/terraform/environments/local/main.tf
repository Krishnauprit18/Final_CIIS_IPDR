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

  cluster_role_arn = module.iam.role_arn
}