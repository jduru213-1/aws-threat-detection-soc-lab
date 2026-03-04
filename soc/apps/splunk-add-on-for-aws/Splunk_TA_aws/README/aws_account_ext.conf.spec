##
## SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
## SPDX-License-Identifier: LicenseRef-Splunk-8-2021
##
##
[<name>]
category = An integer value that represents one of the following AWS account region category codes: 1 (Global), 2 (Government), 4 (China).
iam = A boolean value (0 or 1) that indicates whether the AWS account is an AWS IAM role for EC2 instance. For information about IAM role for EC2 instance, refer to https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html.
private_endpoint_enabled = status of private endpoint
sts_private_endpoint_url = private private endpoint url to use while connecting to sts service for account validation
sts_region = AWS region to use regional endpoint of sts service for account validation
