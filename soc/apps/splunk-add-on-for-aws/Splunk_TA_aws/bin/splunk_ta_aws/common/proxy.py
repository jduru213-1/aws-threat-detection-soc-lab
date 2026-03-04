#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for handling AWS proxy.
"""


import botocore.endpoint
from requests.utils import should_bypass_proxies
from urllib import parse as urlparse
from splunksdc import logging

from splunksdc.config import (  # isort: skip
    BooleanField,
    StanzaParser,
    StringField,
)

logger = logging.get_module_logger()


class ProxySettings:
    """Class for Proxy settings."""

    @staticmethod
    def _wipe(settings):
        params = vars(settings).copy()
        del params["password"]
        return params

    @classmethod
    def load(cls, config):
        """Loads proy settings."""
        content = config.load(
            "splunk_ta_aws/splunk_ta_aws_settings_proxy",
            stanza="aws_proxy",
            virtual=True,
        )
        parser = StanzaParser(
            [
                BooleanField("proxy_enabled", rename="enabled"),
                StringField("proxy_type"),
                StringField("host"),
                StringField("port"),
                StringField("username"),
                StringField("password"),
            ]
        )
        settings = parser.parse(content)
        logger.debug("Load proxy settings success.", **cls._wipe(settings))
        return cls(settings)

    def __init__(self, settings):
        self._settings = settings

    def _make_url(self):
        settings = self._settings
        endpoint = "{host}:{port}".format(  # pylint: disable=consider-using-f-string
            host=settings.host, port=settings.port
        )
        auth = None
        if settings.username and len(settings.username) > 0:
            auth = urlparse.quote(settings.username.encode(), safe="")
            if settings.password and len(settings.password) > 0:
                auth += ":"
                auth += urlparse.quote(settings.password.encode(), safe="")

        if auth:
            endpoint = auth + "@" + endpoint

        url = (settings.proxy_type if settings.proxy_type else "") + "://" + endpoint
        return url

    def hook_boto3_get_proxies(self):
        """Configures the proxies."""
        settings = self._settings
        # http_url = self._make_url('http')
        # https_url = self._make_url('https')
        proxy_url = self._make_url()

        def _get_proxies(creator, url):  # pylint: disable=unused-argument
            if should_bypass_proxies(url, None):
                return {}

            return {"http": proxy_url, "https": proxy_url}

        if settings.enabled:
            creator = botocore.endpoint.EndpointCreator
            creator._get_proxies = _get_proxies  # pylint: disable=protected-access
            logger.info("Proxy is enabled.")
