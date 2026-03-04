#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling checkpoint for Kinesis inputs.
"""


import time
import os
import urllib
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
import splunktalib.state_store as ss
from splunk_ta_aws.common import ta_aws_common
from splunklib.client import Service
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunk_ta_aws.common.aws_checkpoint_migration_dlm import (
    CheckpointMigrationDLM,
    KinesisStrategy,
)
from . import aws_kinesis_consts as akc

logger = logging.get_module_logger()


class AWSKinesisCheckpointer:
    """Class for AWS kinesis checkpointer."""

    def __init__(self, config):
        self._config = config
        self.file_ckpt = 0

        self.initialise_collection()

    def initialise_collection(self):
        config_service = self.create_service_obj()

        collection_name = "_".join(
            [akc.kinesis_log_ns, self._config[tac.datainput], self._config[tac.region]]
        )

        self._collection = KVStoreCheckpoint(
            collection_name=collection_name, service=config_service
        )
        self._collection.load_collection()

        # Create the object of the CheckpointMigrationDLM class
        self.ckpt_obj = CheckpointMigrationDLM(
            self._config, self._collection, KinesisStrategy()
        )

        self._key = self.get_ckpt_key()

    def get_ckpt_key(self):
        """Returns kvstore checkpoint key."""
        return "{}_{}".format(self._config[akc.stream_name], self._config[akc.shard_id])

    def create_service_obj(self):
        """
        This Method is used to create config service object
        """
        server_uri = self._config["server_uri"]
        token = self._config["session_key"]
        appname = self._config["appName"]
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

    def create_file_ckpt_key(self):
        """Returns file checkpoint key."""

        file_ckpt_key = ta_aws_common.b64encode_text(
            "{}|{}|{}".format(  # pylint: disable=consider-using-f-string
                self._config[akc.stream_name],
                self._config[akc.shard_id],
                self._config[tac.name],
            )
        )
        return file_ckpt_key

    def create_state_store(self):
        """
        This Method is used to create the state object to access the File Checkpoint
        """
        state_store = ss.get_state_store(
            self._config,
            self._config[tac.app_name],
            collection_name="aws_kinesis",
            use_kv_store=self._config.get(tac.use_kv_store),
        )
        return state_store

    def sweep_file_checkpoint(self):
        """
        This method is used to sweep the file checkpoint.
        """

        file_ckpt_key = self.create_file_ckpt_key()

        self.file_path = os.path.join(self._config[tac.checkpoint_dir], file_ckpt_key)

        is_sweep_req = self.ckpt_obj._is_sweep_required(1, self.file_path)

        if is_sweep_req:
            self.ckpt_obj.remove_file(self.file_path)

        data_inputs_filepath = os.path.join(
            self._config[tac.checkpoint_dir], "data_input_ckpts"
        )
        if os.path.exists(data_inputs_filepath):
            self.ckpt_obj.remove_file(data_inputs_filepath)

    def sequence_number(self):  # pylint: disable=inconsistent-return-statements
        """Returns sequence number."""
        self._ckpt_data = self._collection.get(self._key)
        if self._ckpt_data:
            return self._ckpt_data["sequence_number"]

    def get_ckpt_from_file_checkpoint(self):
        """This method is used to get the checkpoint from file"""

        file_ckpt_key = self.create_file_ckpt_key()
        state_store = self.create_state_store()
        state = state_store.get_state(file_ckpt_key)
        if state:
            self.file_ckpt = 1
            return state["sequence_number"], True

        return None, False

    def set_sequence_number(self, seq_num):
        """Sets up sequence number."""
        if not self._ckpt_data:
            self._ckpt_data = {"_key": self._key, "sequence_number": seq_num}
            if self.file_ckpt:
                self.ckpt_obj.migrate(
                    datainput=self._config[tac.datainput],
                    data_stream=self._config["stream_name"],
                    shard_id=self._config["shard_id"],
                    data=self._ckpt_data,
                )
                self.sweep_file_checkpoint()
                self.file_ckpt = 0
            else:
                self._collection.save(self._ckpt_data)
        else:
            self._ckpt_data["sequence_number"] = seq_num
            self._collection.batch_save([self._ckpt_data])
