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
    SingleModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
import logging

util.remove_http_proxy_env_vars()


fields = [
    field.RestField(
        "account", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "aws_iam_role", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "regions", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "apis", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sourcetype",
        required=False,
        encrypted=False,
        default="aws:metadata",
        validator=None,
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "retry_max_attempts",
        required=False,
        encrypted=False,
        default=5,
        validator=validator.AllOf(
            validator.Pattern(
                regex=r"""^[1-9]\d*$""",
            ),
            validator.Number(
                max_val=10000,
                min_val=5,
            ),
        ),
    ),
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = SingleModel("aws_metadata_tasks", model, config_name="aws_metadata")


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=AdminExternalHandler,
    )
