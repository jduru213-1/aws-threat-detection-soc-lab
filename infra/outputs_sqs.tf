output "cloudtrail_s3_sqs_queue_url" {
  description = "SQS queue URL for CloudTrail bucket notifications"
  value       = try(aws_sqs_queue.cloudtrail_s3_events[0].id, null)
}

output "cloudtrail_s3_sqs_queue_arn" {
  description = "SQS queue ARN for CloudTrail bucket notifications"
  value       = try(aws_sqs_queue.cloudtrail_s3_events[0].arn, null)
}

output "config_s3_sqs_queue_url" {
  description = "SQS queue URL for Config bucket notifications"
  value       = try(aws_sqs_queue.config_s3_events[0].id, null)
}

output "config_s3_sqs_queue_arn" {
  description = "SQS queue ARN for Config bucket notifications"
  value       = try(aws_sqs_queue.config_s3_events[0].arn, null)
}

output "vpcflow_s3_sqs_queue_url" {
  description = "SQS queue URL for VPC flow log bucket notifications"
  value       = try(aws_sqs_queue.vpcflow_s3_events[0].id, null)
}

output "vpcflow_s3_sqs_queue_arn" {
  description = "SQS queue ARN for VPC flow log bucket notifications"
  value       = try(aws_sqs_queue.vpcflow_s3_events[0].arn, null)
}
