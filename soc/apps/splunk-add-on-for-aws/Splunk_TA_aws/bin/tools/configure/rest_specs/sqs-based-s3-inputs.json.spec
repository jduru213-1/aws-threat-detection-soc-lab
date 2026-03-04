{
  "name": "sqs-based-s3",
  "endpoint": "splunk_ta_aws_aws_sqs_based_s3",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for input"
    },
    {
      "name": "aws_account",
      "required": true,
      "description": "AWS Account name"
    },
    {
      "name": "aws_iam_role",
      "required": false,
      "description": "AWS IAM Role"
    },
    {
      "name": "using_dlq",
      "required": false,
      "description": "Specify either 0 or 1 to disable or enable checking for dead letter queue (DLQ)"
    },
    {
      "name": "sqs_sns_validation",
      "required": false,
      "description": "Enable or disable SNS signature validation. Specify either 0 or 1"
    },
    {
      "name": "parse_firehose_error_data",
      "required": false,
      "description": "Enable of disable firehorse error data"
    },
    {
      "name": "parse_csv_with_header",
      "required": false,
      "description": "Enable parsing of CSV data with header. First line of file will be considered as header. Specify either 0 or 1"
    },
    {
      "name": "parse_csv_with_delimiter",
      "required": false,
      "description": "Enable parsing of CSV data by chosen delimiter. Specify delimiter for parsing csv file"
    },
    {
      "name": "sqs_queue_region",
      "required": true,
      "description": "Name of the AWS region in which the notification queue is located"
    },
    {
      "name": "sqs_queue_url",
      "required": true,
      "description": "Name of SQS queue to which notifications of S3 file(s) creation are sent"
    },
    {
      "name": "sqs_batch_size",
      "required": false,
      "description": "Max number of messages to pull from SQS in one batch"
    },
    {
      "name": "s3_file_decoder",
      "required": true,
      "description": "Name of a decoder which decodes files into events: CloudTrail, Config, S3 Access Logs, ELB Access Logs, CloudFront Access Logs, and CustomLogs"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
    },
    {
      "name": "sqs_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with sqs service"
    },
    {
      "name": "s3_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with s3 service"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with sts service"
    },
    {
      "name": "interval",
      "required": false,
      "description": "Data collection interval"
    },
    {
      "name": "index",
      "required": true,
      "description": "Sourcetype of collected data"
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "Splunk index to ingest data. Default is main"
    },
    {
      "name": "metric_index_flag",
      "required": false,
      "description": "Whether to use event index or metric index"
    }
  ]
}
