# -----------------------------------------------------------------------------
# SQS + S3 notifications for Splunk “SQS-based S3” inputs
# -----------------------------------------------------------------------------
# When a new log object lands in a bucket, S3 sends a message to that source’s
# queue. The Splunk Add-on polls SQS, reads the S3 key from the message, and
# fetches the object. This scales better than scanning the whole bucket
# on a timer.
#
# Each source has: main queue + DLQ (failed messages after maxReceiveCount),
# queue policy allowing only that bucket’s ARN to SendMessage, and
# aws_s3_bucket_notification for s3:ObjectCreated:*.
#
# Visibility timeout (300s) should be ≥ Splunk’s processing time for a batch
# to avoid duplicate visibility.
# -----------------------------------------------------------------------------

resource "aws_sqs_queue" "cloudtrail_s3_events_dlq" {
  count = var.enable_sqs_s3_inputs ? 1 : 0

  name                      = "${var.project_name}-cloudtrail-s3-events-dlq-${local.suffix}"
  message_retention_seconds = 1209600 # 14 days
}

resource "aws_sqs_queue" "cloudtrail_s3_events" {
  count = var.enable_sqs_s3_inputs ? 1 : 0

  name                       = "${var.project_name}-cloudtrail-s3-events-${local.suffix}"
  message_retention_seconds  = 345600 # 4 days
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.cloudtrail_s3_events_dlq[0].arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "config_s3_events_dlq" {
  count = var.enable_sqs_s3_inputs && var.enable_config ? 1 : 0

  name                      = "${var.project_name}-config-s3-events-dlq-${local.suffix}"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "config_s3_events" {
  count = var.enable_sqs_s3_inputs && var.enable_config ? 1 : 0

  name                       = "${var.project_name}-config-s3-events-${local.suffix}"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.config_s3_events_dlq[0].arn
    maxReceiveCount     = 5
  })
}

resource "aws_sqs_queue" "vpcflow_s3_events_dlq" {
  count = var.enable_sqs_s3_inputs && var.enable_vpc_flow_logs ? 1 : 0

  name                      = "${var.project_name}-vpcflow-s3-events-dlq-${local.suffix}"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "vpcflow_s3_events" {
  count = var.enable_sqs_s3_inputs && var.enable_vpc_flow_logs ? 1 : 0

  name                       = "${var.project_name}-vpcflow-s3-events-${local.suffix}"
  message_retention_seconds  = 345600
  visibility_timeout_seconds = 300
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.vpcflow_s3_events_dlq[0].arn
    maxReceiveCount     = 5
  })
}

# Restrict SendMessage to the matching bucket ARN (prevents other buckets from
# spamming the queue).
resource "aws_sqs_queue_policy" "cloudtrail_s3_events" {
  count = var.enable_sqs_s3_inputs ? 1 : 0

  queue_url = aws_sqs_queue.cloudtrail_s3_events[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.cloudtrail_s3_events[0].arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_s3_bucket.cloudtrail.arn }
      }
    }]
  })
}

resource "aws_sqs_queue_policy" "config_s3_events" {
  count = var.enable_sqs_s3_inputs && var.enable_config ? 1 : 0

  queue_url = aws_sqs_queue.config_s3_events[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.config_s3_events[0].arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_s3_bucket.config[0].arn }
      }
    }]
  })
}

resource "aws_sqs_queue_policy" "vpcflow_s3_events" {
  count = var.enable_sqs_s3_inputs && var.enable_vpc_flow_logs ? 1 : 0

  queue_url = aws_sqs_queue.vpcflow_s3_events[0].id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowS3SendMessage"
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.vpcflow_s3_events[0].arn
      Condition = {
        ArnEquals = { "aws:SourceArn" = aws_s3_bucket.vpc_flow_logs[0].arn }
      }
    }]
  })
}

resource "aws_s3_bucket_notification" "cloudtrail_to_sqs" {
  count = var.enable_sqs_s3_inputs ? 1 : 0

  bucket = aws_s3_bucket.cloudtrail.id
  queue {
    queue_arn = aws_sqs_queue.cloudtrail_s3_events[0].arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sqs_queue_policy.cloudtrail_s3_events]
}

resource "aws_s3_bucket_notification" "config_to_sqs" {
  count = var.enable_sqs_s3_inputs && var.enable_config ? 1 : 0

  bucket = aws_s3_bucket.config[0].id
  queue {
    queue_arn = aws_sqs_queue.config_s3_events[0].arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sqs_queue_policy.config_s3_events]
}

resource "aws_s3_bucket_notification" "vpcflow_to_sqs" {
  count = var.enable_sqs_s3_inputs && var.enable_vpc_flow_logs ? 1 : 0

  bucket = aws_s3_bucket.vpc_flow_logs[0].id
  queue {
    queue_arn = aws_sqs_queue.vpcflow_s3_events[0].arn
    events    = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_sqs_queue_policy.vpcflow_s3_events]
}
