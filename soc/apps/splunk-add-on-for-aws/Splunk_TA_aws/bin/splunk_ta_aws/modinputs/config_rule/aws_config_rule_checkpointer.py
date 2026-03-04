#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for checkpoint handling for AWS config rule input.
"""


import base64
import json
import os
import urllib

from splunklib.client import Service
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunk_ta_aws.common.aws_checkpoint_migration_dlm import (
    CheckpointMigrationDLM,
    ConfigRulesStrategy,
)
from splunksdc import logging
from . import aws_config_rule_consts as acc
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.state_store as ss

logger = logging.get_module_logger()


class AWSConfigRuleCheckpointer:
    """Class for AWS Config rule checkpointer."""

    def __init__(self, config):
        self._config = config
        self._state_store = None
        self.initialise_collection()

    def initialise_collection(self):
        service = self.create_service_obj()

        self.data_input = "_".join(self._config[tac.datainput].split("_")[:-1])
        self.region = self._config[tac.region]
        collection_name = "_".join([acc.config_log_rule_ns, self.data_input])
        self._collection = KVStoreCheckpoint(
            collection_name=collection_name, service=service
        )
        self._collection.load_collection()

        # Create the object of the CheckpointMigrationDLM class
        self.ckpt_obj = CheckpointMigrationDLM(
            self._config, self._collection, ConfigRulesStrategy()
        )

    def create_service_obj(self):
        """
        This Method is used to create config service object
        """
        server_uri = self._config["server_uri"]
        token = self._config["session_key"]
        appname = self._config["app_name"]
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

    def create_state_store(self):
        """
        This Method is used to create the state object to access the File Checkpoint
        """
        self._state_store = ss.get_state_store(
            self._config,
            self._config[tac.app_name],
            collection_name="aws_config_rule",
            use_kv_store=self._config.get(tac.use_kv_store),
        )

    def get_migration_status(self, rule_name):
        """
        Get migration flag value

        Returns:
            bool: 0 or 1
        """
        self._key = "{}_{}".format(self.region, rule_name)
        ckpt = self._collection.get(self._key)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def sweep_file_checkpoint(self, is_migrated, data_input, rule_name):
        """
        This method is used to sweep the file checkpoint.

        Args:
            is_migrated (bool): is_migrated flag value 0 or 1
        """

        file_ckpt_key = base64.b64encode(
            "{}|{}|{}".format(  # pylint: disable=consider-using-f-string
                self.region, data_input, rule_name
            ).encode()
        )
        self.file_path = os.path.join(
            self._config[tac.checkpoint_dir], file_ckpt_key.decode("utf-8")
        )

        is_sweep_req = self.ckpt_obj._is_sweep_required(is_migrated, self.file_path)

        if is_sweep_req:
            self.ckpt_obj.remove_file(self.file_path)

    def migrate_ckpt(self, etime, config_rule):
        """
        This method is used to migrate the file checkpoint to KVStore

        Args:
            end_time (Any): end time of the data collection window
        """
        self.ckpt_obj.migrate(
            key=self._key,
            etime=etime,
            datainput=self.data_input,
            region=self.region,
            rule=config_rule,
        )

    def last_evaluation_time(  # pylint: disable=inconsistent-return-statements
        self, rule_name
    ):
        """Returns last evaluation time for checkpoint"""
        self._ckpt_data = self._collection.get(self._key)
        if self._ckpt_data:
            return self._ckpt_data["last_evaluation_time"]

        return None

    def get_ckpt_from_file_checkpoint(self, data_input, rule_name):
        """This method is used to get the checkpoint from file"""
        file_ckpt_key = base64.b64encode(
            "{}|{}|{}".format(  # pylint: disable=consider-using-f-string
                self.region, data_input, rule_name
            ).encode()
        )

        if not self._state_store:
            self.create_state_store()

        state = self._state_store.get_state(file_ckpt_key.decode("utf-8"))
        if state:
            return state["last_evaluation_time"], True

        return None, False

    def set_last_evaluation_time(self, etime):
        """Sets last evaluation time for checkpoint."""
        if not self._ckpt_data:
            data = {"_key": self._key, "last_evaluation_time": etime, "is_migrated": 1}
            self._collection.save(data)
        else:
            self._ckpt_data["last_evaluation_time"] = etime
            self._collection.batch_save([self._ckpt_data])
