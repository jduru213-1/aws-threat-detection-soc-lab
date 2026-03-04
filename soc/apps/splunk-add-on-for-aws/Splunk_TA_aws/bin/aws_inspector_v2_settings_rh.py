#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import aws_settings_base_rh
import splunk.admin as admin
from splunktalib.rest_manager import multimodel


class InspectorV2Logging(aws_settings_base_rh.AWSLogging):
    keyMap = {"level": "log_level"}


class InspectorV2Settings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_inspector_v2"
    modelMap = {
        "logging": InspectorV2Logging,
    }


if __name__ == "__main__":
    admin.init(
        multimodel.ResourceHandler(InspectorV2Settings), admin.CONTEXT_APP_AND_USER
    )
