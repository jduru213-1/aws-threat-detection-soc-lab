#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for cloudwatchlogs data loader.
"""


import sys
import traceback
import boto3
from typing import Iterator
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.common.util as scutil
from splunklib.client import Service
from splunksdc.config import ConfigManager
from solnlib.splunkenv import get_splunkd_access_info
from splunk_ta_aws.common.credentials import (  # isort: skip # pylint: disable=ungrouped-imports
    AWSCredentialsCache,
    AWSCredentialsProviderFactory,
)
from splunksdc import logging
from datetime import timedelta

from . import aws_cloudwatch_logs_checkpointer as checkpointer
from . import aws_cloudwatch_logs_consts as aclc

logger = logging.get_module_logger()


class ExitGraceFully(Exception):
    pass


class CloudWatchLogsDataLoader:
    _MIN_TTL = timedelta(minutes=10)
    """Class for CloudwatchLogs Data Loader."""

    _evt_fmt = (
        "<stream><event>"
        "<time>{time}</time>"
        "<source>{source}</source>"
        "<sourcetype>{sourcetype}</sourcetype>"
        "<index>{index}</index>"
        "<data>{data}</data>"
        "</event></stream>"
    )

    def __init__(self, task_config: dict, meta_config: dict):
        """Init CloudWatchLogsDataLoader object

        Args:
            task_config (dict): dict of task details {"interval": 30,
                                    "source": xxx,
                                    "sourcetype": yyy,
                                    "index": zzz,
                                    "checkpoint_dir": aaa,
                                    "log_group_name": xxx,
                                    }
            meta_config (dict): Dict of meta details
        """
        self._task_config = task_config
        self._meta_config = meta_config
        self._stopped = False
        self._credentials = None
        self._client = None

    def __call__(self) -> None:
        with logging.LogContext(
            datainput=self._task_config[tac.stanza_name],
            region=self._task_config[tac.region],
            log_group=self._task_config[aclc.log_group_name],
        ):
            self.index_data()

    def index_data(self) -> None:
        """Start task process."""
        task = self._task_config
        if task[aclc.lock].locked():
            logger.info("Previous job of the same task still running. Exit current job")
            return

        logger.info("Start collecting cloudwatch logs")
        try:
            self._credentials = self._load_credentials(self._task_config)
            self._client = self._create_cloudwatchlogs_client()
            self._do_index_data()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to collect cloudwatch logs, error=%s",
                traceback.format_exc(),
            )
        logger.info("End of collecting cloudwatch logs")

    def _load_credentials(self, config: dict) -> AWSCredentialsCache:
        """Load the credentials

        Args:
            config (dict): Config details

        Returns:
            AWSCredentialsCache: Object of AWSCredentialsCache
        """
        scheme, host, port = get_splunkd_access_info(self._meta_config["session_key"])
        service = Service(
            scheme=scheme, host=host, port=port, token=self._meta_config["session_key"]
        )
        service_config = ConfigManager(service)
        factory = AWSCredentialsProviderFactory(service_config, config[tac.region])
        provider = factory.create(config[tac.account], config[tac.aws_iam_role])
        return AWSCredentialsCache(provider)

    def _create_cloudwatchlogs_client(self) -> boto3.client:
        """Creates cloudwatchlogs client

        Returns:
            boto3.client: Object of boto3 client
        """
        return self._credentials.client(
            "logs",
            region_name=self._task_config[tac.region],
            endpoint_url=self._get_logs_endpoint_url(),
            config=tacommon.configure_retry(),
        )

    def _get_logs_endpoint_url(self):
        """Fetches endpoint url for cloudwatchlogs

        Returns:
            str: Endpoint url
        """
        config = self._task_config
        default_logs_endpoint = tacommon.format_default_endpoint_url(
            "logs", config[tac.region]
        )
        logs_endpoint_url = tacommon.get_endpoint_url(
            config, "logs_private_endpoint_url", default_logs_endpoint
        )
        return logs_endpoint_url

    def _need_refresh(self) -> bool:
        """Checks whether credentials needs to be refreshed.


        Returns:
            bool: True if credentials needs refresh False otherwise.
        """
        return self._credentials.need_retire(self._MIN_TTL)

    def _keep_alive(self) -> None:
        """Checks whether the credentials needs to be refreshed and when required refreshes the
        credentials.
        """
        if self._need_refresh():
            logger.info(f"Refreshing credentials.")
            self._credentials.refresh()
            self._client = self._create_cloudwatchlogs_client()

    def _do_index_data(self) -> None:
        """Retrive config details and start data ingestion process"""
        with self._task_config[aclc.lock]:
            while not self._stopped:
                done = self._collect_and_index()
                if done:
                    break

    def _collect_and_index(self) -> None:
        """List streams in the log group and start data ingestion process for streams"""
        task = self._task_config
        logger.info("Start to describe streams")
        try:
            streams = self._describe_cloudwatch_log_streams(task[aclc.log_group_name])
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failure in describing cloudwatch logs streams, error=%s",
                traceback.format_exc(),
            )
            return True

        logger.info("Got %s log streams", len(streams))

        done = self._get_log_events_for_streams(streams)
        if done:
            logger.info("End of describing streams")
            return True
        else:
            logger.info("Continue collecting history data")
            return False

    def _describe_cloudwatch_log_streams(self, group_name: str) -> list:
        """Returns cloudwatchlog streams

        Args:
            group_name (str): Log group namne

        Returns:
            list: List of streams in the log group
        """
        kwargs = {"logGroupName": group_name}
        streams = []
        while True:
            self._keep_alive()
            res = self._client.describe_log_streams(**kwargs)
            streams.extend(res["logStreams"])
            if res.get("nextToken"):
                kwargs["nextToken"] = res["nextToken"]
            else:
                break
        return streams

    def _get_cloudwatch_log_events(
        self, group_name: str, stream_name: str, start_time: int, end_time: int
    ) -> Iterator:
        """Returns cloudwatchlog events

        Args:
            group_name (str): Log group namne
            stream_name (str): Stream name
            start_time (int): Start time
            end_time (int): End time

        Yields:
            Iterator: List of events
        """
        kwargs = {
            "logGroupName": group_name,
            "logStreamName": stream_name,
            "startTime": int(start_time),
            "endTime": int(end_time),
            "startFromHead": True,
        }
        while True:
            self._keep_alive()
            res = self._client.get_log_events(**kwargs)
            events = res.get("events") or []
            yield from events
            next_token = res.get("nextForwardToken")
            if events and next_token:
                kwargs["nextToken"] = next_token
            else:
                break

    def _ignore_stream(self, stream: dict, task: dict, last_event_time: int) -> bool:
        """Ignore the stream data ingestion if latest events are not available in the stream

        Args:
            stream (dict): Stream details
            task (dict): Task details
            last_event_time (int): Checkpoint time

        Returns:
            bool: Returns True if no latest data in the stream otherwise False
        """
        if not task[aclc.stream_matcher].match(stream["logStreamName"]):
            logger.debug(
                "Ignore stream_name=%s due to stream_matcher=%s",
                stream["logStreamName"],
                task[aclc.stream_matcher].pattern,
            )
            return True

        for required in ("firstEventTimestamp", "lastEventTimestamp"):
            if required not in stream:
                return True

        if stream["lastEventTimestamp"] <= last_event_time:
            logger.info(
                "Ignore stream_name=%s because it has no events since %s",
                stream["logStreamName"],
                int(last_event_time),
            )
            return True

        return False

    def migrate_file_checkpoint(self, e_time: int, log_stream: str) -> None:
        """Migrate the file checkpoint to KV Store checkpoint

        Args:
            e_time (int): Checkpoint time
            log_stream (str): Stream name
        """
        logger.info("Migration started for log_stream={}.".format(log_stream))
        self.ckpt.migrate_ckpt(e_time)
        logger.info("Migration completed for log_stream={}.".format(log_stream))

    def _get_log_events_for_streams(self, streams: list) -> None:
        """Fetch events of streams

        Args:
            streams (list): List of stream dicts
        """
        task = self._task_config
        time_win = task[aclc.query_window_size] * 60 * 1000
        ignored_streams = 0

        self.ckpt = checkpointer.CloudWatchLogsCheckpointer(
            task, task[aclc.log_group_name], self._meta_config
        )

        for stream in streams:
            if self._stopped:
                return True
            logger.debug(
                "Start process. log_stream=%s, first_event_timestamp=%d, last_event_timestamp=%d",
                stream.get("logStreamName"),
                stream.get("firstEventTimestamp"),
                stream.get("lastEventTimestamp"),
            )

            self.ckpt.initialise_ckpt_key(stream)

            is_migrated = self.ckpt.get_migration_status()
            if is_migrated:
                self.ckpt.sweep_file_checkpoint(is_migrated)

            ckpt_data, file_ckpt = self.ckpt._load_ckpt()
            s_time = self.ckpt._start_time()

            if self._ignore_stream(stream, task, s_time):
                ignored_streams += 1
                if not ckpt_data and file_ckpt:
                    self.migrate_file_checkpoint(s_time, stream["logStreamName"])
                else:
                    self.ckpt.save(s_time)
                continue

            e_time = s_time + time_win
            if e_time >= stream["lastEventTimestamp"]:
                e_time = stream["lastEventTimestamp"] + 1

            logger.debug(
                "Fetching events for log_stream=%s, start_time=%d, end_time=%d",
                stream["logStreamName"],
                s_time,
                e_time,
            )
            try:
                indexed_events = 0
                results = self._get_cloudwatch_log_events(
                    task[aclc.log_group_name],
                    stream["logStreamName"],
                    s_time,
                    e_time,
                )
                self._index_events(results, stream["logStreamName"])
                indexed_events = 1
                if self._stopped:
                    raise ExitGraceFully
            except ExitGraceFully:
                logger.info(
                    "Saving checkpoint for input before termination due to SIGTERM."
                )
            except Exception:  # pylint: disable=broad-except
                logger.error(
                    "Failure in getting cloudwatch logs events, error=%s",
                    traceback.format_exc(),
                )
                continue
            finally:
                if indexed_events:
                    if not ckpt_data and file_ckpt:
                        self.migrate_file_checkpoint(e_time, stream["logStreamName"])
                    else:
                        self.ckpt.save(e_time)
                    if self._stopped:
                        logger.info("Modular input exited with SIGTERM.")
                        sys.exit(0)

        return ignored_streams == len(streams)

    def _index_events(self, results: Iterator, stream_name: str) -> None:
        """Index the events

        Args:
            results (Iterator): Iterator for the list of events
            stream_name (str): Stream name
        """
        evt_fmt = self._evt_fmt
        task = self._task_config
        region = task[tac.region]
        log_group_name = task[aclc.log_group_name]
        total_event_count = 0
        events = []
        for result in results:
            source = "{region}:{log_group}:{stream}".format(  # pylint: disable=consider-using-f-string
                region=region, log_group=log_group_name, stream=stream_name
            )
            event = evt_fmt.format(
                source=source,
                sourcetype=task[tac.sourcetype],
                index=task[tac.index],
                data=scutil.escape_cdata(result["message"]),
                time=result["timestamp"] / 1000.0,
            )
            events.append(event)

            if len(events) >= aclc.INGESTION_BATCH_SIZE:
                event_count = len(events)
                logger.debug(
                    "Ingesting events for log_stream=%s event_count=%d",
                    stream_name,
                    event_count,
                )
                total_event_count += event_count
                task["writer"].write_events("".join(events))
                events = []

        if events:
            event_count = len(events)
            logger.debug(
                "Ingesting events for log_stream=%s event_count=%d",
                stream_name,
                len(events),
            )
            total_event_count += event_count
            task["writer"].write_events("".join(events))

        logger.info(
            "Total ingested events. log_stream=%s, total_event_count=%d",
            stream_name,
            total_event_count,
        )

    def get_interval(self) -> int:
        """Returns interval."""
        return self._task_config[tac.interval]

    def stop(self) -> None:
        """Stops the input."""
        self._stopped = True

    def get_props(self) -> dict:
        """Returns config."""
        return self._task_config
