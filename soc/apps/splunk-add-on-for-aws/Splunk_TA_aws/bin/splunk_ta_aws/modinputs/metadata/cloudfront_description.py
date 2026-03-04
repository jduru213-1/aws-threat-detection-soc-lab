#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Cloudfront description of metadata input
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunksdc.log as logging

from . import description as desc

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


def connect_cloudfront(config):
    """Returns cloudfront connection."""
    retry_config = tacommon.configure_retry(config.get(tac.retry_max_attempts))
    boto_client = boto3.client(
        "cloudfront",
        region_name=config.get(tac.region),
        aws_access_key_id=config.get(tac.key_id),
        aws_secret_access_key=config.get(tac.secret_key),
        aws_session_token=config.get("aws_session_token"),
        config=retry_config,
    )
    return boto_client


@desc.generate_credentials
@desc.decorate
def cloudfront_distributions(config):
    """Returns cloudfront distribution results."""
    conn = connect_cloudfront(config)
    paginator = conn.get_paginator("list_distributions")

    for page in paginator.paginate(PaginationConfig={"PageSize": 1000}):
        for item in page.get("DistributionList", {}).get("Items", []):
            yield item
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, conn)
