{
  "name": "incr-s3",
  "endpoint": "splunk_ta_aws_splunk_ta_aws_logs",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for input"
    },
    {
      "name": "aws_account",
      "required": true,
      "description": "AWS account name"
    },
    {
      "name": "aws_iam_role",
      "required": false,
      "description": "AWS IAM role"
    },
    {
      "name": "host_name",
      "required": false,
      "description": "The host name of the S3 service"
    },
    {
      "name": "aws_s3_region",
      "required": false,
      "description": "AWS region that contains the bucket"
    },
    {
      "name": "bucket_name",
      "required": true,
      "description": "AWS S3 bucket name"
    },
    {
      "name": "log_type",
      "required": true,
      "description": "The type of logs to ingest. Available log type are cloudtrail, elb:accesslogs, cloudfront:accesslogs and s3:accesslogs"
    },
    {
      "name": "log_file_prefix",
      "required": false,
      "description": "Configure the prefix of log file, which along with other path elements, forms the URL under which the addon searches the log files"
    },
    {
      "name": "log_start_date",
      "required": false,
      "description": "The start date of the log. Format = %Y-%m-%d"
    },
    {
      "name": "bucket_region",
      "required": false,
      "description": "AWS region where the bucket exists"
    },
    {
      "name": "distribution_id",
      "required": false,
      "description": "Cloudfront distribution id. Specify only when creating input for collecting cloudfront access logs"
    },
    {
      "name": "max_fails",
      "required": false,
      "description": "Stop discovering new keys if the number of failed files exceeded max_fails"
    },
    {
      "name": "max_number_of_process",
      "required": false,
      "description": "Max number of processes"
    },
    {
      "name": "max_number_of_thread",
      "required": false,
      "description": "Max number of threads"
    },
    {
      "name": "max_retries",
      "required": false,
      "description": "Max number of retries to collect data upon failing requests. Specify -1 to retry until success"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
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
      "description": "Data collection interval, in seconds"
    },
    {
      "name": "sourcetype",
      "required": true,
      "description": "Sourcetype of collected data"
    },
    {
      "name": "index",
      "required": true,
      "description": "Splunk index to ingest data. Default is main"
    },


    {
      "name": "log_name_format",
      "required": false,
      "description": "Distribution ID (Required for log_type='cloudfront:accesslogs')"
    },
    {
      "name": "log_path_format",
      "required": false,
      "description": "Log File Path (Required for log_type='cloudtrail')"
    }


  ]
}
