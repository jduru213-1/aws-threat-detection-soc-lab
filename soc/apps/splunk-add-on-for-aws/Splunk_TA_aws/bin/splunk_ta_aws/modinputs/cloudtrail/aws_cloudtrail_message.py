#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS cloudtrail message.
"""


import calendar
import gzip
import io
import json
import re
import threading
import time
import traceback

import boto3
import splunk_ta_aws.common.ta_aws_common as tacommon
from botocore.config import Config
from botocore.exceptions import ClientError
from splunksdc import logging

from . import aws_cloudtrail_common as ctcommon
from .aws_cloudtrail_common import CloudTrailProcessorError

logger = logging.get_module_logger()


def get_processor(message):
    """
    Process message.

    :param message:
    :return:
    :rtype: MessageProcessor
    """

    processors = (CloudTrailMessage, S3Message)
    for processor in processors:
        if processor.validate(message):
            return processor()
    else:  # pylint: disable=useless-else-on-loop
        raise CloudTrailProcessorError(
            "Invalid CloudTrail message. Please check SQS settings."
        )


class S3ConnectionPool:
    """
    S3 connection pool for buckets in different regions.
    """

    _region_conn_pool: dict = {}
    _region_conn_lock = threading.Lock()

    _bucket_region_cache: dict = {}
    _bucket_region_lock = threading.Lock()

    @classmethod
    def get_conn(  # pylint: disable=too-many-arguments
        cls,
        key_id,
        secret_key,
        bucket,
        default_region="us-east-1",
        s3_endpoint_url=None,
    ):
        """Return s3 connection to region where bucket is located."""
        bucket_region = cls.get_bucket_region(
            bucket, key_id, secret_key, default_region, s3_endpoint_url
        )
        if not s3_endpoint_url:
            s3_endpoint_url = tacommon.format_default_endpoint_url("s3", bucket_region)
        with cls._region_conn_lock:
            if bucket_region not in cls._region_conn_pool:
                cls._region_conn_pool[bucket_region] = boto3.client(
                    "s3",
                    aws_access_key_id=key_id,
                    aws_secret_access_key=secret_key,
                    region_name=bucket_region,
                    config=Config(signature_version="s3v4"),
                    endpoint_url=s3_endpoint_url,
                )
        return cls._region_conn_pool[bucket_region]

    @classmethod
    def get_bucket_region(  # pylint: disable=too-many-arguments
        cls,
        bucket,
        key_id,
        secret_key,
        default_region="us-east-1",
        s3_endpoint_url=None,
    ):
        """Returns AWS bucket region."""
        if not s3_endpoint_url:
            s3_endpoint_url = tacommon.format_default_endpoint_url("s3", default_region)
        with cls._bucket_region_lock:
            if bucket not in cls._bucket_region_cache:
                client = boto3.client(
                    "s3",
                    aws_access_key_id=key_id,
                    aws_secret_access_key=secret_key,
                    region_name=default_region,
                    config=Config(signature_version="s3v4"),
                    endpoint_url=s3_endpoint_url,
                )
                bucket_region = client.get_bucket_location(Bucket=bucket).get(
                    "LocationConstraint"
                )

                # ADDON-16435. Some endpoint has different LocationConstraint.
                if not bucket_region:
                    bucket_region = "us-east-1"
                elif bucket_region == "EU":
                    bucket_region = "eu-west-1"

                cls._bucket_region_cache[bucket] = bucket_region
                return bucket_region

        return cls._bucket_region_cache[bucket]


class MessageProcessor(
    object, metaclass=ctcommon.ThreadLocalSingleton
):  # pylint: disable=too-many-instance-attributes
    """Class for message processor."""

    WRITEN = "writen"
    REDIRECTED = "redirected"
    DISCARDED = "discarded"

    def run(  # pylint: disable=too-many-arguments, too-many-locals
        self,
        session_key,
        datainput,
        aws_account,
        message_id,
        message,
        blacklist_pattern,
        excluded_events_index,
        remove_files_when_done,
        sourcetype,
        index,
        default_region="us-east-1",
        s3_endpoint_url=None,
    ):
        """
        Process Message.

        :param session_key:
        :param datainput
        :param aws_account:
        :param message_id:
        :param message:
        :param blacklist_pattern:
        :param excluded_events_index:
        :param remove_files_when_done:
        :return:
        """
        self._setup(
            session_key,
            datainput,
            aws_account,
            message_id,
            message,
            blacklist_pattern,
            excluded_events_index,
            remove_files_when_done,
            sourcetype,
            index,
        )
        for bucket_name, key_name in self._s3_keys():
            logger.debug(
                "Retrieve from S3 Started",
                datainput=self.datainput,
                message_id=self.message_id,
                s3_bucket_name=bucket_name,
                s3_key_name=key_name,
            )
            try:
                res = self._process_s3_key(
                    bucket_name, key_name, default_region, s3_endpoint_url
                )
            except Exception:  # pylint: disable=broad-except
                logger.error(
                    "Retrieve from S3 Failed",
                    datainput=self.datainput,
                    s3_bucket_name=bucket_name,
                    s3_key_name=key_name,
                    error=traceback.format_exc(),
                )
                continue
            logger.debug(
                "Retrieve from S3 Finished",
                datainput=self.datainput,
                message_id=self.message_id,
                s3_bucket_name=bucket_name,
                s3_key_name=key_name,
                **res
            )
        self._teardown()

    @staticmethod
    def get_s3_key_record_time(record):
        """Returns S3 record time."""
        time_str = record["eventTime"].replace("Z", "GMT")
        time_obj = time.strptime(time_str, "%Y-%m-%dT%H:%M:%S%Z")
        return int(calendar.timegm(time_obj))

    def _load_s3_key(
        self, bucket_name, key_name, default_region="us-east-1", s3_endpoint_url=None
    ):
        s3_key_cont = {}
        s3_conn = s3_key = None

        try:
            s3_conn = S3ConnectionPool.get_conn(
                self.aws_account["key_id"],
                self.aws_account["secret_key"],
                bucket_name,
                default_region,
                s3_endpoint_url,
            )
            s3_key = s3_conn.get_object(Bucket=bucket_name, Key=key_name)
        except ClientError as ex:
            logger.error(
                "Get S3 Key Failed",
                datainput=self.datainput,
                message_id=self.message_id,
                s3_bucket_name=bucket_name,
                s3_key_name=key_name,
                exc=str(ex.response["Error"]),
            )

        # Load S3 key
        if s3_key and "Body" in s3_key:
            with io.BytesIO(s3_key["Body"].read()) as bio:
                with gzip.GzipFile(fileobj=bio) as gz_file:
                    s3_key_cont = json.loads(gz_file.read())

        # Remove S3 key if required
        if self.remove_files_when_done:
            logger.debug(
                "Remove S3 Key",
                datainput=self.datainput,
                message_id=self.message_id,
                s3_bucket_name=bucket_name,
                s3_key_name=key_name,
            )
            try:
                s3_conn.delete_object(Bucket=bucket_name, Key=key_name)
            except ClientError as ex:
                logger.error(
                    "Remove S3 Key Failed",
                    datainput=self.datainput,
                    message_id=self.message_id,
                    s3_bucket_name=bucket_name,
                    s3_key_name=key_name,
                    exc=str(ex.response["Error"]),
                )
        return s3_key_cont

    def _process_s3_key(
        self, bucket_name, key_name, default_region="us-east-1", s3_endpoint_url=None
    ):
        logger.debug(
            "Start getting S3 key",
            datainput=self.datainput,
            s3_bucket_name=bucket_name,
            s3_key_name=key_name,
        )

        s3_key_cont = self._load_s3_key(
            bucket_name, key_name, default_region, s3_endpoint_url
        )
        stats = {
            MessageProcessor.WRITEN: 0,
            MessageProcessor.REDIRECTED: 0,
            MessageProcessor.DISCARDED: 0,
        }

        logger.debug(
            "End of getting S3 key",
            datainput=self.datainput,
            s3_bucket_name=bucket_name,
            s3_key_name=key_name,
        )

        events = []
        for rec in s3_key_cont.get("Records", []):
            res = self._process_s3_key_record(bucket_name, key_name, rec, events)
            stats[res] += 1

        logger.debug(
            "End of processing records",
            datainput=self.datainput,
            s3_bucket_name=bucket_name,
            s3_key_name=key_name,
        )

        ctcommon.event_writer.write_events(events)
        ctcommon.orphan_check()

        logger.debug(
            "End of writting events",
            datainput=self.datainput,
            s3_bucket_name=bucket_name,
            s3_key_name=key_name,
        )
        return stats

    def _process_s3_key_record(self, bucket_name, key_name, record, events):
        if not self.blacklist_pattern or not self.blacklist_pattern.search(
            record["eventName"]
        ):
            rec = ctcommon.event_writer.create_event(
                json.dumps(record),
                index=self.index,
                source="s3://{}/{}".format(  # pylint: disable=consider-using-f-string
                    bucket_name, key_name
                ),
                sourcetype=self.sourcetype,
            )
            events.append(rec)
            return MessageProcessor.WRITEN
        elif self.excluded_events_index:
            rec = ctcommon.event_writer.create_event(
                json.dumps(record),
                index=self.excluded_events_index,
                source="s3://{}/{}".format(  # pylint: disable=consider-using-f-string
                    bucket_name, key_name
                ),
                sourcetype=self.sourcetype,
            )
            events.append(rec)
            return MessageProcessor.REDIRECTED
        else:
            logger.info(
                "Blacklisted Event",
                datainput=self.datainput,
                message_id=self.message_id,
                bucket_name=bucket_name,
                key_name=key_name,
                event_name=record["eventName"],
                event_time=record["eventTime"],
            )
            return MessageProcessor.DISCARDED

    def _setup(  # pylint: disable=too-many-arguments
        self,
        session_key,
        datainput,
        aws_account,
        message_id,
        message,
        blacklist_pattern,
        excluded_events_index,
        remove_files_when_done,
        sourcetype,
        index,
    ):
        self.session_key = session_key  # pylint: disable=attribute-defined-outside-init
        self.datainput = datainput  # pylint: disable=attribute-defined-outside-init
        self.aws_account = aws_account  # pylint: disable=attribute-defined-outside-init
        self.message_id = message_id  # pylint: disable=attribute-defined-outside-init
        self.message = message  # pylint: disable=attribute-defined-outside-init
        if blacklist_pattern:
            blacklist_pattern = re.compile(blacklist_pattern)
        self.blacklist_pattern = (  # pylint: disable=attribute-defined-outside-init
            blacklist_pattern
        )
        self.excluded_events_index = (  # pylint: disable=attribute-defined-outside-init
            excluded_events_index
        )
        self.remove_files_when_done = (  # pylint: disable=attribute-defined-outside-init
            remove_files_when_done
        )
        self.sourcetype = sourcetype  # pylint: disable=attribute-defined-outside-init
        self.index = index  # pylint: disable=attribute-defined-outside-init

    def _teardown(self):
        self.session_key = None  # pylint: disable=attribute-defined-outside-init
        self.datainput = None  # pylint: disable=attribute-defined-outside-init
        self.aws_account = None  # pylint: disable=attribute-defined-outside-init
        self.message_id = None  # pylint: disable=attribute-defined-outside-init
        self.message = None  # pylint: disable=attribute-defined-outside-init
        self.blacklist_pattern = None  # pylint: disable=attribute-defined-outside-init
        self.excluded_events_index = (  # pylint: disable=attribute-defined-outside-init
            None
        )
        self.remove_files_when_done = (  # pylint: disable=attribute-defined-outside-init
            None
        )

    @staticmethod
    def validate(message):
        """
        Determine if given message conforms to this message type.

        :param message:
        :return:
        :rtype: bool
        """
        raise NotImplementedError()

    @staticmethod
    def description():
        """
        Description for this message type.

        :return:
        :rtype: basestring
        """
        raise NotImplementedError()

    def _s3_keys(self):
        """
        Get S3 Bucket and Key Names.

        :return: [(bucket_name, key_name), ...]
        :rtype: list
        """
        raise NotImplementedError()


class CloudTrailMessage(MessageProcessor):
    """
    CloudTrail Message.
    """

    REQUIRED_FIELDS = ("s3Bucket", "s3ObjectKey")

    @staticmethod
    def validate(message):
        """
        It has these keys: "s3Bucket", "s3ObjectKey".

        :param message:
        :return:
        """
        return all(
            f in message for f in CloudTrailMessage.REQUIRED_FIELDS
        ) and isinstance(
            message.get("s3ObjectKey"), (list,)
        )  # validates s3ObjectKey is list

    @staticmethod
    def description():
        return "CloudTrail Message"

    def _s3_keys(self):
        bucket_name = self.message["s3Bucket"]
        for key_name in self.message.get("s3ObjectKey", []):
            yield bucket_name, key_name


class S3Message(MessageProcessor):
    """
    S3 Message.
    """

    RECORD_FIELDS = ("s3", "eventName")

    @staticmethod
    def validate(message):
        """
        1. It has key "Records".
        2. The value of "Records" is a non-empty list.
        3. Elements of the list have key "s3" and "eventName".

        :param message:
        :return:
        """
        try:
            rec = message["Records"][0]
            return all(f in rec for f in S3Message.RECORD_FIELDS)
        except Exception:  # pylint: disable=broad-except
            return False

    @staticmethod
    def description():
        return "CloudTrail Message from S3 Bucket"

    def _s3_keys(self):
        for rec in self.message["Records"]:
            try:
                bucket_name = rec["s3"]["bucket"]["name"]
                key_name = rec["s3"]["object"]["key"]
            except KeyError:
                logger.info(
                    "Invalid S3 notification record",
                    datainput=self.datainput,
                    message_id=self.message_id,
                )
                continue
            yield bucket_name, key_name
