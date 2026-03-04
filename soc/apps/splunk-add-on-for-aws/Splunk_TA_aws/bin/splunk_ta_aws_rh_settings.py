#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS Settings RH.
"""

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import splunk.admin as admin
from splunk_ta_aws.common.local_manager import LocalServiceManager
import splunklib.client as client
import splunk_ta_aws.common.ta_aws_consts as tac

REST_URI_MAP = {
    "aws_proxy": "splunk_ta_aws/splunk_ta_aws_settings_proxy",
    "global_settings": "splunk_ta_aws/splunk_ta_aws_global_settings/aws_inputs_settings",
    "logging": "splunk_ta_aws/splunk_ta_aws_settings_%s/%s",
}

GLOBAL_SETTINGS_ARGS = ["cloudwatch_dimensions_max_threads", "sqs_max_threads"]

LOGGING_ENDPOINTS = {
    "billing_cur": "logging",
    "config": "logging",
    "cloudtrail": "logging",
    "cloudwatch": "logging",
    "s3": "logging",
    "s3_incremental": "splunk_ta_aws_logs",
    "metadata": "logging",
    "cloudwatch_logs": "logging",
    "kinesis": "logging",
    "inspector": "logging",
    "inspector_v2": "logging",
    "config_rule": "logging",
    "sqs": "logging",
    "s3sqs": "logging",
    "cloudtrail_lake": "logging",
}

OPTIONAL_ARGS = ["proxy_enabled", "proxy_type", "host", "port", "username", "password"]


class SettingsHandler(admin.MConfigHandler):
    """Class for settings handler."""

    def __init__(self, *args, **kwargs):
        admin.MConfigHandler.__init__(self, *args, **kwargs)
        self._service = LocalServiceManager(
            app=tac.splunk_ta_aws, session_key=self.getSessionKey()
        ).get_local_service()
        self._object_id = self.callerArgs.id

    def setup(self):
        """Setup method for RH"""
        for arg in (
            GLOBAL_SETTINGS_ARGS + OPTIONAL_ARGS + list(LOGGING_ENDPOINTS.keys())
        ):
            self.supportedArgs.addOptArg(arg)
        return

    def handleList(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "list" action."""
        result = confInfo[self._object_id]
        uri = REST_URI_MAP[self._object_id]

        if self._object_id == "aws_proxy":
            entity = client.Entity(self._service, uri)

            for key in entity.content.keys():
                if key != "password":
                    result[key] = entity[key]

        elif self._object_id == "logging":
            for (
                service
            ) in (
                LOGGING_ENDPOINTS.keys()
            ):  # pylint: disable=consider-using-dict-items, consider-iterating-dictionary
                entity = client.Entity(
                    self._service, uri % (service, LOGGING_ENDPOINTS[service])
                )
                result[service] = entity["level"]

        elif self._object_id == "global_settings":
            entity = client.Entity(self._service, uri)

            for key in entity.content.keys():
                result[key] = entity[key]

        result["eai:appName"] = tac.splunk_ta_aws
        result["eai:userName"] = "nobody"
        result.setMetadata(
            admin.EAI_ENTRY_ACL, {"owner": "nobody", "app": tac.splunk_ta_aws}
        )

        return

    def handleEdit(self, confInfo):  # pylint: disable=invalid-name, unused-argument
        """Called when user invokes the "edit" action."""
        uri = REST_URI_MAP[self._object_id]

        if self._object_id == "aws_proxy":
            query = {}
            for arg in self.callerArgs.data:
                if self.callerArgs.data[arg][0]:
                    query[arg] = self.callerArgs.data[arg][0]
            query["name"] = self._object_id

            entity = client.Entity(self._service, uri)
            entity.post(**query)

        elif self._object_id == "logging":
            for arg in self.callerArgs.data:
                if arg in list(LOGGING_ENDPOINTS.keys()):
                    entity = client.Entity(
                        self._service, uri % (arg, LOGGING_ENDPOINTS[arg])
                    )
                    entity.post(level=self.callerArgs.data[arg][0])

        elif self._object_id == "global_settings":
            query = {}
            for arg in self.callerArgs.data:
                if self.callerArgs.data[arg][0]:
                    query[arg] = self.callerArgs.data[arg][0]

            entity = client.Entity(self._service, uri)
            entity.post(**query)

        return


admin.init(SettingsHandler, admin.CONTEXT_APP_ONLY)
