#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS search alert.
"""
import json
import sys
import traceback

import splunksdc.log as logging
from splunktalib.common import util

from splunk_ta_aws.modalerts.sns.aws_sns_publisher import (  # isort: skip
    SNSMessageContent,
    SNSPublisher,
)
from splunklib.searchcommands import (  # isort: skip
    Configuration,
    Option,
    StreamingCommand,
    dispatch,
)

logger = logging.get_module_logger()
logger.setLevel(logging.INFO)

util.remove_http_proxy_env_vars()


@Configuration()
class AwsSnsAlertCommand(StreamingCommand, SNSPublisher):
    """Class for AWS SNS alert command."""

    account = Option(require=True)
    region = Option(require=True)
    topic_name = Option(require=True)
    publish_all = Option(require=False)

    def stream(self, records):
        """Method for streaming alerts."""
        logger.info("Search Alert - Started")
        splunkd_uri = self.search_results_info.splunkd_uri  # pylint: disable=no-member
        session_key = self.search_results_info.auth_token  # pylint: disable=no-member
        publish_all = util.is_true(self.publish_all or "false")

        err = 0
        count = 0
        for i, rec in enumerate(records):
            try:
                count += 1
                yield self._handle_record(splunkd_uri, session_key, rec, i)
            except Exception as exc:  # pylint: disable=broad-except
                err += 1
                yield self._handle_error(exc, traceback.format_exc(), rec, i)
            if not publish_all:
                break

        if err:
            self.write_warning(
                "%s in %s events failed. "  # pylint: disable=consider-using-f-string
                "Check response events for detail" % (err, count)
            )

    def _handle_record(self, splunkd_uri, session_key, record, serial):
        resp = self.publish(
            splunkd_uri,
            session_key,
            self.account,
            self.region,
            self.topic_name,
            record=record,
        )

        result = {"result": "Success", "response": json.dumps(resp)}
        res = AwsSnsAlertCommand.make_event(**result)
        logger.debug("Search Alert", **result)
        return {"_serial": serial, "_time": record.get("_time"), "_raw": res}

    def _handle_error(self, exc, tb, record, serial):  # pylint: disable=invalid-name
        logger.error("Search Alert", result="Failed", error=tb)
        res = AwsSnsAlertCommand.make_event("Failed", error=exc)
        return {"_serial": serial, "_time": record.get("_time"), "_raw": res}

    @staticmethod
    def make_event(result, **kwargs):
        """Makes event."""
        event = 'Search Alert - result="{result}"'.format(  # pylint: disable=consider-using-f-string
            result=result
        )
        arr = [
            '%s="%s"' % (key, val)  # pylint: disable=consider-using-f-string
            for key, val in kwargs.items()
        ]
        arr.insert(0, event)
        return ", ".join(arr)

    def make_subject(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Makes SNS subject."""
        return "Splunk - Alert from Search"

    def make_message(self, *args, **kwargs):  # pylint: disable=unused-argument
        """Makes SNS message."""
        record = kwargs["record"]
        return SNSMessageContent(
            message=record.get("message", ""),
            timestamp=record.get("timestamp", record.get("_time")),
            entity=record.get("entity", ""),
            correlation_id=record.get(
                "record", self.search_results_info.sid  # pylint: disable=no-member
            ),
            source=record.get("source", ""),
            event=record.get("event", record.get("_raw")),
            search_name="",
            results_link="",
            app=self.search_results_info.ppc_app,  # pylint: disable=no-member
            owner=self.search_results_info.ppc_user,  # pylint: disable=no-member
        )


def main():
    """Main method for aws sns alert module"""
    factory = logging.StreamHandlerFactory()
    formatter = logging.ContextualLogFormatter(True)
    logging.RootHandler.setup(factory, formatter)
    dispatch(AwsSnsAlertCommand, sys.argv, sys.stdin, sys.stdout)
