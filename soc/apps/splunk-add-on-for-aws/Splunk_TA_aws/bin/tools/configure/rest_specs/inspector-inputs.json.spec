{
  "name": "inspector",
  "endpoint": "splunk_ta_aws_aws_inspector",
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
      "description": "AWS iam role"
    },
    {
      "name": "regions",
      "required": true,
      "description": "AWS regions that contain the data. Enter region IDs in comma separated list"
    },
    {
      "name": "polling_interval",
      "required": true,
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
