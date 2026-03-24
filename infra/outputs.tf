# =============================================================================
# Terraform Outputs
# =============================================================================
# Outputs are shown after apply and can be used by scripts or noted for manual
# configuration (e.g. Splunk Add-on). Run: terraform output
# For sensitive secret: terraform output -raw splunk_iam_secret_key
# =============================================================================

output "aws_region" {
  description = "AWS region where resources were created"
  value       = local.region
}

output "cloudtrail_bucket_name" {
  description = "S3 bucket name for CloudTrail logs; use in Splunk S3 input for CloudTrail"
  value       = aws_s3_bucket.cloudtrail.id
}

output "cloudtrail_trail_arn" {
  description = "CloudTrail trail ARN (for reference or IAM conditions)"
  value       = aws_cloudtrail.main.arn
}

output "config_bucket_name" {
  description = "S3 bucket name for AWS Config; use in Splunk S3 input for Config (null if Config disabled)"
  value       = var.enable_config ? aws_s3_bucket.config[0].id : null
}

output "vpc_flow_logs_bucket_name" {
  description = "S3 bucket name for VPC Flow Logs; use in Splunk S3 input for VPC Flow (null if disabled)"
  value       = var.enable_vpc_flow_logs ? aws_s3_bucket.vpc_flow_logs[0].id : null
}

# -----------------------------------------------------------------------------
# Splunk Add-on credentials
# -----------------------------------------------------------------------------
output "splunk_iam_user_arn" {
  description = "IAM user ARN for Splunk Add-on for AWS"
  value       = var.create_splunk_iam_user ? aws_iam_user.splunk[0].arn : null
}

output "splunk_iam_access_key_id" {
  description = "Access key ID; enter as AWS Access Key ID in Splunk Add-on for AWS"
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].id : null
}

output "splunk_iam_secret_key" {
  description = "Secret access key; enter as AWS Secret Access Key in Splunk. Then consider rotating key and re-importing state so secret is not stored long-term."
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].secret : null
  sensitive   = true
}

# -----------------------------------------------------------------------------
# Stratus Red Team credentials
# -----------------------------------------------------------------------------

output "stratus_iam_user_arn" {
  description = "IAM user ARN for Stratus Red Team (attack simulation)"
  value       = var.create_stratus_iam_user ? aws_iam_user.stratus[0].arn : null
}

output "stratus_iam_access_key_id" {
  description = "Access key ID for Stratus IAM user"
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].id : null
}

output "stratus_iam_secret_key" {
  description = "Secret access key for Stratus IAM user (use in a dedicated profile or .env, not committed)"
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].secret : null
  sensitive   = true
}
