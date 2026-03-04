#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS S3 data loader for generic s3 input.
"""


import datetime
import re
import threading
import time
import uuid

import boto3
import botocore
import queue
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
from botocore.config import Config
from dateutil.parser import parse as parse_timestamp

from . import aws_s3_checkpointer as s3ckpt
from . import aws_s3_common as s3common
from . import aws_s3_consts as asc
from . import s3_key_processer as skp

KEY_SIZE_LIMIT = 1024 * 1024 * 8
logger = logging.get_module_logger()
CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


class DummyKey:
    """Class for Dummy key."""

    class DummyBucket:
        """Class for Dummy Bucket."""

        def __init__(self, name):
            self.name = name

    def __init__(self, bucket_name, key_name):
        self.bucket = DummyKey.DummyBucket(bucket_name)
        self.name = key_name


class S3DataLoader:
    """Class for S3 Data Loader."""

    def __init__(self, config):
        """
        :task_config: dict
        {
           bucket_name: xxx,
           host: xxx,
           prefix: xxx,
           after: xxx,
           key_character_set: xxx,
           secret_key: xxx,
           checkpoint_dir: xxx,
           server_uri: xxx,
           session_key: xxx,
           use_kv_store: xxx,
           is_secure: xxx,
           proxy_hostname: xxx,
           proxy_port: xxx,
           proxy_username: xxx,
           proxy_password: xxx,
           data_loader: xxx,
        }
        """

        self._config = config
        self._lock = threading.Lock()
        self._config[asc.bucket_name] = str(self._config[asc.bucket_name])
        self._stopped = False
        self._credentials_service = tacommon.create_credentials_service(
            self._config[tac.server_uri], self._config[tac.session_key]
        )
        # Set proxy before getting credential by boto3
        tacommon.set_proxy_env(self._config)

    def get_interval(self):
        """Returns interval."""
        return self._config[tac.interval]

    def get_props(self):
        """Returns config."""
        return self._config

    def stop(self):
        """Stops input."""
        self._stopped = True

    def __call__(self):
        with logging.LogContext(
            datainput=self._config[asc.data_input],
            bucket_name=self._config[asc.bucket_name],
        ):
            self.index_data()

    def index_data(self):
        """Starts indexing data."""
        try:
            self._do_index_data()
        except Exception:  # pylint: disable=broad-except
            # start_time and job_uid context are lost outside _do_index_data
            logger.exception(
                "Failed to collect data through generic S3.",
                start_time=self._config[asc.start_time],
                job_uid=self._config[asc.job_uid],
            )

    def _do_index_data(self):
        if self._lock.locked():
            logger.info("The last data ingestion iteration hasn't been completed yet.")
            return

        start = time.time()
        start_time = int(time.time())
        self._config[asc.start_time] = start_time
        self._config[asc.job_uid] = str(uuid.uuid4())
        with logging.LogContext(
            start_time=self._config[asc.start_time], job_uid=self._config[asc.job_uid]
        ):
            logger.info("Start processing.")
            with self._lock:
                self.collect_data()
                if not self._stopped:
                    logger.info("Sweep ckpt file after completion of key discovering.")
                    s3ckpt.S3CkptPool.sweep_all()

            cost = time.time() - start
            logger.info("End of processing!", time_cost=cost)

    def _cleanup_index_ckpt(self, index_store):
        last_modified = self._normalize_last_modified(index_store.last_modified())
        if not last_modified or last_modified == self._config.get(asc.last_modified):
            return

        initial_size = 0
        reaped = 0
        for key_name in list(index_store.keys()):
            initial_size += 1
            if not index_store.get_state(key_name):
                # We are done with this key
                idx_ckpt = index_store.get(key_name)
                key_last_modified = self._normalize_last_modified(
                    idx_ckpt[asc.last_modified]
                )
                if key_last_modified < last_modified:
                    index_store.delete_item(key_name, commit=False)
                    reaped += 1
        index_store.save()
        remaining = initial_size - reaped
        logger.info("Cleaned ckpt items.", total=reaped, remaining=remaining)

    def _list_dir(self, bucket, prefix):
        pass

    def collect_data(self):
        """Starts collection of data."""
        index_store = s3ckpt.S3IndexCheckpointer(self._config)
        logger.info(
            "Start processing",
            last_modified=index_store.last_modified(),
            latest_scanned=index_store.latest_scanned(),
        )
        # check if finished in last interval
        if index_store.latest_scanned() >= self._config[asc.terminal_scan_datetime]:
            logger.info(
                "Data collection already finished",
                latest_scanned=index_store.latest_scanned(),
                terminal_scan_datetime=self._config[asc.terminal_scan_datetime],
            )
            return
        with logging.LogContext(phase="discover_key"):
            self._discover_keys(index_store)
        with logging.LogContext(phase="fetch_key"):
            self._fetch_keys(index_store)

    def _poll_progress(self, index_store):
        logger.info("Poll data collection progress.")
        sleep_time = min(20, self._config[asc.polling_interval])
        while 1:
            if tacommon.sleep_until(sleep_time, self.stopped):
                return

            done, errors, total = 0, 0, 0
            for key_name in index_store.keys():
                total += 1
                key_ckpt = index_store.get_state(key_name)
                # Note when finished data collection, the data collection
                # thread deletes the key ckpt
                if key_ckpt is None:
                    done += 1
                elif key_ckpt[asc.state] == asc.failed:
                    errors += 1

            if done + errors >= total:  # pylint: disable=no-else-break
                logger.info("Poll data collection done.")
                break
            else:
                logger.info(
                    "Data collection(s) going on.", jobs_ongoing=total - done - errors
                )

    def _create_ckpts_for_key(self, key, index_store):
        """
        :return: key_store if doing data collection for this key,
        """

        key_store = s3ckpt.S3KeyCheckpointer(self._config, key)
        if key_store.is_new:
            key_store.set_state(asc.started, flush=False)

        # Register this key in the index ckpt
        index_store.add(key.name, key.last_modified, flush=False)
        return key_store

    def _do_collect_data(self, s3_conn, loader_service, key):
        index_func = skp.create_s3_key_processer(
            s3_conn, self._config, loader_service, key, logger
        )

        while 1:
            try:
                return loader_service.run_io_jobs((index_func,), block=False)
            except queue.Full:
                logger.debug("Job Queue is full.", key=key)
                if key.size < KEY_SIZE_LIMIT:
                    # Do data collection in dispatching thread only if
                    # the key is not too big
                    logger.debug("Dispatch function pigback.", key=key)
                    return index_func()
                else:
                    time.sleep(2)
            except Exception:  # pylint: disable=broad-except
                logger.exception("Failed to run io jobs.", key=key)
                time.sleep(2)

    def stopped(self):
        """Checks if input is stopped or not."""
        return self._stopped

    def _get_s3_client(self, credentials):
        region = self._config.get("aws_s3_region")
        if not region:
            region = "us-east-1"  # Default Region
            pattern = r"s3[.-]([\w-]+)\.amazonaws.com"
            if self._config.get(asc.host_name):
                result = re.search(pattern, self._config[asc.host_name])
                if result:
                    region = result.group(1)
        default_s3_url = tacommon.format_default_endpoint_url("s3", region)
        s3_endpoint_url = tacommon.get_endpoint_url(
            self._config, "s3_private_endpoint_url", default_s3_url
        )
        return boto3.client(
            "s3",
            region_name=region,
            use_ssl=self._config.get("use_ssl", True),
            verify=self._config.get("verify", True),
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token,
            config=Config(signature_version="s3v4"),
            endpoint_url=s3_endpoint_url,
        )

    def _discover_keys(self, index_store):
        def _refresh_creds():
            self.credentials = self._check_and_refresh_bucket(  # pylint: disable=attribute-defined-outside-init
                self.credentials, self.s3_conn
            )

        logger.info("Start of discovering S3 keys.")
        # Scanning start time
        scanning_start_time = datetime.datetime.utcnow().strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )
        self.credentials = (  # pylint: disable=attribute-defined-outside-init
            self._generate_credentials()
        )
        self.s3_conn = (  # pylint: disable=attribute-defined-outside-init
            self._get_s3_client(self.credentials)
        )
        last_modified = self._normalize_last_modified(index_store.last_modified())
        keys = s3common.get_keys(
            _refresh_creds,
            self.s3_conn,
            self._config[asc.bucket_name],
            self._config.get(asc.prefix, ""),
            self._config.get(asc.whitelist),
            self._config.get(asc.blacklist),
            last_modified,
        )

        # Loop all keys from S3 bucket
        found = 0
        for key in keys:
            if self._stopped:
                break
            if self._is_key_indexed(key, index_store, last_modified):
                continue
            # if the key is modified after terminal_scan_datetime
            if key.last_modified >= self._config[asc.terminal_scan_datetime]:
                logger.debug(
                    "Skip S3 key while discovering due to last_modified >= "
                    "terminal_scan_datetime",
                    key=key.name,
                    key_last_modified=key.last_modified,
                    terminal_scan_datetime=self._config[asc.terminal_scan_datetime],
                )
                continue

            key_ckpt = self._create_ckpts_for_key(key, index_store)
            if not key_ckpt.is_new:
                continue
            found += 1
            if found % 100 == 0:
                index_store.flush()

            if found % 10000 == 0:
                logger.info("Discovering S3 keys in progress.", new_key_count=found)
        # Set latest scanning time
        latest_scanned = scanning_start_time
        if latest_scanned > self._config[asc.terminal_scan_datetime]:
            latest_scanned = self._config[asc.terminal_scan_datetime]
        index_store.set_latest_scanned(latest_scanned)
        index_store.flush()

        logger.info("End of discovering S3 keys.", new_key_total=found)

    def _is_key_indexed(  # pylint: disable=inconsistent-return-statements
        self, key, index_store, normalized_last_modified
    ):
        if key.last_modified < normalized_last_modified:
            return True
        try:
            ckpt_idx = index_store.get(key.name)
        except KeyError:
            return False

        # Last modified time is not changed
        prev_last_modified = self._normalize_last_modified(ckpt_idx[asc.last_modified])
        if prev_last_modified >= key.last_modified:
            return True

    def _fetch_keys(self, index_store):
        logger.info("Start of fetching S3 objects.")

        loader_service = self._config[tac.data_loader_mgr]
        credentials = self._generate_credentials()
        s3_conn = self._get_s3_client(credentials)

        # Loop all existing keys
        min_last_modified = "z"
        key_count = 0
        for key_name in index_store.keys():
            if self._stopped:
                break
            if not index_store.get_state(key_name):
                # Already done with this key
                continue
            key_last_modified = self._fetch_key(s3_conn, key_name, loader_service)
            if key_last_modified:
                key_count += 1
                if key_last_modified < min_last_modified:
                    min_last_modified = key_last_modified

            # Check credential and create new S3 connection
            credentials = self._check_and_refresh_bucket(credentials, s3_conn)

        logger.info("End of fetching S3 objects.", pending_key_total=key_count)

        if not self._stopped and key_count > 0:
            logger.info("Update ckpt file.", minimum_last_modified=min_last_modified)
            index_store.set_last_modified(min_last_modified)
            self._cleanup_index_ckpt(index_store)
            self._poll_progress(index_store)

    def _normalize_last_modified(self, last_modified):
        """
        Normalize timestamp of S3 key which is from bucket.get_key method.
        :param last_modified:
        :return:
        """
        try:
            mtime = parse_timestamp(last_modified)
            return mtime.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception:
            logger.exception(
                "Failed to normalize last modified time.",
                minimum_last_modified=last_modified,
            )
            raise

    def _fetch_key(self, s3_conn, key_name, loader_service):
        try:
            key = s3common.get_key(s3_conn, self._config[asc.bucket_name], key_name)
            if key is None:
                raise Exception(
                    "{} has been deleted from bucket_name={}".format(  # pylint: disable=consider-using-f-string
                        key_name, self._config[asc.bucket_name]
                    )
                )
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to get object.", key=key_name)

            # For deleted S3 key etc
            key = DummyKey(self._config[asc.bucket_name], key_name)
            key_store = s3ckpt.S3KeyCheckpointer(self._config, key)
            skp.increase_error_count(
                key_store,
                self._config[asc.max_retries],
                key,
                logger,
                self._config[asc.bucket_name],
                count=self._config[asc.max_retries],
            )
            return None

        # if the key is modified after terminal_scan_datetime
        if key.last_modified >= self._config[asc.terminal_scan_datetime]:
            logger.debug(
                "Skip S3 key while discovering due to last_modified >= "
                "terminal_scan_datetime",
                key=key.name,
                key_last_modified=key.last_modified,
                terminal_scan_datetime=self._config[asc.terminal_scan_datetime],
            )
            return None
        self._do_collect_data(s3_conn, loader_service, key)
        return key.last_modified

    def _check_and_refresh_bucket(self, credentials, client):
        if not credentials.need_retire(CREDENTIAL_THRESHOLD):
            return credentials
        logger.info("Refresh credentials of S3 connection.")
        credentials = self._generate_credentials()

        # Change credentails dynamically inside boto3 client
        client._request_signer._credentials = (  # pylint: disable=protected-access
            botocore.credentials.Credentials(
                credentials.aws_access_key_id,
                credentials.aws_secret_access_key,
                credentials.aws_session_token,
            )
        )

        return credentials

    def _generate_credentials(self):
        sts_endpoint_url = tacommon.get_endpoint_url(
            self._config, "sts_private_endpoint_url"
        )
        return self._credentials_service.load(
            self._config[tac.aws_account],
            self._config.get(tac.aws_iam_role),
            self._config.get("aws_s3_region"),
            endpoint_url=sts_endpoint_url,
        )
