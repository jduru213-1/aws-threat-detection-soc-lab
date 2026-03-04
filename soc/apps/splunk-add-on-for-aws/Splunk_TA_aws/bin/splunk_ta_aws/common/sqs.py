#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS SQS queues.
"""
import json
import re
import time

from splunksdc import log as logging

from .sns_signature_validation import sqs_validate

logger = logging.get_module_logger()

_MAX_WAIT_TIME_SECONDS = 20


class SQSMessage:

    """Class for SQS queue."""

    def __init__(self, message, validator=False):
        self._message = message
        self._attributes = message["Attributes"]
        self._validator = validator
        # is validator is true use the built in validator
        # if validator is a function then use the function
        # if validator is false don't validate
        if validator is True:
            self._validator = sqs_validate

    def is_valid(self):
        """Validates signature, throws exception if fails"""
        return self._validator(json.loads(self.body), self.message_id)

    @property
    def message_id(self):
        """Returns messsage id."""
        return self._message["MessageId"]

    @property
    def receipt_handle(self):
        """Returns receipt handle."""
        return self._message["ReceiptHandle"]

    @property
    def md5_of_body(self):
        """Returns MD5 of body."""
        return self._message["MD5OfBody"]

    @property
    def body(self):
        """Returns body."""
        return self._message["Body"]

    @property
    def first_receive_timestamp(self):
        """Returns first receive timestamp."""
        return int(self._attributes["ApproximateFirstReceiveTimestamp"])

    @property
    def receive_count(self):
        """Returns receive count."""
        return int(self._attributes["ApproximateReceiveCount"])

    @property
    def sender_id(self):
        """Returns sender id."""
        return self._attributes["SenderId"]

    @property
    def sent_timestamp(self):
        """Returns sent timestamp."""
        return int(self._attributes["SentTimestamp"])


class QueueAttributes:
    """Class for queue attributes."""

    def __init__(self, attributes):
        self._attributes = attributes

    def _get(self, name):
        return self._attributes.get(name)

    @property
    def visibility_timeout(self):
        """Returns visibility timeout."""
        return int(self._get("VisibilityTimeout"))

    @property
    def redrive_policy(self):
        """Returns redrive policy."""
        return self._get("RedrivePolicy")


def query_url_by_name(client, name):
    """Returns queue URL."""
    params = {
        "QueueName": name,
    }
    logger.debug("SQSGetQueueURL", **params)
    response = client.get_queue_url(**params)
    return response.get("QueueUrl")


class SQSQueue:
    """Class for SQS queue."""

    _PATTERN = re.compile(r"//sqs\.(?P<region>[-\w]+)\.amazonaws\.")

    @classmethod
    def _extract_region(cls, url, default):
        match = cls._PATTERN.search(url)
        if not match:
            return default
        return match.group("region")

    def __init__(self, url, region, endpoint_url=None, validator=False):
        """
        :param url: The URL of queue
        """
        self._url = url
        self._region = self._extract_region(url, region)
        self._endpoint_url = endpoint_url
        self._validator = validator

    def get_messages(self, client, batch_size):
        """
        :param client: sqs service client
        :param batch_size: The max number of messages would be received in one request
        :return: collection of SQSMessage
        """
        url = self._url
        params = {
            "QueueUrl": url,
            "MaxNumberOfMessages": batch_size,
            "WaitTimeSeconds": _MAX_WAIT_TIME_SECONDS,
            "AttributeNames": ["All"],
        }
        logger.debug("Get SQS messages", **params)
        response = client.receive_message(**params)
        messages = response.get("Messages", [])
        if messages:
            logger.debug("Messages received.", count=len(messages))
            return [
                SQSMessage(message, validator=self._validator) for message in messages
            ]
        logger.debug("No message available.")
        return []

    def visibility_heart_beat(self, client, message_state, timeout=500):
        """
        Keeps a message visiblity hidden by pulling the message frequently
        and reseting visiblity

        :param client: sqs service client
        :param message_state: is either a receipt_handle or the message_state returned
        """
        last_time = time.time() - timeout  # if first time then set timeout
        expires = time.time()

        if isinstance(message_state, str):  # first time only has the receipt_handle
            receipt_handle = message_state
        if isinstance(
            message_state, dict
        ):  # subsequent call use the message_state dict
            receipt_handle = message_state["receipt_handle"]
            last_time = message_state["last_time"]
            expires = message_state["expires"]

        if last_time < time.time() - (timeout / 2):
            url = self._url
            params = {
                "QueueUrl": url,
                "ReceiptHandle": receipt_handle,
                "VisibilityTimeout": timeout,
            }
            client.change_message_visibility(**params)
            last_time = time.time()
            expires = last_time + timeout

        return {
            "last_time": last_time,
            "receipt_handle": receipt_handle,
            "expires": expires,
        }

    def delete_message(self, client, message):
        """
        :param client: sqs service client
        :param message: an instance of SQSMessage
        """
        url = self._url
        params = {
            "QueueUrl": url,
            "ReceiptHandle": message.receipt_handle,
        }
        logger.debug("Delete SQS message", **params)
        client.delete_message(**params)

    def get_attributes(self, client):
        """Returns queue attributes."""
        url = self._url
        params = {"QueueUrl": url, "AttributeNames": ["All"]}
        response = client.get_queue_attributes(**params)
        return QueueAttributes(response["Attributes"])

    def client(self, credentials, session=None):
        """Returns client."""
        return credentials.client("sqs", self._region, session, self._endpoint_url)
