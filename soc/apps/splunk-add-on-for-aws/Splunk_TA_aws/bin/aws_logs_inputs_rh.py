#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
)
import splunk_ta_aws.common.ta_aws_consts as tac
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
from aws_common_validator import DataInputModelValidator
import logging

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        "aws_account", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_iam_role", required=False, encrypted=False, default="", validator=None
    ),
    field.RestField(
        "host_name", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_s3_region", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "private_endpoint_enabled", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "s3_private_endpoint_url", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "sts_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "bucket_name", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "interval",
        required=False,
        encrypted=False,
        default=1800,
        validator=validator.Number(
            max_val=31536000,
            min_val=0,
        ),
    ),
    field.RestField(
        "log_type", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "log_file_prefix", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "log_start_date",
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Datetime(r"%Y-%m-%d"),
    ),
    field.RestField(
        "sourcetype", required=False, encrypted=False, default="aws:s3", validator=None
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "bucket_region", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "log_name_format", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "log_path_format",
        required=False,
        encrypted=False,
        default=tac.account_level,
        validator=None,
    ),
    field.RestField(
        "max_fails", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "max_number_of_process",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "max_number_of_thread",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "max_retries", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = DataInputModelValidator(
    "splunk_ta_aws_logs",
    model,
)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
