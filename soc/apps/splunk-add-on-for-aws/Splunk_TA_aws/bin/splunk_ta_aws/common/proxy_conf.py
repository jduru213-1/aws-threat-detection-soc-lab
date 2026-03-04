#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

"""
File for Proxy conf handling.
"""


from .aws_accesskeys import KEY_NAMESPACE, KEY_OWNER

SECTION = "default"
DOMAIN = "_aws_proxy"

import traceback

from splunktalib.common import log

logger = log.Logs("splunk_ta_aws").get_logger("proxy_conf", level="DEBUG")

import splunk_ta_aws.common.ta_aws_consts as tac
from splunk_ta_aws.common.credentials_manager import CredentialManager


class ProxyInfo:  # pylint: disable=too-many-instance-attributes
    """Class for Proxy information."""

    def __init__(self, proxystr):
        self.proxystr = proxystr
        self.enable = None
        self.proxy = None
        self._proxy_type = None
        self._host = None
        self._port = None
        self._user = None
        self._pass = None
        self._parse()

    def _parse(self):
        proxystr = self.proxystr
        if proxystr is None:
            return

        parts = proxystr.split("|")
        self.enable = parts[1]

        proxystr = parts[0]
        self.proxy = proxystr

        proxy_type_str = proxystr.split("://")
        proxy_url = None
        if len(proxy_type_str) == 2:
            self._proxy_type = proxy_type_str[0]
            proxy_url = proxy_type_str[1]
        else:
            proxy_url = proxy_type_str[0]

        account = None
        url = None
        parts = proxy_url.split("@")
        if len(parts) == 1:
            url = parts[0]
        elif len(parts) == 2:
            url = parts[1]
            account = parts[0]
        else:
            logger.error("Invalid proxy string.")
            return

        parts = url.rsplit(":", 1)
        if len(parts) == 1:
            self._host = parts[0]
        elif len(parts) == 2:
            self._host = parts[0]
            self._port = parts[1]
        else:
            logger.error("Invalid proxy string, wrong url.")
            return

        if account is not None:
            parts = account.split(":")
            if len(parts) == 2:
                self._user = parts[0]
                self._pass = parts[1]
            else:
                logger.error("Invalid proxy string, wrong user account.")
                return

    def get_enable(self):
        """Returns if proxy is enabled or not."""
        return self.enable in ("1", "true", "yes", "y", "on")

    def get_proxy(self):
        """Returns proxy"""
        return self.proxy

    def get_proxy_info(self):
        """Returns proxy information"""
        info = {
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "pass": self._pass,
            "proxy_type": self._proxy_type,
        }
        return info


class ProxyManager:
    """Class for Proxy manager."""

    def __init__(self, sessionKey):  # pylint: disable=invalid-name
        self._cred_mgr = CredentialManager(sessionKey=sessionKey)

    def get_proxy_info(self):
        """Get the proxy info object.

        @return: The proxy info object.
        """
        try:
            cred = (
                self._cred_mgr.all()
                .filter_by_app(KEY_NAMESPACE)
                .filter_by_user(KEY_OWNER)
                .filter(realm=DOMAIN)[0]
            )
            proxy = ProxyInfo(cred.clear_password)

            return proxy.get_proxy_info()
        except IndexError as err:
            logger.error(
                "Failed to get proxy information {} ".format(  # pylint: disable=consider-using-f-string
                    type(err).__name__
                )
            )
            return None
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Failed to get proxy information {} ".format(  # pylint: disable=consider-using-f-string
                    type(exc).__name__
                )
            )
            return None

    def get_proxy(self):
        """Get the proxy object.

        @return: The proxy object.
        """
        logger.debug("Get Proxy of ProxyManager")
        try:
            cred = (
                self._cred_mgr.all()
                .filter_by_app(KEY_NAMESPACE)
                .filter_by_user(KEY_OWNER)
                .filter(realm=DOMAIN)
            )
            try:
                proxy = ProxyInfo(next(cred.iterator()).clear_password)
            except StopIteration as err:  # noqa: F841 # pylint: disable=unused-variable
                logger.debug("The proxy is not set")
                return None
            return proxy
        except Exception as exc:  # noqa: F841  # pylint: disable=broad-except
            logger.error("Failed to get proxy. %s", traceback.format_exc())
            return None

    def set(self, proxy, enable):
        """Sets proxies."""
        info = proxy + "|" + enable

        try:
            self._cred_mgr.create_or_set(
                SECTION, DOMAIN, info, KEY_NAMESPACE, KEY_OWNER
            )
        except Exception as exc:
            logger.error(
                "Failed to set proxy {} ".format(  # pylint: disable=consider-using-f-string
                    type(exc).__name__
                )
            )
            raise exc


# Proxy function, translate legacy code
def get_proxy_info(session_key):
    """Returns proxy information"""
    proxy_manager = ProxyManager(session_key)
    proxy = proxy_manager.get_proxy()
    if proxy is not None and proxy.get_enable():
        proxy_info = proxy.get_proxy_info()
        return {
            tac.proxy_type: proxy_info["proxy_type"],
            tac.proxy_hostname: proxy_info["host"],
            tac.proxy_port: proxy_info["port"],
            tac.proxy_username: proxy_info["user"],
            tac.proxy_password: proxy_info["pass"],
        }

    return {
        tac.proxy_type: None,
        tac.proxy_hostname: None,
        tac.proxy_port: None,
        tac.proxy_username: None,
        tac.proxy_password: None,
    }
