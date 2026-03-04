#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
import re
import json
import time
from functools import wraps
from splunksdc import logging
from splunklib import binding
from typing import Any, List, Dict, Union


logger = logging.get_module_logger()


def retry(
    retries: int = 3,
    reraise: bool = True,
    default_return: Any = None,
    exceptions: List = None,
    log_exception: bool = True,
):
    """
    A decorator to run function with max `retries` times if there is exception.

    Args:
        retries (int, optional): Max retries times. Default is 3.
        reraise (bool, optional): Whether exception should be reraised.
        default_return (Any, optional): Default return value for function
            run after max retries and reraise is False.
        exceptions (List, optional): List of exceptions that should retry.
        log_exception (bool, optional): Should log the exception or not.

    Returns:
        The decorator function `do_retry` that takes in a function as input
        and returns a wrapped function with retry functionality.
    """
    max_tries = max(retries, 0) + 1

    def do_retry(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_ex = None
            for i in range(max_tries):
                log_exception = True
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i < 2:
                        logger.warning("{} Hence, retrying..".format(str(e)))
                        log_exception = False
                    if log_exception:
                        logger.error(
                            "Run function: {} failed".format(func.__name__),
                            exc_info=True,
                            stack_info=True,
                        )
                    if not exceptions or any(
                        isinstance(e, exception) for exception in exceptions
                    ):
                        last_ex = e
                        if i < max_tries - 1:
                            time.sleep(2**i)
                    else:
                        raise
            if reraise:
                raise last_ex
            else:
                return default_return

        return wrapper

    return do_retry


class KVStoreCheckpoint:
    def __init__(self, collection_name: str, service: Any, fields={}) -> None:
        """
        KVStore checkpoint

        Args:
            collection_name (str): name of the collection
            service (Any): service
            fields (dict, optional): field object. Defaults to {}.
        """
        self._collection_name = self.get_valid_name(collection_name)
        self._fields = fields
        self._service = service
        self._kv_store = self._service.kvstore
        self._collection = None

    def create_collection(self, **kwargs) -> None:
        """
        Create the new KVStore Collection
        """
        if kwargs.get("accelerated_fields"):
            for k, v in kwargs.get("accelerated_fields").items():
                kwargs["accelerated_fields." + k] = v
            kwargs.pop("accelerated_fields")
        self._kv_store.create(self._collection_name, fields=self._fields, **kwargs)
        logger.info(
            "Created KVStore Collection Successfully: {}".format(self._collection_name)
        )

    @staticmethod
    def delete_collection(KVStore: Any, collection_name: str) -> None:
        """
        Delete the given collection

        Args:
            KVStore (Any): KVStore instance
            collection_name (str): Name of the collection to be deleted
        """
        collection_name = KVStoreCheckpoint.get_valid_name(collection_name)
        try:
            KVStore.delete(collection_name)
            logger.info(f"Deleted KVStore Collection Successfully: {collection_name}.")
        except KeyError as ke:
            logger.debug(
                "Exception while deleting collection.",
                exception=str(ke),
                collection_name=collection_name,
            )
        except Exception as e:
            logger.error(
                "Exception",
                exception=str(e),
                collection_name=collection_name,
            )

    @staticmethod
    def get_valid_name(name: str) -> str:
        """
        Get the name without spl char [except -> "_"]
            ex  => @coll_name_test_^&*
                => coll_name_test

        Args:
            name (str): user provided name

        Returns:
            str: validated name
        """
        return re.sub(r"[^\w]+", "_", name)

    def _is_collection_available(self) -> bool:
        """
        Check if collection available or not

        Returns:
            bool: if collection found
        """
        if self._collection_name not in self._kv_store:
            return False
        return True

    @retry(exceptions=[binding.HTTPError])
    def load_collection(self, **kwargs) -> None:
        """
        This Method used to load | create the KVStore Collection
        """
        # Create the new collection if not exists
        if not self._is_collection_available():
            self.create_collection(**kwargs)

        self._collection = self._kv_store[self._collection_name].data

    @retry(exceptions=[binding.HTTPError])
    def get_collection_data(self) -> Union[Dict, None]:
        """
        This Method is used to retrieve whole collection data

        Returns:
            Union[Dict, None]: checkpoint details
        """
        try:
            data = self._collection.query()
        except binding.HTTPError as e:
            if e.status != 404:
                logger.error(
                    "Unable to get checkpoint details",
                    exc_info=True,
                    stack_info=True,
                )
                raise
            return None
        return data

    @retry(exceptions=[binding.HTTPError])
    def get(self, checkpoint_key: str) -> Union[Dict, None]:
        """
        Get checkpoint details based on provided key

        Args:
            checkpoint_key (str): unique key

        Returns:
            Union[Dict, None]: checkpoint details
        """
        try:
            data = self._collection.query_by_id(id=checkpoint_key)
        except binding.HTTPError as e:
            if e.status != 404:
                logger.error(
                    "Unable to get checkpoint details",
                    exc_info=True,
                    stack_info=True,
                )
                raise
            return None
        return data

    @retry(exceptions=[binding.HTTPError])
    def save(self, record: Dict) -> None:
        """
        Inserts a single record into this collection. If the record does not
        contain an _key field, it will be generated.

        Args:
            record (Dict): A dictionary containing the record to be inserted.

        Returns:
            None
        """
        self._collection.insert(record)

    @retry(exceptions=[binding.HTTPError])
    def batch_save(self, records: List) -> None:
        """
        Inserts a batch of records into this collection. If a record does not contain
        an _key field, it will be generated.

        Args:
            records (List): A list of dictionaries, each containing a record
                to be inserted.

        Returns:
            None
        """
        self._collection.batch_save(*records)

    @retry(exceptions=[binding.HTTPError])
    def delete(self, query: Dict = None) -> None:
        """
        Deletes one or more records from the collection using the provided query.
        If no query is provided, all records will be deleted.

        Args:
            query (Dict, optional): A dictionary containing the query to use for
                deleting records. Defaults to None.

        Returns:
            None
        """
        if query:
            query = json.dumps(query)
        self._collection.delete(query)

    @retry(exceptions=[binding.HTTPError])
    def delete_by_id(self, id: str = None) -> Any:
        """
        Deletes the record with the provided ID.

        Args:
            id (str, optional): The ID of the record to delete. Defaults to None.

        Returns:
            Any: The result of the DELETE request.
        """
        self._collection.delete_by_id(id)

    @retry(exceptions=[binding.HTTPError])
    def update(self, checkpoint_key: str, checkpoint_data: Union[Dict, str]) -> Dict:
        """
        Replaces the document with the specified checkpoint key with the provided data.

        Args:
            checkpoint_key (str): The checkpoint key of the document to be replaced.
            checkpoint_data (Union[Dict, str]): The new data to replace the existing
            document with.

        Returns:
            Dict: The ID of the replaced document.
        """
        self._collection.update(checkpoint_key, checkpoint_data)
