#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for discovering generic cloudwatch metrics.
"""
from .base import DiscoveringPolicy


class DiscoverGenericMetrics(DiscoveringPolicy):
    """Class for discovering generic metrics."""

    def __init__(self, ns):  # pylint: disable=invalid-name, useless-super-delegation
        super(  # pylint: disable=super-with-arguments
            DiscoverGenericMetrics, self
        ).__init__(ns)

    def __call__(self, client):
        for item in client.get_cloudwatch_metrics(self._ns):
            dimensions = {dim["Name"]: dim["Value"] for dim in item["Dimensions"]}
            metric_names = [item["MetricName"]]
            yield self._create_metrics(dimensions, metric_names)
