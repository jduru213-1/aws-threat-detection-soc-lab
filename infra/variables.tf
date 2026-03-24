# -----------------------------------------------------------------------------
# Input variables
# -----------------------------------------------------------------------------
# Set values via:
#   - terraform.tfvars (copy from terraform.tfvars.example)
#   - CLI: terraform apply -var="key=value"
#   - Environment: TF_VAR_<name>
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region where all resources are created (single region keeps the lab simple)."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix for names (S3 buckets, IAM users, trails, queues). Change if you need to avoid collisions."
  type        = string
  default     = "soc-lab"
}

variable "s3_bucket_suffix" {
  description = "Optional suffix so bucket names stay globally unique. If null, a random hex suffix is generated on first apply."
  type        = string
  default     = null
}

variable "enable_config" {
  description = "When true, provisions AWS Config recorder, delivery channel, IAM role, Config bucket, and related policies. Set false to skip Config (e.g. lower cost)."
  type        = bool
  default     = true
}

variable "enable_vpc_flow_logs" {
  description = "When true, enables VPC Flow Logs on the default VPC in this region and delivers to S3. Requires a default VPC; set false if your account has none."
  type        = bool
  default     = true
}

variable "create_splunk_iam_user" {
  description = "When true, creates the soc-lab-splunk-addon IAM user and access key for the Splunk Add-on for AWS (S3 read + optional SQS)."
  type        = bool
  default     = true
}

variable "create_stratus_iam_user" {
  description = "When true, creates the Stratus IAM user and key. Set false if you manage Stratus credentials outside Terraform."
  type        = bool
  default     = true
}

variable "enable_sqs_s3_inputs" {
  description = "When true, creates SQS queues, queue policies, and S3 event notifications so Splunk can use SQS-based S3 inputs (recommended in this lab). Set false only if you will configure direct S3 polling in the add-on instead."
  type        = bool
  default     = true
}
