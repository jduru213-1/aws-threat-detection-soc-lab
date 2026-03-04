#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for SQS based S3 input handler.
"""


import io
import json
import base64
import os.path
import shutil
import tempfile
import threading
import time
import uuid
import traceback
from collections import OrderedDict
from datetime import timedelta
from contextlib import contextmanager

import boto3.session
import botocore.exceptions
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as taconsts
import splunksdc.utils as utils
from urllib import parse as urlparse
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.decoder import DecoderFactory
from splunk_ta_aws.common.proxy import ProxySettings
from splunk_ta_aws.common.s3 import S3Bucket

from splunk_ta_aws.common.sqs import (  # isort: skip # pylint: disable=no-name-in-module, syntax-error
    SQSQueue,
)
from splunk_ta_aws.common import boto3_proxy_patch
from splunksdc import logging  # isort: skip
from splunksdc.batch import BatchExecutor, BatchExecutorExit  # isort: skip
from splunksdc.utils import LogExceptions, LogWith  # isort: skip

from splunk_ta_aws.common.credentials import (  # isort: skip # pylint: disable=ungrouped-imports
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)
from splunksdc.config import (  # isort: skip # pylint: disable=ungrouped-imports
    IntegerField,
    LogLevelField,
    StanzaParser,
    StringField,
    BooleanField,
)

logger = logging.get_module_logger()


class InsufficientMessageDetailsError(Exception):
    """
    Insufficient message details to start processing.
    It should be skipped for future processing.
    """

    pass  # pylint: disable=unnecessary-pass


class Job:
    """Class for Job."""

    def __init__(self, message, created, ttl):
        self._message = message
        self._created = created
        self._expires = ttl + time.time()
        self._job_id = uuid.uuid4()

    @property
    def message(self):
        """Returns message."""
        return self._message

    @property
    def brief(self):
        """Returns message brief."""
        return {
            "message_id": self._message.message_id,
            "created": self._created,
            "expires": self._expires,
            "job_id": self._job_id,
        }

    def set_expires(self, expires):
        self._expires = expires

    def is_expired(self):
        """Returns if key is expired or not"""
        now = time.time()
        return now > self._expires


class S3Notice:
    """
    A wrapper class for easy access the dict based s3 notification.
    """

    def __init__(
        self, region, bucket, key, size, etag, versionid=None
    ):  # pylint: disable=too-many-arguments
        self._region = region
        self._bucket = bucket
        self._key = key
        self._size = size
        self._etag = etag
        self._versionid = versionid

    @property
    def region(self):
        """Returns region."""
        return self._region

    @property
    def bucket(self):
        """Returns bucket."""
        return self._bucket

    @property
    def key(self):
        """Returns key."""
        return self._key

    @property
    def size(self):
        """Returns size."""
        return self._size

    @property
    def etag(self):
        """Returns etag."""
        return self._etag

    @property
    def versionid(self):
        """Returns versionid."""
        return self._versionid

    @property
    def source(self):
        """Returns source of s3 bucket."""
        return "s3://" + self.bucket + "/" + self.key


class S3EventbridgeNoticeParser:
    """Class for S3 notice parser."""

    def __init__(self, message):
        self._message = message

    def parse(self):
        """Parses message."""
        record = self._message

        try:
            notification = self._make(record)
            parsed_record = [notification] if notification.size else []
        except Exception as exc:
            raise TypeError("Unknown Eventbridge message.") from exc
        return parsed_record

    @classmethod
    def _make(cls, record):
        s3_rec = record["detail"]
        s3bucket = s3_rec["bucket"]
        s3object = s3_rec["object"]
        region = record["region"]
        bucket = s3bucket["name"]
        # handling space, plus and other characters in S3 object name
        key = urlparse.unquote_plus(s3object["key"])
        # size and etag may not exist in some events.
        size = s3object.get("size")
        etag = s3object.get("etag")
        versionid = s3object.get("version-id")
        return S3Notice(region, bucket, key, size, etag, versionid)


class S3NoticeParser:
    """Class for S3 notice parser."""

    def __init__(self, message):
        self._message = message

    def parse(self):
        """Parses message."""
        message = self._message
        records = message["Records"]
        # ignore events which doesn't match with ObjectCreated:*.
        records = [self._make(record) for record in records if self._eoi(record)]
        # ignore empty files or size is unknown.
        records = [item for item in records if item.size]
        return records

    @classmethod
    def _eoi(cls, record):
        return record["eventName"].startswith("ObjectCreated:")

    @classmethod
    def _make(cls, record):
        s3_rec = record["s3"]
        s3bucket = s3_rec["bucket"]
        s3object = s3_rec["object"]
        region = record["awsRegion"]
        bucket = s3bucket["name"]
        # handling space, plus and other characters in S3 object name
        key = urlparse.unquote_plus(s3object["key"])
        # size and etag may not exist in some events.
        size = s3object.get("size")
        etag = s3object.get("eTag")
        versionid = s3object.get("versionId")
        return S3Notice(region, bucket, key, size, etag, versionid)


class ConfigNoticeParser:
    """
    Wrapper class for easy accessing config dict
    based notifications.
    """

    _SUPPORTED_MESSAGE_TYPE = [
        "ConfigurationHistoryDeliveryCompleted",
        "ConfigurationSnapshotDeliveryCompleted",
    ]

    _UNSUPPORTED_MESSAGE_TYPE = [
        "ConfigurationItemChangeNotification",
        "ConfigurationSnapshotDeliveryStarted",
        "ComplianceChangeNotification",
        "ConfigRulesEvaluationStarted",
        "OversizedConfigurationItemChangeNotification",
        "OversizedConfigurationItemChangeDeliveryFailed",
    ]

    def __init__(self, message, region_cache):
        self._message = message
        self._region_cache = region_cache

    def parse(self):
        """Parses message."""
        message = self._message
        message_type = message["messageType"]
        if message_type in self._UNSUPPORTED_MESSAGE_TYPE:
            logger.info("Ingnoring this config message.", message_type=message_type)
            return []

        if message_type not in self._SUPPORTED_MESSAGE_TYPE:
            raise TypeError("Unknown config message.")

        # for supported message types
        bucket = message["s3Bucket"]
        region = self._region_cache.get_region(bucket)
        key = message["s3ObjectKey"]
        if not isinstance(key, str):
            raise TypeError("s3ObjectKey is expected to be an unicode object.")
        return [self._make(region, bucket, key)]

    def _make(self, region, bucket, key):
        return S3Notice(region, bucket, key, None, None)


class CloudtrailNoticeParser:
    """
    Wrapper class for easy accessing cloudtrail
    dict based notifications.
    """

    def __init__(self, message, region_cache):
        self._message = message
        self._region_cache = region_cache

    def parse(self):
        """Parses message."""
        message = self._message
        bucket = message["s3Bucket"]
        region = self._region_cache.get_region(bucket)
        keys = message["s3ObjectKey"]
        if not isinstance(keys, list):
            raise TypeError("s3ObjectKey is expected to be a list object.")
        return [self._make(region, bucket, key) for key in keys]

    def _make(self, region, bucket, key):
        return S3Notice(region, bucket, key, None, None)


class CrowdstrikeNoticeParser:
    """
    Wrapper class for easy accessing crowdstrike
    dict based notifications.
    """

    def __init__(self, message, region_cache, s3_agent):
        self._message = message
        self._region_cache = region_cache
        self._s3_agent = s3_agent

    def parse(self):
        """Parses message."""
        message = self._message
        bucket = message["bucket"]
        region = self._region_cache.get_region(bucket)
        files = message["files"]
        s3_list = []
        prefix = message["pathPrefix"]
        if not isinstance(files, list):
            raise TypeError('"Files" is expected to be a list object.')

        is_success_file_exists = self._s3_agent.checkSuccessFile(bucket, region, prefix)
        if is_success_file_exists:
            for _file in files:
                s3_list.append(self._make(region, bucket, _file))
            return s3_list
        else:
            raise InsufficientMessageDetailsError(
                "Skipping the message as _SUCCESS file is not yet generated in {} batch folder. It will be processed in future.".format(  # pylint: disable=consider-using-f-string, line-too-long
                    prefix
                )
            )

    def _make(self, region, bucket, _file):
        try:
            key = _file["path"]
            size = _file["size"]
        except Exception as exc:  # noqa: F841 # pylint: disable=unused-variable
            logger.error("File may not contain the specified keys")
            raise
        return S3Notice(region, bucket, key, size, None)


class SQSBasedS3PipelineAdapter:  # pylint: disable=too-many-instance-attributes
    """Class for SQS based S3 pipeline adapter."""

    _MAX_CHUNK_SIZE = 1048576
    _MIN_TTL = timedelta(seconds=600)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        app,
        config,
        credentials,
        sqs_agent,
        s3_agent,
        s3_region_cache,
        using_dlq,
        decode,
        event_writer,
        max_receive_count,
        exit_on_idle,
        temp_folder,
        sqs_sns_validation,
        parse_firehose_error_data,
        parse_csv_with_header,
        parse_csv_with_delimiter,
    ):
        self._app = app
        self._config = config
        self._credentials = credentials
        self._sqs_agent = sqs_agent
        self._s3_agent = s3_agent
        self._region_cache = s3_region_cache
        self.using_dlq = using_dlq
        self._decode = decode
        self._event_writer = event_writer
        self._idle_count = 0
        self._exit_on_idle = exit_on_idle
        self._temp_folder = temp_folder
        self._max_receive_count = max_receive_count
        self._max_memory_file_size = 8 * 1024 * 1024
        self._sqs_sns_validation = sqs_sns_validation
        self._parse_firehose_error_data = parse_firehose_error_data
        self._parse_csv_with_header = parse_csv_with_header
        self._parse_csv_with_delimiter = parse_csv_with_delimiter
        self._clock = time.time

    def is_aborted(self):
        """Checks if app is aborted or not."""
        if self._config.has_expired():
            return True
        return self._app.is_aborted()

    def discover(self):
        """Discovers messages."""
        credentials = self._credentials
        attributes = self._sqs_agent.get_attributes()
        ttl = attributes.visibility_timeout
        clock = self._clock

        is_dlq_enabled = (
            isinstance(self.using_dlq, str)
            and self.using_dlq.strip()
            and int(self.using_dlq)
        )
        if is_dlq_enabled and (not attributes.redrive_policy):
            logger.error("Dead letter queue not found.")
            yield BatchExecutorExit(True)

        while True:
            if credentials.need_retire(self._MIN_TTL):
                credentials.refresh()

            messages = self._sqs_agent.get_messages()
            now = clock()  # pylint: disable=deprecated-method
            if self._should_exit(messages):
                yield BatchExecutorExit(True)

            # Ignore messages which have been seen a lot of times
            messages = [item for item in messages if not self._should_ignore(item)]
            yield [Job(message, now, ttl) for message in messages]

    def do(self, job, session):  # pylint: disable=invalid-name
        """Do method."""
        with logging.LogContext(**job.brief):
            self._process(job.is_expired, job.set_expires, job.message, session)

    def _process(  # pylint: disable=inconsistent-return-statements
        self, is_expired, set_expires, message, session
    ):
        try:
            if is_expired():
                return logger.error("Visibility timeout expired.")

            try:
                if self._sqs_sns_validation:
                    logger.debug(
                        f"Validating SNS Signature. message_id={message.message_id}"
                    )
                    message.is_valid()
            except Exception as exc:
                return logger.warning(
                    f"Warning: This message does not have a valid SNS Signature {str(exc)}"
                )

            try:
                records = self._parse(message)
            except InsufficientMessageDetailsError as ex:
                self._delete_message(message, session)
                logger.info(f"Unrecognized message ignoring {message.message_id}")
                logger.debug(ex)
                return

            number_of_record = len(records)
            if not number_of_record:
                self._delete_message(message, session)
                return logger.warning(
                    "There's no files need to be processed in this message."
                )
            _is_parse_failed = False
            for i in range(number_of_record):
                record = records[i]
                # this time out is a bit long because it is blocked while downloading.
                try:
                    message_visiblity = self._sqs_agent.visibility_heart_beat(
                        message.receipt_handle, 1200
                    )
                    set_expires(message_visiblity["expires"])
                except Exception as exc:
                    logger.warning(f"unable to modify message visibility {str(exc)}")
                    pass
                with self._open_temp_file() as cache:
                    headers = self._download(record, cache, session)
                    # Check visibility timeout before ingest the first file.
                    # Ingest remain files without check visibility timeout again.
                    if i == 0 and is_expired():
                        return logger.error(
                            "Visibility timeout expired before sent data for indexing."
                        )

                    # parse firehose error data
                    if self._parse_firehose_error_data:
                        cache = self._parse_error_data_file(cache)
                        if not cache:
                            # if parsing failed, do not ingest, break the loop,
                            # and do not delete the message from SQS
                            _is_parse_failed = True
                            break
                        logger.debug("Parsing of error data completed.")

                    self._ingest_file(
                        cache,
                        record,
                        headers,
                        set_expires,
                        message.receipt_handle,
                        self._parse_csv_with_header,
                        self._parse_csv_with_delimiter,
                    )
                    # must closed before deleting

            if not _is_parse_failed:
                self._delete_message(message, session)
            if is_expired():
                files = [record.source for record in records]
                logger.warning(
                    "File has been ingested beyond the visibility timeout.", files=files
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "An error occurred while processing the message.", exc_info=True
            )
            return exc

    def done(self, job, result):
        """Done method."""
        pass  # pylint: disable=unnecessary-pass

    def _parse_error_data_file(self, cache):
        """
        Parse file containing Error Data contents

        Args:
            cache (file): Downloaded file object from the s3 bucket
        """
        try:
            decoded_data = self._decode_chunk_bytes(cache)
            messages = b""
            for data in decoded_data:
                rawData = data["rawData"]
                message = base64.b64decode(rawData)
                messages += message + b"\n"

            return io.BytesIO(messages)
        except Exception:
            # If failed to decode, log the error and return None
            logger.error("Failed to parse error data, error=%s", traceback.format_exc())

    def _decode_chunk_bytes(self, records, chunk_size=3000):
        """
        Extract the bytes from the file and form a json object
        """
        decoded_content = b""  # Initialize an empty bytes object
        while True:
            chunk = records.read(chunk_size)  # Read a chunk of decoded content
            if not chunk:
                break
            decoded_content += chunk
        data = [json.loads(content) for content in decoded_content.strip().split(b"\n")]
        logger.debug("Successfully decoded error data", size=len(data))
        return data

    def allocate(self):
        """Allocates boto session."""
        return boto3.session.Session()

    def _ingest_file(
        self,
        fileobj,
        record,
        headers,
        set_expires,
        receipt_handle,
        parse_csv_with_header,
        parse_csv_with_delimiter,
    ):
        """Prepares data for processing and indexing. Creates metadata dict.
        First, uses parse_csv_with_header to check whether the file should be
        parsed as a delimited file ot not, before sending data and metadata for indexing.
        First, uses source to check whether a file is CSV or not, before data and metadata for indexing.

        @param: fileobj
        @paramType: tempfile.SpooledTemporaryFile

        @param: record
        @paramType: splunk_ta_aws.modinputs.sqs_based_s3.handler

        @param: headers
        @paramType: splunk_ta_aws.common.s3._FetchFileResult

        @param: set_expires
        @paramType: function

        @param: receipt_handle
        @paramType: dict

        @param: parse_csv_with_header
        @paramType: string

        @param: parse_csv_with_delimiter
        @paramType: string
        """
        try:
            source = record.source
            for records, metadata in self._decode(fileobj, source):
                try:
                    receipt_handle = self._sqs_agent.visibility_heart_beat(
                        receipt_handle
                    )
                    set_expires(receipt_handle["expires"])
                except Exception as exc:
                    logger.warning(f"Failed to set message visibility: {str(exc)}")

                metadata = {
                    "source": metadata.source,
                    "sourcetype": metadata.sourcetype,
                }
                if parse_csv_with_header:
                    # If the file extension is not in the list of csv_file_suffixes, log a warning but process
                    # as a delimited file
                    if (
                        not metadata.get("source")
                        .replace(".gz", "")
                        .endswith(taconsts.csv_file_suffixes)
                    ):
                        logger.warning(
                            "The file extension {} is not in a delimited file format.".format(
                                metadata.get("source")
                            )
                        )
                    logger.info(
                        "Processing {} as a delimited file...".format(  # pylint: disable=consider-using-f-string
                            metadata.get("source")
                        )
                    )
                    volume = self._index_csv(
                        records, parse_csv_with_delimiter, **metadata
                    )
                    self._index_summary(headers, source, volume)
                else:
                    logger.info(
                        "{} detected as a custom file. processing...".format(  # pylint: disable=consider-using-f-string
                            metadata.get("source")
                        )
                    )
                    volume = self._event_writer.write_fileobj(records, **metadata)
                    self._index_summary(headers, source, volume)
        except Exception:
            logger.error("Failed to ingest file.", uri=record.source)
            raise

    def _index_csv(self, fileobj, parse_csv_with_delimiter, **metadata):
        """Processes CSV files in chunks of data or all file content at once, and indexes each row

        @param: fileobj
        @paramType: splunk_ta_aws.common.decoder.UTFStreamDecoder

        @param: parse_csv_with_delimiter
        @paramType: string

        @param: **metadata
        @paramType: dict
        """
        truncated_line = None
        header = None
        volume = 0
        row_count = 0
        rows_error_count = 0

        # we should not be calling a private function (_read_multiple_lines) and should read the fileobj with our own
        # helper function !!!
        for chunk in self._event_writer._read_multiple_lines(  # pylint: disable=W0212
            fileobj
        ):
            volume += len(chunk)
            chunk_data = io.BytesIO(bytes(chunk, "utf-8"))
            for csv_line in chunk_data:
                csv_line, truncated_line = utils.handle_truncated_line(
                    csv_line, truncated_line
                )
                # checks if csv_stream is None because, if so, it would be a partial line, and the process moves to
                # the next line
                if csv_line is None:
                    continue

                try:
                    csv_stream = csv_line.decode("utf-8")
                except Exception as ex:  # pylint: disable=W0703
                    row_count += 1
                    rows_error_count += 1
                    logger.error(
                        "Decoding to utf-8 failed. Reason: {}. Data at failure is on row {}. Line is {}.".format(  # pylint: disable=consider-using-f-string
                            ex, row_count, csv_line
                        )
                    )
                    continue

                # handles mapping fields to values
                event, header = utils.parseCSVLine(
                    csv_stream, header, parse_csv_with_delimiter
                )
                if event:
                    try:
                        self._event_writer.write_events([json.dumps(event)], **metadata)
                        row_count += 1
                    except Exception as ex:  # pylint: disable=W0703
                        row_count += 1
                        rows_error_count += 1
                        logger.error(
                            "write_events() failed to index event at row {}. Reason: {}".format(  # pylint: disable=consider-using-f-string
                                row_count, ex
                            )
                        )
                        continue
        logger.info(
            "Delimited File Parser: {} ingested {} rows successfully. There are {} errors.".format(  # pylint: disable=consider-using-f-string
                metadata.get("source"), row_count - rows_error_count, rows_error_count
            )
        )
        return volume

    def _download(self, record, cache, session):
        try:
            return self._s3_agent.download(record, cache, session)
        except (botocore.exceptions.ClientError, IOError):
            logger.error("Failed to download file.", uri=record.source)
            raise

    def _parse(self, message):
        try:
            document = json.loads(message.body)
            if "TopicArn" in document:
                document = json.loads(document["Message"])
                self._sqs_sns_validation = True

            records = None
            parsers = (
                S3NoticeParser(document),
                CloudtrailNoticeParser(document, self._region_cache),
                ConfigNoticeParser(document, self._region_cache),
                S3EventbridgeNoticeParser(document),
                CrowdstrikeNoticeParser(document, self._region_cache, self._s3_agent),
            )

            for parser in parsers:
                try:
                    records = parser.parse()
                    logger.debug(
                        f"successfully parsed message using {parser.__class__.__name__}"
                    )
                    break
                except (KeyError, ValueError, TypeError):
                    continue

            if records is None:
                logger.debug("Unable to parse ")
                raise ValueError(f"Unable to parse message. {document}")
            return records
        except InsufficientMessageDetailsError:
            raise
        except Exception:
            logger.error("Failed to parse message.")
            raise

    def _should_exit(self, messages):
        if not messages:
            self._idle_count += 1
            if self._idle_count >= self._exit_on_idle:
                return True
            return False
        self._idle_count = 0
        return False

    def _should_ignore(self, message):
        return 0 > self._max_receive_count > message.receive_count

    @contextmanager
    def _open_temp_file(self):
        try:
            max_size = self._max_memory_file_size
            folder = self._temp_folder
            stf = tempfile.NamedTemporaryFile(  # pylint: disable=consider-using-with
                dir=folder, delete=False
            )
        except Exception:
            logger.error("Failed to open temporary file.")
            raise

        try:
            # https://bugs.python.org/issue35112
            if not hasattr(stf, "seekable"):
                stf.seekable = lambda: True
            yield stf
        finally:
            stf.close()
            os.remove(stf.name)

    def _delete_message(self, message, session):
        try:
            self._sqs_agent.delete_message(message, session)
        except Exception:
            logger.error("Failed to delete message.")
            raise

    @staticmethod
    def _index_summary(response, source, volume):
        last_modified = response.last_modified.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(
            "Sent data for indexing.",
            size=volume,
            last_modified=last_modified,
            key=source,
        )


class SQSAgent:
    """Class for SQS agent."""

    def __init__(
        self, url, region, credentials, endpoint_url=None, validator=False
    ):  # pylint: disable=R0913
        self._queue = SQSQueue(url, region, endpoint_url, validator)
        self._batch_size = 0
        self._credentials = credentials

    def get_messages(self, session=None):
        """Returns queue messages."""
        client = self._queue.client(self._credentials, session)
        return self._queue.get_messages(client, self._batch_size)

    def visibility_heart_beat(self, message_state, timeout=500):
        """visibility_heart_beat"""
        client = self._queue.client(self._credentials, None)
        return self._queue.visibility_heart_beat(client, message_state, timeout)

    def delete_message(self, message, session=None):
        """Deletes queue messages."""
        client = self._queue.client(self._credentials, session)
        return self._queue.delete_message(client, message)

    def get_attributes(self, session=None):
        """Returns queue attributes."""
        client = self._queue.client(self._credentials, session)
        return self._queue.get_attributes(client)

    def set_batch_size(self, value):
        """Sets batch size."""
        self._batch_size = value


class S3RegionCache:
    """Class for S3 region cache."""

    def __init__(self, credentials, default_region, check_using_dlq):
        self._credentials = credentials
        self._lock = threading.Lock()
        self._region = default_region
        self._s3_region_cache = OrderedDict()
        self._check_using_dlq = check_using_dlq

    def get_region(self, bucket, session=None):
        """Returns S3 region."""
        with self._lock:
            if not int(self._check_using_dlq):
                return self._region
            if bucket in self._s3_region_cache:
                return self._s3_region_cache[bucket]
            else:
                client = self._credentials.client("s3v4", self._region, session)
                s3_region = client.get_bucket_location(Bucket=bucket).get(
                    "LocationConstraint"
                )

                # ADDON-16435. Some endpoint has different LocationConstraint.
                if not s3_region:
                    s3_region = "us-east-1"
                elif s3_region == "EU":
                    s3_region = "eu-west-1"

                self._s3_region_cache[bucket] = s3_region
                return s3_region


class S3Agent:
    """Class for S3 agent."""

    def __init__(self, credentials, endpoint_url=None):
        self._multipart_threshold = 0
        self._credentials = credentials
        self._endpoint_url = endpoint_url

    def download(self, notice, fileobj, session=None):
        """Returns fetched bucket data."""
        bucket = S3Bucket(notice.bucket, notice.region, self._endpoint_url)
        s3_bkt = bucket.client(  # pylint: disable=invalid-name
            self._credentials, session
        )
        etag = notice.etag
        key = notice.key
        versionid = notice.versionid
        condition = {} if not etag else {"IfMatch": etag}
        if versionid:
            condition["VersionId"] = versionid
        if self._should_multipart_download(notice):
            return bucket.transfer(s3_bkt, key, fileobj, **condition)
        return bucket.fetch(s3_bkt, key, fileobj, **condition)

    def checkSuccessFile(  # pylint: disable=invalid-name
        self, bucket_name, region, prefix, session=None
    ):
        """Returns file success boolean."""
        try:
            bucket = S3Bucket(bucket_name, region)
            s3_bkt = bucket.client(self._credentials, session)
            key = "{}/_SUCCESS".format(  # pylint: disable=consider-using-f-string
                prefix
            )
            try:
                s3_bkt.head_object(Bucket=bucket_name, Key=key)
            except botocore.exceptions.ClientError as ex:
                if ex.response["Error"]["Code"] in ["NoSuchKey", "404"]:
                    return False
                else:
                    raise
            return True
        except Exception as exc:
            logger.error("Failed : " + str(exc))
            raise

    def set_multipart_threshold(self, value):
        """Sets multipart threshold."""
        self._multipart_threshold = value

    def _should_multipart_download(self, notice):
        if not notice.size:
            # for config and cloudtrail based sqs message,
            # size is unavailable, directly do multipart
            return True
        # for s3 based sqs message
        elif notice.size >= self._multipart_threshold:
            return True
        return False


class SQSBasedS3Settings:
    """Class for SQS based S3 settings."""

    @classmethod
    def load(cls, config):
        """Returns log level settings."""
        content = config.load("aws_settings", stanza="aws_sqs_based_s3")
        parser = StanzaParser([LogLevelField("log_level", default="WARNING")])
        settings = parser.parse(content)
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def setup_log_level(self):
        """Sets log level."""
        set_log_level(self._settings.log_level)


class SQSBasedS3DataInput:
    """Class for SQS based S3 data input."""

    # pylint: disable=too-many-locals

    def __init__(self, stanza):
        self._kind = stanza.kind
        self._name = stanza.name
        self._args = stanza.content
        self._start_time = int(time.time())

    def create_metadata(self):
        """Returns extracted arguments."""
        stanza = self._kind + "://" + self._name
        parser = StanzaParser(
            [
                StringField("index"),
                StringField("host"),
                StringField("stanza", fillempty=stanza),
            ]
        )
        return self._extract_arguments(parser)

    def create_credentials(self, config):
        """Returns credentials."""
        parser = StanzaParser(
            [
                StringField("aws_account", required=True),
                StringField("aws_iam_role"),
            ]
        )
        args = self._extract_arguments(parser)
        sts_endpoint_url = tacommon.get_endpoint_url(
            self._args, "sts_private_endpoint_url"
        )
        factory = AWSCredentialsProviderFactory(
            config, self._args.get("sqs_queue_region"), sts_endpoint_url
        )
        provider = factory.create(args.aws_account, args.aws_iam_role)
        credentials = AWSCredentialsCache(provider)
        return credentials

    def create_file_decoder(self):
        """Returns file decoder."""
        parser = StanzaParser(
            [
                StringField("s3_file_decoder", rename="name", required=True),
                StringField("sourcetype", default=""),
            ]
        )
        args = self._extract_arguments(parser)
        factory = DecoderFactory.create_default_instance()
        return factory.create(**vars(args))

    def create_sqs_agent(self, credential):
        """Returns SQS agent."""
        parser = StanzaParser(
            [
                StringField("sqs_queue_url", required=True),
                StringField("sqs_queue_region", required=True),
                IntegerField("sqs_batch_size", default=10, lower=1, upper=10),
            ]
        )
        args = self._extract_arguments(parser)
        sqs_endpoint_url = tacommon.get_endpoint_url(
            self._args, "sqs_private_endpoint_url"
        )
        agent = SQSAgent(
            args.sqs_queue_url,
            args.sqs_queue_region,
            credential,
            sqs_endpoint_url,
            validator=True,
        )
        agent.set_batch_size(args.sqs_batch_size)
        return agent

    def create_s3_agent(self, credential):
        """Returns S3 agent."""
        _1MB = 1024 * 1024  # pylint: disable=invalid-name
        _8MB = _1MB * 8  # pylint: disable=invalid-name
        _64MB = _8MB * 8  # pylint: disable=invalid-name
        parser = StanzaParser(
            [
                IntegerField(
                    "s3_multipart_threshold", default=_8MB, lower=_8MB, upper=_64MB
                )
            ]
        )
        args = self._extract_arguments(parser)
        s3_endpoint_url = tacommon.get_endpoint_url(
            self._args, "s3_private_endpoint_url"
        )
        agent = S3Agent(credential, s3_endpoint_url)
        agent.set_multipart_threshold(args.s3_multipart_threshold)
        return agent

    def create_region_cache(self, credentials):
        """Returns S3 region cache."""
        parser = StanzaParser([StringField("sqs_queue_region", required=True)])
        args = self._extract_arguments(parser)
        using_dlq = self.check_using_dlq()
        return S3RegionCache(credentials, args.sqs_queue_region, using_dlq.using_dlq)

    def create_event_writer(self, app):
        """Returns event writer."""
        metadata = self.create_metadata()
        parser = StanzaParser([StringField("use_raw_hec")])
        args = self._extract_arguments(parser)
        url = args.use_raw_hec
        return app.create_event_writer(url, **vars(metadata))

    def create_batch_executor(self):
        """Returns batch executors."""
        parser = StanzaParser(
            [
                IntegerField(
                    "sqs_batch_size",
                    rename="number_of_threads",
                    default=10,
                    lower=1,
                    upper=10,
                ),
            ]
        )
        args = self._extract_arguments(parser)
        return BatchExecutor(number_of_threads=args.number_of_threads)

    def check_using_dlq(self):
        """Returns extracted arguments."""
        parser = StanzaParser(
            [
                StringField("using_dlq"),
            ]
        )
        return self._extract_arguments(parser)

    def parse_options(self):
        """Parses argument."""
        parser = StanzaParser(
            [
                IntegerField("max_receive_count", default=-1),
                IntegerField("exit_on_idle", default=15),
                BooleanField("sqs_sns_validation", default=False),
                BooleanField("parse_firehose_error_data", default=False),
                BooleanField("parse_csv_with_header", default=False),
                StringField("parse_csv_with_delimiter", default=","),
            ]
        )
        return self._extract_arguments(parser)

    def _extract_arguments(self, parser):
        return parser.parse(self._args)

    def create_temp_folder(self, app):
        """Creates temp folder."""
        # clean all temp files at startup.
        temp_folder = os.path.join(app.workspace(), self._name)
        shutil.rmtree(temp_folder, ignore_errors=True)
        if not os.path.exists(temp_folder):
            os.makedirs(temp_folder)
        return temp_folder

    @property
    def name(self):
        """Returns name."""
        return self._name

    @property
    def start_time(self):
        """Returns start time."""
        return self._start_time

    @LogWith(datainput=name, start_time=start_time)
    @LogExceptions(
        logger, "Data input was interrupted by an unhandled exception.", lambda e: -1
    )
    def run(self, app, config):
        """Run SQS based S3 input."""
        settings = SQSBasedS3Settings.load(config)
        settings.setup_log_level()
        proxy = ProxySettings.load(config)
        proxy.hook_boto3_get_proxies()

        # set proxy global variables for the sns signature validation
        if proxy._settings.enabled:
            proxy_url = proxy._make_url()
            boto3_proxy_patch.set_proxies(proxy_url, proxy_url)

        logger.info("Data input started.", **self._args)

        credentials = self.create_credentials(config)
        sqs_agent = self.create_sqs_agent(credentials)
        s3_agent = self.create_s3_agent(credentials)
        s3_region_cache = self.create_region_cache(credentials)
        decoder = self.create_file_decoder()
        options = self.parse_options()
        check_using_dlq = self.check_using_dlq()

        event_writer = self.create_event_writer(app)
        temp_folder = self.create_temp_folder(app)
        executor = self.create_batch_executor()
        components = {
            "app": app,
            "config": config,
            "credentials": credentials,
            "sqs_agent": sqs_agent,
            "s3_agent": s3_agent,
            "s3_region_cache": s3_region_cache,
            "using_dlq": check_using_dlq.using_dlq,
            "decode": decoder,
            "event_writer": event_writer,
            "max_receive_count": options.max_receive_count,
            "exit_on_idle": options.exit_on_idle,
            "temp_folder": temp_folder,
            "sqs_sns_validation": options.sqs_sns_validation,
            "parse_firehose_error_data": options.parse_firehose_error_data,
            "parse_csv_with_header": options.parse_csv_with_header,
            "parse_csv_with_delimiter": options.parse_csv_with_delimiter,
        }
        adapter = SQSBasedS3PipelineAdapter(**components)
        executor.run(adapter)
        return 0
