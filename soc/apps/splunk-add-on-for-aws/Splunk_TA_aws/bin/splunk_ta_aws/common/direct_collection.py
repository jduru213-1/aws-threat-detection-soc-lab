#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for creating modinputs by calling splunkd.
"""
import collections
import json

import splunk.rest as rest
from splunksdc import logging
from splunktalib.common import util

logger = logging.get_module_logger()


class DirectCollection:
    """
    This class will directly create mod inputs by calling splunkd


    collection = DirectCollection('myinput','my_app',sessionkey)
    collection.create('newinput', {"interval":'60","fobar":"barfo"})
    collection.list()
    collection.delete('newinput')

    """

    def __init__(self, input_name, app_name, session_key):
        """

        input_name the name of the mod input
        app_name the name of the app to save the input.conf
        session_key a valid key from splunkd
        """
        self._input_name = input_name
        self._app_name = app_name
        self._session_key = session_key

    def _makeRequestURL(self, name=None):  # pylint: disable=invalid-name
        """
        makes a url for input creation

        name (optional) the name of the input.
        """
        app = self._app_name
        name = "/" + name if name else ""
        return "/servicesNS/nobody/" + app + "/data/inputs/" + self._input_name + name

    def create(self, name, **value):
        """
        creates an mod input

        name the name of the new input
        value a dict that holds the inputs args
        """
        try:
            query = {**value, **{"name": name}}

            url = self._makeRequestURL()
            rest.simpleRequest(
                url,
                sessionKey=self._session_key,
                postargs=query,
                method="POST",
                raiseAllErrors=True,
            )

        except Exception as err:  # pylint: disable=broad-except
            logger.error(  # noqa: F821
                "%s: error when creating input (%s). input error (%s)"  # pylint: disable=consider-using-f-string
                % (self._input_name, name, str(err))
            )
            logger.error(  # noqa: F821
                "%s: error when creating input (%s). input dump (%s)"  # pylint: disable=consider-using-f-string
                % (self._input_name, name, str(value))
            )

    def update(self, name, **value):
        """Update method."""
        try:
            if "disabled" in value:
                # enable is handled seperatly
                is_disabled = util.is_true(value["disabled"])
                action = "disable" if is_disabled else "enable"
                url = self._makeRequestURL(name) + "/" + action
                rest.simpleRequest(
                    url,
                    sessionKey=self._session_key,
                    method="POST",
                    raiseAllErrors=True,
                )
            else:
                query = {**value}
                url = self._makeRequestURL(name)
                rest.simpleRequest(
                    url,
                    sessionKey=self._session_key,
                    postargs=query,
                    method="POST",
                    raiseAllErrors=True,
                )

        except Exception as err:  # pylint: disable=broad-except
            logger.error(  # noqa: F821
                "%s: error when updating input (%s). input error (%s)"  # noqa: F507  # pylint: disable=consider-using-f-string
                % (self._input_name, name, str(err))
            )
            logger.error(  # noqa: F821
                "%s: error when updating input (%s). input dump (%s)"  # noqa: F507  # pylint: disable=consider-using-f-string
                % (self._input_name, name, str(value))
            )

    def list(self):
        """
        list all inputs for the specific input
        """
        results = []
        try:
            get_args = {"count": 0, "output_mode": "json"}
            url = self._makeRequestURL()
            _, content = rest.simpleRequest(
                url,
                sessionKey=self._session_key,
                method="GET",
                getargs=get_args,
                raiseAllErrors=True,
            )
            res = json.loads(content)

            if "entry" in res:
                for entry in res["entry"]:
                    obj = collections.namedtuple("ObjectName", entry.keys())(
                        *entry.values()
                    )
                    results.append(obj)

        except Exception as err:  # pylint: disable=broad-except
            logger.error(  # noqa: F821
                "%s: error when creating input . input error (%s)"  # pylint: disable=consider-using-f-string
                % (self._input_name, str(err))
            )

        return results

    def delete(self, name):
        """'
        deletes input

        """
        try:

            url = self._makeRequestURL(name)
            rest.simpleRequest(
                url, sessionKey=self._session_key, method="DELETE", raiseAllErrors=True
            )

        except Exception as err:  # pylint: disable=broad-except
            logger.error(  # noqa: F821
                "%s: error when creating input (%s). input error (%s)"  # pylint: disable=consider-using-f-string
                % (self._input_name, name, str(err))
            )
