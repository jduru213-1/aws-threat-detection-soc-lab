# Terraform and providers — run `terraform init` before plan/apply.

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

  # Optional remote state (create bucket + DynamoDB lock table first).
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "soc-lab/terraform.tfstate"
  #   region         = "us-east-1"
  #   encrypt        = true
  #   dynamodb_table = "terraform-locks"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "aws-soc-lab"
      ManagedBy = "terraform"
    }
  }
}
