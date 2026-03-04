{
  "name": "account",
  "endpoint": "splunk_ta_aws_aws_account",
  "stanza_fields": [
    {
      "name": "name",
      "required": true,
      "description": "Unique name for AWS account"
    },
    {
      "name": "key_id",
      "required": true,
      "description": "AWS account key id"
    },
    {
      "name": "secret_key",
      "required": true,
      "description": "AWS account secret key"
    },
    {
      "name": "category",
      "required": true,
      "description": "AWS account region category. Specify either 1, 2, or 4 (1 = Global, 2 = US Gov, 4 = China)"
    }
  ]
}
