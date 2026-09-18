module "s3" {
  source = "../../modules/s3"
}

module "sqs" {
  source = "../../modules/sqs"
}

module "iam" {
  source = "../../modules/iam"
}
