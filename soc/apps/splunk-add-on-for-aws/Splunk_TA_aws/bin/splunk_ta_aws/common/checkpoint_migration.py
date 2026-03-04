#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
import os
import requests
import traceback
from splunksdc import logging
from splunksdc.checkpoint import Partition
from abc import ABC, abstractmethod


logger = logging.get_module_logger()


class CheckpointMigration:
    def __init__(
        self, collection, app, config, kind: str, input_name: str, strategy
    ) -> None:
        """
        Checkpoint Migration old

        Args:
            collection (_type_): collection object
            app (_type_): app object
            config (_type_): config object
            kind (str): kind of input
            input_name (str): input name
            strategy (_type_): strategy object
        """
        self._collection = collection
        self._app = app
        self._config = config
        self._kind = kind
        self._input_name = input_name
        self._strategy = strategy
        self._ckpt_data = []

    @staticmethod
    def remove_file(filename: str) -> None:
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
        except:
            logger.error(
                "Failed to remove the checkpoint file: {}. Error: {}".format(
                    filename, traceback.format_exc()
                )
            )

    def load_checkpoint(self, filename: str) -> None:
        """
        This method used to load the file-based checkpoint

        Args:
            filename (str): filename or input name
        """
        with self._app.open_checkpoint(filename) as fp_checkpoint:
            fp_checkpoint.sweep()
            self._strategy._load_checkpoint(self, fp_checkpoint)
        logger.info("Successfully loaded the checkpoint for input: {}".format(filename))

    def migrate(self):
        """
        This method used the migrate the checkpoint to KV Store
        """
        # get the max batch save from limits.conf if specified else default 1000
        max_documents_per_batch_save: int = int(
            self._config._service.confs["limits"]["kvstore"].content.get(
                "max_documents_per_batch_save", 1000
            )
        )
        while self._ckpt_data:
            self._strategy._migrate(self, max_documents_per_batch_save)
            del self._ckpt_data[:max_documents_per_batch_save]
        logger.info(
            "Successfully stored the checkpoints in the kv-store collection: {}".format(
                self._collection._collection_name
            )
        )

    def send_notification(self, name: str, message: str) -> None:
        """
        Used to send the notification splunk UI.

        :param name: message name or key.
        :type input_name: ``string``
        :param message: message value.
        :type input_name: ``string``
        """
        url: str = "{}://{}:{}/services/messages".format(
            self._app._context._server_scheme,
            self._app._context._server_host,
            self._app._context._server_port,
        )
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "Authorization": "Bearer {}".format(self._config._service.token),
        }
        payload = {
            "name": name,
            "value": message,
            "severity": "info",
        }
        response = requests.post(url, data=payload, headers=headers, verify=False)
        if response.status_code == 201:
            logger.info("Successfully sent the migration notification.")
        else:
            logger.warn("Failed to send the migration notification.")


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


class BillingStrategy(StrategyInterface):
    """
    Billing Strategy Class to load and migrate checkpoint

    Args:
        StrategyInterface (_type_): StrategyInterface class
    """

    def _load_checkpoint(self, obj, fp_checkpoint):
        """
        This method used to load the file-based checkpoint

        Args:
            obj (_type_): object of CheckpointMigration
            fp_checkpoint (_type_): object of file checkpoint
        """
        ckpt_keys = list(fp_checkpoint._indexes)

        for key in ckpt_keys:
            pair = fp_checkpoint.find(key)
            obj._ckpt_data.append({"_key": key, "value": pair.value})

    def _migrate(self, obj, max_documents_per_batch_save):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (_type_): object of CheckpointMigration
            max_documents_per_batch_save (_type_): max documents for batch save call
        """
        obj._collection.batch_save(obj._ckpt_data[:max_documents_per_batch_save])


class CloudWatchStrategy(StrategyInterface):
    """
    CloudWatch Strategy Class to load and migrate checkpoint

    Args:
        StrategyInterface (_type_): StrategyInterface class
    """

    def __init__(self, region, account_id):
        """
        __init__ method
        Args:
            region (_type_): region
            account_id (_type_): account id
        """
        self._region = region
        self._account_id = account_id

    def _load_checkpoint(self, obj, fp_checkpoint):
        """
        This method used to load the file-based checkpoint

        Args:
            obj (_type_): object of CheckpointMigration
            fp_checkpoint (_type_): object of file checkpoint
        """
        obj._ckpt_data = list(Partition(fp_checkpoint, "/states/").items())

    def _migrate(self, obj, max_documents_per_batch_save):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (_type_): object of CheckpointMigration
            max_documents_per_batch_save (_type_): max documents for batch save call
        """
        batch_list = []
        for key, value in obj._ckpt_data[:max_documents_per_batch_save]:
            key = "_".join([obj._input_name, self._region, self._account_id, key])
            batch_list.append(
                {"_key": key, "markers": value[0], "expiration": value[1]}
            )
        obj._collection.batch_save(batch_list)


class IncrementalS3Stratgey(StrategyInterface):
    """
    IncrementalS3 Strategy Class to load and migrate checkpoint

    Args:
        StrategyInterface (Any): StrategyInterface class
    """

    def __init__(self, ckpt_key):
        """
        __init__ method
        Args:
            ckpt_key (String): Name of checkpoint key
        """
        self._ckpt_key = ckpt_key

    def _load_checkpoint(self, obj, fp_checkpoint):
        """
        This method used to load the file-based checkpoint

        Args:
            obj (Any): object of CheckpointMigration
            fp_checkpoint (Any): object of file checkpoint
        """
        obj._ckpt_data = list(Partition(fp_checkpoint, "/MK/").items())

    def _migrate(self, obj, max_documents_per_batch_save):
        """
        This method used the migrate the checkpoint to KV Store

        Args:
            obj (Any): object of CheckpointMigration
            max_documents_per_batch_save (int): max documents for batch save call
        """
        batch_list = []
        value_list = []
        for key, _ in obj._ckpt_data[:max_documents_per_batch_save]:
            value_list.append(key)
        batch_list.append({"_key": self._ckpt_key, "value": value_list})
        obj._collection.batch_save(batch_list)
