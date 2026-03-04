#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Runs module for AWS kinesis Input.
"""
from aws_bootstrap_env import run_module  # pylint: disable=E0401

if __name__ == "__main__":
    run_module("splunk_ta_aws.modinputs.kinesis")
