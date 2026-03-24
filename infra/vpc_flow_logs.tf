# -----------------------------------------------------------------------------
# VPC Flow Logs → S3 (default VPC)
# -----------------------------------------------------------------------------
# Flow logs capture accepted/rejected traffic at ENI level. Destination type
# S3 uses the delivery.logs.amazonaws.com service to write objects (no IAM role
# on the flow log resource for S3 destinations).
#
# Requires the default VPC in this region. If your account has no default VPC,
# set enable_vpc_flow_logs = false or create a default VPC first.
# -----------------------------------------------------------------------------

data "aws_vpc" "default" {
  count   = var.enable_vpc_flow_logs ? 1 : 0
  default = true
}

resource "aws_flow_log" "main" {
  count = var.enable_vpc_flow_logs ? 1 : 0

  log_destination      = aws_s3_bucket.vpc_flow_logs[0].arn
  log_destination_type = "s3"
  traffic_type         = "ALL"
  vpc_id               = data.aws_vpc.default[0].id

  tags = {
    Name = "${var.project_name}-vpc-flow-logs"
  }
}

# Allow delivery.logs.amazonaws.com to read ACL and write gzip flow log files.
resource "aws_s3_bucket_policy" "vpc_flow_logs" {
  count = var.enable_vpc_flow_logs ? 1 : 0

  bucket = aws_s3_bucket.vpc_flow_logs[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSLogDeliveryAclCheck"
        Effect    = "Allow"
        Principal = { Service = "delivery.logs.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.vpc_flow_logs[0].arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      },
      {
        Sid       = "AWSLogDeliveryWrite"
        Effect    = "Allow"
        Principal = { Service = "delivery.logs.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.vpc_flow_logs[0].arn}/*"
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
