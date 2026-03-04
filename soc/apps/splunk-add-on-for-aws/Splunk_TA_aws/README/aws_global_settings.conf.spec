##
## SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
## SPDX-License-Identifier: LicenseRef-Splunk-8-2021
##
##
[aws_connection]
is_secure = Does boto use secure connection
verify_certificates =

[aws_inputs_settings]
cloudwatch_dimensions_max_threads = Specify the count to determine the number of thread workers that will operate concurrently to retrieve data for CloudWatch input dimensions.
sqs_max_threads = Specify the count to determine the number of thread workers that will operate concurrently to retrieve data for SQS input.
