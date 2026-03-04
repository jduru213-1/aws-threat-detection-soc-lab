#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for cloudwatch metrics modinput.
"""


import base64
import hashlib
import json
import re
import threading
import time
import zlib
from datetime import datetime, timedelta

from boto3.session import Session
from dateutil.tz import tzutc
from splunksdc import log as logging
from splunksdc.checkpoint import Partition
from splunksdc.utils import LogExceptions, LogWith

logger = logging.get_module_logger()


class Metric:
    """Class for metric."""

    def __init__(self, namespace, name, dimensions, tags=None):
        self._namespace = namespace
        self._name = name
        self._dimensions = dimensions
        self._tags = tags
        self._key = self._make_state_key(namespace, name, dimensions)

    def match(self, filtering):
        """Matches table dimensions."""
        if not filtering.match_name(self._name):
            return False
        if not filtering.match_dimensions(self._dimensions):
            return False
        return True

    def write(self, points, writer):
        """Writes data points."""
        logger.debug("Start writing data points.", key=self._key, count=len(points))
        return writer(points, self._namespace, self._name, self._dimensions, self._tags)

    def get(self, checkpoint):
        """Gets checkpoint."""
        return checkpoint.get(self._key, [])

    def set(self, checkpoint, markers, expiration):
        """Sets checkpoint."""
        return checkpoint.set(self._key, markers, expiration)

    def flatten(self, namespace, name, dimensions, tags):
        """Flattens dimensions."""
        namespace.append(self._namespace)
        name.append(self._name)
        dimensions.append(self._dimensions)
        tags.append(self._tags)

    def query(
        self, client, statistics, period, start_time, end_time
    ):  # pylint: disable=too-many-arguments
        """Queries table points"""
        params = {
            "Namespace": self._namespace,
            "MetricName": self._name,
            "Dimensions": [
                {"Name": key, "Value": value} for key, value in self._dimensions
            ],
            "StartTime": start_time,
            "EndTime": end_time,
            "Period": period,
            "Statistics": statistics,
        }
        response = client.get_metric_statistics(**params)
        points = [MetricPoint(_, period) for _ in response.get("Datapoints", [])]
        points.sort(key=lambda _: _.timestamp)
        logger.debug("GetMetricStatistics success.", key=self._key, count=len(points))
        return points

    @classmethod
    def _make_state_key(cls, namespace, name, dimensions):
        dimensions = json.dumps(dimensions, sort_keys=True)
        seed = "".join([namespace, name, dimensions])
        sha = hashlib.sha224()
        sha.update(seed.encode("utf-8"))
        key = base64.b64encode(sha.digest())
        return key.decode("utf-8")

    @classmethod
    def archive(cls, metrics):
        """Archives data."""
        namespace = []
        name = []
        dimensions = []
        tags = []

        for metric in metrics:
            metric.flatten(namespace, name, dimensions, tags)

        return [namespace, name, dimensions, tags]

    @classmethod
    def restore(cls, quadruples):
        """Restores metrics."""
        return [Metric(*args) for args in zip(*quadruples)]


class MetricStatesCheckpoint:
    """Class for metric states checkpoint."""

    def __init__(self, checkpoint, datainput, config, region, account_id):
        self._checkpoint = checkpoint
        self._datainput = datainput
        self._region = region
        self._account_id = account_id
        self._batch = {}
        self._now = time.time
        self._max_documents_per_batch_save = int(
            config._service.confs["limits"]["kvstore"].content.get(
                "max_documents_per_batch_save", 1000
            )
        )

    def format_key(self, key):
        """
        Format checkpoint key
        Args:
            key (_type_): checkpoint key

        Returns:
            _type_: formatted key with input_name, region and account_id
        """
        return "_".join([self._datainput, self._region, self._account_id, key])

    def set(self, key, data, expiration):
        """Sets value."""
        key = self.format_key(key)
        expiration = self._now() + expiration
        ckpt_data = {"_key": key, "markers": data, "expiration": expiration}
        self._batch[ckpt_data["_key"]] = ckpt_data
        if len(self._batch) >= self._max_documents_per_batch_save:
            self.do_batch_checkpoint()

    def do_batch_checkpoint(self):
        """
        Do batch checkpointing
        """
        if self._batch:
            self._checkpoint.batch_save(list(self._batch.values()))
            self._batch.clear()

    def get(self, key, default):
        """Returns values."""
        key = self.format_key(key)
        item = self._batch.get(key)
        item = item or self._checkpoint.get(key)
        return item["markers"] if item else default

    def sweep(self):
        """Sweeps checkpoint."""
        marker = self._now()
        delete_query = {"expiration": {"$lt": marker}}
        self._checkpoint.delete(delete_query)


class MetricCacheCheckpoint:
    """Class for metric cache checkpoint."""

    def __init__(self, checkpoint):
        self._checkpoint = checkpoint
        self._now = time.time
        self._cache = Partition(checkpoint, "/cache/")

    def archive(self, data, expiration):
        """Updates metrics cache."""
        data = json.dumps(data)
        data = data.encode("utf-8")
        data = zlib.compress(data, 9)
        expiration = self._now() + expiration
        self._cache.set("metrics", data)
        self._cache.set("expiration", expiration)
        logger.debug("Update metrics cache.", size=len(data), expiration=expiration)
        return data

    def restore(self):
        """Restores metrics."""
        item = self._cache.find("metrics")
        if not item:
            return []
        data = item.value
        data = zlib.decompress(data)
        data = json.loads(data)
        logger.debug("Load metrics from cache.")
        return data

    def need_refresh(self):
        """Checks if value is expired or not."""
        item = self._cache.find("expiration")
        if not item:
            return True
        return item.value < self._now()


class MetricFilter:
    """Class for metric filter."""

    def __init__(self, names, dimensions):
        self._names = self._create_pattern_for_names(names)
        self._dimensions = self._create_pattern_for_dimensions(dimensions)

    def get_dimension_keys(self):
        """Returns dimension keys."""
        keys = list(self._dimensions.keys())
        keys.sort()
        return tuple(keys)

    def match_dimensions(self, dimensions):
        """Returns alll cloudwatch dimensions."""
        if len(dimensions) != len(self._dimensions):
            return False

        return all(  # pylint: disable=use-a-generator
            [self._match_one_dimension(key, value) for key, value in dimensions]
        )

    def _match_one_dimension(self, key, value):
        if key not in self._dimensions:
            return False
        pattern = self._dimensions[key]
        return pattern.match(value)

    def match_name(self, name):
        """Returns match_name."""
        return self._names.match(name)

    @classmethod
    def _create_pattern_for_names(cls, regex):
        if isinstance(regex, list):
            regex = "|".join(regex)
        return re.compile(regex)

    @classmethod
    def _create_pattern_for_dimensions(cls, rules):
        dims = {}
        for key, regex in rules.items():
            if isinstance(regex, list):
                regex = "|".join(regex)
            dims[key] = re.compile(regex)
        return dims


class MetricPoint:
    """Class for metric point."""

    _EPOCH = datetime(1970, 1, 1, tzinfo=tzutc())

    def __init__(self, point, period):
        moment = point["Timestamp"]
        self._timestamp = self._datetime_to_timestamp(moment)
        self._value = {k: v for k, v in point.items() if k != "Timestamp"}
        self._period = period

    @property
    def timestamp(self):
        """Returns timestamp"""
        return self._timestamp

    @property
    def iso1806(self):
        """Returns time."""
        moment = datetime.utcfromtimestamp(self._timestamp)
        return moment.strftime("%Y-%m-%dT%H:%M:%SZ")

    @property
    def value(self):
        """Returns value."""
        return self._value

    @property
    def period(self):
        """Returns period."""
        return self._period

    @classmethod
    def _datetime_to_timestamp(cls, dt):  # pylint: disable=invalid-name
        elapse = dt - cls._EPOCH
        return elapse.total_seconds()


class MetricQueryResult:
    """Class for metric query result."""

    def __init__(self):
        self._metrics = []
        self._points = []

    def append(self, metric, points):
        """Appends metrics."""
        self._metrics.append(metric)
        self._points.append(points)

    def __iter__(self):
        return zip(self._metrics, self._points)


class MetricQuery:
    """Class for metric query."""

    def __init__(
        self, metrics, statistics, period, start_time, end_time
    ):  # pylint: disable=too-many-arguments
        self._metrics = metrics
        self._statistics = statistics
        self._period = period
        self._start_time = start_time
        self._end_time = end_time

    def run(self, client):
        """Runs cloudwatch metric input."""
        result = MetricQueryResult()
        for metric in self._metrics:
            points = metric.query(
                client, self._statistics, self._period, self._start_time, self._end_time
            )
            result.append(metric, points)
        return result


class MetricQueryBuilder:
    """Class for metric query builder."""

    def __init__(self, statistics, period, query_window_size):
        self._statistics = statistics
        self._period = period
        self._query_window_size = query_window_size
        self._query_batch_size = 64
        self._now = time.time

    def _make_time_range(self):
        elapse = self._now() // self._period * self._period
        end_time = datetime.utcfromtimestamp(elapse)
        seconds = self._query_window_size * self._period
        start_time = end_time - timedelta(seconds=seconds)
        return start_time, end_time

    def create_batches(self, metrics):
        """Creates batches"""
        start_time, end_time = self._make_time_range()
        queries = []
        args = self._statistics, self._period, start_time, end_time
        logger.debug(
            "Create metric query.",
            period=self._period,
            start_time=str(start_time),
            end_time=str(end_time),
        )
        for metrics in self._chunk(  # pylint: disable=redefined-argument-from-local
            metrics, self._query_batch_size
        ):
            query = MetricQuery(metrics, *args)
            queries.append(query)
        for queries in self._chunk(queries, self._query_batch_size):
            yield queries

    @classmethod
    def _chunk(cls, seq, size):
        return (seq[pos: pos + size] for pos in range(0, len(seq), size))  # fmt: skip


class MetricQueryExecutor:
    """Class for metric query executor."""

    _tlb = threading.local()

    def __init__(
        self, region, credentials, io, endpoint_url=None
    ):  # pylint: disable=invalid-name
        self._credentials = credentials
        self._region = region
        self._endpoint_url = endpoint_url
        self._io = io
        self._top_ctx = logging.ThreadLocalLoggingStack.top()

    def run(self, batches):
        """Runs cloudwatch metric input."""
        for result in self._io.map(self._run, batches):
            if isinstance(result, Exception):
                logger.warning("Querying metric data points failed.")
                continue
            for metric, points in result:
                yield metric, points

        return 0

    def _create_client(self, session):
        return self._credentials.client(
            "cloudwatch", self._region, session, self._endpoint_url
        )

    @property
    def top_ctx(self):
        """Returns top ctx."""
        return self._top_ctx

    @LogWith(prefix=top_ctx)
    @LogExceptions(
        logger, "An error occurred during querying metric data points.", lambda e: e
    )
    def _run(self, batch):
        session = self._acquire_session()
        client = self._create_client(session)
        return batch.run(client)

    @classmethod
    def _acquire_session(cls):
        if not hasattr(cls._tlb, "session"):
            cls._tlb.session = Session()
        return cls._tlb.session
