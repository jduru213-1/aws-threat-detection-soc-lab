{
  "name": "cloudwatch",
  "endpoint": "splunk_ta_aws_aws_cloudwatch",
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
      "name": "metric_namespace",
      "required": false,
      "description": "Cloudwatch metric namespace, for example AWS/EBS"
    },
    {
      "name": "metric_names",
      "required": false,
      "description": "Cloudwatch metric names in JSON array"
    },
    {
      "name": "metric_dimensions",
      "required": false,
      "description": "Cloudwatch Metric Dimensions"
    },
    {
      "name": "statistics",
      "required": false,
      "description": "Cloudwatch metric statistics, Specify either of Average, Sum, SampleCount, Maximum, Minimum"
    },
    {
      "name": "period",
      "required": false,
      "description": "Cloudwatch metrics granularity, in seconds"
    },
    {
      "name": "use_metric_format",
      "required": false,
      "description": "Boolean indicating whether to transform data to metric format"
    },
    {
      "name": "metric_expiration",
      "required": false,
      "description": "How long the discovered metrics would be cached for, in seconds"
    },
    {
      "name": "query_window_size",
      "required": false,
      "description": "How far back to retrieve data points for, in number of data points"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use private endpoint. Specify either 0 or 1"
    },
    {
      "name": "monitoring_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with monitoring service"
    },
    {
      "name": "s3_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with S3 service"
    },
    {
      "name": "ec2_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with EC2 service"
    },
    {
      "name": "elb_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with ELB service"
    },
    {
      "name": "lambda_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with Lambda service"
    },
    {
      "name": "autoscaling_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with Autocalling service"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Private endpoint url to connect with STS service"
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
      "name": "polling_interval",
      "required": false,
      "description": "Data collection interval, in seconds"
    }
  ]
}
