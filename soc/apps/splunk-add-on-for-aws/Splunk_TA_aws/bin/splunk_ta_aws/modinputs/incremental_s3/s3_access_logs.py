#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for incremental S3 S3 accesslogs input.
"""


from splunksdc import logging

from .handler import AWSLogsTask

logger = logging.get_module_logger()


class S3AccessLogsDelegate:
    """Class for S3 accesslogs delegation"""

    @classmethod
    def build(cls, args):
        """Builds prefix."""
        prefix = args.log_file_prefix
        start_date = args.log_start_date

        return cls(prefix, start_date)

    def __init__(self, prefix, start_date):
        self._prefix = prefix
        self._start_date = start_date

    def create_tasks(
        self, s3, bucket, namespace
    ):  # pylint: disable=invalid-name, unused-argument
        """Returns tasks."""
        return [AWSLogsTask(namespace, None)]

    def create_prefix(self, name, params):  # pylint: disable=unused-argument
        """Returns prefix."""
        return self._prefix

    def create_initial_marker(self, name, params):  # pylint: disable=unused-argument
        """Returns marker."""
        marker = self._prefix + self._start_date.strftime("%Y-%m-%d-")
        return marker

    def create_filter(self):
        """Returns filter."""
        return self._filter

    def create_decoder(self):
        """Returns decoder."""
        return self._decode

    @classmethod
    def _filter(cls, files):
        return files

    @classmethod
    def _decode(cls, job, content):  # pylint: disable=unused-argument
        return content
