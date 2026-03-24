# Input variables — set via terraform.tfvars, -var, or TF_VAR_*.

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix for resource names (buckets, IAM, etc.)"
  type        = string
  default     = "soc-lab"
}

variable "s3_bucket_suffix" {
  description = "Optional globally-unique bucket suffix; leave null for random"
  type        = string
  default     = null
}

variable "enable_config" {
  description = "Enable AWS Config recorder and S3 delivery"
  type        = bool
  default     = true
}

variable "enable_vpc_flow_logs" {
  description = "Enable VPC flow logs on the default VPC to S3"
  type        = bool
  default     = true
}

variable "create_splunk_iam_user" {
  description = "Create IAM user for Splunk Add-on for AWS"
  type        = bool
  default     = true
}

variable "create_stratus_iam_user" {
  description = "Create IAM user for Stratus Red Team"
  type        = bool
  default     = true
}

variable "enable_sqs_s3_inputs" {
  description = "SQS queues + S3 notifications for SQS-based Splunk ingestion (disable if you use direct S3 inputs only)"
  type        = bool
  default     = true
}
