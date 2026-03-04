#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import

import splunk.admin as admin

from splunktalib.rest_manager import multimodel

import aws_settings_base_rh


class BillingCurLogging(aws_settings_base_rh.AWSLogging):
    keyMap = {"level": "log_level"}


class BillingCurSettings(multimodel.MultiModel):
    endpoint = "configs/conf-aws_settings"
    modelMap = {
        "logging": BillingCurLogging,
    }


class BillingCurSettingsHandler(aws_settings_base_rh.AWSSettingHandler):
    stanzaName = "aws_billing_cur"


if __name__ == "__main__":
    admin.init(
        multimodel.ResourceHandler(BillingCurSettings, BillingCurSettingsHandler),
        admin.CONTEXT_APP_AND_USER,
    )
