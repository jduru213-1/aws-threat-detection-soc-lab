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
from aws_common_validator import CloudTrailLakeDateValidator, DataInputModelValidator
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
        "private_endpoint_enabled",
        required=False,
        encrypted=False,
        default=0,
        validator=None,
    ),
    field.RestField(
        "cloudtrail_private_endpoint_url",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "sts_private_endpoint_url",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "input_mode",
        required=True,
        encrypted=False,
        default="continuously_monitor",
        validator=CloudTrailLakeDateValidator(),
    ),
    field.RestField(
        "event_data_store",
        required=True,
        encrypted=False,
        validator=None,
    ),
    field.RestField(
        "start_date_time", required=True, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "end_date_time", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sourcetype",
        required=True,
        encrypted=False,
        default="aws:cloudtrail:lake",
        validator=None,
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "query_window_size",
        required=True,
        encrypted=False,
        default=15,
        validator=validator.AllOf(
            validator.Number(
                max_val=60,
                min_val=1,
            ),
            validator.Pattern(
                regex=r"""^\-[1-9]\d*$|^\d*$""",
            ),
        ),
    ),
    field.RestField(
        "delay_throttle",
        required=False,
        encrypted=False,
        default=5,
        validator=validator.AllOf(
            validator.Number(
                max_val=1440,
                min_val=1,
            ),
            validator.Pattern(
                regex=r"""^\-[1-9]\d*$|^\d*$""",
            ),
        ),
    ),
    field.RestField(
        "interval",
        required=True,
        encrypted=False,
        default=3600,
        validator=validator.AllOf(
            validator.Number(
                max_val=31536000,
                min_val=0,
            ),
            validator.Pattern(
                regex=r"""^\-[1-9]\d*$|^\d*$""",
            ),
        ),
    ),
    field.RestField("disabled", required=False, validator=None),
]

model = RestModel(fields, name=None)
endpoint = DataInputModelValidator("aws_cloudtrail_lake", model)


class CloudTrailLakeAdminExternalHandler(AdminExternalHandler):
    def handleCreate(self, confInfo):
        if self.payload.get("input_mode") == "index_once":
            self.payload["delay_throttle"] = ""
            self.payload["interval"] = "-1"
        else:
            self.payload["end_date_time"] = ""
        AdminExternalHandler.handleCreate(self, confInfo)

    def handleEdit(self, confInfo):
        if self.payload.get("input_mode") == "index_once":
            self.payload["delay_throttle"] = ""
            self.payload["interval"] = "-1"
        AdminExternalHandler.handleEdit(self, confInfo)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=CloudTrailLakeAdminExternalHandler,
    )
