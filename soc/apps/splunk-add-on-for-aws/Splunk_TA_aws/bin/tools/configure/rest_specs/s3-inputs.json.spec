{
  "name": "s3",
  "endpoint": "splunk_ta_aws_aws_s3",
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
      "name": "key_name",
      "required": false,
      "description": "S3 key prefix"
    },
    {
      "name": "parse_csv_with_header",
      "required": false,
      "description": "If enabled, all files will be parsed considering first line of each file as the header. Specify either 0 or 1"
    },
    {
      "name": "parse_csv_with_delimiter",
      "required": false,
      "description": "Delimiter to consider while parsing csv files"
    },
    {
      "name": "initial_scan_datetime",
      "required": false,
      "description": "Splunk relative time. Format = %Y-%m-%dT%H:%M:%SZ"
    },
    {
      "name": "terminal_scan_datetime",
      "required": false,
      "description": "Only S3 keys which have been modified before this datetime will be considered. Format = %Y-%m-%dT%H:%M:%SZ"
    },
    {
      "name": "ct_blacklist",
      "required": false,
      "description": "Only valid if sourcetype is set to aws:cloudtrail. A PCRE regex that specifies events names to exclude"
    },
    {
      "name": "blacklist",
      "required": false,
      "description": "Regex specifying S3 keys (folders) to ignore"
    },
    {
      "name": "whitelist",
      "required": false,
      "description": "Regex specifying S3 keys (folders) to ignore. Overrides blacklist"
    },
    {
      "name": "ct_excluded_events_index",
      "required": false,
      "description": "Name of index to put excluded events into. Keep empty to discard the events"
    },
    {
      "name": "max_retries",
      "required": false,
      "description": "Max number of retry attempts to stream incomplete items"
    },
    {
      "name": "recursion_depth",
      "required": false,
      "description": "Number specifying the depth of subfolders to scan. -1 specifies all subfolders (unconstrained)"
    },
    {
      "name": "max_items",
      "required": false,
      "description": "Max trackable items"
    },
    {
      "name": "character_set",
      "required": false,
      "description": "The character encoding use in your S3 files. E.g. UTF-8"
    },
    {
      "name": "is_secure",
      "required": false,
      "description": "Whether to use secure connection to AWS"
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
      "name": "polling_interval",
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
    }
  ]
}
