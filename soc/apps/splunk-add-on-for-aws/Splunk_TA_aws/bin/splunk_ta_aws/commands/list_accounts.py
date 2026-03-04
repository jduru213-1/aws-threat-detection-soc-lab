#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for listing AWS accounts.
"""
import splunk.Intersplunk
import splunk_ta_aws.common.account_util as account_util
import splunksdc.log as logging
from solnlib.splunk_rest_client import get_splunkd_access_info

from splunk_ta_aws.common.ta_aws_common import (  # isort: skip
    load_config,
    make_splunk_endpoint,
    make_splunkd_uri,
)

logger = logging.get_module_logger()


def _fetch_all_accounts(session_key, results):
    splunkd_uri = make_splunkd_uri(*get_splunkd_access_info(session_key))

    # fetch accounts
    accounts = load_config(
        make_splunk_endpoint(
            splunkd_uri,
            "splunk_ta_aws/settings/all_accounts",
        ),
        session_key,
        "Account",
    )

    if accounts:
        for name, account in accounts.items():
            account_id = account_util.get_account_id(account, session_key)

            results.append(
                {
                    "name": name,
                    "account_id": account_id,
                    "category": account["category"],
                }
            )

    # fetch roles
    roles = load_config(
        make_splunk_endpoint(
            splunkd_uri,
            "splunk_ta_aws/settings/splunk_ta_aws_iam_role",
        ),
        session_key,
        "Role",
    )

    if roles:
        for name, role in roles.items():
            account_id = account_util.extract_account_id_from_role_arn(role["arn"])

            if account_id:
                results.append(
                    {"name": name, "account_id": account_id, "category": "N/A"}
                )


def main():
    """Main method for list_accounts module."""
    factory = logging.StreamHandlerFactory()
    formatter = logging.ContextualLogFormatter(True)
    logging.RootHandler.setup(factory, formatter)
    logger.setLevel(logging.INFO)

    results = []
    try:
        results, dummyresults, settings = splunk.Intersplunk.getOrganizedResults()
        session_key = settings["sessionKey"]

        _fetch_all_accounts(session_key, results)
    except Exception:  # pylint: disable=broad-except
        import traceback  # pylint: disable=import-outside-toplevel

        stack = traceback.format_exc()
        logger.error("Error : Traceback: " + str(stack))

    splunk.Intersplunk.outputResults(results)
