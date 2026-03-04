#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Init module for cloudwatch input.
"""


import os
import os.path
import shutil

from splunksdc import environ, logging
from splunksdc.collector import SimpleCollectorV1

from .handler import ModularInput

logger = logging.get_module_logger()


def delete_ckpt(name, *args, **kwargs):  # pylint: disable=unused-argument
    """Deletes checkpoint for cloudwatch input."""
    root = environ.get_checkpoint_folder("aws_cloudwatch")
    path = os.path.join(root, name)

    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)


def modular_input_run(app, config):
    """Runs modular input for cloudwatch input."""
    stanzas = app.inputs()
    modular_input = ModularInput(stanzas)
    return modular_input.run(app, config)


def main():
    """Main method for init module of cloudwatch input."""
    arguments = {
        "aws_account": {"description": "The name of AWS account."},
        "aws_iam_role": {"description": "The name of IAM user would be assumed."},
        "aws_region": {"description": "Which AWS region will be collected."},
        "private_endpoint_enabled": {
            "description": "To enable/disable use of private endpoint"
        },
        "s3_private_endpoint_url": {
            "title": "Private endpoint url to connect with s3 service"
        },
        "ec2_private_endpoint_url": {
            "title": "Private endpoint url to connect with ec2 service"
        },
        "elb_private_endpoint_url": {
            "title": "Private endpoint url to connect with elb service"
        },
        "lambda_private_endpoint_url": {
            "title": "Private endpoint url to connect with lambda service"
        },
        "monitoring_private_endpoint_url": {
            "title": "Private endpoint url to connect with monitoring service"
        },
        "autoscaling_private_endpoint_url": {
            "title": "Private endpoint url to connect with autoscaling service"
        },
        "sts_private_endpoint_url": {
            "title": "Private endpoint url to connect with sts service"
        },
        "metric_namespace": {
            "description": "The namespace of metrics will be collected."
        },
        "metric_names": {
            "description": "Regex filter for metric names. Only metric names matching provided regex will be collected."
        },
        "metric_dimensions": {
            "description": "Regex filter for dimensions. Only dimensions matching provided regex will be collected."
        },
        "statistics": {"description": "Types of statistics that will be collected."},
        "period": {
            "description": "The granularity, in seconds, of the returned data points."
        },
        "use_metric_format": {
            "description": "Whether to transform event to splunk metric format."
        },
        "metric_expiration": {
            "description": "How long the discovered metrics would be cached for, in seconds."
        },
        "query_window_size": {
            "description": "How far back to retrieve data points for, in number of data points."
        },
        "polling_interval": {"description": "Deprecated."},
    }

    SimpleCollectorV1.main(
        modular_input_run,
        title="AWS CloudWatch Metrics",
        use_single_instance=True,
        use_external_validation=False,
        arguments=arguments,
    )
