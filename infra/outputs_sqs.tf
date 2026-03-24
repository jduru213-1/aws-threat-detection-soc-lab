# -----------------------------------------------------------------------------
# SQS outputs for Splunk Add-on (SQS-based S3 inputs)
# -----------------------------------------------------------------------------
# For each log source, configure the add-on with the queue URL (and matching
# index). The add-on polls SQS, then reads the S3 object referenced in the
# message. ARNs are useful for IAM conditions or debugging.
# -----------------------------------------------------------------------------

output "cloudtrail_s3_sqs_queue_url" {
  description = "SQS queue subscribed to new objects in the CloudTrail bucket."
  value       = try(aws_sqs_queue.cloudtrail_s3_events[0].id, null)
}

output "cloudtrail_s3_sqs_queue_arn" {
  description = "ARN of the CloudTrail SQS queue."
  value       = try(aws_sqs_queue.cloudtrail_s3_events[0].arn, null)
}

output "config_s3_sqs_queue_url" {
  description = "SQS queue subscribed to new objects in the Config bucket."
  value       = try(aws_sqs_queue.config_s3_events[0].id, null)
}

output "config_s3_sqs_queue_arn" {
  description = "ARN of the Config SQS queue."
  value       = try(aws_sqs_queue.config_s3_events[0].arn, null)
}

output "vpcflow_s3_sqs_queue_url" {
  description = "SQS queue subscribed to new objects in the VPC flow logs bucket."
  value       = try(aws_sqs_queue.vpcflow_s3_events[0].id, null)
}

output "vpcflow_s3_sqs_queue_arn" {
  description = "ARN of the VPC flow SQS queue."
  value       = try(aws_sqs_queue.vpcflow_s3_events[0].arn, null)
}
