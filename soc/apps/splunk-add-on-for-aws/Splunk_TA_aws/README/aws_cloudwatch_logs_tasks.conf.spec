##
## SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
## SPDX-License-Identifier: LicenseRef-Splunk-8-2021
##
##
[<name>]
account = AWS account used to connect to AWS
aws_iam_role = AWS IAM role that to be assumed in the input.
region = AWS region of CloudWatch Logs
groups = Log group names to get data from, splitted by ','
delay = Number of seconds, recommended to be 1800. Each time the modular input will query the CloudWatch Logs events no later than <delay> seconds before now. This is to assure your log events have already been ingested by CloudWatch Logs when the modular input queries them.
interval = Number of seconds, recommended to be 600. The modular input will make a query once per interval.
only_after = GMT time string in '%Y-%m-%dT%H:%M:%S' format. If set, only events after <only_after> will be queried and indexed.
stream_matcher = REGEX to strictly match stream names. Default to .*
sourcetype = The sourcetype you want.
index = The index you want to put data in.
private_endpoint_enabled = To enable/disable use of private endpoint
logs_private_endpoint_url = Private endpoint url to connect with Cloudwatch logs service
sts_private_endpoint_url = Private endpoint url to connect with sts service
metric_index_flag = Flag to check whether to use metric index or not
query_window_size = Specify the interval of data to be collected in each request(in minutes). Min=1 & Max=43200(30days)
