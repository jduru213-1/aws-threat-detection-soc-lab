#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
from typing import Any, Generator, Optional, Tuple, Union
from splunk_ta_aws import set_log_level
from splunksdc import logging
from .aws_cloudtrail_lake_conf import Configs
from solnlib.modular_input import checkpointer, event_writer
from solnlib.utils import handle_teardown_signals
from datetime import datetime, timedelta, timezone
import splunk_ta_aws.modinputs.cloudtrail_lake.aws_cloudtrail_lake_consts as aclc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import solnlib.orphan_process_monitor as opm
import signal
import os
import sys
import boto3
import time

logger = logging.get_module_logger()


class QueryStatus:
    QUEUED = "QUEUED"
    FINISHED = "FINISHED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class CloudTrailLakeDataCollector:
    def __init__(
        self,
        splunkd_uri: str,
        session_key: str,
        datainput_name: str,
        input_item: dict,
        service: Any,
    ):
        self.splunkd_uri = splunkd_uri
        self.session_key = session_key
        self.datainput_name = datainput_name
        self.input_item = input_item
        self.service = service

        # Load configs
        self.configs = Configs.load(self.splunkd_uri, self.session_key)

        # Set Log Level
        set_log_level(self.configs[Configs.SETTINGS_LOGGING]["logging"]["level"])

        # Set Proxy
        tacommon.set_proxy_env(self.configs[Configs.SETTINGS_PROXY])
        self.aws_account = input_item.get(tac.aws_account)
        self.aws_iam_role = input_item.get(tac.aws_iam_role)
        self.aws_region = input_item.get(tac.aws_region)
        self.sts_private_endpoint_url = input_item.get("sts_private_endpoint_url")
        self.cloudtrail_private_endpoint_url = input_item.get(
            "cloudtrail_private_endpoint_url"
        )
        self.credentials = self.load_credentials()
        self.client = self.create_cloudtrail_lake_client()
        self.event_data_store_name = input_item.get(aclc.EVENT_DATA_STORE)
        self.input_mode = input_item.get(aclc.INPUT_MODE, aclc.DEFAULT_INPUT_MODE)
        self.start_date_time = input_item.get(
            aclc.START_DATE_TIME, aclc.DEFAULT_START_DATE_TIME
        )
        self.start_date_time = self.convert_to_formatted_string(self.start_date_time)
        self.query_window_size = int(
            input_item.get(aclc.QUERY_WINDOW_SIZE, aclc.DEFAULT_QUERY_WINDOW_SIZE)
        )

        # Create/Load KVStore collection
        self.checkpoint = checkpointer.KVStoreCheckpointer(
            "Splunk_TA_aws_cloudtrail_lake", self.session_key, tac.splunk_ta_aws
        )
        self.checkpoint_key = datainput_name
        self.checkpoint_data = {}
        self.event_writer = event_writer.ClassicEventWriter()
        self.event_ingested = False
        self.orphan_process_checker = opm.OrphanProcessChecker()
        self.cancelled = False
        self.event_data_store_id = self.get_event_data_store_id(
            self.event_data_store_name
        )
        handle_teardown_signals(self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        """
        Handle sigterm gracefully and update the checkpoint
        if events are ingested and checkpoint is not updated to restrict data duplication
        """
        logger.info(f"Exit signal {signum} received.")
        try:
            if self.event_ingested:
                self.checkpoint.update(self.checkpoint_key, self.checkpoint_data)
                logger.info(
                    f"Checkpoint for input saved before termination due to SIGTERM.",
                    input=self.checkpoint_key,
                    value=self.checkpoint_data,
                )
        except Exception as exc:
            logger.error(f"SIGTERM termination error {exc}.")
        sys.exit(0)

    def check_orphan(self) -> bool:
        """
        Orphan process checker.Only work for Linux platform. On Windows platform, is_orphan is
        always False and there is no need to do this monitoring on Windows.

        Returns:
            bool: Status about whether process has become orphan
        """
        if self.orphan_process_checker.is_orphan():
            logger.warning(f"Process {os.getpid()} has become orphan.")
            self.cancelled = True
            return True
        return False

    def load_credentials(self) -> Any:
        """
        Loads credentials

        Returns:
            Any: Credentials which will be used for client creation
        """
        credentials = tacommon.load_credentials_from_cache(
            self.splunkd_uri,
            self.session_key,
            self.aws_account,
            self.aws_iam_role,
            self.aws_region,
            self.sts_private_endpoint_url,
        )
        return credentials

    def need_refresh(self) -> bool:
        """
        Checks whether credentials needs to be refreshed.

        Returns:
            bool: True if credentials needs refresh False otherwise.
        """
        return self.credentials.need_retire(aclc.MIN_TTL)

    def create_cloudtrail_lake_client(self) -> Any:
        """
        Creates cloudtrail lake client using generated credentials


        Returns:
            Any: Cloudtrail lake client.
        """
        if not self.cloudtrail_private_endpoint_url:
            self.cloudtrail_private_endpoint_url = tacommon.format_default_endpoint_url(
                "cloudtrail", self.aws_region
            )
        retry_config = tacommon.configure_retry()
        client = boto3.client(
            "cloudtrail",
            region_name=self.aws_region,
            aws_access_key_id=self.credentials.aws_access_key_id,
            aws_secret_access_key=self.credentials.aws_secret_access_key,
            aws_session_token=self.credentials.aws_session_token,
            endpoint_url=self.cloudtrail_private_endpoint_url,
            config=retry_config,
        )
        return client

    def keep_alive(self):
        """
        Checks whether the credentials needs to be refreshed and when required refreshes the
        credentials.
        """
        if self.need_refresh():
            logger.info(f"Refreshing credentials.")
            self.credentials = self.load_credentials()
            self.client = self.create_cloudtrail_lake_client()

    def get_event_data_store_id(
        self, event_data_store_name: str, next_token: Optional[str] = None
    ) -> str:
        """
        Finds corresponding event_data_store_id for event_data_store_name

        Args:
            event_data_store_name (str):Event data store name
            next_token (Optional[str], optional): Next Token which will be used for pagination. Defaults to None.

        Raises:
            Exception: An exception would be raised if not able to find a event_data_store_id for corresponding
                       event_data_store_name.

        Returns:
            str: event_data_store_id
        """
        checkpoint_data = self.checkpoint.get(self.checkpoint_key) or {}
        if checkpoint_data:
            checkpoint_event_data_store_id = checkpoint_data.get(
                aclc.EVENT_DATA_STORE_ID
            )
            return checkpoint_event_data_store_id
        params = {"MaxResults": aclc.MAX_RESULTS}
        while True:
            if self.check_orphan():
                break
            self.keep_alive()
            if next_token:
                params["NextToken"] = next_token
            response = self.client.list_event_data_stores(**params)
            event_data_stores = response.get("EventDataStores", [])
            for event_data_store in event_data_stores:
                if event_data_store.get("Name") == event_data_store_name:
                    return event_data_store.get("EventDataStoreArn").split("/")[1]
            next_token = response.get("NextToken")
            if not next_token:
                break
        raise Exception(
            f"Could not retrieve event data store id for the specified event data store name."
        )

    def get_query_id(self, query_statement: str) -> str:
        """
        Starts executing the query and returns the query_id for given query_statement

        Args:
            query_statement (str): The query_statement which will be executed.

        Raises:
            error: Maximum number of concurrent queries allowed by cloudtrail lake to run are 10.
                   When this limit is exceeded MaxConcurrentQueriesException would be raised by 'start_query'.
                   To recover from this would retry on exponential basis for MAX_RETRIES times.If it still doesn't recover
                   the exception would be raised

        Returns:
            str: Query id of the query which is executing.
        """
        query_id = self.checkpoint_data.get(aclc.QUERY_ID)
        if query_id:
            return query_id
        params = {"QueryStatement": query_statement}
        MAX_RETRIES = aclc.MAX_RETRIES + 1
        for attempt in range(MAX_RETRIES):
            if self.check_orphan():
                break
            self.keep_alive()
            try:
                start_query_response = self.client.start_query(**params)
            except self.client.exceptions.MaxConcurrentQueriesException as error:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Maximum concurrent queries limit exceeded hence retrying the request."
                    )
                    time.sleep(2**attempt)
            else:
                query_id = start_query_response["QueryId"]
                return query_id
        else:
            logger.warning(f"Maxmium number of retries has been exhausted.")
            raise error

    def get_query_status(self, query_id: str) -> Tuple[str, dict]:
        """
        Monitors the query status and when it is either of
        FINISHED,TIMED_OUT,CANCELLED,FAILED returns it along with its response.

        Args:
            query_id (str): Query id obtained from get_query_id

        Raises:
            Exception: The exception would be raised when the query remains in QUEUED status
                       for more than MAX_QUEUED_TIMEOUT seconds.

        Returns:
            Tuple[str,dict]: Query status and its response.
        """
        start_time = time.time()
        current_delay = aclc.INITIAL_DELAY
        while True:
            if self.check_orphan():
                break
            self.keep_alive()
            describe_query_response = self.client.describe_query(QueryId=query_id)
            query_status = describe_query_response["QueryStatus"].upper()
            logger.debug(
                f"Executing Query.", query_id=query_id, query_status=query_status
            )
            if query_status == QueryStatus.QUEUED:
                elapsed_time = time.time() - start_time
                if elapsed_time > aclc.MAX_QUEUED_TIMEOUT:
                    raise Exception(
                        f"Query remained in {query_status} for more than {aclc.MAX_QUEUED_TIMEOUT} seconds."
                    )
                time.sleep(current_delay)
                current_delay = min(current_delay * 2, aclc.MAX_DELAY)
            elif query_status in (
                QueryStatus.FINISHED,
                QueryStatus.CANCELLED,
                QueryStatus.FAILED,
                QueryStatus.TIMED_OUT,
            ):
                return query_status, describe_query_response

    def get_query_results(
        self, query_id: str, next_token: str
    ) -> Generator[dict, None, None]:
        """
        Fetches results for a query_id which has reached 'FINISHED' state.

        Args:
            query_id (str): A query id which is having 'FINISHED' state.
            next_token (str): Next Token which will be used for pagination.

        Yields:
            Generator[dict,None,None]: After fetching results of each page its response will be yielded.
        """
        params = {"MaxQueryResults": aclc.MAX_QUERY_RESULTS, "QueryId": query_id}
        while True:
            if self.check_orphan():
                break
            self.keep_alive()
            if next_token:
                params["NextToken"] = next_token
            response = self.client.get_query_results(**params)
            next_token = response.get("NextToken")
            yield response
            if not next_token:
                break

    def convert_string_to_date(self, input_string: str) -> datetime:
        """
        Converts the given string which is in format '%Y-%m-%d %H:%M:%S'
        to its corresponding datetime equivalent.

        Args:
            input_string (str): Input string in '%Y-%m-%d %H:%M:%S'

        Returns:
            datetime: Datetime object for given input_string
        """
        return datetime.strptime(input_string, "%Y-%m-%d %H:%M:%S")

    def convert_date_to_string(self, input_date: datetime) -> str:
        """
        Converts the given datetime object to its corresponding string equivalent
        in '%Y-%m-%d %H:%M:%S' format

        Args:
            input_date (datetime):The datetime object which is to be converted to string

        Returns:
            str: String in '%Y-%m-%d %H:%M:%S' format.
        """
        return input_date.strftime("%Y-%m-%d %H:%M:%S")

    def convert_to_formatted_string(self, input_value: Union[str, datetime]) -> str:
        """
        Converts the given input_value to the valid formatted string which is expected by API.

        Args:
            input_value (Union[str, datetime]): The input_value can either be a string object
                                                in '%Y-%m-%dT%H:%M:%S' format or valid datetime object

        Returns:
            str: String in '%Y-%m-%d %H:%M:%S' format.
        """
        if isinstance(input_value, datetime):
            # If input is already a datetime object, convert to the desired format
            formatted_string = input_value.strftime("%Y-%m-%d %H:%M:%S")
            return formatted_string
        elif isinstance(input_value, str):
            # Attempt to parse input as datetime object
            input_datetime = datetime.strptime(input_value, "%Y-%m-%dT%H:%M:%S")
            # If successful, convert to the desired format
            formatted_string = input_datetime.strftime("%Y-%m-%d %H:%M:%S")
            return formatted_string

    def get_chunk_start_date_time(self) -> str:
        """
        Fetches the current_start_date_time. For first invocation this would be fetched from input params
        and for subsequent invocations this would be fetched from checkpoint

        Returns:
            str: Current chunk's start_date_time
        """
        chunk_start_date_time = self.checkpoint_data.get(aclc.START_DATE_TIME)
        return chunk_start_date_time

    def get_chunk_end_date_time(
        self,
        current_chunk_start_date_time: datetime,
        query_window_size: int,
        end_date_time: datetime,
    ) -> str:
        """
        Calculates the current_chunk_end_date_time based on current_start_date_time
        and query_window_size.

        Args:
            current_chunk_start_date_time (datetime): start_date_time of current_chunk
            query_window_size (int): Window size.This will be used for calculating current chunk's end_date_time
            end_date_time (datetime): For 'index_once' input mode this value would be fetched from input configuration.
                                      For the 'continuous_monitor' mode this will be current_utc_time-delay_throttle.

        Returns:
            str: Current chunk's end_date_time
        """
        checkpoint_end_date_time = self.checkpoint_data.get(aclc.END_DATE_TIME)
        if checkpoint_end_date_time:
            return checkpoint_end_date_time

        current_chunk_end_date_time = current_chunk_start_date_time + timedelta(
            minutes=query_window_size
        )
        if current_chunk_end_date_time < end_date_time:
            min_chunk_end_date = current_chunk_end_date_time
        else:
            min_chunk_end_date = end_date_time
        return self.convert_date_to_string(min_chunk_end_date)

    def process_results(
        self,
        result_generator: Generator[dict, None, None],
        current_chunk_start_date_time: str,
        current_chunk_end_date_time: str,
    ) -> None:
        """Process results for current chunk

        Args:
            result_generator (Generator[dict,None,None]): Response obtained from get_results()
            current_chunk_start_date_time (str): start_date_time of current chunk
            current_chunk_end_date_time (str): end_date_time of current chunk
        """
        for page_result in result_generator:
            if self.check_orphan():
                break
            query_result_rows = page_result.get("QueryResultRows")
            next_token = page_result.get("NextToken")
            if next_token:
                logger.debug(f"Received NextToken.")
                self.checkpoint_data.update({"next_token": next_token})
            else:
                self.checkpoint_data.update(
                    {
                        "query_id": "",
                        "start_date_time": current_chunk_end_date_time,
                        "end_date_time": "",
                        "next_token": "",
                    }
                )

            logger.info(
                f"Collected events.",
                event_data_store_name=self.event_data_store_name,
                event_count=len(query_result_rows),
                start_date_time=current_chunk_start_date_time,
                end_date_time=current_chunk_end_date_time,
            )
            self.index_events(query_result_rows)
            self.event_ingested = True
            logger.info(
                f"Ingested events.",
                event_data_store_name=self.event_data_store_name,
                event_count=len(query_result_rows),
                start_date_time=current_chunk_start_date_time,
                end_date_time=current_chunk_end_date_time,
            )
            self.checkpoint.update(self.checkpoint_key, self.checkpoint_data)
            logger.info(
                f"Updated checkpoint.",
                input=self.checkpoint_key,
                value=self.checkpoint_data,
            )
            self.event_ingested = False

    def handle_query_exceptions(self, error: Any, key: str, value: str) -> None:
        """
        Handles QueryIdNotFoundException and InvalidNextTokenException

        Args:
            error (Any): QueryIdNotFound or InvalidNextToken exception.
            key (str): This can either be query_id or next_token which has become invalid/expired.
            value (str): Value of either query_id or next_token which has expired/become invalid.
        """
        error_message = error.response.get("Error", {}).get("Message")
        error_code = error.response.get("Error", {}).get("Code")
        logger.warning(f"{error_code}:{error_message}.")
        if key == "query_id":
            self.checkpoint_data.update({"query_id": "", "next_token": ""})
        else:
            self.checkpoint_data.update({"next_token": ""})
        self.checkpoint.update(self.checkpoint_key, self.checkpoint_data)
        logger.info(
            f"Updated checkpoint as stored {key} has expired.This may lead to duplication.",
            input=self.checkpoint_key,
            value=self.checkpoint_data,
        )

    def get_events(self, end_date_time: str) -> None:
        """
        Fetches events from cloudtrail lake by executing SQL like query and ingests them.
        Chunking will be controlled using 'query_window_size' parameter.

        Args:
            end_date_time (str): For 'index_once' input mode this value would be fetched from input configuration
                                 For 'continuously_monitor' input mode at every interval invocation this value would be current_utc_time-delay_throttle
        """
        self.checkpoint_data = self.checkpoint.get(self.checkpoint_key) or {}
        logger.info(
            f"Started collecting data for window.",
            event_data_store=self.event_data_store_name,
            start_date_time=self.start_date_time,
            end_date_time=end_date_time,
        )
        if not self.checkpoint_data:
            self.checkpoint_data = {
                "event_data_store": self.event_data_store_name,
                "event_data_store_id": self.event_data_store_id,
                "query_id": "",
                "start_date_time": self.start_date_time,
                "end_date_time": "",
                "next_token": "",
            }
        else:
            logger.debug(
                f"Found existing checkpoint.",
                input=self.checkpoint_key,
                checkpoint_value=self.checkpoint_data,
            )

        parsed_end_date_time = self.convert_string_to_date(end_date_time)
        while True:
            if self.check_orphan():
                break
            current_chunk_start_date_time = self.get_chunk_start_date_time()
            parsed_current_chunk_start_date_time = self.convert_string_to_date(
                current_chunk_start_date_time
            )
            if parsed_current_chunk_start_date_time == parsed_end_date_time:
                break
            next_token = self.checkpoint_data[aclc.NEXT_TOKEN]
            current_chunk_end_date_time = self.get_chunk_end_date_time(
                parsed_current_chunk_start_date_time,
                self.query_window_size,
                parsed_end_date_time,
            )
            self.checkpoint_data.update({"end_date_time": current_chunk_end_date_time})
            query_statement = aclc.QUERY_STATEMENT.format(
                self.event_data_store_id,
                current_chunk_start_date_time,
                current_chunk_end_date_time,
            )
            logger.info(
                f"Collecting data for chunk.",
                start_date_time=current_chunk_start_date_time,
                end_date_time=current_chunk_end_date_time,
            )
            query_id = self.get_query_id(query_statement)
            try:
                query_status, query_response = self.get_query_status(query_id)
            except self.client.exceptions.QueryIdNotFoundException as error:
                """
                Query id is valid for 7 days. A new query will be formed for
                if this exception occurs.This may lead to duplication.
                """
                self.handle_query_exceptions(error, "query_id", query_id)
                continue

            if query_status == QueryStatus.FINISHED:
                query_string = query_response.get("QueryString")
                query_id = query_response.get("QueryId")
                execution_time_in_milliseconds = query_response.get(
                    "QueryStatistics", {}
                ).get("ExecutionTimeInMillis")
                logger.info(
                    f"QueryStatistics.",
                    query_statement=query_string,
                    query_id=query_id,
                    query_execution_time_in_milliseconds=execution_time_in_milliseconds,
                )
                self.checkpoint_data.update({"query_id": query_id})
                result_generator = self.get_query_results(query_id, next_token)
                try:
                    self.process_results(
                        result_generator,
                        current_chunk_start_date_time,
                        current_chunk_end_date_time,
                    )

                except self.client.exceptions.InvalidNextTokenException as error:
                    self.handle_query_exceptions(error, "next_token", next_token)
                    continue

            else:
                # Query results will only be fetched if query_status is 'FINISHED'.For other query_status values
                # an exception would be raised
                error_message = query_response.get("ErrorMessage")
                if query_status == QueryStatus.TIMED_OUT and error_message:
                    raise Exception(
                        f"Error occurred during query execution.Please reduce the query_window_size.,query_status={query_status},error_message={query_response['ErrorMessage']}."
                    )
                elif error_message:
                    raise Exception(
                        f"Error occurred during query execution,query_status={query_status},error_message={query_response['ErrorMessage']}."
                    )

                else:
                    raise Exception(
                        f"The query status='{query_status}'. Results can only be fetched once it reaches the 'FINISHED' state."
                    )
        if not self.cancelled:
            logger.info(
                f"Completed collecting data for window.",
                event_data_store=self.event_data_store_name,
                start_date_time=self.start_date_time,
                end_date_time=end_date_time,
            )

    def get_event_continuous(self) -> None:
        """
        Collects the data for the 'continuously_monitor' input mode.
        At every interval invocation this mode would collect the data till
        current_utc-time-delay_throttle
        """
        delay_throttle = int(
            self.input_item.get(aclc.DELAY_THROTTLE, aclc.DEFAULT_DELAY_THROTTLE)
        )
        current_utc_time = datetime.now(timezone.utc) - timedelta(
            minutes=delay_throttle
        )
        end_date_time = self.convert_date_to_string(current_utc_time)
        self.get_events(end_date_time)

    def get_events_once(self) -> None:
        """
        Collects the data for the 'index_once' input mode.
        This would be called only once as the interval for is -1
        """
        end_date_time = self.input_item.get(aclc.END_DATE_TIME)
        end_date_time = self.convert_to_formatted_string(end_date_time)
        checkpoint_data = self.checkpoint.get(self.checkpoint_key) or {}
        if checkpoint_data:
            checkpoint_start_date_time = checkpoint_data.get(aclc.START_DATE_TIME)
            if checkpoint_start_date_time == end_date_time:
                logger.info(
                    f"Events for input={self.datainput_name} between start_date_time={self.start_date_time} and end_date_time={end_date_time} have already been ingested."
                )
                return
        self.get_events(end_date_time)

    def index_events(self, query_result_rows: list) -> None:
        """
        Ingests the events to splunk
        The actual JSON event will be fetched from 'eventJson' field from the response

        Args:
            query_result_rows (list): The query_results which are going to be ingested
        """
        self.event_writer.write_events(
            [
                self.event_writer.create_event(
                    data=row[0]["eventJson"],
                    index=self.input_item.get("index"),
                    sourcetype=self.input_item.get("sourcetype"),
                    source=self.datainput_name,
                )
                for row in query_result_rows
            ]
        )

    def run(self) -> None:
        """
        Collects the data based on specified input mode.
        """
        if self.input_mode == "continuously_monitor":
            self.get_event_continuous()
        elif self.input_mode == "index_once":
            self.get_events_once()
