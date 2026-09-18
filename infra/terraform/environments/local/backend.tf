terraform {
  backend "s3" {
    bucket                      = "ciis-terraform-state"
    key                         = "local/terraform.tfstate"
    region                      = "us-east-1"

    endpoint                    = "http://localhost:4566"
    dynamodb_endpoint           = "http://localhost:4566"
    dynamodb_table              = "ciis-terraform-locks"

    access_key                  = "test"
    secret_key                  = "test"

    skip_credentials_validation = true
    skip_region_validation      = true
    use_path_style              = true
  }
}
