#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#

import aws_bootstrap_env

import re

import splunk.admin as admin
import splunk_ta_aws.common.ta_aws_consts as tac
from base_input_rh import BaseInputRestHandler
from splunk_ta_aws.common.direct_collection import DirectCollection
from splunktaucclib.rest_handler.error import RestError

from aws_common_validator import PRIVATE_ENDPOINT_PATTERN  # isort:skip

ARGS = [
    "aws_account",
    "aws_region",
    "private_endpoint_enabled",
    "s3_private_endpoint_url",
    "ec2_private_endpoint_url",
    "elb_private_endpoint_url",
    "lambda_private_endpoint_url",
    "monitoring_private_endpoint_url",
    "autoscaling_private_endpoint_url",
    "sts_private_endpoint_url",
    "index",
    "aws_iam_role",
    "metric_dimensions",
    "metric_names",
    "metric_namespace",
    "period",
    "polling_interval",
    "sourcetype",
    "statistics",
    "disabled",
    "use_metric_format",
    "metric_expiration",
    "query_window_size",
]

GROUP_FIELDS = ["metric_dimensions", "metric_names", "metric_namespace", "statistics"]


class InputsProxyHandler(BaseInputRestHandler):
    def __init__(self, *args, **kwargs):
        self.opt_args = ARGS
        self.required_args = []
        self.group_fields = GROUP_FIELDS
        self.input_name = "aws_cloudwatch"

        self._collection = True

        BaseInputRestHandler.__init__(self, *args, **kwargs)
        self._collection = DirectCollection(
            input_name=self.input_name,
            app_name=tac.splunk_ta_aws,
            session_key=self.getSessionKey(),
        )
        return

    def handleCreate(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "create" action."""
        self._validate_inputs(self.callerArgs)
        BaseInputRestHandler.handleCreate(self, confInfo)

    def handleEdit(self, confInfo):  # pylint: disable=invalid-name
        """Called when user invokes the "edit" action."""
        self._validate_inputs(self.callerArgs)
        BaseInputRestHandler.handleEdit(self, confInfo)

    def _generate_endpoint_list(self, data):
        """Generates list of endpoints which needs to be validated"""
        metric_input_str = data.get("metric_namespace", [None])[0]
        if metric_input_str:
            metric_input_list = metric_input_str[2:-2].split('","')
        else:
            metric_input_list = []
        service_mapping = {
            "AWS/ApplicationELB": "elb_private_endpoint_url",
            "AWS/EBS": "ec2_private_endpoint_url",
            "AWS/EC2": "ec2_private_endpoint_url",
            "AWS/ELB": "elb_private_endpoint_url",
            "AWS/Lambda": "lambda_private_endpoint_url",
            "AWS/S3": "s3_private_endpoint_url",
        }
        endpoint_input_set = {
            "sts_private_endpoint_url",
            "monitoring_private_endpoint_url",
        }
        for key in service_mapping:  # pylint: disable=consider-using-dict-items
            if key in metric_input_list:
                endpoint_input_set.add(service_mapping[key])
                if key == "AWS/EC2":
                    endpoint_input_set.add("autoscaling_private_endpoint_url")
        return endpoint_input_set

    def _validate_inputs(self, data):
        endpoint_input_set = self._generate_endpoint_list(data)
        private_endpoint_enabled = int(data.get("private_endpoint_enabled", ["0"])[0])
        if not private_endpoint_enabled:
            return

        # Validate region and private endpoints
        regions = data.get("aws_region", [""])[
            0
        ]  # contains comma seperated region values
        region_list = regions.split(",")
        if len(region_list) != 1:
            raise RestError(
                400, "Only one region is allowed when private endpoints are enabled."
            )
        pattern = PRIVATE_ENDPOINT_PATTERN.replace("<service_name>", r"(\w+?)")
        pattern = pattern.replace(r"<prefix>", r"((bucket|accesspoint|control)\.)?")
        for endpoint_input in endpoint_input_set:
            input_data = data.get(endpoint_input, [""])[0]
            if not input_data or not input_data.strip():
                required_services = [
                    service.split("_")[0] for service in endpoint_input_set
                ]
                raise RestError(
                    400,
                    "You have enabled use of private endpoints. \
                                    Private Endpoint for following services are required: {}".format(
                        required_services
                    ),
                )
            if not re.match(pattern, input_data.strip()):
                raise RestError(
                    400,
                    "Provided Private Endpoint URL for %s is not valid."  # pylint: disable=consider-using-f-string
                    % endpoint_input.split("_")[0],  # pylint: disable=use-maxsplit-arg
                )


if __name__ == "__main__":
    admin.init(InputsProxyHandler, admin.CONTEXT_APP_ONLY)
