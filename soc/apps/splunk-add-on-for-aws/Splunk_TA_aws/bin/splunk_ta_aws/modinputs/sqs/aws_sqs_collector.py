#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
AWS SQS Queue Message Collecting.
"""


import json
import traceback
from datetime import timedelta

from splunk_ta_aws.common.ta_aws_common import is_http_ok


def get_sqs_queue_url(credentials, queue_name, region):
    """
    Get SQS queue url for given SQS client and queue name.

    :param credentials:
    :param queue_name:
    :param region
    :return:
    """
    client = credentials.client("sqs", region)
    return client.get_queue_url(QueueName=queue_name).get("QueueUrl")


def check_sqs_response(content):
    """
    Check if it is successful while acting on SQS queue.
    :param content: acting response
    :return:
    """
    if not is_http_ok(content):
        err = json.dumps(content.get("Failed") or content)
        raise SQSCollectorException(err)


class SQSCollectorException(Exception):
    """
    Exception for SQS handler.
    """

    pass  # pylint: disable=unnecessary-pass


class SQSCollector:
    """Class for SQS Collector."""

    _MIN_TTL = timedelta(seconds=600)

    def __init__(  # pylint: disable=too-many-arguments
        self, queue_url, region, credentials, logger, handler, *args, **kwargs
    ):
        """
        :param queue_url:
        :param credentials:
        :param logger:
        :param handler: handler to process message from SQS queue.
            It should be in form:
                def handler(messages, *args, **kwargs): ...
        :param args: args for handler
        :param kwargs: kwargs for handler
        """
        self._credentials = credentials
        self._queue_url = queue_url
        self._region = region
        self._logger = logger

        assert callable(handler), '"handler" must be callable'
        self._handler = handler
        self._handler_args = args
        self._handler_kwargs = kwargs

    def run(self, abort_event):
        """
        Run collecting.

        :param abort_event: threading.Event to check for abort signal
        :return:
        """
        return self._collect(abort_event)

    def receive_messages(self):
        """Returns messages."""
        client = self._credentials.client("sqs", self._region)
        resp = client.receive_message(
            QueueUrl=self._queue_url,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
            MaxNumberOfMessages=10,
            WaitTimeSeconds=15,
        )
        check_sqs_response(resp)
        return resp.get("Messages")

    def delete_messages(self, messages):
        """Deletes messages."""
        client = self._credentials.client("sqs", self._region)
        ents = [
            {"Id": msg["MessageId"], "ReceiptHandle": msg["ReceiptHandle"]}
            for msg in messages
        ]
        resp = client.delete_message_batch(
            QueueUrl=self._queue_url,
            Entries=ents,
        )
        check_sqs_response(resp)

    def _collect(self, abort_event):
        msg_count = 0
        try:
            while not abort_event.is_set():
                if self._credentials.need_retire(self._MIN_TTL):
                    self._credentials.refresh()
                msgs = self.receive_messages()
                # If it is None, queue is empty
                if msgs is None:
                    break

                msg_count += len(msgs)
                self._handler(msgs, *self._handler_args, **self._handler_kwargs)
                self.delete_messages(msgs)
            self._logger.info("Pulled %d messages from SQS", msg_count)
        except Exception as exc:  # noqa: F841 # pylint: disable=unused-variable, broad-except
            self._logger.error(
                "Ingest SQS Failed",
                queue_url=self._queue_url,
                error=traceback.format_exc(),
            )
            return False
        else:
            return True
