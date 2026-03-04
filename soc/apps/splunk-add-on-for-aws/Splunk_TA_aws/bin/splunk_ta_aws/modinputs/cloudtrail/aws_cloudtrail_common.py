#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Cloudtrail Common.
"""


import threading

import splunktalib.orphan_process_monitor as opm

# Event writer
event_writer = None  # pylint: disable=invalid-name

_orphan_checker = opm.OrphanProcessChecker()


def orphan_check():
    """
    Check if this is orphan process.
    :return:
    """
    if _orphan_checker.is_orphan():
        raise InputCancellationError("Input was stop. This is an orphan process.")


class InputCancellationError(Exception):
    """
    Input was stop. This is an orphan process.
    """

    pass  # pylint: disable=unnecessary-pass


class CloudTrailProcessorError(Exception):
    """
    AWS CloudTrail notifications processing error.
    """

    pass  # pylint: disable=unnecessary-pass


class ThreadLocalSingleton(type):
    """
    Thread-local singleton: only one instance of a given class per thread.
    """

    _local = threading.local()

    def __call__(cls, *args, **kwargs):
        try:
            return getattr(ThreadLocalSingleton._local, cls.__name__)
        except AttributeError:
            instance = super(ThreadLocalSingleton, cls).__call__()
            setattr(ThreadLocalSingleton._local, cls.__name__, instance)
            return instance
