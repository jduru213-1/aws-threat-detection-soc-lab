#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env  # noqa: F401 # pylint: disable=unused-import
import logging
import datetime

from splunktaucclib.rest_handler.endpoint import (
    field,
    validator,
    RestModel,
)
from splunktaucclib.rest_handler import admin_external, util
from splunktaucclib.rest_handler.admin_external import AdminExternalHandler
from splunktaucclib.rest_handler.error import RestError
from aws_common_validator import DataInputModelValidator

util.remove_http_proxy_env_vars()

BAD_REQUEST_STATUS_CODE = 400
DATETIME_FORMAT = r"%Y-%m-%dT%H:%M:%SZ"
START_DATETIME_FIELD_NAME = "Start DateTime"
END_DATETIME_FIELD_NAME = "End DateTime"


class GenericS3Handler(AdminExternalHandler):
    def handleCreate(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "edit" action."""

        isd = self.get("initial_scan_datetime")
        tsd = self.get("terminal_scan_datetime")

        if isd and isd != "default" and tsd:
            try:
                isd = self.parse_datetime(isd)
                tsd = self.parse_datetime(tsd)
            except ValueError as ex:
                raise RestError(  # pylint: disable=raise-missing-from
                    BAD_REQUEST_STATUS_CODE,
                    "Wrong datetime format: {}".format(
                        str(ex).capitalize()
                    ),  # pylint: disable=consider-using-f-string
                )

            if tsd < isd:
                raise RestError(
                    BAD_REQUEST_STATUS_CODE,
                    'Invalid datetime range. "{}" should be greater than "{}"'.format(  # pylint: disable=consider-using-f-string
                        END_DATETIME_FIELD_NAME, START_DATETIME_FIELD_NAME
                    ),
                )
            elif tsd == isd:
                raise RestError(
                    BAD_REQUEST_STATUS_CODE,
                    'Invalid datetime range. "{}" and "{}" can\'t be same'.format(  # pylint: disable=consider-using-f-string
                        END_DATETIME_FIELD_NAME, START_DATETIME_FIELD_NAME
                    ),
                )

        super(GenericS3Handler, self).handleCreate(
            confInfo
        )  # pylint: disable=super-with-arguments

    def parse_datetime(self, _datetime, _format=DATETIME_FORMAT):
        """Parse the given datetime in given format."""
        return datetime.datetime.strptime(_datetime, _format)

    def get(self, field_name):
        """Get method for s3 inputs RH."""
        field = self.callerArgs.data.get(
            field_name
        )  # pylint: disable=redefined-outer-name
        if field and isinstance(field, (tuple, list)) and field[0]:
            field = field[0]
        else:
            field = None

        if isinstance(field, ("".__class__, "".__class__)):
            field = field.strip()

        return field


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
        "polling_interval",
        required=False,
        encrypted=False,
        default=1800,
        validator=validator.Number(
            max_val=31536000,
            min_val=0,
        ),
    ),
    field.RestField(
        "key_name", required=False, encrypted=False, default=None, validator=None
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
        "initial_scan_datetime",
        required=False,
        encrypted=False,
        default=None,
        validator=validator.Datetime(r"%Y-%m-%dT%H:%M:%SZ"),
    ),
    field.RestField(
        "terminal_scan_datetime",
        required=False,
        encrypted=False,
        default="",
        validator=validator.Datetime(r"%Y-%m-%dT%H:%M:%SZ"),
    ),
    field.RestField(
        "ct_blacklist", required=False, encrypted=False, default="^$", validator=None
    ),
    field.RestField(
        "blacklist", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "whitelist", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField(
        "sourcetype", required=True, encrypted=False, default="aws:s3", validator=None
    ),
    field.RestField(
        "index", required=True, encrypted=False, default="default", validator=None
    ),
    field.RestField(
        "ct_excluded_events_index",
        required=False,
        encrypted=False,
        default=None,
        validator=None,
    ),
    field.RestField(
        "max_retries", required=False, encrypted=False, default=3, validator=None
    ),
    field.RestField(
        "recursion_depth", required=False, encrypted=False, default=-1, validator=None
    ),
    field.RestField(
        "max_items", required=False, encrypted=False, default=100000, validator=None
    ),
    field.RestField(
        "character_set", required=False, encrypted=False, default="auto", validator=None
    ),
    field.RestField(
        "is_secure", required=False, encrypted=False, default=None, validator=None
    ),
    field.RestField("disabled", required=False, validator=None),
]
model = RestModel(fields, name=None)


endpoint = DataInputModelValidator(
    "aws_s3",
    model,
)


if __name__ == "__main__":
    logging.getLogger().addHandler(logging.NullHandler())
    admin_external.handle(
        endpoint,
        handler=GenericS3Handler,
    )
