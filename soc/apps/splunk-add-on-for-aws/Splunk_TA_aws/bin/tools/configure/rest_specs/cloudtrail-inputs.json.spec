{
  "name": "cloudtrail",
  "endpoint": "splunk_ta_aws_aws_cloudtrail",
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
      "name": "aws_region",
      "required": true,
      "description": "AWS region to collect data from"
    },
    {
      "name": "sqs_queue",
      "required": true,
      "description": "Name of the queue where AWS sends new Cloudtrail log notifications"
    },
    {
      "name": "remove_files_when_done",
      "required": false,
      "description": "Boolean value indicating whether Splunk should delete log files from S3 bucket after indexing"
    },
    {
      "name": "exclude_describe_events",
      "required": false,
      "description": "Boolean value indicating whether or not to exclude certain events, such as read-only events that can produce high volume of data"
    },
    {
      "name": "blacklist",
      "required": false,
      "description": "A PCRE regex that specifies event names to exclude if exclude_describe_events is set to True. Leave blank to use default regex ^(?:Describe|List|Get)"
    },
    {
      "name": "excluded_events_index",
      "required": false,
      "description": "Splunk index to put excluded events. Default is empty which discards the events"
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
      "name": "sqs_private_endpoint_enabled",
      "required": false,
      "description": "Private endpoint url to connect with sqs service"
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
