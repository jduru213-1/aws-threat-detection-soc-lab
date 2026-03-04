{
    "name": "metadata",
    "endpoint": "splunk_ta_aws_aws_metadata",
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
            "description": "AWS IAM Role"
        },
        {
            "name": "regions",
            "required": true,
            "description": "AWS regions to get data from, splitted by ','"
        },
        {
            "name": "apis",
            "required": false,
            "description": "APIs to collect data with, and intervals for each api, in the format of <api name>/<api interval in seconds> Ex, apis = ec2_instances/3600, kinesis_stream/3600"
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
