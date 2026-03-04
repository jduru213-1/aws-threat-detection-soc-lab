#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS account handling.
"""


import re

import boto3
import splunk.search as search
import splunk_ta_aws.common.proxy_conf as pc
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
from botocore.exceptions import ClientError
from splunk_ta_aws.common.ta_aws_common import set_proxy_env
from splunktaucclib.rest_handler.error import RestError

ACCOUNT_APPEND_SPL = """
    | makeresults
    | eval account_id="%s", name="%s", category="%s"
    | table account_id, name, category
    | collect `aws-account-index`
"""


def get_account_id(account, session_key):
    """Returns account id."""
    # we can directly get account_id in EC2 Role
    if account.get("iam") and account.get("account_id"):
        return account.get("account_id")

    # Set proxy
    proxy = pc.get_proxy_info(session_key)
    set_proxy_env(proxy)

    # get arn
    arn = _get_caller_identity(account)["Arn"]

    match_results = re.findall(r"^arn:aws(-\S+)?:iam::(\d+):", arn)

    if len(match_results) == 1:
        _, account_id = match_results[0]
        return account_id

    return None


def validate_keys(session_key, **account_info):
    """Validates keys."""
    # Set proxy
    proxy = pc.get_proxy_info(session_key)
    set_proxy_env(proxy)

    try:
        _get_caller_identity(account_info)
    except ClientError as err:
        err_msg = (
            "Failed to validate account due to %s"  # pylint: disable=consider-using-f-string
            % err.response["Error"]["Code"]
        )
        if "Credential should be scoped to a valid region" in err.response["Error"].get(
            "Message"
        ):
            err_msg += " : " + err.response["Error"].get("Message")
        raise RestError(400, err_msg)  # pylint: disable=raise-missing-from

    return True


def append_account_to_summary(
    name=None, account_id=None, category=None, session_key=None
):
    """Appends account to summary."""
    search.dispatch(
        ACCOUNT_APPEND_SPL % (account_id, name, category), sessionKey=session_key
    )


def append_assume_role_to_summary(name=None, arn=None, session_key=None):
    """Appends assume role to summary."""
    account_id = extract_account_id_from_role_arn(arn)

    if account_id:
        search.dispatch(
            ACCOUNT_APPEND_SPL % (account_id, name, "N/A"), sessionKey=session_key
        )


def extract_account_id_from_role_arn(role_arn):  # pylint: disable=invalid-name
    """Extracts account id from role arn."""
    pattern = re.compile(r"^arn:[^\s:]+:iam::(\d+):role")
    search_result = pattern.search(role_arn)

    if search_result:
        return search_result.groups()[0]

    return None


def _get_caller_identity(account):
    credentials = {}

    if account.get("key_id") is not None:
        credentials["aws_access_key_id"] = account["key_id"]
    if account.get("secret_key") is not None:
        credentials["aws_secret_access_key"] = account["secret_key"]
    if account.get("token") is not None:
        credentials["aws_session_token"] = account["token"]
    if account.get("category") is not None:
        category = int(account.get("category"))
        if category == tac.RegionCategory.USGOV:
            region = "us-gov-west-1"
        elif category == tac.RegionCategory.CHINA:
            region = "cn-north-1"
        else:
            region = "us-east-1"  # default region for GLOBAL category
        credentials["region_name"] = region
    if account.get("region_name"):
        credentials["region_name"] = account["region_name"]
    if account.get("endpoint_url"):
        credentials["endpoint_url"] = account.get("endpoint_url")
    else:
        credentials["endpoint_url"] = tacommon.format_default_endpoint_url(
            "sts", credentials["region_name"]
        )
    sts_client = boto3.client("sts", **credentials)
    return sts_client.get_caller_identity()
