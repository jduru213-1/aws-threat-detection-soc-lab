{
  "name": "cloudtrail-lake",
  "endpoint": "splunk_ta_aws_aws_cloudtrail_lake",
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
      "description": "AWS IAM Role"
    },
    {
      "name": "aws_region",
      "required": true,
      "description": "AWS region to collect data from"
    },
    {
      "name": "input_mode",
      "required": true,
      "description": "Input mode whether to collect data continuously or at once."
    },
    {
      "name": "event_data_store",
      "required": true,
      "description": "The cloudtrail lake event data store from which the data will be collected."
    },
    {
      "name": "start_date_time",
      "required": true,
      "description": "Start Date Time"
    },
    {
      "name": "end_date_time",
      "required": false,
      "description": "End Date Time"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
    },
    {
      "name": "cloudtrail_private_endpoint_url",
      "required": false,
      "description": "CPrivate endpoint url to connect with cloudtrail service"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with sts service"
    },
    {
      "name": "query_window_size",
      "required": true,
      "description": "This parameter is used to control the chunk size."
    },
    {
      "name": "delay_throttle",
      "required": false,
      "description": "This parameter specifies how close to \"now\" the end date for a query may be (where \"now\" is the time that the input runs)."
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
