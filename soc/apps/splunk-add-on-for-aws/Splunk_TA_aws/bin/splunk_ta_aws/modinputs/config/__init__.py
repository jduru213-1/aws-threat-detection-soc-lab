"""
Modular Input for AWS Config
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import calendar
import gzip
import io
import json
import logging
import os
import sys
import time

import boto3
import botocore
import splunk_ta_aws.common.proxy_conf as tpc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunksdc.log
import splunktalib.common.util as scutil
import splunktalib.orphan_process_monitor as opm
from botocore.config import Config
from splunk_ta_aws import set_log_level
from splunk_ta_aws.common.aws_accesskeys import APPNAME
from splunk_ta_aws.common.log_settings import get_level
from splunklib import modularinput as smi

# logger should be init at the very begging of everything
logger = splunksdc.log.get_module_logger()

NOT_FOUND = 404


class S3ConnectionPool:
    """
    S3 connection pool for buckets in different regions.
    """

    _region_conn_pool: dict = {}
    _bucket_region_cache: dict = {}

    @classmethod
    def get_conn(cls, key_id, secret_key, bucket, default_region="us-east-1"):
        """Return s3 connection to region where bucket is located."""
        bucket_region = cls.get_bucket_region(
            bucket, key_id, secret_key, default_region
        )
        s3_endpoint_url = tacommon.format_default_endpoint_url("s3", bucket_region)
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
    def get_bucket_region(cls, bucket, key_id, secret_key, default_region="us-east-1"):
        """Returns bucket region."""
        s3_endpoint_url = tacommon.format_default_endpoint_url("s3", default_region)
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

        return cls._bucket_region_cache[bucket]


class MyScript(smi.Script):
    """Class for myscript."""

    def __init__(self):

        super(MyScript, self).__init__()  # pylint: disable=super-with-arguments
        self._canceled = False
        self._ew = None
        self._orphan_checker = opm.OrphanProcessChecker()

        self.input_name = None
        self.input_items = None
        self.enable_additional_notifications = False

        # self.remove_files_when_done = False
        # self.exclude_describe_events = True
        # self.blacklist = None
        # self.blacklist_pattern = None

    def get_scheme(self):
        """overloaded splunklib modularinput method"""

        scheme = smi.Scheme("AWS Config")
        scheme.description = (
            "Collect notifications produced by AWS Config."
            "The feature must be enabled and its SNS topic must be subscribed to an SQS queue."
        )
        scheme.use_external_validation = True
        scheme.streaming_mode_xml = True
        scheme.use_single_instance = False
        # defaults != documented scheme defaults, so I'm being explicit.
        scheme.add_argument(
            smi.Argument(
                "name",
                title="Name",
                description="Choose an ID or nickname for this configuration",
                required_on_create=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                "aws_account",
                title="AWS Account",
                description="AWS account",
                required_on_create=True,
                required_on_edit=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                "aws_region",
                title="SQS Queue Region",
                description=(
                    "Name of the AWS region in which the"
                    " notification queue is located. Regions should be entered as"
                    " e.g., us-east-1, us-west-2, eu-west-1, ap-southeast-1, etc."
                ),
                required_on_create=True,
                required_on_edit=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                "sqs_queue",
                title="SQS Queue Name",
                description=(
                    "Name of queue to which notifications of AWS Config"
                    " are sent. The queue should be subscribed"
                    " to the AWS Config SNS topic."
                ),
                required_on_create=True,
                required_on_edit=True,
            )
        )
        scheme.add_argument(
            smi.Argument(
                "enable_additional_notifications",
                title="Enable Debug",
                description=(
                    "Index additional SNS/SQS events to help with troubleshooting."
                ),
                data_type=smi.Argument.data_type_boolean,
                required_on_create=False,
            )
        )
        scheme.add_argument(
            smi.Argument(
                "polling_interval",
                title="Polling interval for statistics",
                description="Polling interval for statistics",
                data_type=smi.Argument.data_type_number,
                required_on_create=False,
            )
        )

        return scheme

    def validate_input(self, definition):
        """overloaded splunklib modularinput method"""
        pass  # pylint: disable=unnecessary-pass

    def _exit_handler(  # pylint: disable=inconsistent-return-statements
        self, signum, frame=None
    ):  # pylint: disable=unused-argument
        self._canceled = True
        logger.log(logging.INFO, "Cancellation received.")

        if os.name == "nt":
            return True

    def stream_events(self, inputs, ew):  # pylint: disable=invalid-name
        """overloaded splunklib modularinput method"""
        # for multiple instance modinput, inputs dic got only one key
        input_name = scutil.extract_datainput_name(list(inputs.inputs.keys())[0])
        splunksdc.log.setup_root_logger(
            app_name="splunk_ta_aws", modular_name="config", stanza_name=input_name
        )
        with splunksdc.log.LogContext(datainput=input_name):
            self._stream_events(inputs, ew)

    def _stream_events(
        self, inputs, ew
    ):  # pylint: disable=invalid-name, too-many-locals, too-many-branches, too-many-statements
        """helper function"""
        loglevel = get_level("aws_config", self.service.token, appName=APPNAME)

        set_log_level(loglevel)

        logger.log(
            logging.INFO,
            "STARTED: {}".format(  # pylint: disable=consider-using-f-string
                len(sys.argv) > 1 and sys.argv[1] or ""
            ),
        )
        logger.log(logging.DEBUG, "Start streaming.")
        self._ew = ew

        if os.name == "nt":
            import win32api  # pylint: disable=import-outside-toplevel

            win32api.SetConsoleCtrlHandler(self._exit_handler, True)
        else:
            import signal  # pylint: disable=import-outside-toplevel

            signal.signal(signal.SIGTERM, self._exit_handler)
            signal.signal(signal.SIGINT, self._exit_handler)

        # because we only support one stanza...
        self.input_name, self.input_items = inputs.inputs.popitem()

        self.enable_additional_notifications = (
            self.input_items.get("enable_additional_notifications") or "false"
        ).lower() in ("1", "true", "yes", "y", "on")
        # self.configure_blacklist()

        base_sourcetype = self.input_items.get("sourcetype") or "aws:config"
        session_key = self.service.token
        key_id, secret_key = tacommon.get_aws_creds(
            self.input_items, inputs.metadata, {}
        )

        # Set proxy
        proxy_info = tpc.get_proxy_info(session_key)
        tacommon.set_proxy_env(proxy_info)
        endpoint_url = tacommon.format_default_endpoint_url(
            "sqs", self.input_items["aws_region"]
        )
        # Create SQS Connection
        sqs_conn = boto3.client(
            "sqs",
            aws_access_key_id=key_id,
            aws_secret_access_key=secret_key,
            region_name=self.input_items["aws_region"],
            endpoint_url=endpoint_url,
        )
        logger.log(logging.DEBUG, "Connected to SQS successfully")

        try:  # pylint: disable=too-many-nested-blocks
            while not self._canceled:
                queue_name = self.input_items["sqs_queue"]
                queue_url = None
                try:
                    queue_url = sqs_conn.get_queue_url(QueueName=queue_name).get(
                        "QueueUrl"
                    )
                except sqs_conn.exceptions.QueueDoesNotExist:
                    pass

                # Workaround: boto bug for china region cn-north-1
                if not queue_url and self.input_items["aws_region"] == "cn-north-1":
                    try:
                        res = sqs_conn.list_queues(QueueNamePrefix=queue_name)
                        for _queue_url in res.get("QueueUrls", []):
                            if _queue_url.split("/")[-1] == queue_name:
                                queue_url = _queue_url
                                break
                    except botocore.exceptions.ClientError as client_err:
                        logger.log(
                            logging.FATAL,
                            "sqs_conn.get_all_queues(): {} {}: {} - {}".format(  # pylint: disable=consider-using-f-string
                                client_err.response["ResponseMetadata"][
                                    "HTTPStatusCode"
                                ],
                                client_err.response["Error"].get("Code"),
                                client_err.response["Error"].get("Message"),
                                client_err,
                            ),
                        )
                        raise

                if not queue_url:
                    logger.log(  # pylint: disable=consider-using-f-string
                        logging.FATAL,
                        "sqs_conn.get_queue(): Invalid SQS Queue Name: {}".format(  # pylint: disable=consider-using-f-string
                            self.input_items["sqs_queue"]
                        ),
                    )
                    break

                # num_messages=10 was chosen based on aws pricing faq.
                # see request batch pricing: http://aws.amazon.com/sqs/pricing/
                notifications = sqs_conn.receive_message(
                    QueueUrl=queue_url,
                    MaxNumberOfMessages=10,
                    VisibilityTimeout=20,
                    WaitTimeSeconds=20,
                )
                notifications = notifications.get("Messages", [])
                logger.log(
                    logging.DEBUG,
                    "Length of notifications in sqs=%s for region=%s is: %s"  # pylint: disable=consider-using-f-string
                    % (
                        self.input_items["sqs_queue"],
                        self.input_items["aws_region"],
                        len(notifications),
                    ),
                )

                start_time = time.time()
                completed = []
                failed = []

                stats = {"written": 0}

                # if not notifications or self._canceled:
                #     continue

                # Exit if SQS returns nothing. Wake up on interval as specified on inputs.conf
                if len(notifications) == 0:
                    self._canceled = True
                    break

                for notification in notifications:
                    if self._canceled or self._check_orphan():
                        break

                    try:
                        envelope = json.loads(notification.get("Body"))
                    # What do we do with non JSON data?
                    # Leave them in the queue but recommend customer uses a SQS queue only for AWS Config?
                    except Exception as exc:  # pylint: disable=broad-except
                        failed.append(notification)
                        logger.log(
                            logging.ERROR,
                            "problems decoding notification JSON string: {} {}".format(  # pylint: disable=consider-using-f-string
                                type(exc).__name__, exc
                            ),
                        )
                        continue

                    if not isinstance(envelope, dict):
                        failed.append(notification)
                        logger.log(
                            logging.ERROR,
                            "This doesn't look like a valid Config message. Please check SQS settings.",
                        )
                        continue

                    if all(
                        key in envelope
                        for key in ("Type", "MessageId", "TopicArn", "Message")
                    ) and isinstance(envelope["Message"], str):
                        logger.log(
                            logging.DEBUG, "This is considered a Config notification."
                        )
                        try:
                            envelope = json.loads(envelope["Message"])
                            if not isinstance(envelope, dict):
                                failed.append(notification)
                                logger.log(
                                    logging.ERROR,
                                    "This doesn't look like a valid Config message. Please check SQS settings.",
                                )
                                continue
                        except Exception as exc:  # pylint: disable=broad-except
                            failed.append(notification)
                            logger.log(
                                logging.ERROR,
                                "problems decoding message JSON string: {} {}".format(  # pylint: disable=consider-using-f-string
                                    type(exc).__name__, exc
                                ),
                            )
                            continue

                    if "messageType" in envelope:
                        logger.log(
                            logging.DEBUG,
                            "This is considered a Config message. 'Raw Message Delivery' may be 'True'.",
                        )
                        message = envelope
                    else:
                        failed.append(notification)
                        logger.log(
                            logging.ERROR,
                            "This doesn't look like a valid Config message. Please check SQS settings.",
                        )
                        continue

                    # Process: config notifications, history and snapshot notifications (additional)

                    # Process notifications with payload, check ConfigurationItemChangeNotification
                    msg_type = message.get("messageType", "")
                    if msg_type == "ConfigurationItemChangeNotification":
                        logger.log(
                            logging.DEBUG,
                            "Consuming configuration change data in SQS payload.",
                        )
                        # determine _time for the event
                        configuration_item = message.get("configurationItem", "")
                        configuration_item_capture_time = configuration_item.get(
                            "configurationItemCaptureTime", ""
                        )
                        event_time = int(
                            calendar.timegm(
                                time.strptime(
                                    configuration_item_capture_time.replace("Z", "GMT"),
                                    "%Y-%m-%dT%H:%M:%S.%f%Z",
                                )
                            )
                        )
                        # write the event
                        event = smi.Event(
                            data=json.dumps(message),
                            time=event_time,
                            sourcetype=base_sourcetype + ":notification",
                        )
                        ew.write_event(event)
                        stats["written"] += 1
                        completed.append(notification)

                    # Process ConfigurationHistoryDeliveryCompleted and ConfigurationSnapshotDeliveryCompleted

                    # notifications by fetching data from S3 buckets
                    elif (
                        msg_type
                        in [
                            "ConfigurationHistoryDeliveryCompleted",
                            "ConfigurationSnapshotDeliveryCompleted",
                        ]
                        and message.get("s3ObjectKey", "") != ""
                        and message.get("s3Bucket", "") != ""
                    ):
                        config_type = (
                            "history"
                            if msg_type == "ConfigurationHistoryDeliveryCompleted"
                            else "snapshot"
                        )
                        logger.log(
                            logging.DEBUG,
                            "Consuming configuration '{}' change data in S3 bucket.".format(
                                config_type
                            ),
                        )

                        bucket_name = message.get("s3Bucket", "")
                        key = message.get("s3ObjectKey", "")
                        logger.log(
                            logging.INFO,
                            "Consume config '{0}' changes from s3 with s3Bucket '{1}' s3ObjectKey '{2}'".format(  # pylint: disable=consider-using-f-string
                                config_type, bucket_name, key
                            ),
                        )

                        file_json = self.read_from_s3_bucket(
                            completed,
                            failed,
                            key_id,
                            secret_key,
                            notification,
                            bucket_name,
                            key,
                            self.input_items["aws_region"],
                        )

                        self.process_config_changes(
                            file_json,
                            completed,
                            failed,
                            notification,
                            bucket_name,
                            key,
                            False,
                        )

                        logger.log(
                            logging.DEBUG,
                            "Length of completed after reaching into s3bucket: {0}".format(  # pylint: disable=consider-using-f-string
                                len(completed)
                            ),
                        )

                    # Process OversizedConfigurationItemChangeNotification notifications by fetching data from S3 buckets
                    elif msg_type == "OversizedConfigurationItemChangeNotification":
                        logger.log(
                            logging.DEBUG,
                            "Consuming OversizedConfigurationItemChangeNotification data in S3 bucket.",
                        )

                        s3_delivery_summary = "s3DeliverySummary"
                        s3_bucket_location = "s3BucketLocation"

                        if message[s3_delivery_summary][s3_bucket_location] is not None:
                            s3_bucket_info = message[s3_delivery_summary][
                                s3_bucket_location
                            ]
                            bucket_name, key = s3_bucket_info.split("/", 1)
                            logger.log(
                                logging.INFO,
                                "Consume OversizedConfigurationItemChangeNotification from s3 with s3Bucket '{0}' s3ObjectKey '{1}'".format(
                                    bucket_name, key
                                ),
                            )
                        else:
                            log_message = (
                                "OversizedConfigurationItemChangeNotification fetch errorCode={0},"
                                "errorMessage={1}".format(
                                    message[s3_delivery_summary]["errorCode"],
                                    message[s3_delivery_summary]["errorMessage"],
                                )
                            )
                            logger.error(log_message)
                            return []

                        file_json = self.read_from_s3_bucket(
                            completed,
                            failed,
                            key_id,
                            secret_key,
                            notification,
                            bucket_name,
                            key,
                            self.input_items["aws_region"],
                        )

                        self.process_config_changes(
                            file_json,
                            completed,
                            failed,
                            notification,
                            bucket_name,
                            key,
                            True,
                        )

                        logger.log(
                            logging.DEBUG,
                            "Length of completed after reaching into s3bucket: {0}".format(
                                len(completed)
                            ),
                        )

                    # # Ingest all other notification of types: ConfigurationSnapshot*etc.
                    # but only when enable_additional_notifications is true.
                    # elif self.enable_additional_notifications and msg_type.startswith("ConfigurationSnapshot"):
                    #     logger.log(logging.DEBUG, "Consuming additional notifications enabled")
                    #     notificationCreationTime = message.get('notificationCreationTime', '')
                    #     event_time = int(calendar.timegm(time.strptime(notificationCreationTime.replace("Z", "GMT"),
                    #  "%Y-%m-%dT%H:%M:%S.%f%Z")))
                    #     # write the event
                    #     event = smi.Event(data=json.dumps(message),
                    #                   time=event_time,
                    #                   sourcetype=base_sourcetype+":additional")
                    #     ew.write_event(event)
                    #     stats['written'] += 1
                    #     completed.append(notification)

                    elif msg_type in [
                        "ComplianceChangeNotification",
                        "ConfigurationSnapshotDeliveryStarted",
                        "ConfigRulesEvaluationStarted",
                    ]:
                        logger.log(
                            logging.INFO,
                            "Ignore this message and delete the sqs messages.",
                        )
                        completed.append(notification)

                    else:
                        failed.append(notification)
                        logger.log(
                            logging.ERROR,
                            "This doesn't look like a Config notification or message. Please check SQS settings.",
                        )
                        continue

                notification_delete_errors = 0
                # Delete ingested notifications
                if completed:
                    completed = self.remove_duplicate_messages(completed)
                    logger.log(
                        logging.INFO,
                        "Delete {0} completed messages from SQS".format(  # pylint: disable=consider-using-f-string
                            len(completed)
                        ),
                    )
                    del_result = self.delete_message_batch(
                        sqs_conn, queue_url, completed
                    )
                    notification_delete_errors = len(del_result.get("Failed", []))

                if failed:
                    failed = self.remove_duplicate_messages(failed)
                    logger.log(logging.DEBUG, "sqs_queue.delete_message_batch(failed)")
                    logger.log(
                        logging.INFO,
                        "Delete {0} failed messages from SQS".format(  # pylint: disable=consider-using-f-string
                            len(failed)
                        ),
                    )
                    del_result = self.delete_message_batch(sqs_conn, queue_url, failed)

                    logger.log(logging.DEBUG, "sqs_queue.delete_message_batch done")
                    notification_delete_errors = len(del_result.get("Failed", []))
                    failed_messages = ",".join([m["Body"] for m in failed])
                    logger.log(
                        logging.WARN,
                        "Invalid notifications have been removed from SQS : %s",
                        failed_messages,
                    )

                else:
                    logger.log(
                        logging.INFO,
                        (
                            "{} completed, {} failed while processing a notification batch of {}"  # pylint: disable=consider-using-f-string
                            " [{} errors deleting {} notifications]"
                            "  Elapsed: {:.3f}s"
                        ).format(
                            len(completed),
                            len(failed),
                            len(notifications),
                            notification_delete_errors,
                            len(completed),
                            time.time() - start_time,
                        ),
                    )

        except Exception as exc:  # pylint: disable=broad-except
            logger.log(logging.FATAL, "Outer catchall: %s: %s", type(exc).__name__, exc)

    def remove_duplicate_messages(self, messages):
        """Removes duplicate messages."""
        message_ids = set()
        _messages = []
        for message in messages:
            if message["MessageId"] in message_ids:
                continue
            message_ids.add(message["MessageId"])
            _messages.append(message)
        return _messages

    def delete_message_batch(self, sqs_conn, queue_url, messages):
        """Deletes message from batch."""
        delete_batch = []
        for message in messages:
            delete_batch.append(
                {"Id": message["MessageId"], "ReceiptHandle": message["ReceiptHandle"]}
            )
        res = sqs_conn.delete_message_batch(QueueUrl=queue_url, Entries=delete_batch)
        return res

    def _check_orphan(self):
        res = self._orphan_checker.is_orphan()
        if res:
            self._canceled = True
            logger.warn(  # pylint: disable=deprecated-method
                "Process=%s become orphan, exit...", os.getpid()
            )
        return res

    def read_from_s3_bucket(
        self,
        completed_log,
        failed_log,
        key_id,
        secret_key,
        notification,
        bucket_name,
        key,
        default_region="us-east-1",
    ):
        """Extract events from AWS S3 bucket referenced in SNS notification."""
        file_json = {}
        try:
            s3_conn = S3ConnectionPool.get_conn(
                key_id, secret_key, bucket_name, default_region
            )
            s3_file = s3_conn.get_object(Bucket=bucket_name, Key=key)

            if s3_file and "Body" in s3_file:
                with io.BytesIO(s3_file["Body"].read()) as bio:
                    with gzip.GzipFile(fileobj=bio) as gz_f:
                        file_json = json.loads(gz_f.read())
            else:
                logger.log(
                    logging.WARN, "S3 key not found", bucket=bucket_name, key=key
                )

        except botocore.exceptions.ClientError as client_err:

            # if client_err.error_code == 'NoSuchBucket' --- should we delete from queue also?
            # Or is this something that should be left for SQS Redrive?

            loglevel = logging.ERROR
            warning_codes = ("NoSuchKey",)
            if (
                client_err.response["ResponseMetadata"]["HTTPStatusCode"] == NOT_FOUND
                and client_err.response["Error"]["Code"] in warning_codes
            ):
                completed_log.append(notification)
                loglevel = logging.WARN
            else:
                failed_log.append(notification)

            logger.log(
                loglevel,
                "{}: {} {}: {} - {}".format(  # pylint: disable=consider-using-f-string
                    type(client_err).__name__,
                    client_err.response["ResponseMetadata"]["HTTPStatusCode"],
                    client_err.response["Error"].get("Code"),
                    client_err.response["Error"].get("Message"),
                    client_err,
                ),
            )

        except ValueError as value_err:
            failed_log.append(notification)
            logger.log(
                logging.ERROR,
                "Problems reading json from s3:{}/{}: {} {}".format(
                    bucket_name, key, type(value_err).__name__, value_err
                ),
            )

        except IOError as io_err:
            failed_log.append(notification)
            logger.log(
                logging.ERROR,
                "Problems unzipping from s3:{}/{}: {} {}".format(
                    bucket_name, key, type(io_err).__name__, io_err
                ),
            )

        return file_json

    def extra_payload(
        self,
        configuration_item,
        stats,
        source,
        is_ocn,
    ):
        configuration_item_capture_time = configuration_item.get(
            "configurationItemCaptureTime", ""
        )
        """Extract payload information from the config object"""
        event_time = int(
            calendar.timegm(
                time.strptime(
                    configuration_item_capture_time.replace("Z", "GMT"),
                    "%Y-%m-%dT%H:%M:%S.%f%Z",
                )
            )
        )
        # write the event
        if is_ocn:
            base_sourcetype = self.input_items.get("sourcetype") or "aws:config"
            event = smi.Event(
                data=json.dumps(configuration_item),
                time=event_time,
                sourcetype=base_sourcetype + ":notification",
            )
        else:
            event = smi.Event(
                data=json.dumps(configuration_item), time=event_time, source=source
            )
        self._ew.write_event(event)
        stats["written"] += 1

    def process_config_changes(
        self,
        file_json,
        completed_log,
        failed_log,
        notification,
        bucket_name,
        key,
        is_ocn,
    ):
        """Extract events from AWS Config Change"""
        try:
            configuration_items = (
                file_json.get("configurationItem", [])
                if is_ocn
                else file_json.get("configurationItems", [])
            )
            logger.log(
                logging.INFO,
                "Processing {} configurationItems in s3:{}/{}".format(
                    len(configuration_items), bucket_name, key
                ),
            )
        except KeyError as key_err:
            failed_log.append(notification)
            logger.log(
                logging.ERROR,
                "JSON not in the expected format from s3:{}/{}: {} {}".format(
                    bucket_name, key, type(key_err).__name__, key_err
                ),
            )

        stats = {"written": 0}

        source = os.path.basename(key)

        try:
            if is_ocn:
                configuration_item = configuration_items
                self.extra_payload(configuration_item, stats, source, is_ocn)
            else:
                for configuration_item in configuration_items:
                    self.extra_payload(configuration_item, stats, source, is_ocn)

            logger.log(
                logging.INFO,
                ("Fetched {} configurationItems, wrote into {} from s3:{}/{}").format(
                    len(configuration_items), stats["written"], bucket_name, key
                ),
            )
            completed_log.append(notification)

        except IOError as io_err:  # noqa: F841
            logger.log(
                logging.ERROR,
                "Problem in reading the config changes {} {}".format(
                    type(io_err).__name__, io_err
                ),
            )
            if not self._canceled:
                failed_log.append(notification)


def main():
    """Main method for AWS config inputs."""
    exitcode = MyScript().run(sys.argv)
    sys.exit(exitcode)
