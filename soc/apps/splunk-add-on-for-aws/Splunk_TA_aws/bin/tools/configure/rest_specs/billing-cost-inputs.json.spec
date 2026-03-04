{
  "name": "billing-cost",
  "endpoint": "splunk_ta_aws_aws_billing_cur",
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
      "description": "AWS IAM role name"
    },
    {
      "name": "aws_s3_region",
      "required": false,
      "description": "Region to connect with s3 service using regional endpoint"
    },
    {
      "name": "bucket_region",
      "required": false,
      "description": "Region of AWS s3 bucket"
    },
    {
      "name": "bucket_name",
      "required": true,
      "description": "Name of s3 bucket where reports are delivered to"
    },
    {
      "name": "report_prefix",
      "required": false,
      "description": "Prefixes used to allow AWS to deliver reports into a specified folder"
    },
    {
      "name": "report_names",
      "required": false,
      "description": "Regex used to filter reports by name"
    },
    {
      "name": "temp_folder",
      "required": false,
      "description": "Full path to a non-default folder for temporarily storing downloaded detailed billing report .zip files"
    },
    {
      "name": "start_date",
      "required": false,
      "description": "Collect data after this time. Format = %Y-%m"
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
      "required": false,
      "description": "Sourcetype of collected data"
    },
    {
      "name": "index",
      "required": true,
      "description": "Splunk index to ingest data. Default is main"
    }
  ]
}
