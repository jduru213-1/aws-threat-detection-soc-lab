#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for RDS description for metadata input.
"""


import datetime

import boto3
import splunk_ta_aws.common.ta_aws_consts as tac
import splunk_ta_aws.common.ta_aws_common as tacommon
import splunksdc.log as logging

from . import description as desc

logger = logging.get_module_logger()

CREDENTIAL_THRESHOLD = datetime.timedelta(minutes=20)


def get_rds_conn(config):
    """Returns connection from service to region."""
    retry_config = tacommon.configure_retry(config.get(tac.retry_max_attempts))
    boto_client = boto3.client(
        "rds",
        region_name=config[tac.region],
        aws_access_key_id=config[tac.key_id],
        aws_secret_access_key=config[tac.secret_key],
        aws_session_token=config.get("aws_session_token"),
        config=retry_config,
    )
    return boto_client


@desc.generate_credentials
@desc.decorate
def rds_instances(config):
    """Returns RDS instances."""
    rds_conn = get_rds_conn(config)
    paginator = rds_conn.get_paginator("describe_db_instances")

    for page in paginator.paginate(PaginationConfig={"PageSize": 100}):
        for db_instance in page.get("DBInstances", []):
            yield db_instance
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, rds_conn)


@desc.generate_credentials
@desc.decorate
def rds_reserved_instances(config):
    """Takes a parameter of config which is the configuration account information and returns RDS reserved instances."""
    rds_conn = get_rds_conn(config)
    paginator = rds_conn.get_paginator("describe_reserved_db_instances")

    for page in paginator.paginate(PaginationConfig={"PageSize": 100}):
        for db_instance in page.get("ReservedDBInstances", []):
            yield db_instance
        desc.refresh_credentials(config, CREDENTIAL_THRESHOLD, rds_conn)
