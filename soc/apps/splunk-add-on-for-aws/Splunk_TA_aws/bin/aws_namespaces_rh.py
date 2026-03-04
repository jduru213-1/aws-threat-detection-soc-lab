"""
Custom REST Endpoint for enumerating AWS cloudwatch namepaces.
"""

#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

from __future__ import print_function
import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

import splunk
import splunk.admin
from splunksdc import log as logging
from splunk_ta_aws.common import s3util
import splunk_ta_aws.common.ta_aws_common as tacommon


logger = logging.get_module_logger()


class ConfigHandler(splunk.admin.MConfigHandler):
    def setup(self):
        """Setup method for namespaces RH,"""
        self.supportedArgs.addReqArg("aws_region")
        self.supportedArgs.addReqArg("aws_account")

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "edit" action."""
        try:
            key_id, secret_key = tacommon.assert_creds(
                self.callerArgs["aws_account"][0], self.getSessionKey(), logger
            )
            namespaces = s3util.list_cloudwatch_namespaces(
                self.callerArgs["aws_region"][0],
                key_id,
                secret_key,
                self.getSessionKey(),
            )
            confInfo["NameSpacesResult"].append("metric_namespace", namespaces)
        except Exception as exc:
            err = (
                "Error while loading Metric Namespace: type=%s, content=%s"
                ""
                % (  # pylint: disable=consider-using-f-string
                    type(exc),
                    exc,
                )
            )
            print(err)
            raise BaseException()  # pylint: disable=raise-missing-from


def main():
    """Main method for Namespaces RH."""
    splunk.admin.init(ConfigHandler, splunk.admin.CONTEXT_NONE)


if __name__ == "__main__":
    main()
