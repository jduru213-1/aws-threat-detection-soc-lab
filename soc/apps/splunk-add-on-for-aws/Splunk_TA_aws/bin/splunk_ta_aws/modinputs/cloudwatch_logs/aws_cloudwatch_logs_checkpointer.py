#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Cloudwatchlogs Checkpointer.
"""


import json
import re
import urllib

import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.common.util as scutil
import splunktalib.state_store as ss
from splunk_ta_aws.common import pymd5
from splunklib.client import Service
from splunksdc import logging
import os
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunk_ta_aws.common.aws_checkpoint_migration_dlm import (
    CheckpointMigrationDLM,
    CloudwatchLogsStrategy,
)
from . import aws_cloudwatch_logs_consts as aclc
from . import aws_cloudwatch_logs_conf as aclconf

logger = logging.get_module_logger()


class CloudWatchLogsCheckpointer:
    """Class for Cloudwatchlogs Checkpointer."""

    def __init__(self, config, log_group, meta_config):
        self.kv_ckpt_key = None
        self._ckpt_data = None
        self.meta_config = meta_config
        self.config = config
        self.log_group = log_group
        self.initialise_collection()

    def initialise_collection(self):
        service = self.create_service_obj()

        collection_name = "_".join(
            [
                aclc.cloudwatch_logs_log_ns,
                self.config[tac.stanza_name],
                self.config[tac.region],
            ]
        )
        self._collection = KVStoreCheckpoint(
            collection_name=collection_name, service=service
        )
        self._collection.load_collection()

        # Create the object of the CheckpointMigrationDLM class
        self.ckpt_obj = CheckpointMigrationDLM(
            self.config, self._collection, CloudwatchLogsStrategy()
        )

    def create_service_obj(self):
        """
        This Method is used to create config service object
        """
        server_uri = self.meta_config["server_uri"]
        token = self.meta_config["session_key"]
        appname = self.meta_config["app_name"]
        parts = urllib.parse.urlparse(server_uri)
        scheme = parts.scheme
        server_host = parts.hostname
        server_port = parts.port
        service = Service(
            scheme=scheme,
            host=server_host,
            port=server_port,
            token=token,
            owner="nobody",
            app=appname,
        )

        return service

    def initialise_ckpt_key(self, stream):
        self.stream = stream
        self.kv_ckpt_key = self._get_formatted_kv_ckpt_key()

    def sweep_file_checkpoint(self, is_migrated):
        """
        This method is used to sweep the file checkpoint.

        Args:
            is_migrated (bool): is_migrated flag value 0 or 1
        """

        self.file_ckpt_key = self._get_formatted_file_ckpt_key()
        self.file_path = os.path.join(
            self.config[tac.checkpoint_dir], self.file_ckpt_key
        )

        is_sweep_req = self.ckpt_obj._is_sweep_required(is_migrated, self.file_path)

        if is_sweep_req:
            self.ckpt_obj.remove_file(self.file_path)

    def create_state_store(self):
        """
        This Method is used to create the state object to access the File Checkpoint
        """
        if scutil.is_true(self.config.get(tac.use_kv_store)):
            self.state_store = ss.get_state_store(
                self.config,
                self.config[tac.app_name],
                collection_name=aclc.cloudwatch_logs_log_ns,
                use_kv_store=True,
            )
        else:
            self.state_store = ss.get_state_store(
                self.config, self.config[tac.app_name]
            )

    def migrate_ckpt(self, end_time):
        """
        This method is used to migrate the file checkpoint to KVStore

        Args:
            end_time (Any): end time of the data collection window
        """
        self.ckpt_obj.migrate(
            key=self.kv_ckpt_key, end_time=end_time, log_group=self.log_group
        )

    def get_migration_status(self):
        """
        Get migration flag value

        Returns:
            bool: 0 or 1
        """
        ckpt = self._collection.get(self.kv_ckpt_key)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def _load_ckpt(self):
        """
        This method is used to load the checkpoint data

        Returns:
            ckpt_data (Any): KVStore checkpoint data
            file_ckpt (bool) : file checkpoint present or not (1 oe 0)
        """
        file_ckpt = 0
        try:
            self._ckpt_data = self._collection.get(self.kv_ckpt_key)
            if self._ckpt_data:
                self.start_time = self._ckpt_data.get(
                    "start_time", self.config[aclc.only_after]
                )
            else:
                self.create_state_store()
                self.file_ckpt_key = self._get_formatted_file_ckpt_key()
                state = self.state_store.get_state(self.file_ckpt_key)
                if state:
                    file_ckpt = 1
                    self.start_time = state.get(
                        "start_time", self.config[aclc.only_after]
                    )
                else:
                    self.start_time = self.config[aclc.only_after]

        except Exception:  # pylint: disable=broad-except
            logger.error(
                "Failed to load state for stream=%s",
                self.stream,
            )
            raise

        if "firstEventTimestamp" in self.stream:
            self.start_time = max(
                self.start_time, self.stream["firstEventTimestamp"] - 1
            )

        return self._ckpt_data, file_ckpt

    def _get_formatted_kv_ckpt_key(self):
        """This method is used to create the kvstore checkpoint key"""
        stream_name = self.stream["logStreamName"]
        region = self.config[tac.region]
        return "{}_{}_{}".format(region, self.log_group, stream_name)

    def _get_formatted_file_ckpt_key(self):
        """This method is used to create the file checkpoint key"""
        stream_name = self.stream["logStreamName"]
        stanza_name = self.config[tac.stanza_name]
        region = self.config[tac.region]
        group_name = self.config[aclc.log_group_name]

        prefix = re.sub(r"[^\w\d]", "_", stanza_name)
        key = json.dumps([stanza_name, region, group_name, stream_name])
        key = key.encode("utf-8")
        key = prefix + "_" + pymd5.md5(key).hexdigest()

        return key

    def _start_time(self):
        """Returns start time."""
        return self.start_time

    def save(self, end_time):
        """Saves start time."""
        if self._ckpt_data:
            self._ckpt_data["start_time"] = end_time
            self._collection.batch_save([self._ckpt_data])
        else:
            data = {
                "_key": self.kv_ckpt_key,
                "start_time": end_time,
                "log_group": self.log_group,
                "is_migrated": 1,
            }
            self._collection.save(data)
