#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS S3.
"""


def list_cloudwatch_namespaces(
    region, key_id, secret_key, session_key=None
):  # pylint: disable=unused-argument
    """Returns list of cloudwatch namespaces"""
    return [
        "AWS/AutoScaling",
        "AWS/Billing",
        "AWS/CloudFront",
        "AWS/CloudSearch",
        "AWS/DynamoDB",
        "AWS/Events",
        "AWS/ECS",
        "AWS/ElastiCache",
        "AWS/EBS",
        "AWS/EC2",
        "AWS/EC2Spot",
        "AWS/ELB",
        "AWS/ApplicationELB",
        "AWS/ElasticMapReduce",
        "AWS/ES",
        "AWS/Kinesis",
        "AWS/Lambda",
        "AWS/Logs",
        "AWS/ML",
        "AWS/OpsWorks",
        "AWS/Redshift",
        "AWS/RDS",
        "AWS/Route53",
        "AWS/SNS",
        "AWS/SQS",
        "AWS/S3",
        "AWS/SWF",
        "AWS/StorageGateway",
        "AWS/WAF",
        "AWS/WorkSpaces",
    ]
