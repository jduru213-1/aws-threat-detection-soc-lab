# -----------------------------------------------------------------------------
# AWS Config: recorder, delivery channel, IAM role, bucket policy
# -----------------------------------------------------------------------------
# When enable_config is true, Config records resource configuration and delivers
# change snapshots to the Config S3 bucket under prefix "config/".
#
# Order: recorder and delivery channel must exist before the recorder can be
# started (configuration_recorder_status). The IAM role lets Config assume
# roles to read resources and write to S3; inline policies replace or augment
# AWS managed ConfigRole where needed for this module layout.
# -----------------------------------------------------------------------------

resource "aws_config_configuration_recorder" "main" {
  count = var.enable_config ? 1 : 0

  name     = "${var.project_name}-config-recorder"
  role_arn = aws_iam_role.config[0].arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

resource "aws_config_delivery_channel" "main" {
  count = var.enable_config ? 1 : 0

  name           = "${var.project_name}-config-delivery"
  s3_bucket_name = aws_s3_bucket.config[0].id
  s3_key_prefix  = "config"

  depends_on = [aws_config_configuration_recorder.main]
}

resource "aws_config_configuration_recorder_status" "main" {
  count = var.enable_config ? 1 : 0

  name       = aws_config_configuration_recorder.main[0].name
  is_enabled = true

  depends_on = [aws_config_delivery_channel.main]
}

resource "aws_iam_role" "config" {
  count = var.enable_config ? 1 : 0

  name = "${var.project_name}-config-delivery-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })
}

# Allows Config to write objects with bucket-owner-full-control ACL.
resource "aws_iam_role_policy" "config" {
  count = var.enable_config ? 1 : 0

  name = "${var.project_name}-config-s3"
  role = aws_iam_role.config[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectAcl"
        ]
        Resource = "${aws_s3_bucket.config[0].arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.config[0].arn
      }
    ]
  })
}

# Recorder and delivery API calls (scoped config:* actions).
resource "aws_iam_role_policy" "config_recorder" {
  count = var.enable_config ? 1 : 0

  name = "${var.project_name}-config-recorder"
  role = aws_iam_role.config[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["config:Put*", "config:Get*", "config:Describe*", "config:List*", "config:Deliver*"]
        Resource = "*"
      }
    ]
  })
}

# Bucket policy: Config service must list bucket, get ACL, and put objects.
resource "aws_s3_bucket_policy" "config" {
  count = var.enable_config ? 1 : 0

  bucket = aws_s3_bucket.config[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSConfigBucketPermissionsCheck"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.config[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      },
      {
        Sid       = "AWSConfigBucketExistenceCheck"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:ListBucket"
        Resource  = aws_s3_bucket.config[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      },
      {
        Sid       = "AWSConfigBucketDelivery"
        Effect    = "Allow"
        Principal = { Service = "config.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.config[0].arn}/*"
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
          StringLike = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}
