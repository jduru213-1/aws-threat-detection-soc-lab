#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
from splunk_ta_aws.common.ta_aws_common import load_config, make_splunk_endpoint
from splunk_ta_aws.common.ta_aws_consts import splunk_ta_aws
from splunktalib.common.util import is_true
from splunksdc import logging
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.modinputs.cloudtrail_lake.aws_cloudtrail_lake_consts as aclc

logger = logging.get_module_logger()


class Configs:
    """Class for loading cloudtrail lake configs."""

    ACCOUNTS = "accounts"
    SETTINGS_LOGGING = "settings_logging"
    SETTINGS_PROXY = "settings_proxy"

    ENDPOINTS = {
        ACCOUNTS: {
            "endpoint": "splunk_ta_aws/settings/all_accounts",
            "label": "AWS Accounts",
        },
        SETTINGS_LOGGING: {
            "endpoint": "splunk_ta_aws/splunk_ta_aws_settings_cloudtrail_lake/logging",
            "label": "AWS CloudTrail Lake Logging Setting",
        },
    }

    @staticmethod
    def load(splunkd_uri, session_key):
        """Loads AWS cloudtrail Lake configs."""

        user, app = aclc.USER, splunk_ta_aws
        configs = {
            key: load_config(
                make_splunk_endpoint(splunkd_uri, ep["endpoint"], user, app),
                session_key,
                ep["label"],
            )
            for key, ep in Configs.ENDPOINTS.items()
        }
        # handle IAM role for AWS accounts
        for _, item in configs[Configs.ACCOUNTS].items():
            if is_true(item.get("iam")):
                item.pop("key_id")
                item.pop("secret_key")

        configs[Configs.SETTINGS_PROXY] = pc.get_proxy_info(session_key)
        return configs
