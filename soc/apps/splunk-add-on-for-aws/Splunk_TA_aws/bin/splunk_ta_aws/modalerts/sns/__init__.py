"""
Sends alerting messages to AWS SNS topic.
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import json
import time

# This import is required to using k-v logging
import splunksdc.log as logging
from splunk_ta_aws.common.ta_aws_consts import splunk_ta_aws
from splunktalib.common import util

from .aws_alert import (  # isort: skip
    ModularAlert,
    parse,
)
from .aws_sns_publisher import (  # isort: skip
    SNSMessageContent,
    SNSPublisher,
)

logger = logging.get_module_logger()


class AwsSnsModularAlert(ModularAlert, SNSPublisher):
    """Class for AWS SNS modular alert."""

    def _execute(self):
        session_key = self.payload(ModularAlert.SESSION_KEY)
        resp = self.publish(
            self.payload(ModularAlert.SERVER_URI),
            session_key,
            self.param("account"),
            self.param("region"),
            self.param("topic_name"),
        )
        self.log(
            "Finished: response=%s"  # pylint: disable=consider-using-f-string
            % json.dumps(resp)
        )

    def make_subject(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Makes SNS alert subject."""
        return (
            "Splunk - Alert from %s"  # pylint: disable=consider-using-f-string
            % self.payload(ModularAlert.SERVER_HOST)
        )

    def make_message(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Makes SNS message content."""
        return SNSMessageContent(
            message=self.param("message", ""),
            timestamp=self.param("timestamp", self.result("_time", time.time())),
            entity=self.param("entity", ""),
            correlation_id=self.param("correlation_id", self.payload(ModularAlert.SID)),
            source=self.param("source", ""),
            event=self.param("event", ""),
            search_name=self.payload(ModularAlert.SEARCH_NAME),
            results_link=self.payload(ModularAlert.RESULTS_LINK),
            app=self.payload(ModularAlert.APP),
            owner=self.payload(ModularAlert.OWNER),
        )


def main():
    """Main method for sns init file."""
    util.remove_http_proxy_env_vars()
    logger.setLevel(logging.INFO)
    logging.setup_root_logger(app_name=splunk_ta_aws, modular_name="sns_alert_modular")
    AwsSnsModularAlert(logger, parse()).run()
