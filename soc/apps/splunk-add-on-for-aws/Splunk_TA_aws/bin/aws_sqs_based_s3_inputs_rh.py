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
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging
from aws_common_validator import DataInputModelValidator

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        "aws_account", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_iam_role", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "using_dlq", required=False, encrypted=False, default=True, validator=None
    ),
    field.RestField(
        "sqs_sns_validation",
        required=False,
        encrypted=False,
        default=True,
        validator=None,
    ),
    field.RestField(
        "parse_firehose_error_data",
        required=False,
        encrypted=False,
        default=False,
        validator=None,
    ),
    field.RestField(
        "parse_csv_with_header",
        required=False,
        encrypted=False,
        default=False,
        validator=None,
    ),
    field.RestField(
        "parse_csv_with_delimiter",
        required=True,
        encrypted=False,
        default=",",
        validator=validator.String(
            max_len=2,
            min_len=1,
        ),
    ),
    field.RestField(
        "sqs_queue_region", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sqs_queue_url", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sqs_batch_size",
        required=False,
        encrypted=False,
        default="10",
        validator=validator.Number(
            max_val=10,
            min_val=1,
        ),
    ),
    field.RestField(
        "s3_file_decoder", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sourcetype", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "metric_index_flag",
        required=False,
        encrypted=False,
        default="0",
        validator=None,
    ),
    field.RestField(
        "interval",
        required=False,
        encrypted=False,
        default="300",
        validator=validator.Number(
            max_val=31536000,
            min_val=0,
        ),
    ),
    field.RestField("disabled", required=False, validator=None),
    field.RestField("private_endpoint_enabled", required=False, validator=None),
    field.RestField("sqs_private_endpoint_url", required=False, validator=None),
    field.RestField("s3_private_endpoint_url", required=False, validator=None),
    field.RestField(
        "sts_private_endpoint_url",
        required=False,
        validator=None,
    ),
]
model = RestModel(fields, name=None)


endpoint = DataInputModelValidator(
    "aws_sqs_based_s3",
    model,
)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
