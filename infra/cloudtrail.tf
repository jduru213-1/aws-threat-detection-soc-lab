# -----------------------------------------------------------------------------
# CloudTrail trail and bucket policy
# -----------------------------------------------------------------------------
# CloudTrail writes API audit logs to the CloudTrail bucket. AWS requires:
#   - s3:GetBucketAcl on the bucket (service checks ACL before PutObject)
#   - s3:PutObject on bucket/* with aws:SourceAccount and x-amz-acl conditions
#
# Trail: single-region in this lab; include_global_service_events captures
# control-plane events such as IAM in the home region. Log file validation
# enables digest files for tamper detection.
# -----------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AWSCloudTrailAclCheck"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:GetBucketAcl"
        Resource  = aws_s3_bucket.cloudtrail.arn
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = local.account_id
          }
        }
      },
      {
        Sid       = "AWSCloudTrailWrite"
        Effect    = "Allow"
        Principal = { Service = "cloudtrail.amazonaws.com" }
        Action    = "s3:PutObject"
        Resource  = "${aws_s3_bucket.cloudtrail.arn}/*"
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

resource "aws_cloudtrail" "main" {
  name                          = "${var.project_name}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail         = false
  enable_log_file_validation    = true

  depends_on = [
    aws_s3_bucket_policy.cloudtrail
  ]

  tags = {
    Name = "${var.project_name}-trail"
  }
}
