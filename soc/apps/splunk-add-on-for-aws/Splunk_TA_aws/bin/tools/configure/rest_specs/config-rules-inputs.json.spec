{
    "name": "config-rules",
    "endpoint": "splunk_ta_aws_aws_config_rule",
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
            "name": "aws_iam_role",
            "required": false,
            "description": "AWS IAM role"
        },
        {
            "name": "region",
            "required": true,
            "description": "JSON array specifying list of regions"
        },
        {
            "name": "rule_names",
            "required": false,
            "description": "JSON array specifying rule names. Leave blank to select all rules"
        },
        {
            "name": "polling_interval",
            "required": true,
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
