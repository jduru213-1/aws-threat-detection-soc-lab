# -----------------------------------------------------------------------------
# S3 buckets: CloudTrail, AWS Config, VPC Flow Logs
# -----------------------------------------------------------------------------
# One bucket per source so permissions, lifecycle, and Splunk indexes stay
# isolated. Bucket policies for service write access live in cloudtrail.tf,
# config.tf, and vpc_flow_logs.tf respectively.
#
# force_destroy allows `terraform destroy` to delete non-empty buckets (the
# destroy script still empties versioned objects first).
# -----------------------------------------------------------------------------

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Random 8-hex suffix when var.s3_bucket_suffix is null (global uniqueness).
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

locals {
  suffix     = var.s3_bucket_suffix != null ? var.s3_bucket_suffix : random_id.bucket_suffix.hex
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
}

# --- CloudTrail bucket --------------------------------------------------------
resource "aws_s3_bucket" "cloudtrail" {
  bucket = "${var.project_name}-cloudtrail-${local.suffix}"

  force_destroy = true

  tags = {
    Name = "${var.project_name}-cloudtrail"
  }
}

# Expire current objects after 90 days; drop noncurrent versions after 30 days.
# filter {} with no prefix applies the rule to all objects (required shape in AWS provider 5.x).
resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# Versioning supports log integrity features and is typical for audit buckets.
resource "aws_s3_bucket_versioning" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Config bucket (if enable_config) ----------------------------------------
resource "aws_s3_bucket" "config" {
  count  = var.enable_config ? 1 : 0
  bucket = "${var.project_name}-config-${local.suffix}"

  force_destroy = true

  tags = {
    Name = "${var.project_name}-config"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "config" {
  count  = var.enable_config ? 1 : 0
  bucket = aws_s3_bucket.config[0].id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "config" {
  count  = var.enable_config ? 1 : 0
  bucket = aws_s3_bucket.config[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- VPC Flow Logs bucket (if enable_vpc_flow_logs) ---------------------------
resource "aws_s3_bucket" "vpc_flow_logs" {
  count  = var.enable_vpc_flow_logs ? 1 : 0
  bucket = "${var.project_name}-vpcflow-${local.suffix}"

  force_destroy = true

  tags = {
    Name = "${var.project_name}-vpcflow"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "vpc_flow_logs" {
  count  = var.enable_vpc_flow_logs ? 1 : 0
  bucket = aws_s3_bucket.vpc_flow_logs[0].id

  rule {
    id     = "expire-old-logs"
    status = "Enabled"

    filter {}

    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket_public_access_block" "vpc_flow_logs" {
  count  = var.enable_vpc_flow_logs ? 1 : 0
  bucket = aws_s3_bucket.vpc_flow_logs[0].id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
