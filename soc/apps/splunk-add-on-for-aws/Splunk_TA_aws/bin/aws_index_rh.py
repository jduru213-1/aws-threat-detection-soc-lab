#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Custom REST Endpoint for enumerating Indexes for VPC Flow Logs input.
"""
import aws_bootstrap_env
from splunk import admin
from solnlib.splunkenv import get_splunkd_uri
import splunktalib.common.xml_dom_parser as xdp
import splunktalib.conf_manager.request as req


class ConfigHandler(admin.MConfigHandler):
    def setup(self):
        """Setup method for Indexes RH"""
        self.supportedArgs.addOptArg("metric_index_flag")
        return

    def handleList(self, confInfo):
        """Called when user invokes the "edit" action."""
        if (
            self.callerArgs.data.get("metric_index_flag")
            and self.callerArgs.data.get("metric_index_flag")[0] == "1"
        ):
            uri = "{}/services/data/indexes?datatype=metric".format(
                get_splunkd_uri(self.getSessionKey())
            )
        else:
            uri = "{}/services/data/indexes".format(
                get_splunkd_uri(self.getSessionKey())
            )

        indexes = self._do_request(uri, "GET", None, "Failed to get indexes")

        if indexes:
            for idx in indexes:
                index = idx.get("name")
                confInfo[index].append("index", index)

    def _do_request(self, uri, method, payload, err_msg):
        """
        _do_request method
        :param uri: The URL to be requested
        :param method: GET, POST or DELETE
        :param payload: payload
        :param err_msg: Error message to be raised
        """
        response = req.content_request(
            uri, self.getSessionKey(), method, payload, err_msg
        )
        return xdp.parse_conf_xml_dom(response)


if __name__ == "__main__":
    admin.init(ConfigHandler, admin.CONTEXT_NONE)
