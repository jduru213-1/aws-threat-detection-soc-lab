#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS S3 buckets.
"""


from collections import namedtuple

from boto3.s3.inject import download_fileobj
from splunksdc import log as logging

logger = logging.get_module_logger()


class TupleMaker:
    """Class for tuple maker."""

    def __init__(self, typename, recipe):
        self._recipe = recipe
        self._type = namedtuple(typename, recipe.keys())

    def __call__(self, record, **kwargs):
        params = {key: getter(record) for key, getter in self._recipe.items()}
        params.update(kwargs)
        return self._type(**params)


class S3Bucket:
    """Class for S3 bucket."""

    _ListFileResultEntry = TupleMaker(
        "_ListFileResultEntry",
        {
            "key": lambda _: _["Key"],
            "size": lambda _: _["Size"],
            "etag": lambda _: _["ETag"].strip('"'),
            "last_modified": lambda _: _["LastModified"],
            "storage_class": lambda _: _["StorageClass"],
        },
    )

    _FetchFileResult = TupleMaker(
        "_FetchFileResult",
        {
            "key": lambda _: None,
            "size": lambda _: _["ContentLength"],
            "etag": lambda _: _["ETag"],
            "last_modified": lambda _: _["LastModified"],
        },
    )

    def __init__(self, name, region, endpoint_url=None):
        self._name = name
        self._region = region
        self._endpoint_url = endpoint_url

    def list_folders(self, s3, prefix):  # pylint: disable=invalid-name
        """Lists S3 folders."""
        logger.debug("Start listing folders.", prefix=prefix)
        response = s3.list_objects(Bucket=self._name, Delimiter="/", Prefix=prefix)
        prefixes = response.get("CommonPrefixes", [])
        prefixes = [item["Prefix"] for item in prefixes]
        return prefixes

    def list_files(self, s3, prefix, marker):  # pylint: disable=invalid-name
        """lists S3 files."""
        logger.debug("Start listing files.", prefix=prefix, marker=marker)
        response = s3.list_objects(Bucket=self._name, Prefix=prefix, Marker=marker)
        items = response.get("Contents", [])
        return [self._ListFileResultEntry(item) for item in items]

    def client(self, credentials, session=None):
        """Returns client."""
        return credentials.client("s3v4", self._region, session, self._endpoint_url)

    def fetch(self, client, key, fileobj, **kwargs):
        """Fetches S3 object."""
        bucket = self._name
        logger.debug("Start fetching S3 object.", bucket=bucket, key=key)
        response = client.get_object(Bucket=bucket, Key=key, **kwargs)
        body = response["Body"]
        self._blt(body, fileobj)
        body.close()
        fileobj.seek(0)
        return self._FetchFileResult(response, key=key)

    def transfer(self, client, key, fileobj, **kwargs):
        """Transfers S3 object."""
        bucket = self._name
        logger.debug("Start transferring S3 object.", bucket=bucket, key=key)
        headers = client.head_object(Bucket=bucket, Key=key, **kwargs)
        client = _ETagEnforcedClient(client, headers)
        download_fileobj(client, bucket, key, fileobj)
        fileobj.seek(0)
        return self._FetchFileResult(headers)

    @property
    def name(self):
        """Returns name."""
        return self._name

    @property
    def region(self):
        """Returns region."""
        return self._region

    @staticmethod
    def _blt(source, destination, chunk_size=8388608):
        transferred = 0
        while True:
            block = source.read(chunk_size)
            if not block:
                break
            destination.write(block)
            transferred += len(block)
        return transferred


class _ETagEnforcedClient:
    def __init__(self, client, headers):
        self._client = client
        self._headers = headers

    def head_object(self, **kwargs):  # pylint: disable=unused-argument
        """Returns headers."""
        return self._headers

    def get_object(self, **kwargs):
        """Gets object."""
        kwargs = self._enforce_etag(kwargs)
        return self._client.get_object(**kwargs)

    def _enforce_etag(self, kwargs):
        if "ETag" in self._headers:
            kwargs["IfMatch"] = self._headers["ETag"]

        if "VersionId" in self._headers:
            kwargs["VersionId"] = self._headers["VersionId"]
        return kwargs

    def __getattr__(self, item):
        return getattr(self._client, item)
