#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""File for Lamda description for metadata input."""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunksdc.log as logging

from . import description as desc

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


def get_lambda_conn(config):
    """Returns lambda connection."""
    retry_config = tacommon.configure_retry(config.get(tac.retry_max_attempts))
    boto_client = boto3.client(
        "lambda",
        region_name=config[tac.region],
        aws_access_key_id=config[tac.key_id],
        aws_secret_access_key=config[tac.secret_key],
        aws_session_token=config.get("aws_session_token"),
        config=retry_config,
    )
    return boto_client


@desc.generate_credentials
@desc.decorate
def lambda_functions(config):
    """Yields lambda functions."""
    lambda_conn = get_lambda_conn(config)
    paginator = lambda_conn.get_paginator("list_functions")

    for page in paginator.paginate(PaginationConfig={"PageSize": 1000}):
        for function in page.get("Functions", []):
            yield function
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, lambda_conn)
