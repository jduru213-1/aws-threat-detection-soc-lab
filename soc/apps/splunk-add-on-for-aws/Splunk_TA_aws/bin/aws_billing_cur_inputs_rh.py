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
        "bucket_region", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "bucket_name", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "report_prefix", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "report_names", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "temp_folder", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "interval",
        required=False,
        encrypted=False,
        default=3600,
        validator=validator.Number(
            max_val=31536000,
            min_val=0,
        ),
    ),
    field.RestField(
        "start_date",
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Datetime(r"%Y-%m"),
    ),
    field.RestField(
        "sourcetype",
        required=False,
        encrypted=False,
        default="aws:billing:cur",
        validator=None,
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = DataInputModelValidator(
    "aws_billing_cur",
    model,
)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
