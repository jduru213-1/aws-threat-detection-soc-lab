#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

import splunk.admin as admin
from splunktalib.rest_manager import multimodel
import aws_settings_base_rh


class CloudWatchLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {"level": "log_level"}


class CloudWatchSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_settings"
    modelMap = {
        "logging": CloudWatchLogging,
    }


class CloudWatchSettingsHandler(aws_settings_base_rh.AWSSettingHandler):
    stanzaName = "aws_cloudwatch"


if __name__ == "__main__":
    admin.init(
        multimodel.ResourceHandler(CloudWatchSettings, CloudWatchSettingsHandler),
        admin.CONTEXT_APP_AND_USER,
    )
