#!/usr/bin/python

"""
This is the main entry point for AWS CloudWatch Logs TA
"""
#
# SPDX-FileCopyrightText: 2021 Splunk, Inc. <sales@splunk.com>
# SPDX-License-Identifier: LicenseRef-Splunk-8-2021
#
#


import time
import traceback

import splunk_ta_aws.common.ta_aws_common as tacommon
import splunk_ta_aws.common.ta_aws_consts as tac
import splunktalib.data_loader_mgr as dlm
from splunksdc import logging

from . import aws_cloudwatch_logs_conf as acwc
from . import aws_cloudwatch_logs_consts as aclc
from . import aws_cloudwatch_logs_data_loader as acldl

# logger should be init at the very begging of everything
logger = logging.get_module_logger()


def print_scheme():
    """Prints aws cloudwatchlogs scheme."""
    title = "AWS CloudWatch Logs"
    description = "Collect and index events in AWS CloudWatch Logs."
    tacommon.print_scheme(title, description)


def _do_run():
    """
    Main loop. Run this TA for ever
    """

    meta_configs, _, tasks = tacommon.get_configs(
        acwc.AWSCloudWatchLogsConf, "aws_cloudwatch_logs", logger
    )
    if not tasks:
        logger.info("No data input has been configured, exiting...")
        return

    logger.info(
        f"Configuration successfully loaded from the conf file. Total tasks={len(tasks)}"
    )

    meta_configs[tac.log_file] = aclc.cloudwatch_logs_log
    loader_mgr = dlm.create_data_loader_mgr(meta_configs)
    tacommon.setup_signal_handler(loader_mgr, logger)
    conf_change_handler = tacommon.get_file_change_handler(loader_mgr, logger)
    conf_monitor = acwc.create_conf_monitor(conf_change_handler)
    loader_mgr.add_timer(conf_monitor, time.time(), 10)

    jobs = [acldl.CloudWatchLogsDataLoader(task, meta_configs) for task in tasks]
    loader_mgr.run(jobs)


def run():
    """Runs aws cloudwatch logs input."""
    logger.info("Start aws_cloudwatch_logs")
    try:
        _do_run()
    except Exception:  # pylint: disable=broad-except
        logger.error(
            "Failed to collect cloudwatch log data, error=%s", traceback.format_exc()
        )
    logger.info("End aws_cloudwatch_logs")


def main():
    """
    Main entry point
    """
    logging.setup_root_logger(app_name="splunk_ta_aws", modular_name="cloudwatch_logs")
    tacommon.main(print_scheme, run)


if __name__ == "__main__":
    main()

# if __name__ == '__main__':
#    run_module('splunk_ta_aws.modinputs.cloudwatch_logs')
