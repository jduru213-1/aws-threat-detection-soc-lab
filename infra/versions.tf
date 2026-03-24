# -----------------------------------------------------------------------------
# Terraform version and providers
# -----------------------------------------------------------------------------
# Run `terraform init` before `plan` / `apply` so providers are installed.
#
# - aws:    All AWS resources in this stack (S3, IAM, CloudTrail, Config, etc.).
#           Version ~> 5.0 allows 5.x bugfix releases, not 6.x.
# - random: Generates a hex suffix for globally unique S3 bucket names when
#           var.s3_bucket_suffix is null (S3 bucket names must be unique across
#           all of AWS).
#
# Optional remote state: uncomment `backend "s3"` after you create the bucket
# (and optional DynamoDB table for locking). Required for shared/CI workflows;
# local state is fine for a solo lab machine.
# -----------------------------------------------------------------------------

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "soc-lab/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

# Credentials: env vars (e.g. AWS_ACCESS_KEY_ID), ~/.aws/credentials profiles,
# or an IAM role (e.g. on EC2/CI). Region comes from var.aws_region.
#
# default_tags are merged onto resources that support them unless a resource
# sets its own tags.
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "aws-soc-lab"
      ManagedBy = "terraform"
    }
  }
}
