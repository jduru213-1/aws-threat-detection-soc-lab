{
  "name": "kinesis",
  "endpoint": "splunk_ta_aws_aws_kinesis",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for input"
    },
    {
      "name": "account",
      "required": true,
      "description": "AWS Account name"
    },
    {
      "name": "aws_iam_role",
      "required": false,
      "description": "AWS IAM Role"
    },
    {
      "name": "region",
      "required": true,
      "description": "AWS region for kinesis stream"
    },
    {
      "name": "stream_names",
      "required": true,
      "description": "Kinesis stream names in a comma-separated list. Leave empty to collect all streams"
    },
    {
      "name": "init_stream_position",
      "required": false,
      "description": "Stream position to start collecting data from. Specify either TRIM_HORIZON (starting) or LATEST (recent live data)"
    },
    {
      "name": "encoding",
      "required": false,
      "description": "Encoding of stream data. Set to gzip or leave blank, which defaults to Base64"
    },
    {
      "name": "format",
      "required": false,
      "description": "Format of the collected data. Specify CloudWatchLogs or leave empty"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
    },
    {
      "name": "kinesis_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with kinesis service"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with sts service"
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
    },
    {
      "name": "metric_index_flag",
      "required": false,
      "description": "Whether to use event index or metric index"
    }
  ]
}
