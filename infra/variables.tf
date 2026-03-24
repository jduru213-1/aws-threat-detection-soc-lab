# =============================================================================
# Input Variables
# =============================================================================
# These variables control what gets built and how it is named. You can set them
# via: terraform.tfvars file, -var "name=value" on the CLI, or TF_VAR_name
# environment variables. Defaults are used if not set.
# =============================================================================

# -----------------------------------------------------------------------------
# aws_region
# -----------------------------------------------------------------------------
# AWS region where all resources (S3, CloudTrail, Config, etc.)
# will be created. Use a single region to keep costs predictable.
# -----------------------------------------------------------------------------
variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

# -----------------------------------------------------------------------------
# project_name
# -----------------------------------------------------------------------------
# Prefix used in resource names (buckets, trails, IAM user, etc.). Helps
# identify lab resources and avoid clashes with other projects.
# -----------------------------------------------------------------------------
variable "project_name" {
  description = "Project name used in resource names"
  type        = string
  default     = "soc-lab"
}

# -----------------------------------------------------------------------------
# s3_bucket_suffix
# -----------------------------------------------------------------------------
# S3 bucket names must be globally unique across all AWS accounts. If null,
# Terraform generates a random hex suffix. Set this to a fixed value (e.g.
# your account ID or a unique string) if you want reproducible bucket names
# across applies (e.g. for reuse after destroy).
# -----------------------------------------------------------------------------
variable "s3_bucket_suffix" {
  description = "Optional suffix for S3 bucket names (must be globally unique). Leave null to use random."
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# enable_config
# -----------------------------------------------------------------------------
# When true, creates AWS Config recorder, delivery channel, Config S3 bucket,
# and IAM role so configuration snapshots/deltas are delivered to S3 for
# Splunk ingestion. Set to false to skip Config (e.g. to reduce cost).
# -----------------------------------------------------------------------------
variable "enable_config" {
  description = "Enable AWS Config recorder and delivery"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# enable_vpc_flow_logs
# -----------------------------------------------------------------------------
# When true, enables VPC Flow Logs on the default VPC and delivers them to
# the VPC Flow Logs S3 bucket. Requires a default VPC in the region.
# -----------------------------------------------------------------------------
variable "enable_vpc_flow_logs" {
  description = "Enable VPC Flow Logs on the default VPC"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# create_splunk_iam_user
# -----------------------------------------------------------------------------
# When true, creates an IAM user with an access key and policies that allow
# read-only access to the CloudTrail/Config/VPC Flow Logs S3 buckets. Use this user's credentials in the Splunk Add-on for AWS.
# -----------------------------------------------------------------------------
variable "create_splunk_iam_user" {
  description = "Create IAM user for Splunk Add-on for AWS"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# create_stratus_iam_user
# -----------------------------------------------------------------------------
# When true, creates a dedicated IAM user + access key for Stratus Red Team.
# Set false if you want to manage this user outside Terraform.
# -----------------------------------------------------------------------------
variable "create_stratus_iam_user" {
  description = "Create IAM user for Stratus Red Team"
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# enable_sqs_s3_inputs
# -----------------------------------------------------------------------------
# When true, creates SQS queues and S3 bucket notifications for SQS-based S3
# ingestion with the Splunk Add-on for AWS. This is optional; plain S3 inputs
# work without SQS.
# -----------------------------------------------------------------------------
variable "enable_sqs_s3_inputs" {
  description = "Enable SQS-based S3 ingestion (queues + bucket notifications)"
  type        = bool
  default     = true
}
