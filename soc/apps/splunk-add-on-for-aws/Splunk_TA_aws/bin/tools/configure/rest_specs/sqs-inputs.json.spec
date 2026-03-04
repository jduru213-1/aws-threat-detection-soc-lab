{
  "name": "sqs",
  "endpoint": "splunk_ta_aws_splunk_ta_aws_sqs",
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
      "name": "aws_region",
      "required": false,
      "description": "List of AWS regions containing sqs queues"
    },
    {
      "name": "sqs_queues",
      "required": true,
      "description": "AWS sqs queue names list, split by ‘,’"
    },
    {
      "name": "interval",
      "required": true,
      "description": "Data collection interval"
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
