#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for incremental s3 cloudfront accesslogs input.
"""


import gzip
from datetime import datetime
from io import BytesIO

from splunksdc import logging

from .handler import AWSLogsTask

logger = logging.get_module_logger()


class CloudFrontAccessLogsDelegate:
    """Class for cloudfront accesslogs delegation."""

    @classmethod
    def build(cls, args):
        """Returns object with prefix, startdate and filename."""
        prefix = args.log_file_prefix
        start_date = args.log_start_date
        name_format = args.log_name_format

        s1_dt = datetime(1970, 1, 1).strftime(name_format)
        s2_dt = datetime(2010, 10, 10).strftime(name_format)
        filename = ""
        for x_name, y_name in zip(s1_dt, s2_dt):
            if x_name != y_name:
                break
            filename += x_name

        return cls(prefix, start_date, filename)

    def __init__(self, prefix, start_date, filename):
        self._prefix = prefix
        self._start_date = start_date
        self._filename = filename

    def create_tasks(
        self, s3, bucket, namespace
    ):  # pylint: disable=invalid-name, unused-argument
        """Returns AWS tasks."""
        return [AWSLogsTask(namespace, None)]

    def create_prefix(self, name, params):  # pylint: disable=unused-argument
        """Returns prefix."""
        prefix = self._prefix + self._filename
        return prefix

    def create_initial_marker(self, name, params):
        """Returns marker."""
        prefix = self.create_prefix(name, params)
        marker = prefix + self._start_date.strftime("%Y-%m-%d-")
        return marker

    def create_filter(self):
        """Returns filter."""
        return self._filter

    def create_decoder(self):
        """Returns decoder."""
        return self._decode

    @classmethod
    def _filter(cls, files):
        return [item for item in files if item.key.endswith(".gz")]

    @classmethod
    def _decode(cls, job, content):  # pylint: disable=unused-argument
        compressed = BytesIO()
        compressed.write(content)
        compressed.seek(0)

        decompressed = gzip.GzipFile(fileobj=compressed, mode="rb")
        content = decompressed.read()
        decompressed.close()
        compressed.close()

        return content
