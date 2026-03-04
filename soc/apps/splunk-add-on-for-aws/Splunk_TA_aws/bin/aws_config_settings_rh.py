#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh


class ConfigSettingHandler(aws_settings_base_rh.AWSSettingHandler):
    stanzaName = "aws_config"


if __name__ == "__main__":
    admin.init(
        multimodel.ResourceHandler(
            aws_settings_base_rh.AWSSettings, handler=ConfigSettingHandler
        ),
        admin.CONTEXT_APP_AND_USER,
    )
