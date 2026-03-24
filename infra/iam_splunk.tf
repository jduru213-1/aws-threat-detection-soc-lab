# -----------------------------------------------------------------------------
# IAM user for Splunk Add-on for AWS (ingestion identity)
# -----------------------------------------------------------------------------
# This user is read-only toward the log buckets: GetObject / ListBucket on each
# bucket used by the lab. When enable_sqs_s3_inputs is true, a separate inline
# policy grants SQS receive/delete so the add-on can use SQS-based S3 inputs
# (poll queue, then fetch the S3 object referenced in the message).
#
# Paste the access key and secret into Splunk → Add-on → Configuration → AWS
# Account. Outputs: splunk_iam_access_key_id, splunk_iam_secret_key.
# -----------------------------------------------------------------------------

resource "aws_iam_user" "splunk" {
  count = var.create_splunk_iam_user ? 1 : 0

  name = "${var.project_name}-splunk-addon"
  path = "/"

  tags = {
    Name = "${var.project_name}-splunk-addon"
  }
}

resource "aws_iam_user_policy" "splunk_cloudtrail" {
  count = var.create_splunk_iam_user ? 1 : 0

  name = "${var.project_name}-splunk-cloudtrail"
  user = aws_iam_user.splunk[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.cloudtrail.arn,
        "${aws_s3_bucket.cloudtrail.arn}/*"
      ]
    }]
  })
}

resource "aws_iam_user_policy" "splunk_config" {
  count = var.create_splunk_iam_user && var.enable_config ? 1 : 0

  name = "${var.project_name}-splunk-config"
  user = aws_iam_user.splunk[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.config[0].arn,
        "${aws_s3_bucket.config[0].arn}/*"
      ]
    }]
  })
}

resource "aws_iam_user_policy" "splunk_vpcflow" {
  count = var.create_splunk_iam_user && var.enable_vpc_flow_logs ? 1 : 0

  name = "${var.project_name}-splunk-vpcflow"
  user = aws_iam_user.splunk[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["s3:GetObject", "s3:GetObjectVersion", "s3:ListBucket"]
      Resource = [
        aws_s3_bucket.vpc_flow_logs[0].arn,
        "${aws_s3_bucket.vpc_flow_logs[0].arn}/*"
      ]
    }]
  })
}

# Broad SQS permissions on * so the add-on can reach the lab queues without
# listing every queue ARN in policy (acceptable for a dedicated lab user).
resource "aws_iam_user_policy" "splunk_sqs" {
  count = var.create_splunk_iam_user && var.enable_sqs_s3_inputs ? 1 : 0

  name = "${var.project_name}-splunk-sqs"
  user = aws_iam_user.splunk[0].name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "sqs:ListQueues",
        "sqs:GetQueueAttributes",
        "sqs:GetQueueUrl",
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility"
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_access_key" "splunk" {
  count = var.create_splunk_iam_user ? 1 : 0

  user = aws_iam_user.splunk[0].name
}
