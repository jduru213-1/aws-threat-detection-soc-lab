#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovering lambda function metrics.
"""
from .base import DiscoveringPolicy, DiscoveringPolicyRegistry


class DiscoverLambdaMetrics(DiscoveringPolicy):
    """Class for discoverying Lambda Metrics."""

    _METRIC_NAMES = [
        "Invocations",
        "Errors",
        "Dead Letter Error",
        "Duration",
        "Throttles",
        "IteratorAge",
        "ConcurrentExecutions",
        "UnreservedConcurrentExecutions",
    ]

    def __call__(self, client):
        functions = client.get_lambda_functions()
        for item in functions:
            dimension = {"FunctionName": item["FunctionName"]}
            yield self._create_metrics(dimension, self._METRIC_NAMES)


def create_policy_registry():
    """Returns policy registry."""
    registry = DiscoveringPolicyRegistry()
    registry.set(DiscoverLambdaMetrics, "FunctionName")
    return registry
