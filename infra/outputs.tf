# Outputs: `terraform output` (use `-raw` for secrets).

output "aws_region" {
  description = "AWS region where resources were created"
  value       = local.region
}

output "cloudtrail_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail.id
}

output "cloudtrail_trail_arn" {
  description = "CloudTrail trail ARN"
  value       = aws_cloudtrail.main.arn
}

output "config_bucket_name" {
  description = "S3 bucket for AWS Config (null if disabled)"
  value       = var.enable_config ? aws_s3_bucket.config[0].id : null
}

output "vpc_flow_logs_bucket_name" {
  description = "S3 bucket for VPC flow logs (null if disabled)"
  value       = var.enable_vpc_flow_logs ? aws_s3_bucket.vpc_flow_logs[0].id : null
}

output "splunk_iam_user_arn" {
  description = "IAM user ARN for Splunk Add-on for AWS"
  value       = var.create_splunk_iam_user ? aws_iam_user.splunk[0].arn : null
}

output "splunk_iam_access_key_id" {
  description = "Access key ID for Splunk Add-on"
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].id : null
}

output "splunk_iam_secret_key" {
  description = "Secret access key for Splunk Add-on (sensitive; rotate after use if concerned about state)"
  value       = var.create_splunk_iam_user ? aws_iam_access_key.splunk[0].secret : null
  sensitive   = true
}

output "stratus_iam_user_arn" {
  description = "IAM user ARN for Stratus Red Team"
  value       = var.create_stratus_iam_user ? aws_iam_user.stratus[0].arn : null
}

output "stratus_iam_access_key_id" {
  description = "Access key ID for Stratus IAM user"
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].id : null
}

output "stratus_iam_secret_key" {
  description = "Secret access key for Stratus (use in a profile or .env; do not commit)"
  value       = var.create_stratus_iam_user ? aws_iam_access_key.stratus[0].secret : null
  sensitive   = true
}
