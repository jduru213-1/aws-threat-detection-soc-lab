#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovery cloudwatch AWS S3.
"""


import itertools

from .base import DiscoveringPolicy, DiscoveringPolicyRegistry


class DiscoverS3Metrics(DiscoveringPolicy):
    """Class for discovering S3 metrics."""

    _STORAGE_METRIC_NAMES = [
        "BucketSizeBytes",
        "NumberOfObjects",
    ]

    _STORAGE_TYPES = [
        "StandardStorage",
        "StandardIAStorage",
        "OneZoneIAStorage",
        "ReducedRedundancyStorage",
        "GlacierStorage",
        "AllStorageTypes",
    ]

    def __call__(self, client):
        bucket_names = client.get_s3_buckets()
        pairs = itertools.product(bucket_names, self._STORAGE_TYPES)
        for bucket_name, storage_type in pairs:
            dimension = {"BucketName": bucket_name, "StorageType": storage_type}
            yield self._create_metrics(dimension, self._STORAGE_METRIC_NAMES)


def create_policy_registry():
    """Returns policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverS3Metrics, "BucketName", "StorageType")
    return registry
