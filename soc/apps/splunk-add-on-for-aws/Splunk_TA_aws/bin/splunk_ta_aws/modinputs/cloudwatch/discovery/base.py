#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Base file for cloudwatch inputs.
"""


from splunk_ta_aws.modinputs.cloudwatch.metric import Metric


class DiscoveringPolicyRegistry:
    """Class for discovering policy registry."""

    def __init__(self):
        self._registry = {}

    def set(self, policy, *keys):
        """Sets registry keys."""
        self._registry[keys] = policy
        return self

    def get(self, *keys):
        """Returns registry keys."""
        return self._registry.get(keys)


class DiscoveringPolicy:
    """Class for discovering policy."""

    def __init__(self, ns):  # pylint: disable=invalid-name
        self._ns = ns

    def _create_metrics(self, dimensions, metric_names, tags=None):
        dimensions = list(dimensions.items())
        dimensions.sort(key=lambda _: _[0])
        return [Metric(self._ns, name, dimensions, tags) for name in metric_names]

    def __call__(self, client):
        pass
