{
    "name": "config",
    "endpoint": "splunk_ta_aws_aws_config",
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
            "description": "AWS regions to collect data from"
        },
        {
            "name": "sqs_queue",
            "required": true,
            "description": "Sqs queue names where AWS sends Config notifications"
        },
        {
            "name": "polling_interval",
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
            "name": "enable_additional_notifications",
            "required": false,
            "description": "Deprecated"
        }
    ]
}
