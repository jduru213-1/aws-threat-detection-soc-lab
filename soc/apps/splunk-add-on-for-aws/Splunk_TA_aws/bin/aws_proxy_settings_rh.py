#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

import re
import logging
import ipaddress
import splunk.admin as admin
from splunktalib.rest_manager import util, error_ctl
from splunk_ta_aws.common.proxy_conf import ProxyManager
from splunktaucclib.rest_handler.error import RestError

KEY_NAMESPACE = util.getBaseAppName()
KEY_OWNER = "-"

AWS_PROXY = "aws_proxy"

POSSIBLE_KEYS = ("host", "port", "username", "password", "proxy_enabled", "proxy_type")


class HostValidator:
    """Validator to validate hostname and IP address"""

    def __init__(self):
        self.host_regex = re.compile(
            r"^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9])$"
        )

    def validate_host(self, host: str) -> bool:
        """Validates hostname

        Args:
            host (str): Hostname to validate

        Returns:
            bool: True, if hostname is valid else False
        """
        return bool(self.host_regex.match(host))

    def validate_ipv6(self, address: str) -> bool:
        """Validates whether address is IPv6

        Args:
            address (str): address to validate

        Returns:
            bool: True, if address is valid IPv6 else False
        """
        if address.startswith("[") and address.endswith("]"):
            address = address[1:-1]
            try:
                ipaddress.IPv6Address(address)
                return True
            except ipaddress.AddressValueError:
                return False
        return False

    def validate(self, value: str) -> bool:
        """Validate the hostname or IP address

        Args:
            value (str): value to validate

        Returns:
            bool: True, if valid else False
        """
        validators = [self.validate_ipv6, self.validate_host]
        is_valid_host = any(validator(value) for validator in validators)
        return is_valid_host


class ProxyRestHandler(admin.MConfigHandler):
    def __init__(self, scriptMode, ctxInfo):
        admin.MConfigHandler.__init__(self, scriptMode, ctxInfo)

        if self.callerArgs.id and self.callerArgs.id != "aws_proxy":
            error_ctl.RestHandlerError.ctl(
                1202, msgx="aws_proxy", logLevel=logging.INFO
            )

    def setup(self):
        """Setup method for proxy RH."""
        if self.requestedAction in (admin.ACTION_CREATE, admin.ACTION_EDIT):
            for arg in POSSIBLE_KEYS:
                self.supportedArgs.addOptArg(arg)
        return

    def handleCreate(
        self, confInfo
    ):  # pylint: disable=invalid-name # pylint: disable=unused-argument
        """Called when user invokes the "create" action."""

        args = self.validate(self.callerArgs.data)

        try:
            args_dict = {}

            for arg in POSSIBLE_KEYS:
                if arg in args:
                    args_dict[arg] = args[arg][0]
                else:
                    args_dict[arg] = ""

            proxy_str = (
                "%s://%s:%s@%s:%s"
                % (  # pylint: disable=consider-using-f-string
                    args_dict["proxy_type"],
                    args_dict["username"],
                    args_dict["password"],
                    args_dict["host"],
                    args_dict["port"],
                )
            )

            if "proxy_enabled" in args:
                enable = True if args_dict["proxy_enabled"] == "1" else False
            else:
                proxy = self.get()
                enable = True if (proxy and proxy.get_enable()) else False
            self.update(proxy_str, enable)
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        try:
            proxy = self.get()
            if not proxy:
                confInfo[AWS_PROXY].append("proxy_enabled", "0")
                return

            m = re.match(
                r"^((?P<proxy_type>\S*)(://))?(?P<username>\S*):(?P<password>\S*)@(?P<host>\S+):(?P<port>\d+$)",
                proxy.get_proxy(),
            )

            if not m:
                confInfo[AWS_PROXY].append("proxy_enabled", "0")
                return

            groupDict = m.groupdict()
            confInfo[AWS_PROXY].append("proxy_type", groupDict["proxy_type"])
            confInfo[AWS_PROXY].append("username", groupDict["username"])
            confInfo[AWS_PROXY].append("password", groupDict["password"])
            confInfo[AWS_PROXY].append("host", groupDict["host"])
            confInfo[AWS_PROXY].append("port", groupDict["port"])
            confInfo[AWS_PROXY].append(
                "proxy_enabled", proxy.get_enable() and "1" or "0"
            )
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)
        return

    def validate(self, args):
        """Validates the proxy."""
        if "proxy_enabled" in args and args["proxy_enabled"][0] not in ("0", "1"):
            error_ctl.RestHandlerError.ctl(
                1100,
                msgx="proxy_enabled={}".format(
                    args["proxy_enabled"][0]
                ),  # pylint: disable=consider-using-f-string
                logLevel=logging.INFO,
            )
        if "host" in args:
            host = args["host"][0]
            host_validator = HostValidator()
            if not host_validator.validate(host):
                raise RestError(400, "Please enter a valid hostname or IP address")
        return args

    def get(self):
        """Getter method for proxy."""
        pm = ProxyManager(self.getSessionKey())
        proxy = pm.get_proxy()
        return proxy

    def update(self, proxy, enable):
        """Update method for proxy."""
        try:
            pm = ProxyManager(self.getSessionKey())
            pm.set(proxy, str(enable).lower())
        except Exception as exc:
            error_ctl.RestHandlerError.ctl(400, msgx=exc, logLevel=logging.INFO)


if __name__ == "__main__":
    admin.init(ProxyRestHandler, admin.CONTEXT_NONE)
