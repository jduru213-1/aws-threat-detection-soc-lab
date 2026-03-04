#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for incremental s3 input adapter.
"""


import itertools
import time
from datetime import datetime, timedelta
from sortedcontainers import sorteddict

import boto3
import boto3.session
from botocore.exceptions import ClientError
from dateutil.tz import tzutc
from splunk_ta_aws.common.decoder import UTFStreamDecoder
from splunksdc import logging
from splunksdc.batch import BatchExecutorExit

logger = logging.get_module_logger()


class AWSLogsMarkPad:
    """Class for AWS logs mark pad."""

    OVERLAPPED = 500

    def __init__(self, collection, checkpoint_key):
        self._collection = collection
        self._ckpt_key = checkpoint_key
        self._cached_store = sorteddict.SortedDict()

    def read(self):
        """Reads items."""
        items = self._collection.get(self._ckpt_key)
        if items and items.get("value"):
            for value in items["value"]:
                self._cached_store[value] = None
            return [value for value in items["value"]]
        return []

    def update(self, keys):
        """Update method."""
        keys = keys[-self.OVERLAPPED:]  # fmt: skip
        for key in keys:
            self._cached_store[key] = None
        ckpt_data = {"_key": self._ckpt_key, "value": list(self._cached_store.keys())}
        self._collection.batch_save([ckpt_data])
        items = self._collection.get(self._ckpt_key)

        markers = []
        if items and items.get("value"):
            markers = [value for value in items["value"]]
        delta = len(markers) - self.OVERLAPPED
        if delta > 0:
            expired = markers[:delta]
            for key in expired:
                del self._cached_store[key]
            ckpt_data = {
                "_key": self._ckpt_key,
                "value": list(self._cached_store.keys()),
            }
            self._collection.batch_save([ckpt_data])


class JobStrip:
    """Class for Job strip."""

    def __init__(
        self, key, size, etag, mtime, retried=0
    ):  # pylint: disable=too-many-arguments
        self.key = key
        self.size = size
        self.etag = etag
        self.mtime = mtime
        self.retried = retried


class PleaseRetry(Exception):
    """Class for please retry exception."""

    pass  # pylint: disable=unnecessary-pass


class AWSLogsJobPad:
    """Class for AWS logs job pad."""

    def __init__(self, checkpoint):
        self._store = checkpoint.partition("/PS/")

    def add(self, strip):
        """Adds jobs."""
        key = strip.key
        args = (strip.size, strip.etag, strip.mtime, strip.retried)
        self._store.set(key, args)
        logger.debug("Job added.", key=key)

    def remove(self, key):
        """Removes jobs."""
        self._store.delete(key)
        logger.debug("Job removed.", key=key)

    def jobs(self):
        """Returns jobs."""
        for key, args in self._store.items():
            job = JobStrip(key, *args)
            yield job


class AWSLogsPipelineAdapter:  # pylint: disable=too-many-instance-attributes
    """Class for AWS logs pipeline adapter."""

    _SWEEP_CYCLE = 64
    _EPOCH = datetime(1970, 1, 1, tzinfo=tzutc())
    _MIN_TTL = timedelta(minutes=15)

    def __init__(  # pylint: disable=too-many-arguments
        self,
        app,
        credentials,
        prefix,
        marker,
        key_filter,
        decoder,
        event,
        checkpoint,
        bucket,
        max_retries,
        max_fails,
        collection,
        checkpoint_key,
    ):
        self._app = app
        self._credentials = credentials
        self._prefix = prefix
        self._marker = marker
        self._key_filter = key_filter
        self._decoder = decoder
        self._event = event
        self._checkpoint = checkpoint
        self._bucket = bucket
        self._max_retries = max_retries
        self._max_fails = max_fails
        self._collection = collection
        self._checkpoint_key = checkpoint_key

    def is_aborted(self):
        """Checks if job is aborted or not."""
        return self._app.is_aborted()

    def discover(self):
        """Discover method."""
        checkpoint = self._checkpoint
        bucket = self._bucket
        prefix = self._prefix
        marker = self._marker

        pending = AWSLogsJobPad(checkpoint)
        markpad = AWSLogsMarkPad(self._collection, self._checkpoint_key)

        # process failed keys
        yield self._find_failed_jobs(pending)

        # if there are too many failed keys
        # do not try to get more fresh keys
        if self._count_fails(pending) > self._max_fails:
            logger.error("Too many items in retrying queue.")
            yield BatchExecutorExit(True)

        for cycle in itertools.count():
            if self.is_aborted():
                yield BatchExecutorExit(True)

            if self._credentials.need_retire(self._MIN_TTL):
                logger.info("Credentials will expire soon.")
                yield BatchExecutorExit(False)

            if cycle % self._SWEEP_CYCLE == 0:
                checkpoint.sweep()

            # get more fresh keys
            markers = markpad.read()
            if not markers:
                markers.append(marker)
            marker = markers[0]
            s3_obj = bucket.client(self._credentials)
            files = bucket.list_files(s3_obj, prefix, marker)
            fresh_files = self._find_fresh_files(files, markers)

            for item in files:
                key = item.key
                if key in fresh_files:
                    logger.debug("Fresh file found.", key=key)
                    strip = self.make_job_strip(item)
                    pending.add(strip)
                markers.append(key)

            markpad.update(markers)

            # process fresh keys
            yield self._find_fresh_jobs(pending)

            # no more fresh key
            if not fresh_files:
                yield BatchExecutorExit(True)

    @classmethod
    def make_job_strip(cls, item):
        """Returns job strip object."""
        key = item.key
        size = item.size
        etag = item.etag.lower()
        last_modified = item.last_modified
        delta_to_epoch = last_modified - cls._EPOCH
        mtime = int(delta_to_epoch.total_seconds())
        strip = JobStrip(key, size, etag, mtime)
        return strip

    def do(self, job, s3):  # pylint: disable=invalid-name
        """Do method."""
        # will retry except 404
        try:
            content = self._fetch(job, s3)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Job downloading failed.")
            if isinstance(exc, ClientError):
                code = exc.response["Error"].get(  # pylint: disable=no-member
                    "Code", "Unknown"
                )
                if code in ["NoSuchKey", "InvalidObjectState"]:
                    return exc
            return PleaseRetry()

        # never retry
        try:
            records = self._decoder(job, content)
            return records
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Job decoding failed.")
            return exc

    def done(self, job, result):
        """Done method."""
        checkpoint = self._checkpoint
        pending = AWSLogsJobPad(checkpoint)
        if not isinstance(result, Exception):
            logger.debug("Job success.", key=job.key)
            volume = self._index_records(job, result)
            self._index_summary(job, volume)
            pending.remove(job.key)
            return

        if isinstance(result, PleaseRetry):
            job.retried += 1
            if self._should_retry(job.retried):
                pending.add(job)
                logger.info("Job will retry.", key=job.key, retried=job.retried)
                return

        # fall through
        logger.info("Job failed.", key=job.key)
        pending.remove(job.key)

    def allocate(self):
        """Allocates Session."""
        session = boto3.session.Session()
        s3_obj = self._bucket.client(self._credentials, session)
        return s3_obj

    def _fetch(self, job, s3):  # pylint: disable=invalid-name
        response = s3.get_object(Bucket=self._bucket.name, Key=job.key)
        body = response["Body"]
        content = body.read()
        body.close()
        return content

    def _index_records(self, job, records):
        source = "s3://" + self._bucket.name + "/" + job.key
        records = UTFStreamDecoder.create(records)
        return self._event.write_fileobj(records, source=source)

    def _find_fresh_files(self, files, markers):
        fresh_files = set()
        files = self._key_filter(files)
        for item in files:
            key = item.key
            if key in markers:
                logger.debug("Skip ingested file.", key=key)
                continue
            if key.endswith("/"):
                logger.debug("Ignore placeholder.", key=key)
                continue
            if item.storage_class in ["GLACIER"]:
                logger.info("Ignore archived file.", key=key)
                continue
            size = item.size
            if size == 0:
                logger.debug("Ignore empty file.", key=key)
                continue
            fresh_files.add(key)
        return fresh_files

    def _should_retry(self, retried):
        max_retries = self._max_retries
        if max_retries == -1:
            return True
        return retried <= max_retries

    @staticmethod
    def _count_fails(pad):
        count = 0
        for item in pad.jobs():
            if item.retried > 0:
                count += 1
        return count

    @staticmethod
    def _find_failed_jobs(pad):
        return [item for item in pad.jobs() if item.retried > 0]

    @staticmethod
    def _find_fresh_jobs(pad):
        return [item for item in pad.jobs() if item.retried == 0]

    @staticmethod
    def _index_summary(job, volume):
        mtime = time.gmtime(job.mtime)
        mtime = time.strftime("%Y-%m-%dT%H:%M:%SZ", mtime)
        logger.info(
            "Sent data for indexing.", key=job.key, last_modified=mtime, size=volume
        )
