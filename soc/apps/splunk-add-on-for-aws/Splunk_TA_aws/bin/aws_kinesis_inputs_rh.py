#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
from splunktaucclib.rest_handler.endpoint import (  # noqa: F401 # pylint: disable=unused-import
    field,
    validator,
    RestModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging
from aws_common_validator import SingleModelValidator

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        "account", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_iam_role", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "region", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "private_endpoint_enabled", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "kinesis_private_endpoint_url", required=False, encrypted=False, validator=None
    ),
    field.RestField(
        "sts_private_endpoint_url",
        required=False,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "stream_names", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "init_stream_position",
        required=False,
        encrypted=False,
        default="LATEST",
        validator=None,
    ),
    field.RestField(
        "encoding", required=False, encrypted=False, default="", validator=None
    ),
    field.RestField(
        "format", required=False, encrypted=False, default="", validator=None
    ),
    field.RestField(
        "sourcetype",
        required=False,
        encrypted=False,
        default="aws:kinesis",
        validator=None,
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
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = SingleModelValidator("aws_kinesis_tasks", model, config_name="aws_kinesis")


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
