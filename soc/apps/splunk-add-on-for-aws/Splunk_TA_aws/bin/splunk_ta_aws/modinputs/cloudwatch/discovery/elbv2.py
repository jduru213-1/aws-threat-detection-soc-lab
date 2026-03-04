#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovering ELB v2 cloudwatch metrics.
"""
from collections import namedtuple

from .base import DiscoveringPolicy, DiscoveringPolicyRegistry

ELBV2TargetGroup = namedtuple(
    "ELBV2TargetGroup", ["target_group_arn", "protocol", "load_balancer_arns"]
)


class DiscoverELBV2Metrics(DiscoveringPolicy):
    """Class for Discovering ELBV2 metrics."""

    _NET_METRIC_NAMES = [
        "ActiveFlowCount",
        "ConsumedLCUs",
        "HealthyHostCount",
        "NewFlowCount",
        "ProcessedBytes",
        "TCP_Client_Reset_Count",
        "TCP_ELB_Reset_Count",
        "TCP_Target_Reset_Count",
        "UnHealthyHostCount",
    ]

    @classmethod
    def _create_app_elb_metrics_names(cls, dimensions):
        """
        # e.g.
        # 3 means the metric name exists for dimensions: LoadBalancer and LoadBalancer-AvailabilityZone
        """
        dims2mask = {
            "LoadBalancer": 1,
            "AvailabilityZone-LoadBalancer": 2,
            "AvailabilityZone-LoadBalancer-TargetGroup": 4,
            "LoadBalancer-TargetGroup": 8,
            "TargetGroup": 16,
        }

        keys = list(dimensions.keys())
        keys.sort()
        index = "-".join(keys)
        mask = dims2mask[index]

        metric_names = {
            "ActiveConnectionCount": 1,
            "ClientTLSNegotiationErrorCount": 3,
            "ConsumedLCUs": 1,
            "HTTP_Fixed_Response_Count": 3,
            "HTTP_Redirect_Count": 3,
            "HTTP_Redirect_Url_Limit_Exceeded_Count": 1,
            "HTTPCode_ELB_3XX_Count": 3,
            "HTTPCode_ELB_4XX_Count": 3,
            "HTTPCode_ELB_5XX_Count": 3,
            "IPv6ProcessedBytes": 1,
            "IPv6RequestCount": 15,
            "NewConnectionCount": 1,
            "ProcessedBytes": 1,
            "RejectedConnectionCount": 3,
            "RequestCount": 15,
            "RuleEvaluations": 1,
            "HealthyHostCount": 12,
            "HTTPCode_Target_2XX_Count": 15,
            "HTTPCode_Target_3XX_Count": 15,
            "HTTPCode_Target_4XX_Count": 15,
            "HTTPCode_Target_5XX_Count": 15,
            "RequestCountPerTarget": 24,
            "TargetConnectionErrorCount": 15,
            "TargetResponseTime": 15,
            "TargetTLSNegotiationErrorCount": 15,
            "UnHealthyHostCount": 12,
            "ELBAuthError": 1,
            "ELBAuthFailure": 1,
            "ELBAuthLatency": 1,
            "ELBAuthSuccess": 1,
        }
        return [key for key, value in metric_names.items() if value & mask]

    def _generate_metrics(self, dimensions):
        metric_names = self._NET_METRIC_NAMES
        if self._ns == "AWS/ApplicationELB":
            metric_names = self._create_app_elb_metrics_names(dimensions)

        return self._create_metrics(dimensions, metric_names)

    def _create_elb2zone_lookup(self, client):
        typename = "network" if self._ns == "AWS/NetworkELB" else ""
        typename = "application" if self._ns == "AWS/ApplicationELB" else typename
        instances = client.get_elbv2_instances()
        instances = [_ for _ in instances if _["Type"].lower() == typename]
        result = {}
        for item in instances:
            elb = item["LoadBalancerArn"]
            elb = self._extract_load_balancer_path(elb)
            zones = result.setdefault(elb, set())
            for zone in item["AvailabilityZones"]:
                zones.add(zone["ZoneName"])
        return result

    def _create_tgp2elb_lookup(self, client):
        groups = [
            ELBV2TargetGroup(
                target_group_arn=item.get("TargetGroupArn"),
                protocol=item.get("Protocol"),
                load_balancer_arns=item.get("LoadBalancerArns", []),
            )
            for item in client.get_elbv2_target_groups()
        ]
        protocol = ["TCP"] if self._ns == "AWS/NetworkELB" else []
        protocol = ["HTTP", "HTTPS"] if self._ns == "AWS/ApplicationELB" else protocol
        result = {}
        for item in groups:
            if item.protocol not in protocol:
                continue
            tgp = self._extract_resource_path(item.target_group_arn)
            elements = result.setdefault(tgp, set())
            for elb in item.load_balancer_arns:
                elb = self._extract_load_balancer_path(elb)
                elements.add(elb)
        return result

    @classmethod
    def _extract_load_balancer_path(cls, arn):
        arn = cls._extract_resource_path(arn)
        pos = arn.find("/")
        if pos != -1:
            arn = arn[pos + 1:]  # fmt: skip
        return arn

    @staticmethod
    def _extract_resource_path(arn):
        parts = arn.split(":")
        if len(parts) >= 6:
            return parts[5]
        return ""


class DiscoverByLB(DiscoverELBV2Metrics):
    """Class for Discovering by LB"""

    def __call__(self, client):
        result = self._create_elb2zone_lookup(client)
        for elb in result.keys():  # pylint: disable=consider-iterating-dictionary
            dimensions = {"LoadBalancer": elb}
            yield self._generate_metrics(dimensions)


class DiscoverByAZLB(DiscoverELBV2Metrics):
    """Class for Discovering by AZLB"""

    def __call__(self, client):
        result = self._create_elb2zone_lookup(client)
        for elb, zones in result.items():
            for availability_zone in zones:
                dimensions = {
                    "LoadBalancer": elb,
                    "AvailabilityZone": availability_zone,
                }
                yield self._generate_metrics(dimensions)


class DiscoverByTG(DiscoverELBV2Metrics):
    """Class for Discovering by TG"""

    def __call__(self, client):
        result = self._create_tgp2elb_lookup(client)
        for tgp in result.keys():  # pylint: disable=consider-iterating-dictionary
            dimensions = {"TargetGroup": tgp}
            yield self._generate_metrics(dimensions)


class DiscoverByTGLB(DiscoverELBV2Metrics):
    """Class for Discovering by TGLB"""

    def __call__(self, client):
        result = self._create_tgp2elb_lookup(client)
        for tgp, instances in result.items():
            for elb in instances:
                dimensions = {"LoadBalancer": elb, "TargetGroup": tgp}
                yield self._generate_metrics(dimensions)


class DiscoverByAZTGLB(DiscoverELBV2Metrics):
    """Class for Discovering by AZTGLB"""

    def __call__(self, client):
        tgp2elb = self._create_tgp2elb_lookup(client)
        elb2zone = self._create_elb2zone_lookup(client)
        for tgp, instances in tgp2elb.items():
            for elb in instances:
                for availability_zone in elb2zone.get(elb, []):
                    dimensions = {
                        "LoadBalancer": elb,
                        "TargetGroup": tgp,
                        "AvailabilityZone": availability_zone,
                    }
                    yield self._generate_metrics(dimensions)


def create_policy_registry():
    """Creates policy registry for cloudwatch."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverByLB, "LoadBalancer")
    registry.set(DiscoverByTG, "TargetGroup")
    registry.set(DiscoverByAZLB, "AvailabilityZone", "LoadBalancer")
    registry.set(DiscoverByTGLB, "LoadBalancer", "TargetGroup")
    registry.set(DiscoverByAZTGLB, "AvailabilityZone", "LoadBalancer", "TargetGroup")
    return registry
