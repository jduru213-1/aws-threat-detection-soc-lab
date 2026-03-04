#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovering SNS metrics.
"""
from .base import DiscoveringPolicy, DiscoveringPolicyRegistry


class DiscoverSNSMetrics(DiscoveringPolicy):
    """Class for discoverying SNS Metrics."""

    _METRIC_NAMES = [
        "NumberOfMessagesPublished",
        "NumberOfNotificationsDelivered",
        "NumberOfNotificationsFailed",
        "NumberOfNotificationsFilteredOut",
        "NumberOfNotificationsFilteredOut-NoMessageAttributes",
        "NumberOfNotificationsFilteredOut-InvalidAttributes",
        "PublishSize",
        "SMSMonthToDateSpentUSD",
        "SMSSuccessRate",
    ]

    def __call__(self, client):
        topic_names = self._get_topics(client)
        for topic_name in topic_names:
            dimension = {"TopicName": topic_name}
            yield self._create_metrics(dimension, self._METRIC_NAMES)

    @classmethod
    def _get_topics(cls, client):
        names = []
        topics = client.get_sns_topics()
        for topic in topics:
            arn = topic["TopicArn"]
            names.append(arn.split(":")[5])
        return names


def create_policy_registry():
    """Returns policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverSNSMetrics, "TopicName")
    return registry
