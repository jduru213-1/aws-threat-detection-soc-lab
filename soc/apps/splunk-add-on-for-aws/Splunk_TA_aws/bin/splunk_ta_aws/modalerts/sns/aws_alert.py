#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for SNS alert execution.
"""
import json
import logging
import sys
import traceback


def parse():
    """Parses the alert command."""
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        try:
            return json.loads(sys.stdin.read())
        except Exception:  # pylint: disable=broad-except
            print(
                "ERROR Unexpected error: %s"  # pylint: disable=consider-using-f-string
                % traceback.format_exc(),
                sys.stderr,
            )
            sys.exit(3)
    else:
        print(
            'Argument "--execute" is required: %s. '  # pylint: disable=consider-using-f-string
            % json.dumps(sys.argv),
            sys.stderr,
        )
        sys.exit(2)


class ModularAlert:
    """
    Splunk modular alert.
    """

    # contents in payload
    SERVER_URI = "server_uri"
    SERVER_HOST = "server_host"
    SESSION_KEY = "session_key"

    OWNER = "owner"
    APP = "app"
    CONFIGURATION = "configuration"

    SID = "sid"
    SEARCH_NAME = "search_name"
    RESULT = "result"
    RESULTS_FILE = "results_file"
    RESULTS_LINK = "results_link"

    def __init__(self, logger, payload):
        self._payload = payload
        self._logger = logger

    def payload(self, name):
        """Returns payload."""
        return self._payload[name]

    def result(self, field, default=""):
        """Returns modular alert result."""
        result = self.payload(ModularAlert.RESULT)
        if not result:
            return default
        return result.get(field, default)

    def param(self, param, default=None):
        """Return modular alert params."""
        return self.payload(ModularAlert.CONFIGURATION).get(param, default)

    def run(self):
        """Runs alert."""
        self.log("Started")
        try:
            self._execute()
        except Exception:  # pylint: disable=broad-except
            self.exit_with_err(traceback.format_exc())

    def _execute(self):
        """
        Execute alert.

        :return:
        """
        raise NotImplementedError()

    def log(self, msg, level=logging.INFO):
        """Logs information about Modular Alert."""
        self._logger.log(
            msg="Modular Alert - %s" % msg,  # pylint: disable=consider-using-f-string
            level=level,
        )

    def exit_with_err(self, msg, status=1):
        """Exits on alert fail."""
        self.log(
            "Alert Failed: %s" % msg,  # pylint: disable=consider-using-f-string
            level=logging.ERROR,
        )
        sys.exit(status)
