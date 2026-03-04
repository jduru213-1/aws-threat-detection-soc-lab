##
## SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
## SPDX-License-Identifier: LicenseRef-Splunk-8-2021
##
##
[<name>]
account = AWS account used to connect to AWS
region = AWS region
stream_names = Kinesis stream names in a comma-separated list. Leave empty to collect all streams.
encoding = gzip or empty
format = CloudWatchLogs or empty
init_stream_position = TRIM_HORIZON or LATEST
aws_iam_role = AWS IAM role that to be assumed.
sourcetype = Sourcetype
index = The index you want to put data in.
private_endpoint_enabled = To enable/disable use of private endpoint
kinesis_private_endpoint_url = Private endpoint url to connect with kinesis service
sts_private_endpoint_url = Private endpoint url to connect with sts service
metric_index_flag = Flag to check whether to use metric index or not
