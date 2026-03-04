#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
# pylint: disable=invalid-name
"""
File for AWS cloudwatch logs constants.
"""
cloudwatch_logs_log = "main"
cloudwatch_logs_log_ns = "splunk_ta_aws_cloudwatch_logs"

only_after = "only_after"
delay = "delay"
groups = "groups"
stream_matcher = "stream_matcher"
log_group_name = "log_group_name"
lock = "lock"
query_window_size = "query_window_size"

INGESTION_BATCH_SIZE = 1000
DEAFULT_QUERY_WINDOW_SIZE = 10
