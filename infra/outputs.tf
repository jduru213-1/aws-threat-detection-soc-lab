# -----------------------------------------------------------------------------
# Outputs (run: terraform output; secrets: terraform output -raw <name>)
# -----------------------------------------------------------------------------
# After apply, use:
#   - Bucket names: reference or troubleshooting; Splunk “SQS-based S3” inputs
#     primarily need the queue URLs from outputs_sqs.tf (and IAM keys below).
#   - splunk_* / stratus_* : keys for .env files or manual entry (sensitive).
# -----------------------------------------------------------------------------

output "aws_region" {
  description = "Region where this stack was applied (matches provider)."
  value       = local.region
}

output "cloudtrail_bucket_name" {
  description = "S3 bucket receiving CloudTrail log objects."
  value       = aws_s3_bucket.cloudtrail.id
}

output "cloudtrail_trail_arn" {
  description = "Management events trail ARN (single-region in this lab)."
  value       = aws_cloudtrail.main.arn
}

output "config_bucket_name" {
  description = "S3 bucket for AWS Config snapshots (null if enable_config is false)."
  value       = var.enable_config ? aws_s3_bucket.config[0].id : null
}

output "vpc_flow_logs_bucket_name" {
  description = "S3 bucket for VPC flow log files (null if VPC flow logs disabled)."
  value       = var.enable_vpc_flow_logs ? aws_s3_bucket.vpc_flow_logs[0].id : null
}

output "splunk_iam_user_arn" {
  description = "Splunk add-on IAM user ARN."
  value       = var.create_splunk_iam_user ? aws_iam_user.splunk[0].arn : null
}

output "splunk_iam_access_key_id" {
  description = "Splunk add-on access key ID (paste into Add-on → Configuration → AWS Account)."
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].id : null
}

output "splunk_iam_secret_key" {
  description = "Splunk add-on secret key (sensitive). Rotating the key in AWS and re-importing state reduces long-lived secrets in tfstate."
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].secret : null
  sensitive   = true
}

output "stratus_iam_user_arn" {
  description = "Stratus simulation user ARN."
  value       = var.create_stratus_iam_user ? aws_iam_user.stratus[0].arn : null
}

output "stratus_iam_access_key_id" {
  description = "Stratus access key ID."
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].id : null
}

output "stratus_iam_secret_key" {
  description = "Stratus secret key (sensitive). Use in a dedicated profile or .env.stratus; never commit."
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].secret : null
  sensitive   = true
}
