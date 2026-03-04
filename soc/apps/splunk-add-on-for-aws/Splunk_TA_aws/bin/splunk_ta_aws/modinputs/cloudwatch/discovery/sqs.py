#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for cloudwatch discovery.
"""
from .base import DiscoveringPolicy, DiscoveringPolicyRegistry
from .generic import DiscoverGenericMetrics


class DiscoverSQSMetrics(DiscoveringPolicy):
    """Class for discovering SQS Metrics."""

    _METRIC_NAMES = [
        "ApproximateAgeOfOldestMessage",
        "ApproximateNumberOfMessagesDelayed",
        "ApproximateNumberOfMessagesNotVisible",
        "ApproximateNumberOfMessagesVisible",
        "NumberOfEmptyReceives",
        "NumberOfMessagesDeleted",
        "NumberOfMessagesReceived",
        "NumberOfMessagesSent",
        "SentMessageSize",
    ]

    def __call__(self, client):
        queue_urls = client.get_sqs_queues()
        queue_names = [self._parse_queue_name(url) for url in queue_urls]
        if len(queue_names) >= 1000:
            return self._list_metrics(client)
        return self._generate_metrics(queue_names)

    def _list_metrics(self, client):
        policy = DiscoverGenericMetrics(self._ns)
        for metrics in policy(client):
            yield metrics

    def _generate_metrics(self, queue_names):
        for name in queue_names:
            dimension = {"QueueName": name}
            yield self._create_metrics(dimension, self._METRIC_NAMES)

    @classmethod
    def _parse_queue_name(cls, url):
        pos = url.rfind("/")
        return url[pos + 1:]  # fmt: skip


def create_policy_registry():
    """Creates policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverSQSMetrics, "QueueName")
    return registry
