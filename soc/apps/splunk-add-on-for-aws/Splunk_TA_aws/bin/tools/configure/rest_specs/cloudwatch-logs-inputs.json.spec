{
  "name": "cloudwatch-logs",
  "endpoint": "splunk_ta_aws_aws_cloudwatch_logs",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for input"
    },
    {
      "name": "account",
      "required": true,
      "description": "AWS account name"
    },
    {
      "name": "region",
      "required": true,
      "description": "AWS region to collect data from"
    },
    {
      "name": "groups",
      "required": true,
      "description": "Log group names to get data from, split by comma (,)"
    },
    {
      "name": "delay",
      "required": false,
      "description": "The input will query the CloudWatch Logs events no later than <delay> seconds before now"
    },
    {
      "name": "only_after",
      "required": false,
      "description": "Only events after the specified GMT time will be collected. Format = %Y-%m-%dT%H:%M:%S"
    },
    {
      "name": "stream_matcher",
      "required": false,
      "description": "Regex to match log stream names for ingesting events"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
    },
    {
      "name": "logs_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with logs service"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with STS service"
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
    },
    {
      "name": "query_window_size",
      "required": true,
      "description": "Specify the interval of data to be collected in each request(in minutes). Min=1 & Max=43200(30days)"
    },
    {
      "name": "metric_index_flag",
      "required": false,
      "description": "Whether to use event index or metric index"
    }
  ]
}
