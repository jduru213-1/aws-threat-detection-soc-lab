#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Custom REST Endpoint for enumerating AWS SQS queue names.
"""


import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import splunk
import splunk.admin
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
from aws_sqs_queue_urls_rh import SQSQueueURLsHandler


class SQSQueueNamesHandler(SQSQueueURLsHandler):
    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "edit" action."""
        # Set proxy for boto3
        proxy = pc.get_proxy_info(self.getSessionKey())
        tacommon.set_proxy_env(proxy)
        queue_names = list(
            map(
                lambda queue_url: queue_url.split("/")[-1],
                self._list_queues(),
            )
        )
        for queue in queue_names:
            confInfo[queue].append("sqs_queue", queue)


def main():
    """Main method for SQS queue names RH."""
    splunk.admin.init(SQSQueueNamesHandler, splunk.admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()
