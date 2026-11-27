terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
  # State lives in the S3 bucket made by infra/bootstrap; the bucket name is passed with
  # -backend-config=backend.hcl so the account id is not committed. use_lockfile stops two
  # applies running at once (no DynamoDB lock table needed).
  backend "s3" {
    key          = "papertrail/prod.tfstate"
    region       = "ap-southeast-2"
    encrypt      = true
    use_lockfile = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "papertrail", Environment = var.env, ManagedBy = "terraform" }
  }
}

data "aws_caller_identity" "me" {}
