#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Incremental S3 input handler.
"""


import os
from collections import namedtuple

import boto3.session
import botocore.endpoint
import botocore.exceptions
import splunk_ta_aws.common.ta_aws_consts as tac
from splunksdc import logging
from splunksdc.batch import BatchExecutor
from splunksdc.utils import LogExceptions

from .adapter import AWSLogsPipelineAdapter
from splunk_ta_aws.common.kv_checkpoint import KVStoreCheckpoint
from splunk_ta_aws.common.checkpoint_migration import (
    CheckpointMigration,
    IncrementalS3Stratgey,
)
import multiprocessing

logger = logging.get_module_logger()


AWSLogsTask = namedtuple("AWSLogsTask", ("name", "params"))


class AWSLogsHandler:  # pylint: disable=too-many-instance-attributes
    """Class for AWS Logs handler."""

    # pylint: disable=too-many-locals
    _EXCEPTIONS = (
        IOError,
        botocore.exceptions.BotoCoreError,
        botocore.exceptions.ClientError,
    )

    def __init__(  # pylint: disable=too-many-arguments
        self,
        settings,
        proxy,
        data_input_name,
        metadata,
        options,
        bucket,
        delegate,
        credentials,
    ):
        self._settings = settings
        self._proxy = proxy
        self._data_input_name = data_input_name
        self._metadata = metadata
        self._options = options
        self._bucket = bucket
        self._delegate = delegate
        self._credentials = credentials
        self._config = None
        self._collection = None

    def run(self, app, config):
        """Runs scheduler for app."""
        self._lock = multiprocessing.Lock()
        self._data_input_kind = self._metadata.stanza.split("://")[0]
        self._collection_name = "_".join(
            [tac.splunk_ta_aws, self._data_input_kind, self._data_input_name]
        )

        data_input_name = self._data_input_name
        opt = self._options
        bucket = self._bucket
        session = boto3.session.Session()
        s3_obj = bucket.client(self._credentials, session)
        tasks = self._delegate.create_tasks(s3_obj, bucket, data_input_name)
        scheduler = app.create_task_scheduler(self.run_task)
        scheduler.set_max_number_of_worker(opt.max_number_of_process)
        for name, params in tasks:
            scheduler.add_task(name, params, 0)

        scheduler.run([app.is_aborted, config.has_expired])
        return 0

    # A pickable wrapper of perform
    def run_task(self, app, name, params):
        """Runs app task."""
        return self.perform(app, name, params)

    def create_config(self, app):
        """Create config object"""
        if not self._config:
            self._config = app.create_config_service()

    def load_collection(self, config):
        """Load the collection"""
        if not self._collection:
            self._collection = KVStoreCheckpoint(
                collection_name=self._collection_name, service=config._service
            )
            self._collection.load_collection()

    @LogExceptions(
        logger, "Task was interrupted by an unhandled exception.", lambda e: -1
    )
    def perform(self, app, name, params):
        """Performs event writing operations."""
        if os.name == "nt":
            self._settings.setup_log_level()
            self._proxy.hook_boto3_get_proxies()

        metadata = self._metadata
        opt = self._options
        bucket = self._bucket
        prefix = self._delegate.create_prefix(name, params)
        marker = self._delegate.create_initial_marker(name, params)
        key_filter = self._delegate.create_filter()
        decoder = self._delegate.create_decoder()
        credentials = self._credentials
        event = app.create_event_writer(**vars(metadata))
        self._ckpt_key = name.rsplit(os.path.sep, 1)[-1]
        self._migration_status_key = "_".join([self._ckpt_key, "migration_status"])

        with self._lock:
            logger.debug("Successfully acquired lock for loading KVStore collection.")
            # config & collection objects from run() are not picklable inside process hence creating new objects in process
            self.create_config(app)
            self.load_collection(self._config)

        is_migrated = self._get_migration_status()
        if not is_migrated:
            self._perform_migration(app, name, self._config)

        with app.open_checkpoint(name) as checkpoint:
            while not app.is_aborted():
                # refresh credential in case it has expired.
                credentials.refresh()
                adapter = AWSLogsPipelineAdapter(
                    app,
                    credentials,
                    prefix,
                    marker,
                    key_filter,
                    decoder,
                    event,
                    checkpoint,
                    bucket,
                    opt.max_retries,
                    opt.max_fails,
                    self._collection,
                    self._ckpt_key,
                )
                pipeline = BatchExecutor(number_of_threads=opt.max_number_of_thread)
                if pipeline.run(adapter):
                    # no more new files
                    break
        return 0

    def _get_migration_status(self):
        """
        Get migration flag value

        Returns:
            bool: 0 or 1
        """
        ckpt = self._collection.get(self._migration_status_key)
        if ckpt:
            return ckpt.get("is_migrated", 0)
        return 0

    def _update_migrate_flag_ckpt(self):
        """
        Update/Add migration flag in the KVStore
        """
        ckpt_data = {"_key": self._migration_status_key, "is_migrated": 1}
        self._collection.save(ckpt_data)

    def _get_checkpoint(self, app, name):
        """
        Checks for existing file based ckpt and returns its path if it exists

        Args:
            app (Any): App object

        Returns:
            path (Any): Path of the file it exists
        """
        file_name = "".join([name, ".ckpt"])
        file_path = os.path.join(app.workspace(), file_name)
        if os.path.isfile(file_path):
            return os.path.join(app.workspace(), name)

    def _perform_migration(self, app, name, config):
        """
        Perform migration of file checkpoint to KVStore

        Args:
            app (Any): App object
            config (Any): Config object
        """
        migrate_ckpt = CheckpointMigration(
            self._collection,
            app,
            config,
            self._data_input_kind,
            self._data_input_name,
            IncrementalS3Stratgey(self._ckpt_key),
        )
        file_ckpt = self._get_checkpoint(app, name)
        if file_ckpt:
            logger.info(f"Migration started for input {self._data_input_name}.")
            migrate_ckpt.load_checkpoint(file_ckpt)
            migrate_ckpt.migrate()
            self._update_migrate_flag_ckpt()
            logger.info(f"Migration completed for input {self._data_input_name}.")
        else:
            self._update_migrate_flag_ckpt()
