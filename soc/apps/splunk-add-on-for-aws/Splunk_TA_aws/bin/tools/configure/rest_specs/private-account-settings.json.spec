{
  "name": "private-account",
  "endpoint": "splunk_ta_aws_aws_private_account",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for AWS private account"
    },
    {
      "name": "key_id",
      "required": true,
      "description": "AWS private account key id"
    },
    {
      "name": "secret_key",
      "required": true,
      "description": "AWS private account secret key"
    },
    {
      "name": "category",
      "required": true,
      "description": "AWS private account region category. Specify either 1, 2, or 4 (1 = Global, 2 = US Gov, 4 = China)"
    },
    {
      "name": "sts_region",
      "required": true,
      "description": "AWS region to be used for api calls of STS service"
    },
    {
      "name": "private_endpoint_enabled",
      "required": false,
      "description": "Whether to use user provided AWS private endpoints for making api calls to AWS services. Specify either 0 or 1"
    },
    {
      "name": "sts_private_endpoint_url",
      "required": false,
      "description": "Required if private_endpoint_enabled=1. AWS private endpoint url"
    }
  ]
}
