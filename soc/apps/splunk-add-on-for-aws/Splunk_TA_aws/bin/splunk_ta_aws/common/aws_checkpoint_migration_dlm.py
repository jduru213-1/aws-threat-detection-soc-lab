#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Checkpoint Migration.
"""


from splunksdc import log as logging
import os
import traceback
import threading
from abc import ABC, abstractmethod

logger = logging.get_module_logger()


class CheckpointMigrationDLM:
    """
    Class for AWS Inspector Checkpoint Migration
    """

    def __init__(self, config, collection, strategy):
        """
        Args:
            config (Any): Config object
            collection (Any): collection object
            strategy (Any): strategy object
        """
        self._config = config
        self._collection = collection
        self._strategy = strategy

    def load_checkpoint(self, state_store, key):
        """
        Loads the checkpoint data from the file checkpoint

        Args:
            state_store (Any): object of File state_store
            key (str): checkpoint key of the file checkpoint
        """

        self._strategy._load_checkpoint(self, state_store, key)

    def migrate(self, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            kwargs: keyword arguments
        """
        self._strategy._migrate(self, **kwargs)

    def _load_file_ckpt_req(self, file_path):
        """
        Check loading file based checkpoint is required or not

        Args:
            file_path (str): path of the chekpoint file

        Returns:
            bool: True or False
        """
        if os.path.exists(file_path):
            return True
        return False

    def _is_sweep_required(self, is_migrated, file_path):
        """
        Check sweeping file checkpoint is required or not

        Args:
            is_migrated (bool): migration flag value - 0 or 1
            file_path (str): file path value

        Returns:
            bool: True or False
        """
        if is_migrated and os.path.exists(file_path):
            return True
        return False

    def remove_file(self, filename: str):
        """
        Used to remove the checkpoint file

        :param filename: checkpoint file path.
        :type filename: ``string``
        """
        try:
            os.remove(filename)
            lock_file = filename.replace(".ckpt", ".lock")
            if os.path.exists(lock_file):
                os.remove(lock_file)
            logger.info("Successfully removed the checkpoint file: {}".format(filename))
        except FileNotFoundError:
            pass
        except:
            logger.error(
                "Failed to remove the checkpoint file: {}. Error: {}".format(
                    filename, traceback.format_exc()
                )
            )


class StrategyInterface(ABC):
    """
    Strategy Interface class
    """

    @abstractmethod
    def _load_checkpoint(self):
        pass

    @abstractmethod
    def _migrate(self):
        pass


class InspectorStrategy(StrategyInterface):
    def _load_checkpoint(self, obj, state_store, key):
        """
        Loads the checkpoint data from the file checkpoint

        Args:
            obj (Any): object of CheckpointMigrationDLM
            state_store (Any): object of the state_store
            key (str): checkpoint key of the file checkpoint
        """

        state = state_store.get_state(key)

        if state:
            if "completed_arns" in state:
                self._unprocessed_assessment_arns = state.get("completed_arns", [])
                self._assessment_last_check_at = state.get("last_check_at", 0)
            else:
                self._unprocessed_findings_arns = state.get("finding_arns", [])
                self._findings_last_check_at = state.get("last_check_at", 0)

    def _migrate(self, obj, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigrationDLM
            kwargs: keyword arguments
        """

        if kwargs["file_type"] == "assessment_runs":
            data = {
                "_key": kwargs["key"],
                "last_check_at": self._assessment_last_check_at,
                "unprocessed_assessment_arns": self._unprocessed_assessment_arns,
                "is_migrated": 1,
            }
        else:
            data = {
                "_key": kwargs["key"],
                "last_check_at": self._findings_last_check_at,
                "unprocessed_findings_arns": self._unprocessed_findings_arns,
                "is_migrated": 1,
            }

        obj._collection.save(data)


class InspectorV2Strategy(StrategyInterface):
    def _load_checkpoint(self, obj, state_store, key):
        """
        Loads the checkpoint data from the file checkpoint

        Args:
            obj (Any): object of CheckpointMigrationDLM
            state_store (Any): object of the state_store
            key (str): checkpoint key of the file checkpoint
        """

        state = state_store.get_state(key)
        if state:
            self._last_check_at = state.get("last_check_at", 0)

    def _migrate(self, obj, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigrationDLM
            kwargs: keyword arguments
        """

        data = {
            "_key": kwargs["key"],
            "last_check_at": self._last_check_at,
            "is_migrated": 1,
        }

        obj._collection.save(data)


class CloudwatchLogsStrategy(StrategyInterface):
    def _load_checkpoint(self, obj, state_store, key):
        pass

    def _migrate(self, obj, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigrationDLM
            kwargs: keyword arguments
        """

        data = {
            "_key": kwargs["key"],
            "start_time": kwargs["end_time"],
            "log_group": kwargs["log_group"],
            "is_migrated": 1,
        }

        obj._collection.save(data)


class ConfigRulesStrategy(StrategyInterface):
    def _load_checkpoint(self, obj, state_store, key):
        pass

    def _migrate(self, obj, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigrationDLM
            kwargs: keyword arguments
        """

        logger.info(
            "Migration started for datainput={} region={} rule={}".format(
                kwargs["datainput"], kwargs["region"], kwargs["rule"]
            )
        )

        data = {
            "_key": kwargs["key"],
            "last_evaluation_time": kwargs["etime"],
            "is_migrated": 1,
        }
        obj._collection.save(data)

        logger.info(
            "Migration completed for datainput={} region={} rule={}".format(
                kwargs["datainput"], kwargs["region"], kwargs["rule"]
            )
        )


class KinesisStrategy(StrategyInterface):
    def _load_checkpoint(self, obj, state_store, key):
        pass

    def _migrate(self, obj, **kwargs):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigrationDLM
            kwargs: keyword arguments
        """
        logger.info(
            "Migration started for datainput={} data_stream={} shard_id={}".format(
                kwargs["datainput"], kwargs["data_stream"], kwargs["shard_id"]
            )
        )
        obj._collection.save(kwargs["data"])
        logger.info(
            "Migration completed for datainput={} data_stream={} shard_id={}".format(
                kwargs["datainput"], kwargs["data_stream"], kwargs["shard_id"]
            )
        )
