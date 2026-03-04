#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#
"""
Runs module for AWS Config inputs.
"""
from aws_bootstrap_env import run_module

if __name__ == "__main__":
    run_module("splunk_ta_aws.modinputs.config")
