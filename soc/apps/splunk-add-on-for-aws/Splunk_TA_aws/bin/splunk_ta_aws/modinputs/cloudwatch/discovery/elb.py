#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovery cloudwatch ELB instances.
"""
from .base import DiscoveringPolicy, DiscoveringPolicyRegistry


class DiscoverELBMetrics(DiscoveringPolicy):
    """Class for discovering ELB metrics."""

    _METRIC_NAMES = [
        "BackendConnectionErrors",
        "HealthyHostCount",
        "HTTPCode_Backend_2XX",
        "HTTPCode_Backend_3XX",
        "HTTPCode_Backend_4XX",
        "HTTPCode_Backend_5XX",
        "HTTPCode_ELB_4XX",
        "HTTPCode_ELB_5XX",
        "Latency",
        "RequestCount",
        "SpilloverCount",
        "SurgeQueueLength",
        "UnHealthyHostCount",
        "EstimatedALBActiveConnectionCount",
        "EstimatedALBConsumedLCUs",
        "EstimatedALBNewConnectionCount",
        "EstimatedProcessedBytes",
    ]


class DiscoverELBMetricsForAZ(DiscoverELBMetrics):
    """Class for discovering ELB metrics for AZ"""

    def __call__(self, client):
        zones = set()
        for item in client.get_elb_instances():
            for zone in item["AvailabilityZones"]:
                zones.add(zone)

        for zone in zones:
            dimension = {"AvailabilityZone": zone}
            yield self._create_metrics(dimension, self._METRIC_NAMES)


class DiscoverELBMetricsForName(DiscoverELBMetrics):
    """Class for discovering ELB metrics for name"""

    def __call__(self, client):
        for item in client.get_elb_instances():
            dimension = {"LoadBalancerName": item["LoadBalancerName"]}
            yield self._create_metrics(dimension, self._METRIC_NAMES)


class DiscoverELBMetricsForNameAndAZ(DiscoverELBMetrics):
    """Class for discovering ELB metrics for name and AZ"""

    def __call__(self, client):
        for item in client.get_elb_instances():
            lbn = item["LoadBalancerName"]
            for zone in item["AvailabilityZones"]:
                dimensions = {"LoadBalancerName": lbn, "AvailabilityZone": zone}
                yield self._create_metrics(dimensions, self._METRIC_NAMES)


def create_policy_registry():
    """Returns policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverELBMetricsForAZ, "AvailabilityZone")
    registry.set(DiscoverELBMetricsForName, "LoadBalancerName")
    registry.set(DiscoverELBMetricsForNameAndAZ, "AvailabilityZone", "LoadBalancerName")
    return registry
