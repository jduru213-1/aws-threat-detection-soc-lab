#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS Kinesis inputs.
"""


import math
import time
from gzip import GzipFile
from io import BytesIO
from urllib import parse as urlparse

import boto3
import splunk_ta_aws.common.ta_aws_common as tacommon
import botocore.exceptions

from splunk_ta_aws.common import (  # isort: skip
    boto3_proxy_patch,
    ta_aws_common,
    ta_aws_consts,
)


def is_http_ok(response):
    """Returns if Http code is 200/201 or not"""
    return response["ResponseMetadata"]["HTTPStatusCode"] in (200, 201)


def http_code(response):
    """Returns Http code."""
    return response["ResponseMetadata"]["HTTPStatusCode"]


def is_likely_gzip(data):
    """Returns if the data is zipped or not."""
    # Maybe not gzip actually, but we don't care
    if len(data) < 2:
        return False
    return data[0] == 0x1F and data[1] == 0x8B


def assemble_proxy_url(hostname, port, username=None, password=None):
    """Returns proxy endpoint URL."""
    endpoint = "{host}:{port}".format(  # pylint: disable=consider-using-f-string
        host=hostname, port=port
    )
    auth = None
    if username:
        auth = urlparse.quote(username.encode(), safe="")
        if password:
            auth += ":"
            auth += urlparse.quote(password.encode(), safe="")

    if auth:
        return auth + "@" + endpoint
    return endpoint


def set_proxy_env(config):
    """Sets up proxy environment."""
    if not config.get("proxy_hostname"):
        return

    username = config.get("proxy_username")
    password = config.get("proxy_password")
    hostname = config["proxy_hostname"]
    port = config["proxy_port"]
    url = assemble_proxy_url(hostname, port, username, password)
    boto3_proxy_patch.set_proxies("http://" + url, "https://" + url)


def set_endpoint_urls(data):
    """Sets endpoint URLs for input."""
    if not data.get("private_endpoint_enabled", 0) is None:
        private_endpoint_enabled = int(data.get("private_endpoint_enabled", 0))
        if private_endpoint_enabled:
            data["sts_endpoint_url"] = data["sts_private_endpoint_url"]
            data["kinesis_endpoint_url"] = data["kinesis_private_endpoint_url"]


class KinesisClient:  # pylint: disable=too-many-instance-attributes
    """Class for Kinesis client"""

    LATEST = "LATEST"
    TRIM_HORIZON = "TRIM_HORIZON"
    AFTER_SEQUENCE_NUMBER = "AFTER_SEQUENCE_NUMBER"
    AT_SEQUENCE_NUMBER = "AT_SEQUENCE_NUMBER"
    MAX_READ_BPS = 2 * 1024 * 1024

    def __init__(self, config, logger):
        """
        :config: dict object
        {
        "region": xxx,
        "key_id": aws key id,
        "secret_key": aws secret key,
        "stream_name": stream_name,
        "shard_id": shard_id,
        "sequence_number": xxx,
        "shard_iterator_type": 'AT_SEQUENCE_NUMBER'|'AFTER_SEQUENCE_NUMBER'|'TRIM_HORIZON'|'LATEST'
        }
        """
        # Set proxy for boto3
        ta_aws_common.set_proxy_env(config)
        # set_proxy_env(config)
        self._config = config
        self.logger = logger
        self._region_name = config["region"]
        self._splunk_uri = config[ta_aws_consts.server_uri]
        self._session_key = config[ta_aws_consts.session_key]
        self._aws_account = config[ta_aws_consts.aws_account]
        self._aws_iam_role = config[ta_aws_consts.aws_iam_role]
        self._kinesis_endpoint_url = config.get("kinesis_endpoint_url")
        self._sts_endpoint_url = config.get("sts_endpoint_url")
        self._credentials = self._load_credentials()
        self._client = self._create_kinesis_client(self._credentials)

    def _need_refresh(self):
        return self._credentials.need_retire()

    def _load_credentials(self):
        credentials = ta_aws_common.load_credentials_from_cache(
            self._splunk_uri,
            self._session_key,
            self._aws_account,
            self._aws_iam_role,
            self._region_name,
            self._sts_endpoint_url,
        )
        return credentials

    def _create_kinesis_client(self, credentials):
        if not self._kinesis_endpoint_url:
            self._kinesis_endpoint_url = ta_aws_common.format_default_endpoint_url(
                "kinesis", self._region_name
            )
        retry_config = tacommon.configure_retry()
        client = boto3.client(
            "kinesis",
            region_name=self._region_name,
            aws_access_key_id=credentials.aws_access_key_id,
            aws_secret_access_key=credentials.aws_secret_access_key,
            aws_session_token=credentials.aws_session_token,
            endpoint_url=self._kinesis_endpoint_url,
            config=retry_config,
        )
        return client

    def _keep_alive(self):
        if self._need_refresh():
            credentials = self._load_credentials()
            self._client = self._create_kinesis_client(credentials)
            self._credentials = credentials

    def list_streams(self):
        """
        :return: a list of stream names in this region
        """

        stream_names = []
        params = {"Limit": 10000}
        while 1:
            self._keep_alive()
            response = self._client.list_streams(**params)
            if not is_http_ok(response):
                msg = "Failed to list Kinesis streams, errorcode={}".format(  # pylint: disable=consider-using-f-string
                    http_code(response)
                )
                raise Exception(msg)

            stream_names.extend(response.get("StreamNames", []))
            if response.get("HasMoreStreams"):
                params["ExclusiveStartStreamName"] = stream_names[-1]
            else:
                break

        return stream_names

    def describe_streams(self, stream_names=None):
        """
        :param stream_names: a list of stream names, if None, describe all
        streams
        :return: a dict of dict, each dict contains
        {
        'StreamName': 'string',
        'StreamARN': 'string',
        'StreamStatus': 'CREATING'|'DELETING'|'ACTIVE'|'UPDATING',
        'Shards': [
             {
                 'ShardId': 'string',
                 'ParentShardId': 'string',
                 'AdjacentParentShardId': 'string',
                 'HashKeyRange': {
                     'StartingHashKey': 'string',
                     'EndingHashKey': 'string'
                 },
                 'SequenceNumberRange': {
                     'StartingSequenceNumber': 'string',
                     'EndingSequenceNumber': 'string'
                 }
             },...]
        }
        """

        if stream_names is None:
            stream_names = self.list_streams()

        streams = {}
        for stream_name in stream_names:
            self._keep_alive()
            response = self._client.describe_stream(StreamName=stream_name)

            if not is_http_ok(response):
                msg = "Failed to describe Kinesis stream={0}, errorcode={1}".format(  # noqa: F523  # pylint: disable=consider-using-f-string
                    stream_name, http_code(response)
                )
                raise Exception(msg)

            if not response.get("StreamDescription"):
                continue

            streams[stream_name] = response["StreamDescription"]
        return streams

    def put_records(self, events):
        """
        :params events: a list of strings
        :return: a list of error events
        {
        "ErrorCode": xxx,
        "ErrorMessage": xxx,
        "Data": xxx,
        }
        """

        now = str(time.time())
        records = [{"Data": event, "PartitionKey": now} for event in events]

        response = self._client.put_records(
            Records=records, StreamName=self._config["stream_name"]
        )

        if not is_http_ok(response):
            msg = "Failed to put records in stream={0}, errorcode={1}".format(  # noqa: F523  # pylint: disable=consider-using-f-string
                self._config["stream_name"], http_code(response)
            )
            raise Exception(msg)

        error_events = []
        for i, record in enumerate(response["Records"]):
            if record.get("ErrorCode"):
                error_events.append(
                    {
                        "ErrorCode": record["ErrorCode"],
                        "ErrorMessage": record["ErrorMessage"],
                        "Data": events[i],
                    }
                )
        return error_events

    def get_records(self):
        """
        :return: a generator which generates a list of records in the format of
        {
        "Data": raw payload,
        "ApproximateArrivalTimestamp": datetime object,
        "SequenceNumber": seq number,
        "PartitionKey": partition key
        }
        """

        encoding = self._config.get("encoding")
        shard_iter = self.get_shard_iterator()
        while 1:
            self._keep_alive()
            response = self._client.get_records(ShardIterator=shard_iter, Limit=10000)

            if not is_http_ok(response):
                time.sleep(2)
                continue

            shard_iter = response.get("NextShardIterator")
            if not shard_iter:
                break

            records = response.get("Records")
            if not records:
                yield records
                time.sleep(2)
                continue

            size_of_record = 0
            for rec in records:
                size_of_record += len(rec["Data"])
                if encoding == "gzip" or is_likely_gzip(rec["Data"]):
                    gzf = GzipFile(fileobj=BytesIO(rec["Data"]))
                    try:
                        rec["Data"] = gzf.read()
                    except IOError:
                        pass

                # data = rec["Data"].decode("utf-8", errors="ignore")
                # rec["Data"] = data.encode("utf-8")

            self._config["sequence_number"] = records[-1]["SequenceNumber"]
            yield records
            # internal= [1, 5] , AWS said the size_of_record would not larger than 10MB.

            interval = math.ceil(float(size_of_record) / self.MAX_READ_BPS)
            time.sleep(interval)

    def get_shard_iterator(self):
        """Returns shared iterator."""
        iter_type = self._config["shard_iterator_type"]
        if iter_type not in (self.LATEST, self.TRIM_HORIZON) and not self._config.get(
            "sequence_number"
        ):
            self._config["sequence_number"] = self._get_init_sequence_number()

        params = {}
        kk_items = {
            "stream_name": "StreamName",
            "shard_id": "ShardId",
            "sequence_number": "StartingSequenceNumber",
            "shard_iterator_type": "ShardIteratorType",
        }

        for key, k in kk_items.items():
            if self._config.get(key):
                params[k] = self._config[key]

        if self._config.get("sequence_number"):
            params["ShardIteratorType"] = self.AFTER_SEQUENCE_NUMBER

        response = self._client.get_shard_iterator(**params)
        if not is_http_ok(response):
            msg = (
                "Failed to get shard iterator for stream={0}, shard_id={1}, "  # noqa: F523  # pylint: disable=consider-using-f-string
                "errorcode={2}"
            ).format(
                self._config["stream_name"],
                self._config["shard_id"],
                http_code(response),
            )
            raise Exception(msg)
        return response["ShardIterator"]

    def _get_init_sequence_number(self):
        streams = self.describe_streams([self._config["stream_name"]])
        for shard in streams[self._config["stream_name"]]["Shards"]:
            if shard["ShardId"] == self._config["shard_id"]:
                return shard["SequenceNumberRange"]["StartingSequenceNumber"]
        else:  # pylint: disable=useless-else-on-loop
            msg = (
                "Failed to get sequence number for stream_name={0}, "  # pylint: disable=consider-using-f-string
                "shard_id={1}"  # noqa: F523
            ).format(self._config["stream_name"], self._config["shard_id"])
            raise Exception(msg)
