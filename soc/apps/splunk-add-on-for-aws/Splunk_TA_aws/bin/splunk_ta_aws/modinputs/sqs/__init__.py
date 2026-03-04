#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
AWS SQS Modular Input
"""


from splunksdc.collector import SimpleCollectorV1

from .aws_sqs_data_loader import Input


def main():
    """Main method for SQS input module."""
    SimpleCollectorV1.main(
        Input(),
        description="Collect and index AWS SQS messages",
        arguments={"placeholder": {}},
    )
