#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovery cloudwatch EC2 metrics.
"""


import itertools

from .base import DiscoveringPolicy, DiscoveringPolicyRegistry


class DiscoverEC2Metrics(DiscoveringPolicy):
    """Class for discovering EC2 metrics."""

    _METRIC_NAMES = [
        "CPUUtilization",
        "DiskReadOps",
        "DiskWriteOps",
        "DiskReadBytes",
        "DiskWriteBytes",
        "NetworkIn",
        "NetworkOut",
        "NetworkPacketsIn",
        "NetworkPacketsOut",
        "StatusCheckFailed",
        "StatusCheckFailed_Instance",
        "StatusCheckFailed_System",
        "MetadataNoToken",
    ]

    _T2_METRIC_NAMES = [
        "CPUCreditUsage",
        "CPUCreditBalance",
        "CPUSurplusCreditBalance",
        "CPUSurplusCreditsCharged",
    ]

    _C5_M5_METRIC_NAMES = [
        "EBSReadOps",
        "EBSWriteOps",
        "EBSReadBytes",
        "EBSWriteBytes",
        "EBSIOBalance%",
        "EBSByteBalance%",
    ]

    @classmethod
    def _get_instances(cls, client):
        # pylint: disable=unnecessary-comprehension
        reservations = client.get_ec2_reservations()
        instances = [reservation["Instances"] for reservation in reservations]
        result = itertools.chain.from_iterable(instances)
        return [instance for instance in result]

    @classmethod
    def _get_detail_monitored_instances(cls, client):
        instances = cls._get_instances(client)
        return [_ for _ in instances if _["Monitoring"]["State"] == "enabled"]

    @classmethod
    def _create_metric_names(cls, *types):
        result = set()
        for typename in types:
            parts = [cls._METRIC_NAMES]
            if typename.startswith("t2"):
                parts.append(cls._T2_METRIC_NAMES)
            elif typename.startswith(
                "t3"
            ):  # ADDON-41767 Added Support for t3 instance type
                parts.append(cls._T2_METRIC_NAMES)
                parts.append(cls._C5_M5_METRIC_NAMES)
            elif typename.startswith("c5") or typename.startswith("m5"):
                parts.append(cls._C5_M5_METRIC_NAMES)
            for name in itertools.chain(*parts):
                result.add(name)
        return result


class DiscoverEC2MetricsByInstance(DiscoverEC2Metrics):
    """Class for discovering EC2 metrics by instance"""

    _EXT_DIMS = [
        "ImageId",
        "InstanceType",
        "PrivateIpAddress",
        "PublicIpAddress",
        "PrivateDnsName",
        "PublicDnsName",
        "Architecture",
    ]

    def __call__(self, client):
        for item in self._get_instances(client):
            tags = self._extract_extra_dimensions(item)
            dimensions = {"InstanceId": item["InstanceId"]}
            typename = item["InstanceType"]
            metric_names = self._create_metric_names(typename)
            yield self._create_metrics(dimensions, metric_names, tags)

    @classmethod
    def _extract_extra_dimensions(cls, instance):
        extra = [{item["Key"]: item["Value"]} for item in instance.get("Tags", [])]
        dims = {key: instance.get(key) for key in cls._EXT_DIMS}
        extra.extend([{key: value} for key, value in dims.items() if value])
        return extra


class DiscoverEC2MetricsByInstanceType(DiscoverEC2Metrics):
    """Class for discovering EC2 metrics by instance type."""

    def __call__(self, client):
        instances = self._get_detail_monitored_instances(client)
        for typename in {_["InstanceType"] for _ in instances}:
            dimensions = {"InstanceType": typename}
            metric_names = self._create_metric_names(typename)
            yield self._create_metrics(dimensions, metric_names)


class DiscoverEC2MetricsByImage(DiscoverEC2Metrics):
    """Class for discovering EC2 metrics by image"""

    # pylint: disable=unnecessary-comprehension
    def __call__(self, client):
        instances = self._get_detail_monitored_instances(client)
        images = {}
        for instance in instances:
            types = images.setdefault(instance["ImageId"], set())
            types.add(instance["InstanceType"])

        for image, types in images.items():
            dimensions = {"ImageId": image}
            metric_names = {metric for metric in self._create_metric_names(*types)}
            yield self._create_metrics(dimensions, metric_names)


class DiscoverEC2MetricsByAutoScalingGroup(DiscoverEC2Metrics):
    """Class for discovering EC2 metrics by autoscaling group"""

    def __call__(self, client):
        auto_scaling_groups = client.get_auto_scaling_groups()
        configurations = {
            item["LaunchConfigurationName"]: item["InstanceType"]
            for item in client.get_launch_configurations()
        }
        for group in auto_scaling_groups:
            lcn = group.get("LaunchConfigurationName")
            if lcn is not None:
                typename = configurations.get(lcn)
            else:
                configurations1 = {}
                for instances in group["Instances"]:
                    configurations1[
                        instances["LaunchTemplate"]["LaunchTemplateName"]
                    ] = instances["InstanceType"]
                    lcn = instances.get("LaunchTemplate").get("LaunchTemplateName")
                    typename = configurations1.get(lcn)
                    dimensions = {"AutoScalingGroupName": group["AutoScalingGroupName"]}
                    metric_names = self._create_metric_names(typename)
                    yield self._create_metrics(dimensions, metric_names)
                typename = None

            if typename is None:
                continue
            metric_names = self._create_metric_names(typename)
            dimensions = {"AutoScalingGroupName": group["AutoScalingGroupName"]}
            yield self._create_metrics(dimensions, metric_names)


def create_policy_registry():
    """Returns policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverEC2MetricsByInstance, "InstanceId")
    registry.set(DiscoverEC2MetricsByAutoScalingGroup, "AutoScalingGroupName")
    registry.set(DiscoverEC2MetricsByImage, "ImageId")
    registry.set(DiscoverEC2MetricsByInstanceType, "InstanceType")
    return registry
