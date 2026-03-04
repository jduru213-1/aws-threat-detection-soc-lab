#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS inspector v2 data loader.
"""


import datetime
import math
import threading
import time
import sys
import os
import traceback
from operator import le  # noqa: F401 # pylint: disable=unused-import

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from . import aws_inspector_v2_conf as aiconf
from . import aws_inspector_v2_consts as aiconsts
from splunk_ta_aws.common.aws_checkpoint_migration_dlm import (
    CheckpointMigrationDLM,
    InspectorV2Strategy,
)
from botocore.exceptions import ClientError
from splunksdc import log as logging
from splunktalib import state_store
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunksdc.utils import LogWith  # isort: skip

BUFFER_TIME = 120  # keeping buffer for end-date filter
START_TIME = 1  # keeping 1 sec extra for Iclusive date-time filter
MINUS_SEC = 1  # to avoid data loss in case of conf-reload or restart
logger = logging.get_module_logger()


class ExitGraceFully(Exception):
    pass


class AWSInspectorV2FindingsDataLoader:  # pylint: disable=too-many-instance-attributes
    """Class for AWS inspector v2 findings data loader."""

    def __init__(self, config, client, account_id, collection):
        self._cli = client
        self._collection = collection
        self._config = config

        self._last_check_at = 0
        self.region = config[tac.region]
        data_input = config[tac.datainput]
        self._source = "{}:{}:inspector:v2:finding".format(  # pylint: disable=consider-using-f-string
            account_id, self.region
        )
        self._source_type = self._config.get(
            tac.sourcetype, "aws:inspector:v2:findings"
        )
        self._ckpt_key = "findings_v2_{}_{}".format(data_input, self.region)

    @property
    def _writer(self):
        return self._config[tac.event_writer]

    def run(self):
        """Run method for input"""
        self._load()
        end = int(time.time()) - BUFFER_TIME
        begin = self._last_check_at + START_TIME  # adding 1 sec
        time_start = time.perf_counter()
        self._get_findings(begin, end)
        time_stop = time.perf_counter()
        total_time_elapsed = time_stop - time_start
        logger.info(
            "Total input execution time in seconds. execution_time=%s",
            round(total_time_elapsed, 2),
        )

    def _get_findings(self, begin_timestamp, end_timestamp):
        # boto3 do not accept unix timestamp on windows
        # cast to datetime by hand
        begin = datetime.datetime.utcfromtimestamp(begin_timestamp)
        end = datetime.datetime.utcfromtimestamp(end_timestamp)
        params = {
            "filterCriteria": {
                "updatedAt": [{"startInclusive": begin, "endInclusive": end}]
            },
            "sortCriteria": {"field": "LAST_OBSERVED_AT", "sortOrder": "ASC"},
        }
        logger.debug("Request params=%s", params)
        paginator = self._cli.get_paginator("list_findings")
        total_findings = 0
        try:
            for page in paginator.paginate(**params):
                for finding in page.get("findings", []):
                    if self._config[tac.data_loader_mgr].stopped():
                        raise ExitGraceFully
                    event = self._writer.create_event(
                        index=self._config.get(tac.index, "default"),
                        host=self._config.get(tac.host, ""),
                        source=self._source,
                        sourcetype=self._source_type,
                        time=None,
                        unbroken=False,
                        done=False,
                        events=finding,
                    )
                    self._writer.write_events((event,))
                    total_findings += 1
            self._last_check_at = end_timestamp
            logger.info("Total ingested findings. total_findings=%s", total_findings)
            logger.debug("Saving checkpoint. last_check_at=%s", self._last_check_at)
            self._save()
            logger.info("Saved checkpoint. last_check_at=%s", self._last_check_at)
        except ClientError as ce:  # pylint: disable=invalid-name
            logger.error("Failed to collect data, Exception: %s", ce)
            if ce.response["ResponseMetadata"]["HTTPStatusCode"] == 403:
                logger.error(
                    "Failed to collect inspector v2 findings for region=%s, "
                    "region might be disabled in the AWS console",
                    self.region,
                )
        except ExitGraceFully:
            logger.info("Modular input exited with SIGTERM.")
        finally:
            if self._config[tac.data_loader_mgr].stopped():
                sys.exit(0)

    def _save(self):
        self.ckpt_data["last_check_at"] = math.trunc(self._last_check_at)
        self._collection.batch_save([self.ckpt_data])

    def _load(self):
        self.ckpt_data = self._collection.get(self._ckpt_key)
        if self.ckpt_data:
            self._last_check_at = self.ckpt_data.get("last_check_at", 1)


class AWSInspectorV2DataLoader:
    """Class for AWS inspector v2 data loader."""

    def __init__(self, config):
        self._config = config
        self._stopped = False
        self._lock = threading.Lock()
        self._cli, self._credentials = tacommon.get_service_client(
            self._config, tac.inspector_v2
        )

    def create_state_store(self):
        """
        This Method is used to create the state object to access the File Checkpoint
        """
        self._state_store = state_store.get_state_store(
            self._config,
            self._config[tac.app_name],
            collection_name="aws_inspector_v2",
            use_kv_store=self._config.get(tac.use_kv_store),
        )

    def update_migrate_flag_ckpt(self, key):
        """
        Update/Add migration flag in the KVStore

        Args:
            key (str): checkpoint key stored in the KVStore Collection
        """
        ckpt_data = {"_key": key, "is_migrated": 1}
        self._collection.save(ckpt_data)

    def get_migration_status(self, key):
        """
        Get migration flag value

        Args:
            key (str): KVStore checkpoint key

        Returns:
            bool: 0 or 1
        """
        ckpt = self._collection.get(key)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def migrate_checkpoint(self):
        """
        This method is used to migrate the checkpoint to KVStore if required.
        """

        self.kv_ckpt_key = "findings_v2_{}_{}".format(
            self._config[tac.datainput], self._config[tac.region]
        )

        is_migrated = self.get_migration_status(self.kv_ckpt_key)

        self._state_key = tacommon.b64encode_text(
            "findings_v2_{}_{}".format(  # pylint: disable=consider-using-f-string
                self._config[tac.datainput], self._config[tac.region]
            )
        )

        self._file_path = os.path.join(
            self._config[tac.checkpoint_dir], self._state_key
        )

        is_sweep_req = self.ckpt_obj._is_sweep_required(is_migrated, self._file_path)

        if is_sweep_req:
            self.ckpt_obj.remove_file(self._file_path)

        if not is_migrated:
            self.peform_migration()

        internals_filepath = os.path.join(self._config[tac.checkpoint_dir], "internals")
        if os.path.exists(internals_filepath):
            self.ckpt_obj.remove_file(internals_filepath)

    def peform_migration(self):
        load_file_ckpt = self.ckpt_obj._load_file_ckpt_req(self._file_path)

        if load_file_ckpt:
            self.create_state_store()
            logger.info(f"Migration started for input {self.kv_ckpt_key}.")
            self.ckpt_obj.load_checkpoint(self._state_store, self._state_key)
            logger.info(
                "Successfully loaded the checkpoint for input: {}".format(
                    self._config[tac.datainput]
                )
            )
            self.ckpt_obj.migrate(key=self.kv_ckpt_key)
            logger.info(f"Migration completed for input {self.kv_ckpt_key}.")
        else:
            self.update_migrate_flag_ckpt(self.kv_ckpt_key)

    def _do_indexing(self):
        if self._credentials.need_retire():
            self._cli, self._credentials = tacommon.get_service_client(
                self._config, tac.inspector_v2
            )
        account_id = self._credentials.account_id

        # Create the config service object
        service = aiconf.create_service_obj(self._config)
        collection_name = aiconsts.inspector_v2_log_ns
        self._collection = KVStoreCheckpoint(
            collection_name=collection_name, service=service
        )
        self._collection.load_collection()

        # Create the object of the CheckpointMigrationDLM class
        self.ckpt_obj = CheckpointMigrationDLM(
            self._config, self._collection, InspectorV2Strategy()
        )

        # Migrate the file checkpoint to KVStore Checkpoint.
        self.migrate_checkpoint()
        AWSInspectorV2FindingsDataLoader(
            self._config, self._cli, account_id, self._collection
        ).run()

    @property
    def input_name(self):
        """Returns name."""
        return self._config[tac.datainput]

    @property
    def input_region(self):
        """Returns start time."""
        return self._config[tac.region]

    @LogWith(datainput=input_name, region=input_region)
    def __call__(self):
        if self._lock.locked():
            logger.info(
                "Last round of data collection for inspector v2 findings is still running."
            )
            return

        logger.info("Start collecting inspector v2 findings.")

        try:
            with self._lock:
                self._do_indexing()
        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to collect inspector v2 findings for region=%s, "
                "datainput=%s, error=%s",
                self._config[tac.region],
                self._config[tac.datainput],
                traceback.format_exc(),
            )
        logger.info("End of collecting inspector v2 findings.")

    def get_interval(self):
        """Returns input polling interval."""
        return self._config[tac.polling_interval]

    def stop(self):
        """Stops the input."""
        self._stopped = True

    def stopped(self):
        """Returns if the input is stopped or not."""
        return self._stopped or self._config[tac.data_loader_mgr].stopped()

    def get_props(self):
        """Returns config."""
        return self._config
