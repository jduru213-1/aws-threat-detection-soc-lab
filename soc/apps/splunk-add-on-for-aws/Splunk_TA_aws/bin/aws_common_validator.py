#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
File for AWS common validators.
"""


import re

from splunksdc import log as logging
from splunktaucclib.rest_handler.endpoint import DataInputModel, SingleModel, validator
from splunktaucclib.rest_handler.error import RestError
from datetime import datetime

logger = logging.get_module_logger()

PRIVATE_ENDPOINT_PATTERN = r"^((http|https)://<prefix>vpce(-(\w+?)){2}((-(\w+?)){3,4})?\.<service_name>\.((\w+?)-){2,3}\d\.vpce\.amazonaws\.com(\.cn)?(/)?)$"  # pylint: disable=line-too-long

PRIVATE_ENDPOINT_MAPPING = {
    "aws_sqs_based_s3": [
        "sqs_private_endpoint_url",
        "s3_private_endpoint_url",
        "sts_private_endpoint_url",
    ],
    "aws_cloudtrail": [
        "sqs_private_endpoint_url",
        "s3_private_endpoint_url",
        "sts_private_endpoint_url",
    ],
    "aws_cloudtrail_lake": [
        "cloudtrail_private_endpoint_url",
        "sts_private_endpoint_url",
    ],
    "aws_cloudwatch_logs": ["logs_private_endpoint_url", "sts_private_endpoint_url"],
    "aws_kinesis": ["kinesis_private_endpoint_url", "sts_private_endpoint_url"],
    "default": ["s3_private_endpoint_url", "sts_private_endpoint_url"],
}


def on_fetch_validate_urls(data):
    """Validates the URL after it is entered in the field"""
    for key in data.keys():
        data[key] = data[key].strip()
        service = key.split("_")[0]
        if service == "s3":
            pattern = PRIVATE_ENDPOINT_PATTERN.replace(
                r"<prefix>", r"((bucket|accesspoint|control)\.)?"
            )
        else:
            pattern = PRIVATE_ENDPOINT_PATTERN.replace(r"<prefix>", "")
        pattern = pattern.replace(r"<service_name>", service)
        if not re.match(pattern, data[key]):
            raise RestError(
                400,
                "Provided Private Endpoint URL for %s is not valid."  # pylint: disable=consider-using-f-string
                % service,
            )


def on_save_validate_urls(endpoint_input_list, data):
    """Validates the URL after inputs are saved."""
    pattern = PRIVATE_ENDPOINT_PATTERN.replace("<service_name>", r"(\w+?)")
    pattern = pattern.replace(r"<prefix>", r"((bucket|accesspoint|control)\.)?")
    logger.debug(
        "Validating private endpoints : {}".format(  # pylint: disable=consider-using-f-string
            data.keys()
        )
    )
    for endpoint_input in endpoint_input_list:
        if endpoint_input in data.keys():
            input_data = data.get(endpoint_input, "").strip()
            if not input_data:
                raise RestError(
                    400,
                    "You have enabled use of private endpoints. \
                                    You must provide private endpoints for all specified services.",
                )
            if not re.match(pattern, input_data):
                raise RestError(
                    400,
                    "Provided Private Endpoint URL for %s is not valid."  # pylint: disable=consider-using-f-string
                    % endpoint_input.split("_")[0],
                )
        else:
            raise RestError(
                400,
                "You have enabled use of private endpoints. \
                                You must provide private endpoints for all specified services.",
            )


class DataInputModelValidator(DataInputModel):
    """Input validator for Inputs which uses DataInputModel"""

    def validate(self, name, data, existing=None):
        """Validate Input parameters."""
        endpoint_input_list = PRIVATE_ENDPOINT_MAPPING.get(
            self.input_type, PRIVATE_ENDPOINT_MAPPING.get("default")
        )
        private_endpoint_enabled = int(data.get("private_endpoint_enabled", "0"))
        logger.debug(
            "Checking private endpoint status : {}".format(  # pylint: disable=consider-using-f-string
                private_endpoint_enabled
            )
        )
        if private_endpoint_enabled:
            on_save_validate_urls(endpoint_input_list, data)
        super(  # pylint: disable=super-with-arguments
            DataInputModelValidator, self
        ).validate(name, data, existing)


class SingleModelValidator(SingleModel):
    """Input validator for Inputs which uses SingleModel"""

    def validate(self, name, data, existing=None):
        """Validate Input parameters."""
        endpoint_input_list = PRIVATE_ENDPOINT_MAPPING.get(
            self.config_name, PRIVATE_ENDPOINT_MAPPING.get("default")
        )
        private_endpoint_enabled = int(data.get("private_endpoint_enabled", "0"))
        logger.debug(
            "Checking private endpoint status : {}".format(  # pylint: disable=consider-using-f-string
                private_endpoint_enabled
            )
        )
        if private_endpoint_enabled:
            on_save_validate_urls(endpoint_input_list, data)
        super(  # pylint: disable=super-with-arguments
            SingleModelValidator, self
        ).validate(name, data, existing)


class CloudTrailLakeDateValidator(validator.Validator):
    def __init__(self):
        super(CloudTrailLakeDateValidator, self).__init__()

    def validate(self, value, data):
        return self.date_validations(data)

    def date_validations(self, data):
        now = datetime.utcnow()
        try:
            start_date_time = datetime.strptime(
                data.get("start_date_time"), "%Y-%m-%dT%H:%M:%S"
            )
        except ValueError:
            self.put_msg("Start date/time must be in 'YYYY-MM-DDTHH:MM:SS' format")
            return False

        if start_date_time > now:
            self.put_msg("The Start date/time cannot be in the future")
            return False

        if data.get("input_mode") == "index_once":
            if not data.get("end_date_time"):
                self.put_msg(
                    "End date/time is required if Index Once imput mode is selected"
                )
                return False
            try:
                end_date_time = datetime.strptime(
                    data.get("end_date_time"), "%Y-%m-%dT%H:%M:%S"
                )
            except ValueError:
                self.put_msg("End date/time must be in 'YYYY-MM-DDTHH:MM:SS' format")
                return False

            if end_date_time > now:
                self.put_msg("The End date/time cannot be in the future")
                return False

            if start_date_time > end_date_time:
                self.put_msg(
                    "The Start date/time cannot be ahead of the End date/time."
                )
                return False

            if start_date_time == end_date_time:
                self.put_msg("The Start date/time cannot be same as the End date/time.")
                return False

        return True
