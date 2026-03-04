#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for loading kinesis inputs.
"""


import json
import threading
import time
import traceback

import splunksdc.log as logging

from . import aws_kinesis_consts as akc

logger = logging.get_module_logger()


import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.common.util as scutil

from . import aws_kinesis_checkpointer as ackpt
from . import aws_kinesis_common as akcommon


def extract_timestamp(evt, now):
    """Extracts event timestamp."""
    timestamp = evt["timestamp"] if evt.get("timestamp") else now
    return "{0:.3f}".format(  # pylint: disable=consider-using-f-string
        timestamp / 1000.0
    )


@scutil.catch_all(logger, reraise=True, default_result=[])
def handle_cloudwatchlogs_fmt_records(  # pylint: disable=invalid-name
    data, config, writer
):
    """Returns events"""
    index = config.get(tac.index, "default")
    host = config.get(tac.host, "")
    now = time.time() * 1000
    records = json.loads(data)

    events = []
    source = "{region}:{log_group}:{stream}".format(  # pylint: disable=consider-using-f-string
        region=config[tac.region],
        log_group=records["logGroup"],
        stream=records["logStream"],
    )

    for evt in records["logEvents"]:
        if evt["message"].strip():
            event = writer.create_event(
                index=index,
                host=host,
                source=source,
                sourcetype=config.get(tac.sourcetype),
                time=extract_timestamp(evt, now),
                unbroken=False,
                done=False,
                events=evt["message"],
            )
            events.append(event)
        else:
            logger.info("Skipping the message as kinesis data event has a blank value.")
    return events


class KinesisDataLoader:
    """Class for Kinesis data loader."""

    def __init__(self, config):
        """
        :config: dict object
        {
        "interval": 36000,
        "sourcetype": yyy,
        "index": zzz,
        "region": xxx,
        "key_id": aws key id,
        "secret_key": aws secret key
        "stream_name": stream name,
        "shard_id": shard_id,
        "init_stream_position": TRIM_HORIZON or LATEST
        }
        """

        self._config = config
        self._stopped = False
        self._lock = threading.Lock()
        self._ckpt = ackpt.AWSKinesisCheckpointer(config)
        self._source = "{stream_name}:{shard_id}".format(  # pylint: disable=consider-using-f-string
            stream_name=self._config["stream_name"], shard_id=self._config["shard_id"]
        )

    @property
    def datainput(self):
        return self._config[tac.datainput]

    @property
    def stream(self):
        return self._config[akc.stream_name]

    @property
    def shard_id(self):
        return self._config[akc.shard_id]

    def __call__(self):
        with logging.LogContext(
            datainput=self.datainput, stream=self.stream, shard_id=self.shard_id
        ):
            self.index_data()

    def index_data(self):
        """Starts collection of data."""
        if self._lock.locked():
            return

        logger.info("Start collecting from Kinesis stream")

        with self._lock:
            try:
                self._do_index_data()
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed collecting from Kinesis stream")
        logger.info("End of collecting from Kinesis stream")

    def _do_index_data(self):
        self._set_stream_position()
        akcommon.set_endpoint_urls(self._config)
        self._client = (  # pylint: disable=attribute-defined-outside-init
            akcommon.KinesisClient(self._config, logger)
        )
        start, total_indexed = time.time(), 0
        for records in self._client.get_records():
            if not records:
                if self.file_ckpt or self.sequence_number is None:
                    if self.sequence_number is None:
                        self.sequence_number = ""
                    self._ckpt.set_sequence_number(self.sequence_number)
                    self.file_ckpt = False
                continue

            if self._stopped:
                return

            logger.debug("Received %d records", len(records))
            total_indexed = self._index_data(records)
            if total_indexed >= 1000:
                logger.info(
                    "Indexing %s records takes=%s seconds",
                    str(total_indexed),
                    time.time() - start,
                )
                start = time.time()
                total_indexed = 0

            self.sequence_number = records[-1]["SequenceNumber"]
            self._ckpt.set_sequence_number(records[-1]["SequenceNumber"])
            if self.file_ckpt:
                self.file_ckpt = False

    def _handle_fmt_record(self, rec, events):
        rec_fmt = self._config.get(akc.record_format, "")
        sourcetype = self._config.get(tac.sourcetype, "aws:kinesis")
        if sourcetype == "aws:cloudwatchlogs:vpcflow" or rec_fmt == akc.cloudwatchlogs:
            try:
                events.extend(
                    handle_cloudwatchlogs_fmt_records(
                        rec["Data"], self._config, self._config[tac.event_writer]
                    )
                )
            except Exception:  # pylint: disable=broad-except
                return False
            else:
                return True
        else:
            return False

    def _index_data(self, records):
        indexed = 0
        events = []
        writer = self._config[tac.event_writer]

        for rec in records:
            if not rec["Data"]:
                continue
            indexed += 1
            handled = self._handle_fmt_record(rec, events)
            if not handled:
                evt_time = tacommon.total_seconds(rec["ApproximateArrivalTimestamp"])

                data = rec["Data"].decode("utf-8").strip()
                if data:
                    data = scutil.try_convert_to_json(data)
                    event = writer.create_event(
                        index=self._config.get(tac.index, "default"),
                        host=self._config.get(tac.host, ""),
                        source=self._source,
                        sourcetype=self._config.get(tac.sourcetype, "aws:kinesis"),
                        time=evt_time,
                        unbroken=False,
                        done=False,
                        events=data,
                    )
                    events.append(event)
                else:
                    logger.info(
                        "Skipping the message as kinesis data event has a blank value."
                    )

        try:
            writer.write_events(events, retry=30)
        except Exception:
            logger.error("Failed to index events, error=%s", traceback.format_exc())
            raise
        logger.debug("Indexed %d records", len(events))
        return indexed

    def get_interval(self):
        """Returns polling interval for input."""
        return self._config.get(tac.polling_interval, 10)

    def stop(self):
        """Stops the kinesis data loader."""
        self._stopped = True
        logger.info("KinesisDataLoader is going to exit")

    def stopped(self):
        """Returns if the config is stopped or not."""
        return self._stopped or self._config[tac.data_loader_mgr].stopped()

    def get_props(self):
        """Returns configs"""
        return self._config

    def _set_stream_position(self):
        self.file_ckpt = False
        self.sequence_number = self._ckpt.sequence_number()
        if self.sequence_number == None:
            (
                self.sequence_number,
                self.file_ckpt,
            ) = self._ckpt.get_ckpt_from_file_checkpoint()

        if self.sequence_number:
            logger.info(
                "Pick up from sequence_number=%s",
                self.sequence_number,
            )
            self._config[akc.sequence_number] = self.sequence_number
            self._config[
                akc.shard_iterator_type
            ] = akcommon.KinesisClient.AFTER_SEQUENCE_NUMBER
        else:
            self._config[akc.shard_iterator_type] = self._config[
                akc.init_stream_position
            ]
