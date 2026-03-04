#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Files for handling logging.
"""


import logging
import os

_levelNames = [logging.getLevelName(_) for _ in range(0, 60, 10)]

PARENT = os.path.sep + os.path.pardir
PATH = os.path.abspath(__file__ + PARENT)
while os.path.basename(PATH) != "bin":
    PATH = os.path.abspath(PATH + PARENT)
DEFAULT = (
    os.path.abspath(PATH + PARENT) + os.path.sep + "default" + os.path.sep + "log_level"
)
LOCAL = (
    os.path.abspath(PATH + PARENT) + os.path.sep + "local" + os.path.sep + "log_level"
)


def level_from_file():
    """Gets log level from file."""
    try:
        with open(LOCAL) as local_fp:  # pylint: disable=unspecified-encoding
            level = local_fp.readline().strip()
        if level in _levelNames:
            return level
    except Exception:  # pylint: disable=broad-except
        pass

    try:
        with open(DEFAULT) as default_fp:  # pylint: disable=unspecified-encoding
            level = default_fp.readline().strip()
        if level in _levelNames:
            return level
    except Exception:  # pylint: disable=broad-except
        pass

    return "INFO"


try:
    import splunk.clilib.cli_common as scc
    from splunk.rest import simpleRequest

    def get_level(name, token, appName="-"):  # pylint: disable=invalid-name
        """Gets log level"""
        HOST = scc.getMgmtUri()  # pylint: disable=invalid-name
        url = HOST + "/servicesNS/nobody/%s/properties/log_info/%s/level" % (  # pylint: disable=consider-using-f-string
            appName,
            name,
        )  # fmt: skip
        reload_url = (
            HOST
            + "/servicesNS/nobody/%s/configs/conf-log_info/_reload"  # pylint: disable=consider-using-f-string
            % appName
        )  # fmt: skip
        simpleRequest(reload_url, sessionKey=token)
        (_, level) = simpleRequest(url, sessionKey=token)
        level = level.decode("utf-8")
        if level in _levelNames:
            return level
        else:
            return "INFO"

    def set_level(name, token, level, appName="-"):  # pylint: disable=invalid-name
        """Sets log level."""
        if level in _levelNames:
            HOST = scc.getMgmtUri()  # pylint: disable=invalid-name
            response = simpleRequest(
                HOST
                + "/servicesNS/nobody/%s/properties/log_info/%s"  # pylint: disable=consider-using-f-string
                % (appName, name),
                postargs={"level": level},
                sessionKey=token,
            )
            return response
        else:
            return None

except Exception:  # pylint: disable=broad-except

    def get_level(
        name, token, appName="-"
    ):  # pylint: disable=invalid-name, unused-argument
        """Gets log level from file."""
        return level_from_file()

    def set_level(  # type: ignore # pylint: disable=invalid-name
        name, level, token, appName="-"  # pylint: disable=unused-argument
    ):
        """Sets log level."""
        return None
