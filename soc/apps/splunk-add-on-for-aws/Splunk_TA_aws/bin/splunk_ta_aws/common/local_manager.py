#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Splunk local service manager.
"""


import os

import splunk.entity as entity
import splunklib.client as client
from splunktalib.common import util

CONF_WEB = "configs/conf-web"


class LocalServiceManager:
    """Class for local service manager."""

    def __init__(self, app=None, owner="nobody", session_key=None, service=None):
        self._app = app
        self._owner = owner
        self._session_key = session_key
        if service is None:
            splunkd_host_port = os.environ.get(
                "SPLUNK_MGMT_HOST_PORT", "127.0.0.1:8089"
            )
            enable_ssl = self._get_entity("configs/conf-server", "sslConfig").get(
                "enableSplunkdSSL"
            )
            scheme = "https" if util.is_true(enable_ssl) else "http"
            host_and_port = splunkd_host_port.split(":")
            self.local_splunk_host = host_and_port[0]
            self.local_splunk_port = host_and_port[1]
            self._service = client.Service(
                host=self.local_splunk_host,
                port=self.local_splunk_port,
                app=self._app,
                owner=self._owner,
                token=self._session_key,
                scheme=scheme,
            )
        else:
            self._service = service

    def get_local_service(self):
        """Returns local service."""
        return self._service

    def _get_entity(self, path, name):
        return entity.getEntity(
            path,
            name,
            sessionKey=self._session_key,
            namespace=self._app,
            owner=self._owner,
        )
