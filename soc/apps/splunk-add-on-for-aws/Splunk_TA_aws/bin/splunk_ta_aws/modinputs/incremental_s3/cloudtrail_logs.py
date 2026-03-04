#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for incremental S3 for Cloudtrail logs input.
"""


import gzip
import json
import os
import re
from io import BytesIO

from splunksdc import logging
import splunk_ta_aws.common.ta_aws_consts as tac

from .handler import AWSLogsTask

logger = logging.get_module_logger()


class CloudTrailLogsDelegate:
    """Class for Cloudtrail logs delegation."""

    @classmethod
    def build(cls, args):
        """Returns delegate."""
        prefix = args.log_file_prefix
        start_date = args.log_start_date
        partitions = args.log_partitions
        log_path_format = args.log_path_format

        if len(prefix) > 0 and not prefix.endswith("/"):
            prefix += "/"

        partitions = re.compile(partitions)

        return cls(prefix, start_date, partitions, log_path_format)

    def __init__(self, prefix, start_date, partitions, log_path_format):
        self._prefix = prefix
        self._start_date = start_date
        self._partitions = partitions
        self._log_path_format = log_path_format

    def create_tasks(self, s3, bucket, namespace):  # pylint: disable=invalid-name
        """Returns tasks."""
        partitions = self._enumerate_partitions(s3, bucket)
        logger.info("Discover partitions finished.", partitions=partitions)

        return [self._make_task(namespace, partition) for partition in partitions]

    def _enumerate_partitions(self, s3, bucket):  # pylint: disable=invalid-name
        partitions = []
        prefix = self._prefix + "AWSLogs/"
        if self._log_path_format == tac.organization_level:
            self._get_organization_partitions(s3, bucket, prefix, partitions)
        else:
            self._get_account_partitions(s3, bucket, prefix, partitions)
        return partitions

    def _get_organization_partitions(self, s3, bucket, prefix, partitions):
        """Get the prefixes at Organization Level"""
        for prefix in bucket.list_folders(s3, prefix):
            self._get_account_partitions(s3, bucket, prefix, partitions)

    def _get_account_partitions(self, s3, bucket, prefix, partitions):
        """Get the prefixes at Account Level"""
        for prefix in bucket.list_folders(s3, prefix):
            prefix += "CloudTrail/"
            regions = bucket.list_folders(s3, prefix)
            regions = list(filter(self._interested, regions))
            partitions.extend(regions)

    def _interested(self, prefix):
        if not self._partitions:
            return True
        if self._partitions.match(prefix):
            return True
        return False

    def create_prefix(self, name, params):  # pylint: disable=unused-argument
        """Returns prefix."""
        return params

    def create_initial_marker(self, name, params):  # pylint: disable=unused-argument
        """Returns marker."""
        return params + self._start_date.strftime("%Y/%m/%d/")

    def create_filter(self):
        """Returns filter."""
        return self._filter

    def create_decoder(self):
        """Returns decoder."""
        return self._decode

    @classmethod
    def _filter(cls, files):
        return [item for item in files if item.key.endswith(".json.gz")]

    @classmethod
    def _decode(cls, job, content):  # pylint: disable=unused-argument
        compressed = BytesIO()
        compressed.write(content)
        compressed.seek(0)

        decompressed = gzip.GzipFile(fileobj=compressed, mode="rb")
        content = json.load(decompressed)
        decompressed.close()
        compressed.close()
        records = "\n".join([json.dumps(item) for item in content.get("Records", [])])
        records = records.encode("utf-8")
        return records

    @classmethod
    def _make_task(cls, namespace, partition):
        suffix = partition
        suffix = suffix.lower().replace("/", "_")
        suffix = suffix[:-1]
        name = os.path.join(namespace, suffix)
        return AWSLogsTask(name, partition)
