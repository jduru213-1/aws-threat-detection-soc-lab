#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for Cloudwatch inputs UCC Rh.
"""

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
    DataInputModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        "aws_account", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_iam_role", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_region", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "private_endpoint_enabled", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "monitoring_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "s3_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "ec2_private_endpoint_url", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "elb_private_endpoint_url", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "lambda_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "autoscaling_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "sts_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "metric_namespace",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "metric_names", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "metric_dimensions",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "statistics", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "polling_interval",
        required=False,
        encrypted=False,
        default="3600",
        validator=validator.Number(
            max_val=86400,
            min_val=60,
        ),
    ),
    field.RestField(
        "period",
        required=False,
        encrypted=False,
        default="300",
        validator=validator.Number(
            max_val=86400,
            min_val=60,
        ),
    ),
    field.RestField(
        "sourcetype",
        required=False,
        encrypted=False,
        default="aws:cloudwatch",
        validator=None,
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "use_metric_format",
        required=False,
        encrypted=False,
        default="false",
        validator=None,
    ),
    field.RestField(
        "metric_expiration",
        required=False,
        encrypted=False,
        default="3600",
        validator=None,
    ),
    field.RestField(
        "query_window_size",
        required=False,
        encrypted=False,
        default="7200",
        validator=None,
    ),
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = DataInputModel(
    "aws_cloudwatch",
    model,
)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
