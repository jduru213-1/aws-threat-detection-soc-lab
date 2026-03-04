#!/usr/bin/python

"""
This is the main entry point for AWS Generic S3 input.
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import os
import time

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunksdc.log as logging
import splunktalib.data_loader_mgr as dlm

from . import aws_s3_checkpointer as s3ckpt
from . import aws_s3_conf as asconfig
from . import aws_s3_consts as asc
from . import aws_s3_data_loader as asl

logger = logging.get_module_logger()


def use_single_instance():
    """Checks if using single instance or not."""
    return os.environ.get("s3_single_instance", "false").lower()


def print_scheme():
    """Prints scheme."""
    # pylint: disable=consider-using-f-string
    import sys  # pylint: disable=import-outside-toplevel

    scheme = """<scheme>
    <title>AWS S3</title>
    <description>Collect and index log files stored in AWS S3.</description>
    <use_external_validation>true</use_external_validation>
    <use_single_instance>{}</use_single_instance>
    <streaming_mode>xml</streaming_mode>
    <endpoint>
        <args>
            <arg name="name">
                <title>Name</title>
                <description>Unique data input name</description>
            </arg>
            <arg name="aws_account">
                <title>AWS Account</title>
            </arg>
            <arg name="aws_iam_role">
                <title>Assume Role</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="aws_s3_region">
                <title>AWS Region</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="private_endpoint_enabled">
                <title>Use Private Endpoints</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="s3_private_endpoint_url">
                <title>Private Endpoint URL (S3)</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="sts_private_endpoint_url">
                <title>Private Endpoint URL (STS)</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="polling_interval">
                <title>Polling interval</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="bucket_name">
                <title>Bucket Name</title>
            </arg>
            <arg name="key_name">
                <title>Key prefix</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="parse_csv_with_header">
                <title>Parse CSV data with header</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="parse_csv_with_delimiter">
                <title>Parse CSV data by delimiter</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="initial_scan_datetime">
                <title>Start datetime</title>
                <description>Only S3 keys which have been modified after this datetime will be considered</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="terminal_scan_datetime">
                <title>End datetime</title>
                <description>Only S3 keys which have been modified before this datetime will be considered</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="whitelist">
                <title>Whitelist Regex</title>
                <description>S3 key names which match this regex will be indexed</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="blacklist">
                <title>Blacklist Regex</title>
                <description>S3 key names which match this regex will be ignored, but whitelist dominates</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="host_name">
                <title>S3 host name</title>
                <description>For example: s3-ap-south-east-1.awsamazon.com</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="is_secure">
                <title>Secure S3 connection</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="ct_blacklist">
                <title>Blacklist for CloudTrail Describe events</title>
                <description>Only valid when manually set sourcetype=aws:cloudtrail. PCRE regex for specifying event names to be excluded. Leave blank to use the default set of read-only event names</description>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="ct_excluded_events_index">
                <title>index for the excluded CloudTrail events</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="recursion_depth">
                <title>For folder keys</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="character_set">
                <title>The encoding used in your S3 files</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="max_retries">
                <title>Max number of retry attempts to stream incomplete items</title>
                <required_on_create>false</required_on_create>
            </arg>
            <arg name="max_items">
                <title>Max trackable items</title>
                <required_on_create>false</required_on_create>
            </arg>
        </args>
    </endpoint>
    </scheme>""".format(
        use_single_instance()
    )
    sys.stdout.write(scheme)


def _do_run():
    meta_configs, _, tasks = tacommon.get_configs(asconfig.AWSS3Conf, "aws_s3", logger)

    if not tasks:
        logger.info("No data input has been configured, exiting...")
        return

    logger.debug(
        "Configuration read from environment.", single_instance=use_single_instance()
    )
    meta_configs[tac.log_file] = asc.s3_log
    loader_mgr = dlm.create_data_loader_mgr(meta_configs)
    tacommon.setup_signal_handler(loader_mgr, logger)
    conf_change_handler = tacommon.get_file_change_handler(loader_mgr, logger)
    conf_monitor = asconfig.create_conf_monitor(conf_change_handler)
    loader_mgr.add_timer(conf_monitor, time.time(), 10)

    jobs = [asl.S3DataLoader(task) for task in tasks]
    loader_mgr.run(jobs)


def run():
    """
    Main loop. Run this TA forever
    """

    logger.info("Start generic aws_s3.")
    if "S3_USE_SIGV4" not in os.environ:
        os.environ["S3_USE_SIGV4"] = "True"

    try:
        time.sleep(5)
        _do_run()
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to collect s3 data!")
    logger.info("Sweep and close checkpoint file while tearing down")
    s3ckpt.S3CkptPool.close_all()
    logger.info("End generic aws_s3")


def main():
    """
    Main entry point
    """
    tacommon.main(print_scheme, run)


def delete_ckpt(input_name):
    """Deletes checkpoint."""
    s3ckpt.delete_ckpt(input_name)


if __name__ == "__main__":
    main()
