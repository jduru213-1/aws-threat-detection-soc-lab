#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for proxy handling.
"""


import botocore.endpoint
from requests.utils import should_bypass_proxies

HTTP_PROXY = None
HTTPS_PROXY = None


def _get_proxies(self, url):  # pylint: disable=unused-argument
    if should_bypass_proxies(url, None):
        return {}
    return {"http": HTTP_PROXY, "https": HTTPS_PROXY}


botocore.endpoint.EndpointCreator._get_proxies = (  # pylint: disable=protected-access
    _get_proxies
)


def set_proxies(http_proxy, https_proxy):
    """Sets proxies."""
    global HTTP_PROXY  # pylint: disable=global-statement
    global HTTPS_PROXY  # pylint: disable=global-statement

    HTTP_PROXY = http_proxy
    HTTPS_PROXY = https_proxy
